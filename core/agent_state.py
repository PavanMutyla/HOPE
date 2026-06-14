from dataclasses import dataclass
from typing import Literal


@dataclass
class AgentState:
    active: Literal["hope", "atlas"] = "hope"


agent_state = AgentState()
