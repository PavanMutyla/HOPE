from dataclasses import dataclass, field

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


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, VoiceAgent] = {}

    def register(self, agent: VoiceAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> VoiceAgent:
        if name not in self._agents:
            raise KeyError(f"No agent registered with name '{name}'")
        return self._agents[name]

    def all(self) -> list[VoiceAgent]:
        return list(self._agents.values())

    async def switch(self, name: str, context: LLMContext, llm: OpenAILLMService) -> None:
        agent = self.get(name)
        msgs = list(context.messages)
        msgs[0] = {"role": "system", "content": agent.system_prompt}
        context.set_messages(msgs)
        await llm.push_frame(
            TTSUpdateSettingsFrame(delta=KokoroTTSSettings(voice=agent.voice_id))
        )
        agent_state.active = name
