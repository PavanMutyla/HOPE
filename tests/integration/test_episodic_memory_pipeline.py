"""Integration tests for the episodic memory stack end to end: EpisodicMemory
facade driving real SQLite + real Chroma (temp dirs, fake embedding function
to keep this offline) through a full write -> query -> hydrate round trip,
including multimodal content.

Requires `chromadb`; skipped entirely if it isn't installed yet.
"""

import base64

import pytest

chromadb = pytest.importorskip("chromadb")

from memory.episodic_memory.store import EpisodicMemory  # noqa: E402


@pytest.fixture
def memory(tmp_path, fake_embedding_function):
    store = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    yield store
    store.close()


@pytest.mark.integration
def test_write_query_round_trip_with_mixed_multimodal_content(memory):
    image_bytes = b"screenshot-bytes-from-atlas"
    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()

    memory.write(
        agent="atlas",
        session_id="sess-1",
        reason="threshold",
        span_turns=4,
        summary="Atlas took a screenshot showing a permissions error dialog.",
        messages=[
            {"role": "user", "content": "read this screen and tell me what's wrong"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I see a permissions error dialog."},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    )
    memory.write(
        agent="hope",
        session_id="sess-2",
        reason="session_end",
        span_turns=2,
        summary="Pavan asked HOPE about tomorrow's calendar.",
        messages=[{"role": "user", "content": "what's on my calendar tomorrow?"}],
    )

    hits = memory.query("permissions error dialog screenshot", k=1)

    assert len(hits) == 1
    episode = hits[0]
    assert episode.agent == "atlas"
    assert episode.reason == "threshold"
    assert episode.span_turns == 4

    assistant_message = episode.messages[1]
    assert assistant_message.content_text == "I see a permissions error dialog."
    assert len(assistant_message.media) == 1

    media_part = assistant_message.media[0]
    assert media_part.mime == "image/png"
    from pathlib import Path
    assert Path(media_part.path).read_bytes() == image_bytes


@pytest.mark.integration
def test_two_episodes_stay_isolated_and_both_retrievable(memory):
    memory.write(
        agent="hope", session_id="s1", reason="threshold", span_turns=1,
        summary="discussion about groceries and meal planning",
        messages=[{"role": "user", "content": "what should I cook tonight?"}],
    )
    memory.write(
        agent="atlas", session_id="s2", reason="threshold", span_turns=1,
        summary="discussion about renaming files in the workspace",
        messages=[{"role": "user", "content": "rename these files for me"}],
    )

    grocery_hits = memory.query("groceries and meal planning", k=1)
    file_hits = memory.query("renaming files in the workspace", k=1)

    assert grocery_hits[0].agent == "hope"
    assert file_hits[0].agent == "atlas"
    assert grocery_hits[0].id != file_hits[0].id


@pytest.mark.integration
def test_repeated_image_across_episodes_dedupes_end_to_end(memory, tmp_path):
    image_bytes = b"same-screenshot-reused-twice"
    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
    content = [{"type": "image_url", "image_url": {"url": data_uri}}]

    memory.write(
        agent="atlas", session_id="s1", reason="threshold", span_turns=1,
        summary="first sighting of the error screenshot",
        messages=[{"role": "assistant", "content": content}],
    )
    memory.write(
        agent="atlas", session_id="s2", reason="threshold", span_turns=1,
        summary="second sighting of the same error screenshot",
        messages=[{"role": "assistant", "content": content}],
    )

    media_dir = tmp_path / "media"
    stored_files = [p for p in media_dir.rglob("*") if p.is_file()]
    assert len(stored_files) == 1
