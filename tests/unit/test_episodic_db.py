"""Unit tests for the episodic SQLite layer — schema, message normalization,
and multimodal (image) handling."""

import base64

import pytest

from memory.episodic_memory import episodic


@pytest.fixture
def conn(tmp_path):
    connection = episodic.connect(tmp_path / "episodic.db")
    yield connection
    connection.close()


@pytest.fixture
def media_dir(tmp_path):
    return tmp_path / "media"


@pytest.mark.unit
def test_create_episode_returns_prefixed_ulid(conn, media_dir):
    episode_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "threshold", 2, "a summary",
        [{"role": "user", "content": "hi"}],
    )

    assert episode_id.startswith("ep_")


@pytest.mark.unit
def test_create_episode_persists_episode_row(conn, media_dir):
    episode_id = episodic.create_episode(
        conn, media_dir, "atlas", "sess-2", "session_end", 5, "closing summary",
        [{"role": "user", "content": "hi"}],
    )

    episode = episodic.get_episode(conn, episode_id)

    assert episode.agent == "atlas"
    assert episode.session_id == "sess-2"
    assert episode.reason == "session_end"
    assert episode.span_turns == 5
    assert episode.summary == "closing summary"


@pytest.mark.unit
def test_get_episode_returns_none_for_missing_id(conn, media_dir):
    assert episodic.get_episode(conn, "ep_does_not_exist") is None


@pytest.mark.unit
def test_plain_text_messages_round_trip_in_order(conn, media_dir):
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    episode_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "threshold", 3, "summary", messages
    )

    episode = episodic.get_episode(conn, episode_id)

    assert [m.content_text for m in episode.messages] == ["first", "second", "third"]
    assert [m.role for m in episode.messages] == ["user", "assistant", "user"]
    assert [m.seq for m in episode.messages] == [0, 1, 2]


@pytest.mark.unit
def test_tool_call_message_preserves_tool_calls_and_id(conn, media_dir):
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]
    messages = [
        {"role": "assistant", "content": None, "tool_calls": tool_calls},
        {"role": "tool", "content": "file contents", "tool_call_id": "call_1"},
    ]
    episode_id = episodic.create_episode(
        conn, media_dir, "atlas", "sess-1", "threshold", 2, "summary", messages
    )

    episode = episodic.get_episode(conn, episode_id)

    assert episode.messages[0].tool_calls == tool_calls
    assert episode.messages[0].content_text is None
    assert episode.messages[1].tool_call_id == "call_1"


@pytest.mark.unit
def test_inline_image_is_hashed_and_stored_on_disk(conn, media_dir):
    image_bytes = b"fake-png-bytes"
    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "look at this"},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }
    ]
    episode_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "threshold", 1, "summary", messages
    )

    episode = episodic.get_episode(conn, episode_id)
    message = episode.messages[0]

    assert message.content_text == "look at this"
    assert len(message.media) == 1
    part = message.media[0]
    assert part.kind == "image"
    assert part.mime == "image/png"
    assert part.external_url is None
    assert part.path is not None
    from pathlib import Path
    assert Path(part.path).read_bytes() == image_bytes


@pytest.mark.unit
def test_external_image_url_is_referenced_not_fetched(conn, media_dir):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://example.com/pic.png"}},
            ],
        }
    ]
    episode_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "threshold", 1, "summary", messages
    )

    episode = episodic.get_episode(conn, episode_id)
    part = episode.messages[0].media[0]

    assert part.external_url == "https://example.com/pic.png"
    assert part.media_hash is None
    assert part.path is None
    assert not media_dir.exists() or not any(media_dir.rglob("*"))


@pytest.mark.unit
def test_identical_image_across_episodes_dedupes_in_media_table(conn, media_dir):
    image_bytes = b"same-image-bytes"
    data_uri = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    messages = [
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_uri}}]}
    ]

    episodic.create_episode(conn, media_dir, "hope", "sess-1", "threshold", 1, "s1", messages)
    episodic.create_episode(conn, media_dir, "hope", "sess-2", "threshold", 1, "s2", messages)

    row_count = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    assert row_count == 1


@pytest.mark.unit
def test_multiple_episodes_are_independently_retrievable(conn, media_dir):
    id1 = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "threshold", 1, "summary one",
        [{"role": "user", "content": "a"}],
    )
    id2 = episodic.create_episode(
        conn, media_dir, "atlas", "sess-2", "threshold", 1, "summary two",
        [{"role": "user", "content": "b"}],
    )

    assert id1 != id2
    assert episodic.get_episode(conn, id1).summary == "summary one"
    assert episodic.get_episode(conn, id2).summary == "summary two"


@pytest.mark.unit
def test_list_episodes_by_reason_returns_only_matching_episodes(conn, media_dir):
    raw_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "session_end_raw", 1, "raw",
        [{"role": "user", "content": "a"}],
    )
    episodic.create_episode(
        conn, media_dir, "hope", "sess-2", "threshold", 1, "folded",
        [{"role": "user", "content": "b"}],
    )

    ids = episodic.list_episodes_by_reason(conn, "session_end_raw")

    assert ids == [raw_id]


@pytest.mark.unit
def test_list_episodes_by_reason_with_no_matches_returns_empty(conn, media_dir):
    assert episodic.list_episodes_by_reason(conn, "session_end_raw") == []


@pytest.mark.unit
def test_update_episode_summary_replaces_summary_and_reason(conn, media_dir):
    episode_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "session_end_raw", 1, "raw dump",
        [{"role": "user", "content": "a"}],
    )

    episodic.update_episode_summary(conn, episode_id, "a real summary", "session_end")

    episode = episodic.get_episode(conn, episode_id)
    assert episode.summary == "a real summary"
    assert episode.reason == "session_end"


@pytest.mark.unit
def test_update_episode_summary_leaves_messages_untouched(conn, media_dir):
    episode_id = episodic.create_episode(
        conn, media_dir, "hope", "sess-1", "session_end_raw", 2, "raw dump",
        [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
    )

    episodic.update_episode_summary(conn, episode_id, "a real summary", "session_end")

    episode = episodic.get_episode(conn, episode_id)
    assert [m.content_text for m in episode.messages] == ["a", "b"]
