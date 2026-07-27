import asyncio
import json
import uuid
from pathlib import Path
from typing import Awaitable, Callable

from loguru import logger
from openai import AsyncOpenAI

from sub_agents.atlas.prompt import ATLAS_PROMPT
from sub_agents.atlas.voice_prompt import ATLAS_VOICE_PROMPT
from sub_agents.atlas import tools as fs
from core.voice.agent import VoiceAgent
from memory.episodic_memory.store import EpisodicMemory
from settings import settings

_TOOL_DISPATCH: dict[str, Callable] = {
    "read_file": fs.read_file,
    "write_file": fs.write_file,
    "edit_file": fs.edit_file,
    "delete_file": fs.delete_file,
    "list_directory": fs.list_directory,
    "create_directory": fs.create_directory,
    "delete_directory": fs.delete_directory,
    "delete_all_in_directory": fs.delete_all_in_directory,
}

ResultCallback = Callable[[str], Awaitable[None]]


def _normalize_message(message: dict | object) -> dict:
    """episodic.create_episode() reads messages via dict.get(); the OpenAI SDK
    hands back assistant turns as ChatCompletionMessage objects, not dicts."""
    if isinstance(message, dict):
        return message
    tool_calls = getattr(message, "tool_calls", None)
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", None),
        "tool_calls": [tc.model_dump() for tc in tool_calls] if tool_calls else None,
    }


class Atlas:
    def __init__(self, episodic_memory: EpisodicMemory | None = None) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._workspace = Path(settings.atlas_workspace)
        self._busy = False
        self._episodic_memory = episodic_memory or EpisodicMemory()

    async def run(self, task: str, result_callback: ResultCallback) -> None:
        if self._busy:
            await result_callback(
                "Atlas is still working on a previous task. Ask me again in a moment."
            )
            return

        self._busy = True
        logger.info(f"Atlas starting task: {task}")
        try:
            result, messages = await self._run_loop(task)
        except Exception as exc:
            logger.exception(f"Atlas task failed: {exc}")
            result = f"Atlas ran into a problem: {exc}"
        else:
            await self._write_episodic(task, result, messages)
        finally:
            self._busy = False

        logger.info(f"Atlas finished. Result: {result}")
        await result_callback(result)

    async def _run_loop(self, task: str) -> tuple[str, list[dict]]:
        messages = [
            {"role": "system", "content": ATLAS_PROMPT},
            {"role": "user", "content": task},
        ]

        while True:
            response = await self._client.chat.completions.create(
                model=settings.atlas_llm_model,
                messages=messages,
                tools=fs.TOOL_SCHEMAS,
                tool_choice="auto",
            )

            choice = response.choices[0]

            if choice.finish_reason == "stop":
                return choice.message.content or "Done.", messages

            if choice.finish_reason == "tool_calls":
                messages.append(choice.message)
                for tool_call in choice.message.tool_calls:
                    tool_result = await self._execute_tool(tool_call)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })
                continue

            return choice.message.content or "Done.", messages

    async def _write_episodic(self, task: str, result: str, messages: list[dict]) -> None:
        """Best-effort: one episode per completed task, tagged agent='atlas' in
        the same shared store the voice pipeline writes to. Failure here must
        never surface as a task failure to the caller."""
        try:
            normalized = [_normalize_message(message) for message in messages]
            await asyncio.to_thread(
                self._episodic_memory.write,
                agent="atlas",
                session_id=str(uuid.uuid4()),
                reason="task_complete",
                span_turns=len(normalized),
                summary=f"Task: {task}\nResult: {result}",
                messages=normalized,
            )
        except Exception:
            logger.exception("Atlas episodic memory write failed — continuing without persistence")

    async def _execute_tool(self, tool_call) -> str:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        fn = _TOOL_DISPATCH.get(name)
        if fn is None:
            return f"Unknown tool: {name}"

        try:
            return await fn(self._workspace, **args)
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            return str(exc)
        except PermissionError as exc:
            logger.warning(f"Atlas blocked path traversal attempt: {exc}")
            return str(exc)


atlas_agent = VoiceAgent(
    name="atlas",
    system_prompt=ATLAS_VOICE_PROMPT,
    voice_id=settings.kokoro_atlas_voice_id,
)
