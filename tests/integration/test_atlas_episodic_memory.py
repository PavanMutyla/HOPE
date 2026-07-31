"""
Integration tests for Atlas's episodic memory hook — one episode per
completed task, written into the same shared EpisodicMemory store the voice
pipeline uses, tagged agent="atlas".
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

chromadb = pytest.importorskip("chromadb")

from memory.episodic_memory.store import EpisodicMemory  # noqa: E402
from sub_agents.atlas.agent import Atlas  # noqa: E402


@pytest.fixture
def episodic_memory(tmp_path, fake_embedding_function):
    store = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    yield store
    store.close()


def _fake_response(finish_reason: str, content: str | None = None, tool_calls=None):
    message = MagicMock()
    message.role = "assistant"
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def atlas(episodic_memory):
    instance = Atlas(episodic_memory=episodic_memory, semantic_memory=MagicMock())
    instance._client = MagicMock()
    return instance


@pytest.mark.integration
async def test_completed_task_writes_one_episode_tagged_atlas(atlas, episodic_memory):
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="Listed 3 files.")
    )

    await atlas.run("list the files", AsyncMock())

    results = episodic_memory.query("list the files", k=5, agent="atlas")
    assert len(results) == 1
    assert results[0].agent == "atlas"
    assert results[0].reason == "task_complete"


@pytest.mark.integration
async def test_completed_task_writes_one_semantic_fact_tagged_atlas(atlas):
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="Listed 3 files.")
    )

    await atlas.run("list the files", AsyncMock())

    atlas._semantic_memory.add.assert_called_once_with(
        agent="atlas", text="Task: list the files\nResult: Listed 3 files."
    )


@pytest.mark.integration
async def test_semantic_write_failure_does_not_break_result_callback():
    """A broken semantic store must never swallow the task's actual result,
    same guarantee as the episodic write failure case below."""
    broken_semantic = MagicMock()
    broken_semantic.add.side_effect = RuntimeError("mem0 unreachable")
    atlas = Atlas(episodic_memory=MagicMock(), semantic_memory=broken_semantic)
    atlas._client = MagicMock()
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="All done.")
    )
    result_callback = AsyncMock()

    await atlas.run("do the thing", result_callback)

    result_callback.assert_called_once_with("All done.")


@pytest.mark.integration
async def test_episode_summary_contains_task_and_result(atlas, episodic_memory):
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="Created report.txt.")
    )

    await atlas.run("create report.txt", AsyncMock())

    [episode] = episodic_memory.query("create report.txt", k=5, agent="atlas")
    assert "create report.txt" in episode.summary
    assert "Created report.txt." in episode.summary


@pytest.mark.integration
async def test_tool_call_turn_is_normalized_and_persisted(atlas, episodic_memory):
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "list_directory"
    tool_call.function.arguments = json.dumps({"path": "."})
    tool_call.model_dump.return_value = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "list_directory", "arguments": json.dumps({"path": "."})},
    }

    atlas._client.chat.completions.create = AsyncMock(
        side_effect=[
            _fake_response("tool_calls", tool_calls=[tool_call]),
            _fake_response("stop", content="Done."),
        ]
    )

    await atlas.run("list the workspace", AsyncMock())

    [episode] = episodic_memory.query("list the workspace", k=5, agent="atlas")
    roles = [m.role for m in episode.messages]
    assert roles == ["system", "user", "assistant", "tool"]
    assert episode.messages[2].tool_calls == [tool_call.model_dump.return_value]
    assert episode.messages[3].tool_call_id == "call_1"


@pytest.mark.integration
async def test_failed_task_does_not_write_an_episode(atlas, episodic_memory):
    atlas._client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    await atlas.run("this will fail", AsyncMock())

    results = episodic_memory.query("this will fail", k=5, agent="atlas")
    assert results == []


@pytest.mark.integration
async def test_episodic_write_failure_does_not_break_result_callback():
    """A broken episodic store must never swallow the task's actual result."""
    broken_memory = MagicMock()
    broken_memory.write.side_effect = RuntimeError("db is locked")
    atlas = Atlas(episodic_memory=broken_memory, semantic_memory=MagicMock())
    atlas._client = MagicMock()
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="All done.")
    )
    result_callback = AsyncMock()

    await atlas.run("do the thing", result_callback)

    result_callback.assert_called_once_with("All done.")


@pytest.mark.integration
async def test_busy_atlas_never_attempts_a_write(atlas, episodic_memory):
    atlas._busy = True

    await atlas.run("anything", AsyncMock())

    assert episodic_memory.query("anything", k=5, agent="atlas") == []


# ── Plan tracking ──────────────────────────────────────────────────────


@pytest.mark.integration
async def test_completed_task_resolves_its_plan(atlas, episodic_memory):
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="Listed 3 files.")
    )

    await atlas.run("list the files", AsyncMock())

    [plan] = episodic_memory.list_plans(agent="atlas", status="completed")
    assert plan.description == "list the files"
    assert plan.resulting_episode_id is not None

    [episode] = episodic_memory.query("list the files", k=5, agent="atlas")
    assert plan.resulting_episode_id == episode.id


@pytest.mark.integration
async def test_failed_task_abandons_its_plan(atlas, episodic_memory):
    atlas._client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    await atlas.run("this will fail", AsyncMock())

    [plan] = episodic_memory.list_plans(agent="atlas", status="abandoned")
    assert plan.description == "this will fail"
    assert plan.resulting_episode_id is None


@pytest.mark.integration
async def test_busy_atlas_never_creates_a_plan(atlas, episodic_memory):
    atlas._busy = True

    await atlas.run("anything", AsyncMock())

    assert episodic_memory.list_plans(agent="atlas") == []


@pytest.mark.integration
async def test_plan_creation_failure_does_not_break_result_callback():
    """A broken plan-tracking write must never swallow the task's actual
    result, same guarantee as the episodic/semantic failure cases above."""
    broken_memory = MagicMock()
    broken_memory.create_plan.side_effect = RuntimeError("db is locked")
    atlas = Atlas(episodic_memory=broken_memory, semantic_memory=MagicMock())
    atlas._client = MagicMock()
    atlas._client.chat.completions.create = AsyncMock(
        return_value=_fake_response("stop", content="All done.")
    )
    result_callback = AsyncMock()

    await atlas.run("do the thing", result_callback)

    result_callback.assert_called_once_with("All done.")
