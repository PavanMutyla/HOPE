"""SubAgentManager — spawns, tracks and retires HOPE's dynamic sub-agents.

A spawned sub-agent exists in three places at once, and this class keeps
them in step so no caller has to:

- AgentRegistry  — so Pavan can talk to it ("connect me to Emma") over the
                   shared pipeline, exactly like Atlas.
- VoicePool      — so it has a voice nobody else live is using.
- the blackboard — the durable row (agents table) the dashboard reads, and
                   the record that survives a crash so startup can clean up.

Sub-agents are disposable per hope.py process: everything live is retired on
shutdown, and anything still live at startup is a leftover from a killed
run, retired before anything new spawns.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Callable

from loguru import logger

from core.agents.spec import SubAgentSpec
from core.voice.agent import AgentRegistry, VoiceAgent
from core.voice.voice_pool import VoicePool, VoicePoolExhausted
from memory.coordination.store import Blackboard


class SubAgentLimitReached(RuntimeError):
    pass


@dataclass
class LiveSubAgent:
    agent_id: str
    spoken_name: str
    voice_id: str
    spec: SubAgentSpec
    voice_agent: VoiceAgent
    status: str = "working"
    findings: str = ""
    task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        """Registry key — the spoken name, lower-cased, so switch_to('emma') works."""
        return self.voice_agent.name


class SubAgentManager:
    def __init__(
        self,
        registry: AgentRegistry,
        blackboard: Blackboard,
        voice_pool: VoicePool,
        max_live: int,
    ) -> None:
        self._registry = registry
        self._blackboard = blackboard
        self._voice_pool = voice_pool
        self._max_live = max_live
        self._live: dict[str, LiveSubAgent] = {}  # registry name -> agent

    async def startup(self) -> None:
        stale = await asyncio.to_thread(self._blackboard.retire_live_agents)
        if stale:
            logger.info(f"Retired {stale} sub-agent(s) left over from a previous run")

    async def spawn(
        self,
        spec: SubAgentSpec,
        prompt_for: Callable[["LiveSubAgent"], str],
        run_id: str | None = None,
    ) -> LiveSubAgent:
        """prompt_for builds the agent's *voice-mode* system prompt from its
        live state — called every time Pavan connects, not once here, so it
        always reflects what the agent has found so far."""
        if len(self._live) >= self._max_live:
            await self._evict_oldest_idle()
        try:
            voice = self._voice_pool.lease()
        except VoicePoolExhausted as exc:
            raise SubAgentLimitReached(str(exc)) from exc

        try:
            agent_id = await asyncio.to_thread(
                self._blackboard.register_agent,
                voice.spoken_name, spec.template, voice.voice_id, spec.objective, run_id,
            )
        except Exception:
            self._voice_pool.release(voice.spoken_name)
            raise

        voice_agent = VoiceAgent(
            name=voice.spoken_name.lower(),
            system_prompt="",
            voice_id=voice.voice_id,
            spoken_name=voice.spoken_name,
        )
        live = LiveSubAgent(
            agent_id=agent_id,
            spoken_name=voice.spoken_name,
            voice_id=voice.voice_id,
            spec=spec,
            voice_agent=voice_agent,
        )
        voice_agent.prompt_provider = lambda: prompt_for(live)
        self._registry.register(voice_agent)
        self._live[live.name] = live
        logger.info(f"Spawned {spec.template} {live.spoken_name} ({voice.voice_id}): {spec.objective}")
        return live

    async def _evict_oldest_idle(self) -> None:
        """At the cap, a finished (idle) agent makes room — it has already
        handed in its findings. A *working* one is never evicted to make room;
        the spawn is refused instead."""
        for live in self._live.values():  # dicts keep insertion order: oldest first
            if live.status in ("idle", "failed"):
                await self.retire(live.name)
                return
        raise SubAgentLimitReached(
            f"{self._max_live} sub-agents are already working — wait for one to finish."
        )

    async def set_status(self, live: LiveSubAgent, status: str) -> None:
        live.status = status
        try:
            await asyncio.to_thread(self._blackboard.set_agent_status, live.agent_id, status)
        except Exception:
            logger.exception(f"Couldn't record status '{status}' for {live.spoken_name}")

    async def retire(self, name: str) -> bool:
        """Cancels the agent if it's still working. The caller is responsible
        for handing the voice back to HOPE first if this agent is active."""
        live = self._live.pop(name.strip().lower(), None)
        if live is None:
            return False
        if live.task is not None and not live.task.done():
            live.task.cancel()
        self._registry.unregister(live.name)
        self._voice_pool.release(live.spoken_name)
        await self.set_status(live, "retired")
        logger.info(f"Retired {live.spoken_name}")
        return True

    async def retire_all(self) -> None:
        for name in list(self._live):
            await self.retire(name)

    def find(self, name: str) -> LiveSubAgent | None:
        return self._live.get(name.strip().lower())

    def is_subagent(self, name: str) -> bool:
        return name.strip().lower() in self._live

    def live(self) -> list[LiveSubAgent]:
        return list(self._live.values())
