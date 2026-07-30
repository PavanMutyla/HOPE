"""ProceduralMemory facade — reads and writes procedures as plain markdown
files with YAML frontmatter, under `procedures/<agent>/<name>.md`.

Deliberately not a database. Procedures are meant to be git-tracked,
hand-readable, and hand-editable (deprecating one is just changing
`status: active` to `status: deprecated` in a text editor) — same
philosophy as Claude Code's own `.claude/skills/*/SKILL.md`. Episodic and
semantic memory are auto-generated, high-volume, and gitignored under
data_store/; procedures are curated, low-volume, and belong in git instead.

No embedding/vector index either — at the expected scale (tens of
procedures per agent, not thousands) a keyword-overlap ranking over
name+description is enough to find the right one, and it keeps this tier
free of any new infra. Revisit only if that stops being true.

Append-don't-mutate: saving over an existing *active* procedure is refused
— write a new one and deprecate the old, matching how Voyager's skill
library and this project's semantic-memory dedup both avoid silently
overwriting proven procedures.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from memory.procedural_memory.schema import Procedure
from settings import settings

_STEP_LINE = re.compile(r"^\s*\d+\.\s+(.*\S)\s*$")
_SLUG_INVALID = re.compile(r"[^a-z0-9]+")

# Filtered out of recall() scoring so near-universal words (which show up in
# almost every description) don't inflate overlap scores for unrelated
# procedures — a cheap stand-in for what a real embedder gets for free.
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "it", "to", "of", "in", "on", "for", "and", "or",
    "when", "then", "this", "that", "with", "at", "by", "be", "do", "does",
    "please", "you", "your", "i", "my", "me",
})


def _keywords(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in _STOPWORDS}


def _slugify(name: str) -> str:
    slug = _SLUG_INVALID.sub("-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError(f"'{name}' has no usable characters for a filename slug")
    return slug


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render(procedure: Procedure) -> str:
    frontmatter = {
        "name": procedure.name,
        "agent": procedure.agent,
        "status": procedure.status,
        "description": procedure.description,
        "success_count": procedure.success_count,
        "failure_count": procedure.failure_count,
        "created_at": procedure.created_at,
        "last_used_at": procedure.last_used_at,
        "source": procedure.source,
        "source_episode_id": procedure.source_episode_id,
        "superseded_by": procedure.superseded_by,
    }
    body_steps = "\n".join(f"{i}. {step}" for i, step in enumerate(procedure.steps, start=1))
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body_steps}\n"


def _parse(text: str) -> Procedure:
    _, frontmatter_text, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter_text) or {}
    steps = [m.group(1) for line in body.splitlines() if (m := _STEP_LINE.match(line))]
    return Procedure(steps=steps, **meta)


class ProceduralMemory:
    def __init__(self, base_dir: str | Path | None = None):
        self._base_dir = Path(base_dir or settings.procedures_dir)

    def _path_for(self, agent: str, name: str) -> Path:
        return self._base_dir / agent / f"{_slugify(name)}.md"

    def save(
        self,
        agent: str,
        name: str,
        description: str,
        steps: list[str],
        source: str = "manual",
        source_episode_id: str | None = None,
    ) -> Procedure:
        path = self._path_for(agent, name)
        if path.exists() and _parse(path.read_text()).status == "active":
            raise ValueError(
                f"Procedure '{name}' for agent '{agent}' already exists and is active — "
                "deprecate it first (edit its frontmatter: status -> deprecated) before "
                "saving a replacement."
            )
        procedure = Procedure(
            name=_slugify(name),
            agent=agent,
            description=description,
            status="active",
            steps=steps,
            success_count=0,
            failure_count=0,
            created_at=_now(),
            last_used_at=None,
            source=source,
            source_episode_id=source_episode_id,
            superseded_by=None,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render(procedure))
        return procedure

    def get(self, agent: str, name: str) -> Procedure | None:
        path = self._path_for(agent, name)
        if not path.exists():
            return None
        return _parse(path.read_text())

    def list_all(self, agent: str | None = None, status: str | None = "active") -> list[Procedure]:
        agents = [agent] if agent is not None else self._known_agents()
        procedures = []
        for agent_name in agents:
            agent_dir = self._base_dir / agent_name
            if not agent_dir.is_dir():
                continue
            for path in sorted(agent_dir.glob("*.md")):
                procedure = _parse(path.read_text())
                if status is None or procedure.status == status:
                    procedures.append(procedure)
        return procedures

    def _known_agents(self) -> list[str]:
        if not self._base_dir.is_dir():
            return []
        return sorted(p.name for p in self._base_dir.iterdir() if p.is_dir())

    def recall(self, query: str, agent: str | None = None, k: int = 3) -> list[Procedure]:
        """Keyword-overlap ranking over name+description — no embedding step.
        Good enough at tens-of-procedures scale; revisit only if that stops
        being true (see module docstring)."""
        query_words = _keywords(query)
        if not query_words:
            return []
        scored = []
        for procedure in self.list_all(agent=agent, status="active"):
            haystack = _keywords(f"{procedure.name} {procedure.description}")
            score = len(query_words & haystack)
            if score > 0:
                scored.append((score, procedure))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [procedure for _, procedure in scored[:k]]

    def record_outcome(self, agent: str, name: str, success: bool) -> Procedure:
        path = self._path_for(agent, name)
        procedure = self.get(agent, name)
        if procedure is None:
            raise ValueError(f"No procedure '{name}' for agent '{agent}'")
        updated = procedure.model_copy(
            update={
                "success_count": procedure.success_count + (1 if success else 0),
                "failure_count": procedure.failure_count + (0 if success else 1),
                "last_used_at": _now(),
            }
        )
        path.write_text(_render(updated))
        return updated

    def deprecate(self, agent: str, name: str, superseded_by: str | None = None) -> Procedure:
        path = self._path_for(agent, name)
        procedure = self.get(agent, name)
        if procedure is None:
            raise ValueError(f"No procedure '{name}' for agent '{agent}'")
        updated = procedure.model_copy(update={"status": "deprecated", "superseded_by": superseded_by})
        path.write_text(_render(updated))
        return updated
