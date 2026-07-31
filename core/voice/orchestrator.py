import asyncio

from openai import AsyncOpenAI

from core.voice.agent import AgentRegistry
from core.voice.pipeline import VoicePipelineBundle
from settings import settings


class VoiceOrchestrator:
    def __init__(self, registry: AgentRegistry, bundle: VoicePipelineBundle) -> None:
        self._registry = registry
        self.bundle = bundle
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def switch_to(self, name: str) -> None:
        await self._registry.switch(name, self.bundle.context, self.bundle.llm)
        self.bundle.panel.set_agent(name)

    async def agent_to_agent(self, from_agent: str, to_agent: str, message: str) -> str:
        agent = self._registry.get(to_agent)
        response = await self._client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": f"[from {from_agent}]: {message}"},
            ],
        )
        return response.choices[0].message.content or ""

    async def broadcast(self, from_agent: str, to_agents: list[str], message: str) -> dict[str, str]:
        """Send the same message to multiple agents concurrently, keyed by agent name.

        Runs one agent_to_agent() call per target via asyncio.gather instead of
        awaiting them one at a time, so a slow or failing agent doesn't delay
        the others. Any exception propagates — same failure behavior as calling
        agent_to_agent() directly.
        """
        replies = await asyncio.gather(
            *(self.agent_to_agent(from_agent, to_agent, message) for to_agent in to_agents)
        )
        return dict(zip(to_agents, replies))
