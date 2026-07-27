"""Unit tests for the Chroma-backed episodic vector store.

Requires the `chromadb` dependency (see pyproject.toml). Skipped entirely if
it isn't installed yet, so the rest of the suite stays green in the meantime.
"""

import pytest

chromadb = pytest.importorskip("chromadb")

from memory.episodic_memory.vector_store import EpisodicVectorStore  # noqa: E402


@pytest.fixture
def store(tmp_path, fake_embedding_function):
    return EpisodicVectorStore(tmp_path / "chroma", embedding_function=fake_embedding_function)


@pytest.mark.unit
def test_upsert_then_query_returns_the_episode_id(store):
    store.upsert("ep_1", "Pavan asked about deploying the app.", {"agent": "hope"})

    results = store.query("deploying the app", k=1)

    assert results == ["ep_1"]


@pytest.mark.unit
def test_query_respects_k(store):
    for i in range(5):
        store.upsert(f"ep_{i}", f"summary number {i}", {"agent": "hope"})

    results = store.query("summary", k=2)

    assert len(results) == 2


@pytest.mark.unit
def test_upsert_is_idempotent_for_same_id(store):
    store.upsert("ep_1", "first version", {"agent": "hope"})
    store.upsert("ep_1", "updated version", {"agent": "hope"})

    results = store.query("updated version", k=5)

    assert results.count("ep_1") == 1


@pytest.mark.unit
def test_query_with_agent_filters_out_other_agents(store):
    store.upsert("ep_hope", "deploying the app", {"agent": "hope"})
    store.upsert("ep_atlas", "deploying the app", {"agent": "atlas"})

    results = store.query("deploying the app", k=5, agent="hope")

    assert results == ["ep_hope"]


@pytest.mark.unit
def test_query_without_agent_searches_across_all_agents(store):
    store.upsert("ep_hope", "deploying the app", {"agent": "hope"})
    store.upsert("ep_atlas", "deploying the app", {"agent": "atlas"})

    results = store.query("deploying the app", k=5)

    assert set(results) == {"ep_hope", "ep_atlas"}


@pytest.mark.unit
def test_query_with_agent_matching_nothing_returns_empty(store):
    store.upsert("ep_hope", "deploying the app", {"agent": "hope"})

    results = store.query("deploying the app", k=5, agent="atlas")

    assert results == []
