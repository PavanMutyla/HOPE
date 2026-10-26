"""Integration tests for sub_agents/research/deep_research.py.

The LLM is scripted (no API calls) and search/fetch are faked, but everything
DeepResearch persists goes to real stores: a real Blackboard (runs, agents,
sources), a real EpisodicMemory (the run's episode + plan) and real files
(findings, report, page text). Those writes are all best-effort, so a mock
would only prove they were attempted.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.manager import SubAgentManager
from core.voice.agent import AgentRegistry
from core.voice.voice_pool import VoicePool
from memory.coordination.store import Blackboard
from memory.episodic_memory.store import EpisodicMemory
from sub_agents.research.deep_research import DeepResearch
from sub_agents.research.toolbox import ResearchToolbox
from tools.web.fetch import PageText
from tools.web.search import SearchResult


def _reply(content=None, tool_calls=None):
    finish = "tool_calls" if tool_calls else "stop"
    message = SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=message)])


def _call(name, args, call_id):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


class ScriptedLLM:
    """Answers by role, recognised from the system prompt: planner, researcher, writer."""

    def __init__(self, subtopics, researcher_fails_for=None, ignore_budget=False):
        self.subtopics = subtopics
        self.researcher_fails_for = researcher_fails_for
        self.ignore_budget = ignore_budget
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs["messages"][0]["content"]
        if system.startswith("You plan research"):
            return _reply(json.dumps({"subtopics": self.subtopics}))
        if system.startswith("You write HOPE's final research report"):
            return _reply(json.dumps({
                "report_markdown": "Kokoro has 54 voices [source](https://voices.example/list).",
                "spoken_summary": "Kokoro ships fifty-four voices.",
            }))
        objective = kwargs["messages"][1]["content"]
        if objective == self.researcher_fails_for:
            raise RuntimeError("model fell over")
        tool_turns = sum(1 for m in kwargs["messages"] if isinstance(m, dict) and m.get("role") == "tool")
        if "tools" in kwargs and (self.ignore_budget or tool_turns == 0):
            return _reply(tool_calls=[
                _call("web_search", {"query": objective}, f"c{tool_turns}a"),
                _call("read_url", {"url": "https://voices.example/list"}, f"c{tool_turns}b"),
            ])
        return _reply(f"- Found it for '{objective}' [1]\nSources: 1. https://voices.example/list")


@pytest.fixture
def stores(tmp_path, fake_embedding_function):
    episodic = EpisodicMemory(
        db_path=tmp_path / "episodic.db",
        media_dir=tmp_path / "media",
        persist_dir=tmp_path / "chroma",
        embedding_function=fake_embedding_function,
    )
    blackboard = Blackboard(episodic, db_path=tmp_path / "blackboard.db")
    yield episodic, blackboard
    blackboard.close()
    episodic.close()


def _research(tmp_path, stores, llm, max_live=5):
    episodic, blackboard = stores
    registry = AgentRegistry()
    manager = SubAgentManager(registry, blackboard, VoicePool(), max_live)
    search = MagicMock()
    search.search = AsyncMock(return_value=[SearchResult(title="List", url="https://voices.example/list")])
    reader = AsyncMock(return_value=PageText(
        url="https://voices.example/list", title="Voice list", text="54 voices.", truncated=False
    ))

    def toolbox(search_provider, board, run_id, agent_id, pages_dir):
        return ResearchToolbox(search_provider, board, run_id, agent_id, pages_dir, read_url=reader)

    research = DeepResearch(
        manager, blackboard, episodic, search,
        client=llm, research_dir=tmp_path / "research", toolbox_factory=toolbox,
    )
    return research, manager, registry


_TWO = [{"objective": "English voices", "boundaries": "not others"},
        {"objective": "Other languages", "boundaries": "not English"}]


@pytest.mark.integration
async def test_full_run_completes_and_reports_back(tmp_path, stores):
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    callback = AsyncMock()
    await research.run("What voices does Kokoro have?", callback)

    message = callback.call_args[0][0]
    assert message.startswith("Kokoro ships fifty-four voices.")
    assert "report.md" in message


@pytest.mark.integration
async def test_run_row_is_completed_with_report_and_summary(tmp_path, stores):
    _, blackboard = stores
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("Q", AsyncMock())

    run = blackboard.get_run(research.current_run_id)
    assert run.status == "completed"
    assert run.summary == "Kokoro ships fifty-four voices."
    assert (tmp_path / "research" / run.run_id / "report.md").read_text().startswith("# Q")


@pytest.mark.integration
async def test_one_researcher_per_subtopic_with_distinct_voices(tmp_path, stores):
    research, manager, registry = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("Q", AsyncMock())

    live = manager.live()
    assert len(live) == 2
    assert len({agent.voice_id for agent in live}) == 2
    assert all(registry.find(agent.spoken_name) for agent in live)  # Pavan can connect to each


@pytest.mark.integration
async def test_finished_researchers_stay_idle_with_their_findings(tmp_path, stores):
    research, manager, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("Q", AsyncMock())

    for agent in manager.live():
        assert agent.status == "idle"
        assert "Found it" in agent.findings
        assert "Found it" in agent.voice_agent.current_prompt()


@pytest.mark.integration
async def test_each_researchers_findings_are_saved_to_disk(tmp_path, stores):
    research, manager, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("Q", AsyncMock())

    run_dir = tmp_path / "research" / research.current_run_id
    for agent in manager.live():
        assert "Found it" in (run_dir / f"{agent.spoken_name.lower()}.md").read_text()


@pytest.mark.integration
async def test_pages_read_land_as_sources_in_real_blackboard(tmp_path, stores):
    _, blackboard = stores
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("Q", AsyncMock())

    sources = blackboard.list_sources(research.current_run_id)
    assert {s.url for s in sources} == {"https://voices.example/list"}
    assert len(sources) == 2  # one per researcher


@pytest.mark.integration
async def test_run_writes_one_researcher_episode_to_real_episodic_memory(tmp_path, stores):
    episodic, _ = stores
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("What voices does Kokoro have?", AsyncMock())

    episodes = episodic.query("Kokoro voices", 5, agent="researcher")
    assert len(episodes) == 1
    assert "What voices does Kokoro have?" in episodes[0].summary


@pytest.mark.integration
async def test_run_resolves_its_plan(tmp_path, stores):
    episodic, _ = stores
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    await research.run("Q", AsyncMock())

    assert episodic.list_plans("researcher", "pending") == []
    assert len(episodic.list_plans("researcher", "completed")) == 1


@pytest.mark.integration
async def test_planner_output_is_capped_in_code(tmp_path, stores, monkeypatch):
    from settings import settings

    monkeypatch.setattr(settings, "research_max_researchers", 2)
    many = [{"objective": f"topic {i}", "boundaries": ""} for i in range(9)]
    research, manager, _ = _research(tmp_path, stores, ScriptedLLM(many))
    await research.run("Q", AsyncMock())
    assert len(manager.live()) == 2


@pytest.mark.integration
async def test_empty_plan_falls_back_to_one_researcher_on_the_question(tmp_path, stores):
    research, manager, _ = _research(tmp_path, stores, ScriptedLLM([]))
    await research.run("Just one thing?", AsyncMock())
    assert [agent.spec.objective for agent in manager.live()] == ["Just one thing?"]


@pytest.mark.integration
async def test_one_failed_researcher_does_not_sink_the_run(tmp_path, stores):
    _, blackboard = stores
    research, manager, _ = _research(tmp_path, stores, ScriptedLLM(_TWO, researcher_fails_for="Other languages"))
    await research.run("Q", AsyncMock())

    assert blackboard.get_run(research.current_run_id).status == "completed"
    statuses = {agent.spec.objective: agent.status for agent in manager.live()}
    assert statuses == {"English voices": "idle", "Other languages": "failed"}


@pytest.mark.integration
async def test_every_researcher_failing_fails_the_run_and_abandons_the_plan(tmp_path, stores):
    episodic, blackboard = stores
    one = [{"objective": "only", "boundaries": ""}]
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(one, researcher_fails_for="only"))
    callback = AsyncMock()
    await research.run("Q", callback)

    assert "problem" in callback.call_args[0][0]
    assert blackboard.get_run(research.current_run_id).status == "failed"
    assert len(episodic.list_plans("researcher", "abandoned")) == 1
    assert research.busy is False


@pytest.mark.integration
async def test_tool_budget_is_enforced_even_if_the_model_keeps_calling(tmp_path, stores, monkeypatch):
    from settings import settings

    monkeypatch.setattr(settings, "research_max_tool_calls", 3)
    llm = ScriptedLLM([{"objective": "greedy", "boundaries": ""}], ignore_budget=True)
    research, _, _ = _research(tmp_path, stores, llm)
    await research.run("Q", AsyncMock())

    researcher_calls = [c for c in llm.calls if c["messages"][0]["content"].startswith("You are ")]
    executed = sum(
        1 for m in researcher_calls[-1]["messages"]
        if isinstance(m, dict) and m.get("role") == "tool" and "budget" not in m["content"]
    )
    assert executed == 3
    assert "tools" not in researcher_calls[-1]  # the final turn is forced to answer


@pytest.mark.integration
async def test_second_run_while_busy_is_refused(tmp_path, stores):
    research, _, _ = _research(tmp_path, stores, ScriptedLLM(_TWO))
    research._busy = True
    callback = AsyncMock()
    await research.run("Q", callback)
    assert "already going" in callback.call_args[0][0]


@pytest.mark.integration
async def test_research_is_never_written_to_semantic_memory():
    """Mem0 is Pavan-scoped: a web claim would become a durable fact about him."""
    import inspect

    import sub_agents.research.deep_research as module

    assert "semantic" not in inspect.getsource(module.DeepResearch).lower()
