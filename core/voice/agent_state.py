from dataclasses import dataclass


@dataclass
class AgentState:
    active: str = "hope"


agent_state = AgentState()
