from openai import AsyncOpenAI

from core.agent import AgentRegistry
from core.voice import VoicePipelineBundle
from settings import settings


class VoiceOrchestrator:
    def __init__(self, registry: AgentRegistry, bundle: VoicePipelineBundle) -> None:
        self._registry = registry
        self.bundle = bundle
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def switch_to(self, name: str) -> None:
        await self._registry.switch(name, self.bundle.context, self.bundle.llm)

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
