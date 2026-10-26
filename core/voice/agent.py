from dataclasses import dataclass, field
from typing import Callable

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import TTSUpdateSettingsFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.kokoro.tts import KokoroTTSSettings
from pipecat.services.openai.llm import OpenAILLMService

from core.voice.agent_state import agent_state


@dataclass
class VoiceAgent:
    name: str
    system_prompt: str
    voice_id: str
    tools: list[FunctionSchema] = field(default_factory=list)
    # What Pavan calls this agent out loud ("Emma"). None for the fixed
    # agents, whose registry name already is their spoken name.
    spoken_name: str | None = None
    # Rebuilds the system prompt at switch time instead of freezing it at
    # registration — a researcher's prompt has to include whatever it has
    # found so far, which keeps changing after it's registered.
    prompt_provider: Callable[[], str] | None = None

    def current_prompt(self) -> str:
        return self.prompt_provider() if self.prompt_provider else self.system_prompt


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, VoiceAgent] = {}

    def register(self, agent: VoiceAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> VoiceAgent:
        if name not in self._agents:
            raise KeyError(f"No agent registered with name '{name}'")
        return self._agents[name]

    def unregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def find(self, name: str) -> VoiceAgent | None:
        """Look up by registry name or spoken name, case-insensitively —
        the name arrives via STT and the LLM, so 'emma' and 'Emma' both count."""
        wanted = name.strip().lower()
        for agent in self._agents.values():
            if agent.name.lower() == wanted or (agent.spoken_name or "").lower() == wanted:
                return agent
        return None

    def all(self) -> list[VoiceAgent]:
        return list(self._agents.values())

    async def switch(self, name: str, context: LLMContext, llm: OpenAILLMService) -> None:
        agent = self.get(name)
        msgs = list(context.messages)
        msgs[0] = {"role": "system", "content": agent.current_prompt()}
        context.set_messages(msgs)
        await llm.push_frame(
            TTSUpdateSettingsFrame(delta=KokoroTTSSettings(voice=agent.voice_id))
        )
        agent_state.active = name
