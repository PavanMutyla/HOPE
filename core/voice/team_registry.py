from pydantic import BaseModel, ConfigDict

from core.voice.team_voice import TeamVoice


class TeamMember(BaseModel):
    """An agent that listens in on HOPE's live conversation and can speak up
    on its own TeamVoice when it has something relevant to add.

    Separate from AgentRegistry/VoiceAgent (core/voice/agent.py) on purpose:
    "who can take over the shared pipeline" (HOPE<->Atlas voice switch) and
    "who's listening in the background" are orthogonal — an agent can be in
    either registry, both, or neither.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    interject_prompt: str
    llm_model: str
    voice: TeamVoice


class TeamRegistry:
    def __init__(self) -> None:
        self._members: dict[str, TeamMember] = {}

    def register(self, member: TeamMember) -> None:
        self._members[member.name] = member

    def all(self) -> list[TeamMember]:
        return list(self._members.values())


team_registry = TeamRegistry()
