"""Unit tests for memory/semantic_memory — SemanticMemory facade and Mem0
config wiring. Mem0 itself is mocked/injected; no real LLM or vector store
calls happen here (see tests/integration/test_semantic_memory_live.py for
the real round trip, gated behind RUN_LIVE_TESTS)."""

from unittest.mock import MagicMock

import pytest

from memory.semantic_memory.config import build_mem0_config
from memory.semantic_memory.store import SemanticMemory


@pytest.mark.unit
def test_add_passes_user_id_and_agent_id_to_mem0(fake_env):
    mock_mem0 = MagicMock()
    memory = SemanticMemory(client=mock_mem0)

    memory.add(agent="hope", text="Pavan prefers dark mode.")

    mock_mem0.add.assert_called_once_with(
        "Pavan prefers dark mode.", user_id="TestUser", agent_id="hope"
    )


@pytest.mark.unit
def test_query_with_no_agent_filters_on_user_id_only(fake_env):
    mock_mem0 = MagicMock()
    mock_mem0.search.return_value = {"results": []}
    memory = SemanticMemory(client=mock_mem0)

    memory.query("workspace path")

    mock_mem0.search.assert_called_once_with(
        "workspace path", filters={"user_id": "TestUser"}, limit=5
    )


@pytest.mark.unit
def test_query_with_agent_adds_agent_id_filter(fake_env):
    mock_mem0 = MagicMock()
    mock_mem0.search.return_value = {"results": []}
    memory = SemanticMemory(client=mock_mem0)

    memory.query("tool quirks", agent="atlas")

    mock_mem0.search.assert_called_once_with(
        "tool quirks", filters={"user_id": "TestUser", "agent_id": "atlas"}, limit=5
    )


@pytest.mark.unit
def test_query_respects_custom_k(fake_env):
    mock_mem0 = MagicMock()
    mock_mem0.search.return_value = {"results": []}
    memory = SemanticMemory(client=mock_mem0)

    memory.query("anything", k=10)

    assert mock_mem0.search.call_args.kwargs["limit"] == 10


@pytest.mark.unit
def test_query_returns_the_results_list(fake_env):
    mock_mem0 = MagicMock()
    facts = [{"memory": "fact one", "agent_id": "hope"}]
    mock_mem0.search.return_value = {"results": facts}
    memory = SemanticMemory(client=mock_mem0)

    assert memory.query("anything") == facts


@pytest.mark.unit
def test_get_all_with_no_agent_filters_on_user_id_only(fake_env):
    mock_mem0 = MagicMock()
    mock_mem0.get_all.return_value = {"results": []}
    memory = SemanticMemory(client=mock_mem0)

    memory.get_all()

    mock_mem0.get_all.assert_called_once_with(filters={"user_id": "TestUser"})


@pytest.mark.unit
def test_get_all_with_agent_adds_agent_id_filter(fake_env):
    mock_mem0 = MagicMock()
    mock_mem0.get_all.return_value = {"results": []}
    memory = SemanticMemory(client=mock_mem0)

    memory.get_all(agent="atlas")

    mock_mem0.get_all.assert_called_once_with(filters={"user_id": "TestUser", "agent_id": "atlas"})


@pytest.mark.unit
def test_get_all_returns_the_results_list(fake_env):
    mock_mem0 = MagicMock()
    facts = [{"memory": "fact one", "agent_id": "hope"}]
    mock_mem0.get_all.return_value = {"results": facts}
    memory = SemanticMemory(client=mock_mem0)

    assert memory.get_all() == facts


@pytest.mark.unit
def test_build_mem0_config_points_at_semantic_persist_dir(fake_env):
    config = build_mem0_config(persist_dir="/tmp/some-chroma-dir", history_db_path="/tmp/some-history.db")

    assert config["vector_store"]["provider"] == "chroma"
    assert config["vector_store"]["config"]["path"] == "/tmp/some-chroma-dir"
    assert config["history_db_path"] == "/tmp/some-history.db"


@pytest.mark.unit
def test_build_mem0_config_overrides_default_reasoning_model(fake_env):
    """Mem0 defaults to gpt-5-mini, which rejects Mem0's own hardcoded
    temperature=0.1 — confirmed by spike (see
    docs/HOPE_Semantic_Memory_Spike_Notes.md). Must be overridden."""
    config = build_mem0_config(persist_dir="/tmp/x", history_db_path="/tmp/y/history.db")

    assert config["llm"]["config"]["model"] != "gpt-5-mini"
    assert config["llm"]["config"]["model"] == "gpt-4o-mini"


@pytest.mark.unit
def test_build_mem0_config_passes_api_key_explicitly(fake_env):
    config = build_mem0_config(persist_dir="/tmp/x", history_db_path="/tmp/y/history.db")

    assert config["llm"]["config"]["api_key"] == "test-openai-key-not-real"
    assert config["embedder"]["config"]["api_key"] == "test-openai-key-not-real"


@pytest.mark.unit
def test_build_mem0_config_creates_history_db_parent_dir(fake_env, tmp_path):
    history_path = tmp_path / "nested" / "history.db"
    assert not history_path.parent.exists()

    build_mem0_config(persist_dir=str(tmp_path / "chroma"), history_db_path=str(history_path))

    assert history_path.parent.exists()
