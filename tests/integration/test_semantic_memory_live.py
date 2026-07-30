"""Live end-to-end test of semantic memory against the real OpenAI API and a
real (temp-dir) Mem0/Chroma instance. Off by default — normal `pytest` runs
stay offline and free. To run it:

    RUN_LIVE_TESTS=1 .venv/bin/pytest tests/integration/test_semantic_memory_live.py -v -s

Needs a real OPENAI_API_KEY in .env. Reads .env directly (via dotenv) so the
fake test env from conftest doesn't shadow the real key. Mirrors
tests/integration/test_summarizer_live.py's opt-in pattern.
"""

import os

import pytest
from dotenv import dotenv_values

_env = dotenv_values(".env")
_key = _env.get("OPENAI_API_KEY", "")
_live = bool(os.getenv("RUN_LIVE_TESTS")) and _key.startswith("sk-")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _live, reason="set RUN_LIVE_TESTS=1 and a real OPENAI_API_KEY in .env"
    ),
]


@pytest.mark.asyncio
async def test_live_add_then_query_round_trip(tmp_path):
    from mem0 import Memory

    from memory.semantic_memory.config import build_mem0_config
    from memory.semantic_memory.store import SemanticMemory

    config = build_mem0_config(
        persist_dir=str(tmp_path / "chroma"),
        history_db_path=str(tmp_path / "history.db"),
    )
    config["llm"]["config"]["api_key"] = _key
    config["embedder"]["config"]["api_key"] = _key
    client = Memory.from_config(config)
    memory = SemanticMemory(client=client)

    memory.add(agent="hope", text="Pavan's main dev workspace is /home/pavan/Desktop/Projects/HOPE.")
    memory.add(agent="atlas", text="Atlas should never delete files outside its workspace.")

    shared_results = memory.query("where is Pavan's dev workspace?")
    assert any("HOPE" in fact["memory"] for fact in shared_results)

    hope_only = memory.query("workspace", agent="hope")
    assert all(fact.get("agent_id") == "hope" for fact in hope_only)

    atlas_only = memory.query("where is Pavan's dev workspace?", agent="atlas")
    assert not any("HOPE" in fact["memory"] for fact in atlas_only)
