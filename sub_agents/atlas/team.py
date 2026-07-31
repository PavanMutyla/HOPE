from core.voice.team_registry import TeamMember
from core.voice.team_voice import TeamVoice
from settings import settings
from sub_agents.atlas.team_prompt import ATLAS_INTERJECT_PROMPT


def build_atlas_team_member() -> TeamMember:
    """Constructed lazily, not at import time — TeamVoice eagerly builds a real
    Kokoro engine and opens a real audio output stream, same reason
    build_pipeline() defers its own heavy construction to call time."""
    return TeamMember(
        name="atlas",
        interject_prompt=ATLAS_INTERJECT_PROMPT,
        llm_model=settings.atlas_llm_model,
        voice=TeamVoice(voice_id=settings.kokoro_atlas_voice_id),
    )
