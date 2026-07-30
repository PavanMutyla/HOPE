"""Manual audit export for semantic memory — run whenever Pavan wants to
spot-check what Mem0's automatic extraction pipeline has accumulated. Purely
observational: writes markdown snapshots, diffable against the previous run
via `git diff` if data_store/ is ever tracked. Nothing reads this back in.
See docs/HOPE_Semantic_Memory_Design.md §7.

Usage (run from the repo root, so `memory`/`settings` resolve as packages):
    .venv/bin/python -m scripts.export_semantic_facts
"""

from datetime import datetime, timezone
from pathlib import Path

from memory.semantic_memory.store import SemanticMemory
from settings import settings

# Update when a new agent is added — see CLAUDE.md's "Adding a New Agent".
KNOWN_AGENTS = ["hope", "atlas"]

EXPORT_DIR = Path(settings.semantic_persist_dir).parent / "export"


def _render(scope_label: str, facts: list[dict]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Semantic memory export — {scope_label}",
        "",
        f"Generated: {generated_at}",
        f"Fact count: {len(facts)}",
        "",
    ]
    for fact in facts:
        agent_id = fact.get("agent_id") or "shared"
        lines.append(f"- **({agent_id})** {fact.get('memory', '')}")
        lines.append(
            f"  - id: `{fact.get('id', '?')}` · "
            f"created: {fact.get('created_at', '?')} · "
            f"updated: {fact.get('updated_at', '?')}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    memory = SemanticMemory()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    shared_facts = memory.get_all()
    (EXPORT_DIR / "shared.md").write_text(_render("shared (everyone)", shared_facts))
    print(f"shared: {len(shared_facts)} facts -> {EXPORT_DIR / 'shared.md'}")

    for agent in KNOWN_AGENTS:
        agent_facts = memory.get_all(agent=agent)
        path = EXPORT_DIR / f"{agent}.md"
        path.write_text(_render(f"{agent} (private)", agent_facts))
        print(f"{agent}: {len(agent_facts)} facts -> {path}")


if __name__ == "__main__":
    main()
