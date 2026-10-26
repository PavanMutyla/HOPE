import asyncio
import dataclasses
import time

from loguru import logger


from pipecat.frames.frames import FunctionCallResultProperties
from pipecat.services.llm_service import FunctionCallParams

from sub_agents.atlas.agent import Atlas


from core.agents.manager import SubAgentManager
from core.voice.agent_state import agent_state
from core.voice.orchestrator import VoiceOrchestrator
from core.voice.team_state import team_state
from memory.board import live as board_live
from settings import settings
from sub_agents.research.deep_research import DeepResearch
from tools.tool_log import brief_args
from tools.web import fetch
from tools.web.fetch import FetchBlocked, as_untrusted
from tools.web.search import SearchError, SearchProvider
from tools.schema import (
    AddTaskArgs,
    CheckPlansArgs,
    ClaimTaskArgs,
    ConnectToAgentArgs,
    ConsultAgentsArgs,
    DelegateToAtlasArgs,
    DeleteTaskArgs,
    DisableTeamModeArgs,
    EnableTeamModeArgs,
    GetActiveTasksArgs,
    GetLocationAndTimeArgs,
    GetQuickNoteArgs,
    GetSignalsArgs,
    GetTasksArgs,
    GetWeatherArgs,
    HandbackToHopeArgs,
    ListSubagentsArgs,
    PostTaskArgs,
    ReadWebpageArgs,
    RecallMemoryArgs,
    RecallProcedureArgs,
    RecallSemanticArgs,
    RecordProcedureOutcomeArgs,
    ResearchStatusArgs,
    RetireSubagentArgs,
    SaveProcedureArgs,
    SearchWebArgs,
    SendSignalArgs,
    StartDeepResearchArgs,
    ToggleTaskArgs,
    UpdateQuickNoteArgs,
    UpdateTaskArgs,
    UpdateTaskStatusArgs,
    function_schema,
)

atlas = Atlas()

# ── Tool schemas exposed to HOPE's LLM ────────────────────────────────────────

delegate_to_atlas_schema = function_schema(
    "delegate_to_atlas",
    (
        f"Delegate a filesystem task to Atlas. Use whenever {settings.user_name} asks to create, "
        "read, edit, or delete files or folders. Pass a clear natural-language "
        "description of the task."
    ),
    DelegateToAtlasArgs,
)

connect_to_agent_schema = function_schema(
    "connect_to_agent",
    (
        f"Switch the active voice to another agent so {settings.user_name} can speak with it directly — "
        f"Atlas, or any live researcher by its spoken name. Use when {settings.user_name} says "
        "'connect me to Atlas', 'let me talk to Emma', or similar."
    ),
    ConnectToAgentArgs,
)

handback_to_hope_schema = function_schema(
    "handback_to_hope",
    (
        "Hand the active voice back to HOPE. "
        f"Use when {settings.user_name} says 'HOPE take over', 'back to HOPE', 'thanks Atlas', 'thanks Emma', "
        "or similar."
    ),
    HandbackToHopeArgs,
)

recall_memory_schema = function_schema(
    "recall_memory",
    (
        "Search past conversation history (episodic memory) for relevant context "
        "from earlier sessions. Defaults to searching your own history; pass "
        "agent_name to search a specific agent's history instead, or 'all' to "
        "search everyone's history."
    ),
    RecallMemoryArgs,
)

recall_semantic_schema = function_schema(
    "recall_semantic",
    (
        "Search durable facts and preferences (not conversation history — use "
        "recall_memory for that). Defaults to the shared pool everyone can see; "
        "pass agent_name to see only one agent's private facts."
    ),
    RecallSemanticArgs,
)

save_procedure_schema = function_schema(
    "save_procedure",
    (
        "Save a reusable step-by-step procedure under your own name, so you can "
        "follow it again later instead of figuring it out from scratch. Only call "
        f"this when {settings.user_name} explicitly confirms they want something remembered as a "
        "procedure — never save one unprompted."
    ),
    SaveProcedureArgs,
)

recall_procedure_schema = function_schema(
    "recall_procedure",
    (
        "Look up a saved procedure for a task you might have done before. "
        "Defaults to your own saved procedures; pass agent_name to check a "
        "specific agent's instead. Returns steps plus success/failure counts so "
        "you can judge how much to trust it before following it."
    ),
    RecallProcedureArgs,
)

record_procedure_outcome_schema = function_schema(
    "record_procedure_outcome",
    (
        "Report whether a procedure you just followed (via recall_procedure) "
        "actually worked. Keeps its success/failure count accurate so future "
        "recalls reflect how trustworthy it really is."
    ),
    RecordProcedureOutcomeArgs,
)

consult_agents_schema = function_schema(
    "consult_agents",
    (
        "Ask multiple agents the same question or task concurrently and gather all "
        "their replies at once, instead of contacting them one at a time. Use when "
        f"you need input from more than one agent to answer {settings.user_name}."
    ),
    ConsultAgentsArgs,
)

enable_team_mode_schema = function_schema(
    "enable_team_mode",
    (
        "Turn on team mode so other agents can listen in on this conversation and "
        "speak up on their own, in their own voice, when they have something "
        f"relevant to add. Use when {settings.user_name} says something like 'bring the team in' "
        "or 'let everyone listen in'."
    ),
    EnableTeamModeArgs,
)

disable_team_mode_schema = function_schema(
    "disable_team_mode",
    (
        f"Turn off team mode so it's back to just you and {settings.user_name}. Use when {settings.user_name} "
        "says something like 'just us' or 'team mode off'."
    ),
    DisableTeamModeArgs,
)

check_plans_schema = function_schema(
    "check_plans",
    (
        "Check on tasks that were planned — what's still pending, or what's "
        "already completed/abandoned. Defaults to your own pending plans; pass "
        "agent_name to check a specific agent's instead, or 'all' for everyone's. "
        "Pass status to see resolved plans instead of just pending ones."
    ),
    CheckPlansArgs,
)

post_task_schema = function_schema(
    "post_task",
    (
        "Post a task to the shared coordination pool for any agent to pick up — "
        "use this to hand off work without waiting for a specific agent to be "
        "free, unlike delegate_to_atlas which targets Atlas directly."
    ),
    PostTaskArgs,
)

claim_task_schema = function_schema(
    "claim_task",
    (
        "Claim an open task from the coordination pool so you're the one working "
        "on it. Fails harmlessly if another agent already claimed it first."
    ),
    ClaimTaskArgs,
)

update_task_status_schema = function_schema(
    "update_task_status",
    (
        "Update the status of a task you're working on — mark it in_progress, "
        "completed, or failed. Completing or failing a task also records it in "
        "durable memory automatically."
    ),
    UpdateTaskStatusArgs,
)

get_active_tasks_schema = function_schema(
    "get_active_tasks",
    (
        "Check what tasks are currently open, claimed, or in progress in the "
        "shared coordination pool. Pass agent_name to see only one agent's "
        "tasks, or omit to see everyone's."
    ),
    GetActiveTasksArgs,
)

send_signal_schema = function_schema(
    "send_signal",
    "Send a direct message to another agent's inbox in the coordination pool.",
    SendSignalArgs,
)

get_signals_schema = function_schema(
    "get_signals",
    (
        "Check your inbox for unread messages other agents have sent you via "
        "send_signal. Reading a message marks it read."
    ),
    GetSignalsArgs,
)

add_task_schema = function_schema(
    "add_task",
    (
        "Add an item to the shared board's Today, Planned, or Pending list — "
        f"visible to {settings.user_name} and every agent, not just you."
    ),
    AddTaskArgs,
)

update_task_schema = function_schema(
    "update_task",
    "Change the text of an existing board task.",
    UpdateTaskArgs,
)

toggle_task_schema = function_schema(
    "toggle_task",
    "Mark a board task done, or undone if it's already done.",
    ToggleTaskArgs,
)

delete_task_schema = function_schema(
    "delete_task",
    "Remove an item from the board entirely.",
    DeleteTaskArgs,
)

get_tasks_schema = function_schema(
    "get_tasks",
    "Read the current items on one of the board's Today, Planned, or Pending lists.",
    GetTasksArgs,
)

get_quick_note_schema = function_schema(
    "get_quick_note",
    "Read the shared board's Quick notes.",
    GetQuickNoteArgs,
)

update_quick_note_schema = function_schema(
    "update_quick_note",
    (
        "Replace the shared board's Quick notes with new content. This overwrites "
        "the whole note, so read it first with get_quick_note if you want to add "
        "to what's already there rather than replace it."
    ),
    UpdateQuickNoteArgs,
)

get_location_and_time_schema = function_schema(
    "get_location_and_time",
    f"Get {settings.user_name}'s home location and the current local date/time.",
    GetLocationAndTimeArgs,
)

get_weather_schema = function_schema(
    "get_weather",
    f"Get the current weather and today's forecast at {settings.user_name}'s home location.",
    GetWeatherArgs,
)

search_web_schema = function_schema(
    "search_web",
    (
        "Search the web for a quick fact or a current answer. For anything that needs "
        "several sources compared, use start_deep_research instead."
    ),
    SearchWebArgs,
)

read_webpage_schema = function_schema(
    "read_webpage",
    "Read the main text of one public web page, e.g. a result from search_web.",
    ReadWebpageArgs,
)

start_deep_research_schema = function_schema(
    "start_deep_research",
    (
        "Start a deep research run in the background: researchers, each with their own "
        f"voice, search the web in parallel and a cited report comes back. Use when {settings.user_name} "
        "asks you to research, investigate, or compare something properly. Takes a few "
        f"minutes; keep talking with {settings.user_name} meanwhile."
    ),
    StartDeepResearchArgs,
)

research_status_schema = function_schema(
    "research_status",
    "Check how the current or most recent deep research run is going.",
    ResearchStatusArgs,
)

list_subagents_schema = function_schema(
    "list_subagents",
    "List the sub-agents that exist right now — their names, what they're on, and status.",
    ListSubagentsArgs,
)

retire_subagent_schema = function_schema(
    "retire_subagent",
    (
        f"Dismiss a sub-agent {settings.user_name} no longer needs, freeing its voice. Stops it if it's "
        "still working."
    ),
    RetireSubagentArgs,
)

ALL_SCHEMAS = [
    delegate_to_atlas_schema,
    connect_to_agent_schema,
    handback_to_hope_schema,
    recall_memory_schema,
    recall_semantic_schema,
    save_procedure_schema,
    recall_procedure_schema,
    record_procedure_outcome_schema,
    check_plans_schema,
    consult_agents_schema,
    enable_team_mode_schema,
    disable_team_mode_schema,
    post_task_schema,
    claim_task_schema,
    update_task_status_schema,
    get_active_tasks_schema,
    send_signal_schema,
    get_signals_schema,
    add_task_schema,
    update_task_schema,
    toggle_task_schema,
    delete_task_schema,
    get_tasks_schema,
    get_quick_note_schema,
    update_quick_note_schema,
    get_location_and_time_schema,
    get_weather_schema,
    search_web_schema,
    read_webpage_schema,
    start_deep_research_schema,
    research_status_schema,
    list_subagents_schema,
    retire_subagent_schema,
]

# What a connected sub-agent may call while it holds the shared pipeline. The
# researcher voice prompt only ever needs to hand back, but its context holds
# web-derived findings — so this is enforced in code (see _guarded), not left
# to the prompt: a page that talked the model into delegate_to_atlas or
# update_quick_note gets refused here.
SUBAGENT_VOICE_TOOLS = frozenset({
    "handback_to_hope", "connect_to_agent", "list_subagents", "research_status",
})

# HOPE's own reads are capped well below the researchers' — this text lands in
# the live voice context, which every following turn pays for.
_HOPE_PAGE_CHARS = 6000

# ── Handlers ──────────────────────────────────────────────────────────────────

async def delegate_to_atlas_handler(params: FunctionCallParams) -> None:
    args = DelegateToAtlasArgs(**params.arguments)
    await params.result_callback(
        "Task received. Atlas is on it.",
        properties=FunctionCallResultProperties(is_final=False),
    )
    asyncio.create_task(atlas.run(args.task, params.result_callback))


def _make_connect_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = ConnectToAgentArgs(**params.arguments)
        agent = orchestrator.find_agent(args.name)
        if agent is None:
            await params.result_callback(
                f"There's no agent called {args.name} right now — check list_subagents."
            )
            return
        await orchestrator.switch_to(agent.name)
        await params.result_callback(f"Connecting you to {agent.spoken_name or agent.name.title()} now.")
    return handler


def _make_handback_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        HandbackToHopeArgs(**params.arguments)
        await orchestrator.switch_to("hope")
        await params.result_callback("HOPE is back.")
    return handler


def _make_recall_memory_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = RecallMemoryArgs(**params.arguments)
        # HOPE defaults to everyone's history: it owns the conversation and
        # hands work to the others, so "did I ask about X?" has to reach
        # Atlas's tasks and research runs too. Everyone else defaults to
        # their own.
        default = "all" if agent_state.active == "hope" else agent_state.active
        agent_name = args.agent_name or default
        agent = None if agent_name == "all" else agent_name

        episodes = await asyncio.to_thread(
            orchestrator.bundle.episodic_memory.query, args.query, 5, agent
        )

        if not episodes:
            await params.result_callback("No matching memories found.")
            return

        summary_text = "\n".join(f"- ({episode.agent}) {episode.summary}" for episode in episodes)
        await params.result_callback(summary_text)
    return handler


def _make_recall_semantic_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = RecallSemanticArgs(**params.arguments)  # omitted agent_name -> shared pool, unlike recall_memory

        facts = await asyncio.to_thread(
            orchestrator.bundle.semantic_memory.query, args.query, 5, args.agent_name
        )

        if not facts:
            await params.result_callback("No matching facts found.")
            return

        summary_text = "\n".join(
            f"- ({fact.get('agent_id') or 'shared'}) {fact['memory']}" for fact in facts
        )
        await params.result_callback(summary_text)
    return handler


def _make_save_procedure_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = SaveProcedureArgs(**params.arguments)

        try:
            procedure = await asyncio.to_thread(
                orchestrator.bundle.procedural_memory.save,
                agent_state.active, args.name, args.description, args.steps,
            )
        except ValueError as exc:
            await params.result_callback(str(exc))
            return

        await params.result_callback(
            f"Saved procedure '{procedure.name}' with {len(procedure.steps)} steps."
        )
    return handler


def _make_recall_procedure_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = RecallProcedureArgs(**params.arguments)
        agent_name = args.agent_name or agent_state.active

        procedures = await asyncio.to_thread(
            orchestrator.bundle.procedural_memory.recall, args.query, agent_name, 3
        )

        if not procedures:
            await params.result_callback("No matching procedures found.")
            return

        lines = []
        for procedure in procedures:
            steps_text = " -> ".join(procedure.steps)
            lines.append(
                f"- {procedure.name}: {procedure.description} "
                f"(succeeded {procedure.success_count}x, failed {procedure.failure_count}x) "
                f"steps: {steps_text}"
            )
        await params.result_callback("\n".join(lines))
    return handler


def _make_record_procedure_outcome_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = RecordProcedureOutcomeArgs(**params.arguments)

        try:
            procedure = await asyncio.to_thread(
                orchestrator.bundle.procedural_memory.record_outcome,
                agent_state.active, args.name, args.success,
            )
        except ValueError as exc:
            await params.result_callback(str(exc))
            return

        await params.result_callback(
            f"Recorded. '{procedure.name}' has {procedure.success_count} successes "
            f"and {procedure.failure_count} failures so far."
        )
    return handler


def _make_check_plans_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = CheckPlansArgs(**params.arguments)
        agent_name = args.agent_name or agent_state.active
        agent = None if agent_name == "all" else agent_name
        status = args.status or "pending"

        matching_plans = await asyncio.to_thread(
            orchestrator.bundle.episodic_memory.list_plans, agent, status
        )

        if not matching_plans:
            await params.result_callback(f"No {status} plans found.")
            return

        lines = [f"- ({plan.agent}) {plan.description} [{plan.status}]" for plan in matching_plans]
        await params.result_callback("\n".join(lines))
    return handler


def _make_consult_agents_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = ConsultAgentsArgs(**params.arguments)

        try:
            replies = await orchestrator.broadcast(agent_state.active, args.agent_names, args.message)
        except KeyError as exc:
            await params.result_callback(str(exc))
            return

        summary_text = "\n".join(f"- {name}: {reply}" for name, reply in replies.items())
        await params.result_callback(summary_text)
    return handler


async def enable_team_mode_handler(params: FunctionCallParams) -> None:
    EnableTeamModeArgs(**params.arguments)
    team_state.enabled = True
    await params.result_callback("Team mode is on — everyone's listening now.")


async def disable_team_mode_handler(params: FunctionCallParams) -> None:
    DisableTeamModeArgs(**params.arguments)
    team_state.enabled = False
    await params.result_callback("Team mode is off — back to just us.")


def _make_post_task_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = PostTaskArgs(**params.arguments)

        task_id = await asyncio.to_thread(
            orchestrator.bundle.blackboard.post_task, args.description, agent_state.active
        )
        await params.result_callback(f"Posted task {task_id}.")
    return handler


def _make_claim_task_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = ClaimTaskArgs(**params.arguments)

        claimed = await asyncio.to_thread(
            orchestrator.bundle.blackboard.claim_task, args.task_id, agent_state.active
        )
        if claimed:
            await params.result_callback(f"Claimed task {args.task_id}.")
        else:
            await params.result_callback(
                f"Could not claim task {args.task_id} — already claimed or doesn't exist."
            )
    return handler


def _make_update_task_status_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = UpdateTaskStatusArgs(**params.arguments)

        updated = await asyncio.to_thread(
            orchestrator.bundle.blackboard.update_task_status,
            args.task_id, args.status, args.detail,
        )
        if updated:
            await params.result_callback(f"Task {args.task_id} marked {args.status}.")
        else:
            await params.result_callback(f"No task found with id {args.task_id}.")
    return handler


def _make_get_active_tasks_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = GetActiveTasksArgs(**params.arguments)

        tasks = await asyncio.to_thread(
            orchestrator.bundle.blackboard.get_active_tasks, args.agent_name
        )
        if not tasks:
            await params.result_callback("No active tasks found.")
            return

        lines = [
            f"- ({task.task_id}) {task.description} "
            f"[{task.status}, owner={task.owner_agent or 'unclaimed'}]"
            for task in tasks
        ]
        await params.result_callback("\n".join(lines))
    return handler


def _make_send_signal_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = SendSignalArgs(**params.arguments)

        signal_id = await asyncio.to_thread(
            orchestrator.bundle.blackboard.send_signal,
            agent_state.active, args.to_agent, args.payload,
        )
        await params.result_callback(f"Sent signal {signal_id} to {args.to_agent}.")
    return handler


def _make_get_signals_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = GetSignalsArgs(**params.arguments)
        agent_name = args.agent_name or agent_state.active

        signals = await asyncio.to_thread(
            orchestrator.bundle.blackboard.get_signals_for, agent_name
        )
        if not signals:
            await params.result_callback("No unread signals.")
            return

        lines = [f"- from {signal.from_agent}: {signal.payload}" for signal in signals]
        await params.result_callback("\n".join(lines))
    return handler


def _make_add_task_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = AddTaskArgs(**params.arguments)

        item = await asyncio.to_thread(
            orchestrator.bundle.board.add_item, args.list_type, args.text, agent_state.active
        )
        await params.result_callback(f"Added to {args.list_type} (id {item.id}): {item.text}")
    return handler


def _make_update_task_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = UpdateTaskArgs(**params.arguments)

        item = await asyncio.to_thread(
            orchestrator.bundle.board.update_item_text, args.item_id, args.text, agent_state.active
        )
        if item is None:
            await params.result_callback(f"No task found with id {args.item_id}.")
        else:
            await params.result_callback(f"Updated task {item.id}: {item.text}")
    return handler


def _make_toggle_task_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = ToggleTaskArgs(**params.arguments)

        item = await asyncio.to_thread(
            orchestrator.bundle.board.toggle_item, args.item_id, agent_state.active
        )
        if item is None:
            await params.result_callback(f"No task found with id {args.item_id}.")
        else:
            state = "done" if item.done else "not done"
            await params.result_callback(f"Task {item.id} is now {state}.")
    return handler


def _make_delete_task_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = DeleteTaskArgs(**params.arguments)

        deleted = await asyncio.to_thread(orchestrator.bundle.board.delete_item, args.item_id)
        if deleted:
            await params.result_callback(f"Deleted task {args.item_id}.")
        else:
            await params.result_callback(f"No task found with id {args.item_id}.")
    return handler


def _make_get_tasks_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = GetTasksArgs(**params.arguments)

        items = await asyncio.to_thread(orchestrator.bundle.board.list_items, args.list_type)
        if not items:
            await params.result_callback(f"Nothing on the {args.list_type} list.")
            return

        lines = [
            f"- ({item.id}) {item.text} [{'done' if item.done else 'not done'}, {item.agent}]"
            for item in items
        ]
        await params.result_callback("\n".join(lines))
    return handler


def _make_get_quick_note_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        GetQuickNoteArgs(**params.arguments)

        note = await asyncio.to_thread(orchestrator.bundle.board.get_quick_note)
        if not note.content:
            await params.result_callback("Quick notes is empty.")
        else:
            await params.result_callback(note.content)
    return handler


def _make_update_quick_note_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        args = UpdateQuickNoteArgs(**params.arguments)

        await asyncio.to_thread(
            orchestrator.bundle.board.update_quick_note, args.content, agent_state.active
        )
        await params.result_callback("Quick notes updated.")
    return handler


async def get_location_and_time_handler(params: FunctionCallParams) -> None:
    GetLocationAndTimeArgs(**params.arguments)
    info = await board_live.get_location_and_time()
    await params.result_callback(
        f"{info['city']} ({info['lat']}, {info['lon']}) — {info['local_time']} on {info['local_date']}."
    )


async def get_weather_handler(params: FunctionCallParams) -> None:
    GetWeatherArgs(**params.arguments)
    w = await board_live.get_weather()
    await params.result_callback(
        f"{w['temp_c']}°C, {w['condition']}. High {w['hi_c']}°, low {w['lo_c']}°, "
        f"wind {w['wind_kmh']} km/h."
    )


def _make_search_web_handler(search_provider: SearchProvider):
    async def handler(params: FunctionCallParams) -> None:
        args = SearchWebArgs(**params.arguments)
        logger.info(f'[web] {agent_state.active} searching: "{args.query}"')
        try:
            results = await search_provider.search(args.query, 5)
        except SearchError as exc:
            logger.warning(f"[web] search failed: {exc}")
            await params.result_callback(str(exc))
            return
        logger.info(f"[web] got {len(results)} results")
        if not results:
            await params.result_callback("No results.")
            return
        lines = [f"- {r.title} ({r.url}): {r.snippet}" for r in results]
        await params.result_callback(as_untrusted(f"search: {args.query}", "\n".join(lines)))
    return handler


async def read_webpage_handler(params: FunctionCallParams) -> None:
    args = ReadWebpageArgs(**params.arguments)
    logger.info(f"[web] {agent_state.active} reading: {args.url}")
    try:
        page = await fetch.read_url(args.url)
    except FetchBlocked as exc:
        logger.warning(f"[web] blocked: {exc}")
        await params.result_callback(str(exc))
        return
    except Exception as exc:
        logger.warning(f"[web] couldn't read {args.url}: {exc}")
        await params.result_callback(f"Couldn't read {args.url}: {exc}")
        return
    logger.info(f'[web] read "{page.title}" ({len(page.text)} chars)')
    text = page.text[:_HOPE_PAGE_CHARS] or "(no readable text)"
    await params.result_callback(as_untrusted(page.url, f"Title: {page.title}\n\n{text}"))


def _make_start_deep_research_handler(research: DeepResearch):
    async def handler(params: FunctionCallParams) -> None:
        args = StartDeepResearchArgs(**params.arguments)
        if research.busy:
            await params.result_callback(
                "A research run is already going — I'll report back when it's done."
            )
            return
        await params.result_callback(
            "Research started. Researchers are being spawned.",
            properties=FunctionCallResultProperties(is_final=False),
        )
        asyncio.create_task(research.run(args.question, params.result_callback))
    return handler


def _make_research_status_handler(orchestrator: "VoiceOrchestrator", research: DeepResearch, manager: SubAgentManager):
    async def handler(params: FunctionCallParams) -> None:
        ResearchStatusArgs(**params.arguments)
        blackboard = orchestrator.bundle.blackboard
        if research.current_run_id:
            run = await asyncio.to_thread(blackboard.get_run, research.current_run_id)
        else:
            runs = await asyncio.to_thread(blackboard.list_runs, 1)
            run = runs[0] if runs else None
        if run is None:
            await params.result_callback("No research has been run yet.")
            return
        sources = await asyncio.to_thread(blackboard.list_sources, run.run_id)
        lines = [f"Research on '{run.question}' is {run.status}, {len(sources)} pages read so far."]
        lines += [
            f"- {live.spoken_name}: {live.status} — {live.spec.objective}"
            for live in manager.live()
        ]
        if run.report_path:
            lines.append(f"Report: {run.report_path}")
        await params.result_callback("\n".join(lines))
    return handler


def _make_list_subagents_handler(manager: SubAgentManager):
    async def handler(params: FunctionCallParams) -> None:
        ListSubagentsArgs(**params.arguments)
        live = manager.live()
        if not live:
            await params.result_callback("No sub-agents right now.")
            return
        lines = [
            f"- {agent.spoken_name} ({agent.spec.template}, {agent.status}): {agent.spec.objective}"
            for agent in live
        ]
        await params.result_callback("\n".join(lines))
    return handler


def _make_retire_subagent_handler(orchestrator: "VoiceOrchestrator", manager: SubAgentManager):
    async def handler(params: FunctionCallParams) -> None:
        args = RetireSubagentArgs(**params.arguments)
        live = manager.find(args.name)
        if live is None:
            await params.result_callback(f"There's no sub-agent called {args.name}.")
            return
        if agent_state.active == live.name:
            await orchestrator.switch_to("hope")
        await manager.retire(live.name)
        await params.result_callback(f"{live.spoken_name} has been dismissed.")
    return handler


def _guarded(name: str, handler, manager: SubAgentManager | None):
    """Refuse anything outside SUBAGENT_VOICE_TOOLS while a sub-agent holds the
    shared pipeline. Atlas and HOPE are unaffected."""
    if manager is None or name in SUBAGENT_VOICE_TOOLS:
        return handler

    async def wrapped(params: FunctionCallParams) -> None:
        if manager.is_subagent(agent_state.active):
            await params.result_callback(
                f"{name} isn't available to a researcher — hand back to HOPE for that."
            )
            return
        await handler(params)
    return wrapped


def _logged(name: str, handler):
    """One "[tool]" line when a tool is called and one when it answers —
    the dashboard's Tools card is a filter over exactly these lines."""
    async def wrapped(params: FunctionCallParams) -> None:
        logger.info(f"[tool] {agent_state.active} → {name}({brief_args(params.arguments)})")
        started = time.monotonic()

        async def result_callback(result, *args, **kwargs):
            logger.info(
                f"[tool] {name} answered in {time.monotonic() - started:.1f}s "
                f"({len(str(result))} chars)"
            )
            await params.result_callback(result, *args, **kwargs)

        try:
            await handler(dataclasses.replace(params, result_callback=result_callback))
        except Exception:
            logger.exception(f"[tool] {name} failed")
            raise
    return wrapped


# ── Wiring ────────────────────────────────────────────────────────────────────

def setup(
    orchestrator: "VoiceOrchestrator",
    manager: SubAgentManager | None = None,
    research: DeepResearch | None = None,
    search_provider: SearchProvider | None = None,
) -> None:
    """Register all tools on HOPE's LLM. Called once from hope.py after orchestrator is created.

    The sub-agent and internet tools are only registered when their
    collaborators are passed — their schemas are still in ALL_SCHEMAS, and an
    unregistered call fails visibly rather than silently doing nothing.
    """
    handlers = {
        "delegate_to_atlas": delegate_to_atlas_handler,
        "connect_to_agent": _make_connect_handler(orchestrator),
        "handback_to_hope": _make_handback_handler(orchestrator),
        "recall_memory": _make_recall_memory_handler(orchestrator),
        "recall_semantic": _make_recall_semantic_handler(orchestrator),
        "save_procedure": _make_save_procedure_handler(orchestrator),
        "recall_procedure": _make_recall_procedure_handler(orchestrator),
        "record_procedure_outcome": _make_record_procedure_outcome_handler(orchestrator),
        "check_plans": _make_check_plans_handler(orchestrator),
        "consult_agents": _make_consult_agents_handler(orchestrator),
        "enable_team_mode": enable_team_mode_handler,
        "disable_team_mode": disable_team_mode_handler,
        "post_task": _make_post_task_handler(orchestrator),
        "claim_task": _make_claim_task_handler(orchestrator),
        "update_task_status": _make_update_task_status_handler(orchestrator),
        "get_active_tasks": _make_get_active_tasks_handler(orchestrator),
        "send_signal": _make_send_signal_handler(orchestrator),
        "get_signals": _make_get_signals_handler(orchestrator),
        "add_task": _make_add_task_handler(orchestrator),
        "update_task": _make_update_task_handler(orchestrator),
        "toggle_task": _make_toggle_task_handler(orchestrator),
        "delete_task": _make_delete_task_handler(orchestrator),
        "get_tasks": _make_get_tasks_handler(orchestrator),
        "get_quick_note": _make_get_quick_note_handler(orchestrator),
        "update_quick_note": _make_update_quick_note_handler(orchestrator),
        "get_location_and_time": get_location_and_time_handler,
        "get_weather": get_weather_handler,
        "read_webpage": read_webpage_handler,
    }
    if search_provider is not None:
        handlers["search_web"] = _make_search_web_handler(search_provider)
    if manager is not None:
        handlers["list_subagents"] = _make_list_subagents_handler(manager)
        handlers["retire_subagent"] = _make_retire_subagent_handler(orchestrator, manager)
    if manager is not None and research is not None:
        handlers["start_deep_research"] = _make_start_deep_research_handler(research)
        handlers["research_status"] = _make_research_status_handler(orchestrator, research, manager)

    llm = orchestrator.bundle.llm
    for name, handler in handlers.items():
        llm.register_function(
            name, _logged(name, _guarded(name, handler, manager)), cancel_on_interruption=False
        )
