"""Unit tests for the pydantic episodic memory models — strictness and
immutability, since these are the typed contract on top of the SQLite schema
in memory/episodic_memory/migrations/0001_init.sql."""

import pydantic
import pytest

from memory.episodic_memory.schema import Episode, EpisodeMediaPart, EpisodeMessage, MediaRef


@pytest.mark.unit
def test_media_ref_requires_all_fields():
    ref = MediaRef(hash="abc", path="/tmp/abc", mime="image/png", size=10)
    assert ref.hash == "abc"


@pytest.mark.unit
def test_media_ref_is_frozen():
    ref = MediaRef(hash="abc", path="/tmp/abc", mime="image/png", size=10)
    with pytest.raises(pydantic.ValidationError):
        ref.hash = "changed"


@pytest.mark.unit
def test_strict_mode_rejects_type_coercion():
    """Strict mode must not silently coerce a string into the int `size`
    field — a caller passing malformed data should fail loudly, not produce
    a MediaRef with a stringly-typed size."""
    with pytest.raises(pydantic.ValidationError):
        MediaRef(hash="abc", path="/tmp/abc", mime="image/png", size="10")


@pytest.mark.unit
def test_episode_media_part_defaults_are_none():
    part = EpisodeMediaPart(seq=0, kind="image", mime="image/png")
    assert part.media_hash is None
    assert part.path is None
    assert part.external_url is None


@pytest.mark.unit
def test_episode_message_defaults_to_empty_media_list():
    message = EpisodeMessage(seq=0, role="user", content_text="hi")
    assert message.media == []


@pytest.mark.unit
def test_episode_message_media_lists_are_independent_between_instances():
    """Mutable-looking default (`media: list[...] = Field(default_factory=list)`)
    must not be shared across instances the way a bare `[]` class attribute
    would be."""
    a = EpisodeMessage(seq=0, role="user", content_text="a")
    b = EpisodeMessage(seq=1, role="user", content_text="b")

    # media is frozen at the model level, but the two instances must not be
    # the *same* list object
    assert a.media is not b.media


@pytest.mark.unit
def test_episode_holds_ordered_messages():
    message = EpisodeMessage(seq=0, role="user", content_text="hi")
    episode = Episode(
        id="ep_1", ts="2026-01-01T00:00:00Z", session_id="s1", agent="hope",
        reason="threshold", span_turns=1, summary="summary", messages=[message],
    )
    assert episode.messages[0].content_text == "hi"
