"""DeepResearch — HOPE's first use of dynamically spawned sub-agents.

    plan (1 call) → spawn N researchers, each with its own voice → run them
    concurrently → writer synthesizes a cited report → HOPE says the summary

Runs in the background the same way Atlas does, so Pavan keeps talking to
HOPE meanwhile, and can connect to any researcher by name — mid-run or after
— to ask what it found.

Where everything lands:
- research_runs / agents / research_sources rows  → blackboard.db
- each researcher's findings, the final report     → research_dir/<run_id>/
- page text actually read                          → research_dir/pages/<sha256>.txt
- one episode for the whole run (agent="researcher") → episodic memory

Deliberately NOT written to semantic memory. Mem0 is scoped to Pavan by
default, so "an article says X" would turn into a durable fact *about
Pavan* that every agent then recalls as true. Research stays recallable
through episodic memory (recall_memory with agent_name='researcher').
"""

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

from loguru import logger
from openai import AsyncOpenAI

from core.agents.manager import LiveSubAgent, SubAgentLimitReached, SubAgentManager
from core.agents.spec import SubAgentSpec
from memory.coordination.store import Blackboard
from memory.episodic_memory.store import EpisodicMemory
from settings import settings
from sub_agents.research import prompts
from sub_agents.research.toolbox import TOOL_SCHEMAS, ResearchToolbox
from tools.web.search import SearchProvider

ResultCallback = Callable[[str], Awaitable[None]]

_EPISODIC_AGENT = "researcher"
_MAX_LOOP_TURNS = 40  # backstop beyond the tool-call budget, in case a model never stops


class DeepResearch:
    def __init__(
        self,
        manager: SubAgentManager,
        blackboard: Blackboard,
        episodic_memory: EpisodicMemory,
        search_provider: SearchProvider,
        client: AsyncOpenAI | None = None,
        research_dir: str | Path | None = None,
        toolbox_factory=ResearchToolbox,
    ) -> None:
        self._manager = manager
        self._blackboard = blackboard
        self._episodic_memory = episodic_memory
        self._search = search_provider
        self._client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._research_dir = Path(research_dir or settings.research_dir)
        self._toolbox_factory = toolbox_factory
        self._toolboxes: dict[str, ResearchToolbox] = {}  # agent_id -> toolbox
        self._busy = False
        self.current_run_id: str | None = None

    @property
    def busy(self) -> bool:
        return self._busy

    async def run(self, question: str, result_callback: ResultCallback) -> None:
        if self._busy:
            await result_callback("A research run is already going — I'll tell you when it's done.")
            return
        self._busy = True
        run_id = None
        plan_id = None
        try:
            run_id = await asyncio.to_thread(self._blackboard.create_run, question)
            self.current_run_id = run_id
            plan_id = await self._create_plan(question)
            message = await self._run(run_id, question)
            await self._resolve_plan(plan_id, run_id, question, message)
        except Exception as exc:
            logger.exception(f"Research run failed: {exc}")
            if run_id is not None:
                await self._mark_run(run_id, "failed")
            await self._abandon_plan(plan_id)
            message = f"The research run hit a problem: {exc}"
        finally:
            self._busy = False
        await result_callback(message)

    async def _run(self, run_id: str, question: str) -> str:
        run_dir = self._research_dir / run_id
        subtopics = await self._plan(question)
        await self._mark_run(run_id, "researching")

        researchers: list[LiveSubAgent] = []
        for subtopic in subtopics:
            spec = SubAgentSpec(
                template="researcher",
                objective=subtopic["objective"],
                boundaries=subtopic.get("boundaries") or "Stay on your objective.",
                output_format=prompts.RESEARCHER_OUTPUT_FORMAT,
                tools=["web_search", "read_url"],
                max_tool_calls=settings.research_max_tool_calls,
            )
            try:
                live = await self._manager.spawn(spec, self._voice_prompt, run_id=run_id)
            except SubAgentLimitReached as exc:
                logger.warning(f"Running with {len(researchers)} researcher(s): {exc}")
                break
            self._toolboxes[live.agent_id] = self._toolbox_factory(
                self._search, self._blackboard, run_id, live.agent_id, self._research_dir / "pages"
            )
            researchers.append(live)
        if not researchers:
            raise SubAgentLimitReached("No researcher could be spawned — every slot is busy.")

        for live in researchers:
            live.task = asyncio.create_task(self._research(live, question, run_dir))
        await asyncio.gather(*(live.task for live in researchers), return_exceptions=True)

        finished = [live for live in researchers if live.status == "idle" and live.findings]
        if not finished:
            raise RuntimeError("every researcher failed")

        await self._mark_run(run_id, "writing")
        report, spoken = await self._write(question, finished)
        report_path = run_dir / "report.md"
        await asyncio.to_thread(_write_text, report_path, f"# {question}\n\n{report}\n")
        await asyncio.to_thread(
            self._blackboard.update_run, run_id, "completed", str(report_path), spoken
        )

        names = ", ".join(live.spoken_name for live in finished)
        return (
            f"{spoken}\n\nThe full report is saved at {report_path}. "
            f"{names} {'is' if len(finished) == 1 else 'are'} still around if you want to ask "
            f"about the details."
        )

    async def _plan(self, question: str) -> list[dict]:
        cap = settings.research_max_researchers
        response = await self._client.chat.completions.create(
            model=settings.research_llm_model,
            messages=[
                {"role": "system", "content": prompts.planner_prompt(cap)},
                {"role": "user", "content": question},
            ],
            response_format={"type": "json_object"},
        )
        try:
            subtopics = json.loads(response.choices[0].message.content or "{}").get("subtopics", [])
        except json.JSONDecodeError:
            subtopics = []
        subtopics = [s for s in subtopics if isinstance(s, dict) and s.get("objective")]
        # The cap is enforced here too, not only asked for in the prompt.
        return subtopics[:cap] or [{"objective": question, "boundaries": ""}]

    async def _research(self, live: LiveSubAgent, question: str, run_dir: Path) -> None:
        toolbox = self._toolboxes[live.agent_id]
        try:
            findings = await self._research_loop(live, question, toolbox)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"Researcher {live.spoken_name} failed")
            await self._manager.set_status(live, "failed")
            return
        live.findings = findings
        await asyncio.to_thread(
            _write_text, run_dir / f"{live.spoken_name.lower()}.md",
            f"# {live.spoken_name}: {live.spec.objective}\n\n{findings}\n",
        )
        await self._manager.set_status(live, "idle")

    async def _research_loop(self, live: LiveSubAgent, question: str, toolbox: ResearchToolbox) -> str:
        messages: list = [
            {
                "role": "system",
                "content": prompts.researcher_prompt(
                    live.spoken_name, live.spec, question, date.today().isoformat()
                ),
            },
            {"role": "user", "content": live.spec.objective},
        ]
        calls_left = live.spec.max_tool_calls
        for _ in range(_MAX_LOOP_TURNS):
            out_of_budget = calls_left <= 0
            if out_of_budget:
                messages.append({
                    "role": "user",
                    "content": "Tool budget used up. Write your findings now from what you've read.",
                })
            response = await self._client.chat.completions.create(
                model=settings.research_llm_model,
                messages=messages,
                **({} if out_of_budget else {"tools": TOOL_SCHEMAS, "tool_choice": "auto"}),
            )
            choice = response.choices[0]
            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                return choice.message.content or "No findings."

            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                if calls_left > 0:
                    result = await toolbox.dispatch(tool_call.function.name, tool_call.function.arguments)
                    calls_left -= 1
                else:
                    result = "Tool budget used up — no more calls."
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
        return "Stopped after too many turns without a final answer."

    async def _write(self, question: str, finished: list[LiveSubAgent]) -> tuple[str, str]:
        findings = "\n\n".join(
            f"## {live.spoken_name} — {live.spec.objective}\n{live.findings}" for live in finished
        )
        response = await self._client.chat.completions.create(
            model=settings.research_llm_model,
            messages=[
                {"role": "system", "content": prompts.WRITER_PROMPT},
                {"role": "user", "content": f"Question: {question}\n\n{findings}"},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = {}
        report = payload.get("report_markdown") or findings
        spoken = payload.get("spoken_summary") or "The research is done."
        return report, spoken

    def _voice_prompt(self, live: LiveSubAgent) -> str:
        toolbox = self._toolboxes.get(live.agent_id)
        return prompts.researcher_voice_prompt(
            live.spoken_name,
            live.spec.objective,
            live.status,
            toolbox.pages_read if toolbox else [],
            live.findings,
        )

    async def _mark_run(self, run_id: str, status: str) -> None:
        try:
            await asyncio.to_thread(self._blackboard.update_run, run_id, status)
        except Exception:
            logger.exception(f"Couldn't mark research run {run_id} '{status}'")

    async def _create_plan(self, question: str) -> str | None:
        try:
            return await asyncio.to_thread(self._episodic_memory.create_plan, _EPISODIC_AGENT, question)
        except Exception:
            logger.exception("Research plan creation failed — continuing without a tracked plan")
            return None

    async def _resolve_plan(self, plan_id: str | None, run_id: str, question: str, message: str) -> None:
        """Best-effort, like Atlas: one episode per completed run, then the plan
        is resolved against it — or abandoned if the episode didn't land."""
        try:
            episode_id = await asyncio.to_thread(
                self._episodic_memory.write,
                agent=_EPISODIC_AGENT,
                session_id=run_id,
                reason="task_complete",
                span_turns=0,
                summary=f"Research question: {question}\nResult: {message}",
                messages=[],
            )
        except Exception:
            logger.exception("Research episodic write failed — continuing without persistence")
            await self._abandon_plan(plan_id)
            return
        if plan_id is None:
            return
        try:
            await asyncio.to_thread(self._episodic_memory.resolve_plan, plan_id, episode_id)
        except Exception:
            logger.exception("Research plan resolution failed")

    async def _abandon_plan(self, plan_id: str | None) -> None:
        if plan_id is None:
            return
        try:
            await asyncio.to_thread(self._episodic_memory.abandon_plan, plan_id)
        except Exception:
            logger.exception("Research plan abandonment failed")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
