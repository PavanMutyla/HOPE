import asyncio

from loguru import logger
from openai import AsyncOpenAI
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from core.voice.agent_state import agent_state
from core.voice.team_registry import TeamMember, TeamRegistry
from core.voice.team_state import team_state

PASS_TOKEN = "PASS"


class TeamBroadcastObserver(FrameProcessor):
    """Sidecar pipeline processor (pass-through, same pattern as StatusMonitor/
    LangfuseObserver) that fans a finalized user transcript out to every
    registered team member concurrently, whenever team mode is on.

    Never blocks or alters the frame flow — HOPE's own turn proceeds exactly
    as before regardless of what any team member decides to do.
    """

    def __init__(self, registry: TeamRegistry, client: AsyncOpenAI) -> None:
        super().__init__()
        self._registry = registry
        self._client = client

    def _handle_frame(self, frame) -> None:
        if not team_state.enabled or not isinstance(frame, TranscriptionFrame):
            return
        for member in self._registry.all():
            if member.name != agent_state.active:
                asyncio.create_task(self._maybe_interject(member, frame.text))

    async def process_frame(self, frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        self._handle_frame(frame)
        await self.push_frame(frame, direction)

    async def _maybe_interject(self, member: TeamMember, transcript: str) -> None:
        try:
            response = await self._client.chat.completions.create(
                model=member.llm_model,
                messages=[
                    {"role": "system", "content": member.interject_prompt},
                    {"role": "user", "content": transcript},
                ],
            )
            reply = (response.choices[0].message.content or "").strip()
        except Exception:
            logger.exception(f"Team interject check failed for {member.name}")
            return

        if reply and reply.upper() != PASS_TOKEN:
            await member.voice.speak(reply)
