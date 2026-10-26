"""Unit tests for sub_agents/research/toolbox.py — the researcher's only tools.

Source recording is a best-effort persistence path, so it's checked against a
real Blackboard and real files, not a mock."""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.coordination.store import Blackboard
from sub_agents.research.toolbox import TOOL_SCHEMAS, ResearchToolbox
from tools.web.fetch import FetchBlocked, PageText
from tools.web.search import SearchError, SearchResult


@pytest.fixture
def blackboard(tmp_path):
    board = Blackboard(MagicMock(), db_path=tmp_path / "blackboard.db")
    yield board
    board.close()


def _toolbox(blackboard, tmp_path, search=None, read_url=None, run_id="run_1"):
    provider = MagicMock()
    provider.search = search or AsyncMock(return_value=[SearchResult(title="T", url="https://a.org", snippet="S")])
    reader = read_url or AsyncMock(return_value=PageText(url="https://a.org", title="A", text="Body text", truncated=False))
    return ResearchToolbox(provider, blackboard, run_id, "agt_1", tmp_path / "pages", read_url=reader)


@pytest.mark.unit
def test_schemas_expose_exactly_the_two_read_only_tools():
    assert {s["function"]["name"] for s in TOOL_SCHEMAS} == {"web_search", "read_url"}


@pytest.mark.unit
@pytest.mark.parametrize("tool", ["write_file", "delete_directory", "update_quick_note", "delegate_to_atlas"])
async def test_any_other_tool_is_unknown(blackboard, tmp_path, tool):
    result = await _toolbox(blackboard, tmp_path).dispatch(tool, json.dumps({"path": "/"}))
    assert result == f"Unknown tool: {tool}"


@pytest.mark.unit
async def test_bad_json_arguments_are_reported(blackboard, tmp_path):
    assert "valid JSON" in await _toolbox(blackboard, tmp_path).dispatch("web_search", "{nope")


@pytest.mark.unit
async def test_search_results_are_wrapped_as_untrusted(blackboard, tmp_path):
    result = await _toolbox(blackboard, tmp_path).dispatch("web_search", json.dumps({"query": "kokoro"}))
    assert result.startswith("<untrusted_web_content")
    assert "https://a.org" in result


@pytest.mark.unit
async def test_search_error_goes_back_to_the_agent(blackboard, tmp_path):
    search = AsyncMock(side_effect=SearchError("degoog isn't reachable"))
    result = await _toolbox(blackboard, tmp_path, search=search).web_search("q")
    assert result == "degoog isn't reachable"


@pytest.mark.unit
async def test_blocked_url_goes_back_to_the_agent(blackboard, tmp_path):
    reader = AsyncMock(side_effect=FetchBlocked("local address"))
    result = await _toolbox(blackboard, tmp_path, read_url=reader).read_url("http://localhost")
    assert result == "local address"


@pytest.mark.unit
async def test_network_error_does_not_raise(blackboard, tmp_path):
    reader = AsyncMock(side_effect=OSError("reset"))
    assert "Couldn't read" in await _toolbox(blackboard, tmp_path, read_url=reader).read_url("https://a.org")


@pytest.mark.unit
async def test_read_page_is_recorded_as_source_in_real_blackboard(blackboard, tmp_path):
    run_id = blackboard.create_run("Q")
    toolbox = _toolbox(blackboard, tmp_path, run_id=run_id)
    await toolbox.read_url("https://a.org")

    sources = blackboard.list_sources(run_id)
    assert [(s.url, s.title, s.agent_id) for s in sources] == [("https://a.org", "A", "agt_1")]


@pytest.mark.unit
async def test_read_page_text_is_stored_content_addressed(blackboard, tmp_path):
    await _toolbox(blackboard, tmp_path).read_url("https://a.org")
    digest = hashlib.sha256(b"Body text").hexdigest()
    assert (tmp_path / "pages" / f"{digest}.txt").read_text() == "Body text"


@pytest.mark.unit
async def test_pages_read_tracks_progress_for_voice_mode(blackboard, tmp_path):
    toolbox = _toolbox(blackboard, tmp_path)
    await toolbox.read_url("https://a.org")
    assert toolbox.pages_read == [("A", "https://a.org")]


@pytest.mark.unit
async def test_empty_page_is_not_recorded(blackboard, tmp_path):
    reader = AsyncMock(return_value=PageText(url="https://a.org", title="A", text="  ", truncated=False))
    toolbox = _toolbox(blackboard, tmp_path, read_url=reader)
    assert "no readable text" in await toolbox.read_url("https://a.org")
    assert toolbox.pages_read == []
