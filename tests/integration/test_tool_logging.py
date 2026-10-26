"""The "[tool]" and "[web]" log lines the dashboard's Tools and Web cards
filter on, and the browser hope.py opens once the dashboard answers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger
from pipecat.services.llm_service import FunctionCallParams

from tools.tool_log import brief_args


@pytest.fixture
def log_lines():
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(m.record["message"]), level="INFO")
    yield lines
    logger.remove(sink)


def _params(arguments: dict, result_callback) -> FunctionCallParams:
    return FunctionCallParams(
        function_name="x", tool_call_id="call_1", arguments=arguments, llm=MagicMock(),
        pipeline_worker=MagicMock(), context=MagicMock(), result_callback=result_callback,
        app_resources=None,
    )


@pytest.mark.unit
def test_brief_args_keeps_file_contents_out_of_the_log():
    line = brief_args({"path": "notes.md", "content": "x" * 500 + "\nmore", "lines": 3})
    assert line.startswith("path='notes.md', content='xxx")
    assert "…" in line and len(line) < 120
    assert line.endswith("lines=3")


@pytest.mark.integration
async def test_every_tool_call_logs_its_call_and_its_answer(log_lines):
    from core.voice.agent_state import agent_state
    from tools.registry import _logged

    async def handler(params):
        await params.result_callback("three tasks")

    outer = AsyncMock()
    agent_state.active = "hope"
    await _logged("get_tasks", handler)(_params({"list_type": "today"}, outer))

    outer.assert_awaited_once_with("three tasks")  # the real callback still gets the result
    assert log_lines[0] == "[tool] hope → get_tasks(list_type='today')"
    assert log_lines[1].startswith("[tool] get_tasks answered in ")
    assert log_lines[1].endswith("(11 chars)")


@pytest.mark.integration
async def test_a_failing_tool_is_logged_and_still_raises(log_lines):
    from tools.registry import _logged

    async def handler(params):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await _logged("get_tasks", handler)(_params({}, AsyncMock()))
    assert "[tool] get_tasks failed" in log_lines


@pytest.mark.integration
async def test_setup_registers_every_tool_logged(mock_orchestrator, log_lines):
    from tools.registry import setup

    setup(mock_orchestrator)
    registered = {
        call.args[0]: call.args[1]
        for call in mock_orchestrator.bundle.llm.register_function.call_args_list
    }
    assert registered["get_weather"].__qualname__.startswith("_logged")


@pytest.mark.integration
async def test_hope_web_search_is_logged_for_the_web_card(log_lines):
    from core.voice.agent_state import agent_state
    from tools.registry import _make_search_web_handler
    from tools.web.search import SearchResult

    provider = SimpleNamespace(search=AsyncMock(return_value=[
        SearchResult(title="Kokoro", url="https://example.com", snippet="tts"),
    ]))
    agent_state.active = "hope"
    await _make_search_web_handler(provider)(_params({"query": "kokoro"}, AsyncMock()))
    assert log_lines == ['[web] hope searching: "kokoro"', "[web] got 1 results"]


# ── dashboard auto-open ─────────────────────────────────────────

class _Proc:
    def __init__(self, exits_after: int | None = None):
        self._polls = 0
        self._exits_after = exits_after

    def poll(self):
        self._polls += 1
        if self._exits_after is not None and self._polls > self._exits_after:
            return 1
        return None


@pytest.fixture
def hope_module(monkeypatch):
    import hope

    opened: list[str] = []
    monkeypatch.setattr(hope.webbrowser, "open", opened.append)
    monkeypatch.setattr(hope.asyncio, "sleep", AsyncMock())
    return hope, opened


@pytest.mark.integration
async def test_browser_opens_once_the_dashboard_answers(hope_module, monkeypatch):
    hope, opened = hope_module
    answers = iter([False, False, True])
    monkeypatch.setattr(hope, "is_listening", lambda port: next(answers))

    await hope._open_dashboard_when_ready(_Proc())
    assert opened == ["http://localhost:3000"]


@pytest.mark.integration
async def test_browser_not_opened_when_turned_off_or_reflex_dies(hope_module, monkeypatch):
    hope, opened = hope_module
    monkeypatch.setattr(hope, "is_listening", lambda port: False)

    await hope._open_dashboard_when_ready(_Proc(exits_after=2))  # reflex crashed
    await hope._open_dashboard_when_ready(None)  # autostart off
    monkeypatch.setattr(hope.settings, "dashboard_open_browser", False)
    monkeypatch.setattr(hope, "is_listening", lambda port: True)
    await hope._open_dashboard_when_ready(_Proc())
    assert opened == []
