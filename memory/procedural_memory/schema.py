"""Typed record for procedural memory, read back out of the markdown files
under `procedures/<agent>/<name>.md` by procedural.py. Unlike episodic/semantic,
this is the *only* representation — there's no separate database, the
markdown file's YAML frontmatter + numbered-list body is both the storage
format and the read contract. See docs/HOPE_Procedural_Memory_Design.md.
"""

from pydantic import BaseModel, ConfigDict


class Procedure(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    name: str
    agent: str
    description: str
    status: str  # "active" | "deprecated"
    steps: list[str]
    success_count: int
    failure_count: int
    created_at: str
    last_used_at: str | None = None
    source: str  # "manual" | "atlas_task"
    source_episode_id: str | None = None
    superseded_by: str | None = None
