from pydantic import BaseModel


class TeamState(BaseModel):
    enabled: bool = False


team_state = TeamState()
