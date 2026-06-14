import asyncio
import json
from pathlib import Path
from typing import Awaitable, Callable

from loguru import logger
from openai import AsyncOpenAI

from atlas.prompt import ATLAS_PROMPT
from atlas import tools as fs
from settings import settings

_TOOL_DISPATCH: dict[str, Callable] = {
    "read_file": fs.read_file,
    "write_file": fs.write_file,
    "edit_file": fs.edit_file,
    "delete_file": fs.delete_file,
    "list_directory": fs.list_directory,
    "create_directory": fs.create_directory,
    "delete_directory": fs.delete_directory,
}

ResultCallback = Callable[[str], Awaitable[None]]


class Atlas:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._workspace = Path(settings.atlas_workspace)
        self._busy = False

    async def run(self, task: str, result_callback: ResultCallback) -> None:
        if self._busy:
            await result_callback(
                "Atlas is still working on a previous task. Ask me again in a moment."
            )
            return

        self._busy = True
        logger.info(f"Atlas starting task: {task}")
        try:
            result = await self._run_loop(task)
        except Exception as exc:
            logger.exception(f"Atlas task failed: {exc}")
            result = f"Atlas ran into a problem: {exc}"
        finally:
            self._busy = False

        logger.info(f"Atlas finished. Result: {result}")
        await result_callback(result)

    async def _run_loop(self, task: str) -> str:
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
                return choice.message.content or "Done."

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

            return choice.message.content or "Done."

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
