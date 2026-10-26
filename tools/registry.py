import asyncio


from pipecat.frames.frames import FunctionCallResultProperties
from pipecat.services.llm_service import FunctionCallParams

from sub_agents.atlas.agent import Atlas


from core.voice.agent_state import agent_state
from core.voice.orchestrator import VoiceOrchestrator
from core.voice.team_state import team_state
from memory.board import live as board_live
from tools.schema import (
    AddTaskArgs,
    CheckPlansArgs,
    ClaimTaskArgs,
    ConnectToAtlasArgs,
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
    PostTaskArgs,
    RecallMemoryArgs,
    RecallProcedureArgs,
    RecallSemanticArgs,
    RecordProcedureOutcomeArgs,
    SaveProcedureArgs,
    SendSignalArgs,
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
        "Delegate a filesystem task to Atlas. Use whenever Pavan asks to create, "
        "read, edit, or delete files or folders. Pass a clear natural-language "
        "description of the task."
    ),
    DelegateToAtlasArgs,
)

connect_to_atlas_schema = function_schema(
    "connect_to_atlas",
    (
        "Switch the active voice to Atlas so Pavan can speak directly with Atlas. "
        "Use when Pavan says 'connect me to Atlas', 'let me talk to Atlas', or similar."
    ),
    ConnectToAtlasArgs,
)

handback_to_hope_schema = function_schema(
    "handback_to_hope",
    (
        "Hand the active voice back to HOPE. "
        "Use when Pavan says 'HOPE take over', 'back to HOPE', 'thanks Atlas', or similar."
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
        "this when Pavan explicitly confirms he wants something remembered as a "
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
        "you need input from more than one agent to answer Pavan."
    ),
    ConsultAgentsArgs,
)

enable_team_mode_schema = function_schema(
    "enable_team_mode",
    (
        "Turn on team mode so other agents can listen in on this conversation and "
        "speak up on their own, in their own voice, when they have something "
        "relevant to add. Use when Pavan says something like 'bring the team in' "
        "or 'let everyone listen in'."
    ),
    EnableTeamModeArgs,
)

disable_team_mode_schema = function_schema(
    "disable_team_mode",
    (
        "Turn off team mode so it's back to just you and Pavan. Use when Pavan "
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
        "visible to Pavan and every agent, not just you."
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
    "Get Pavan's home location and the current local date/time.",
    GetLocationAndTimeArgs,
)

get_weather_schema = function_schema(
    "get_weather",
    "Get the current weather and today's forecast at Pavan's home location.",
    GetWeatherArgs,
)

ALL_SCHEMAS = [
    delegate_to_atlas_schema,
    connect_to_atlas_schema,
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
]

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
        ConnectToAtlasArgs(**params.arguments)
        await orchestrator.switch_to("atlas")
        await params.result_callback("Connecting you to Atlas now.")
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
        agent_name = args.agent_name or agent_state.active
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


# ── Wiring ────────────────────────────────────────────────────────────────────

def setup(orchestrator: "VoiceOrchestrator") -> None:
    """Register all tools on HOPE's LLM. Called once from hope.py after orchestrator is created."""
    llm = orchestrator.bundle.llm
    llm.register_function(
        "delegate_to_atlas",
        delegate_to_atlas_handler,
        cancel_on_interruption=False,
    )
    llm.register_function(
        "connect_to_atlas",
        _make_connect_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "handback_to_hope",
        _make_handback_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "recall_memory",
        _make_recall_memory_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "recall_semantic",
        _make_recall_semantic_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "save_procedure",
        _make_save_procedure_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "recall_procedure",
        _make_recall_procedure_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "record_procedure_outcome",
        _make_record_procedure_outcome_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "check_plans",
        _make_check_plans_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "consult_agents",
        _make_consult_agents_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "enable_team_mode",
        enable_team_mode_handler,
        cancel_on_interruption=False,
    )
    llm.register_function(
        "disable_team_mode",
        disable_team_mode_handler,
        cancel_on_interruption=False,
    )
    llm.register_function(
        "post_task",
        _make_post_task_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "claim_task",
        _make_claim_task_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "update_task_status",
        _make_update_task_status_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "get_active_tasks",
        _make_get_active_tasks_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "send_signal",
        _make_send_signal_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "get_signals",
        _make_get_signals_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "add_task",
        _make_add_task_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "update_task",
        _make_update_task_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "toggle_task",
        _make_toggle_task_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "delete_task",
        _make_delete_task_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "get_tasks",
        _make_get_tasks_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "get_quick_note",
        _make_get_quick_note_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "update_quick_note",
        _make_update_quick_note_handler(orchestrator),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "get_location_and_time",
        get_location_and_time_handler,
        cancel_on_interruption=False,
    )
    llm.register_function(
        "get_weather",
        get_weather_handler,
        cancel_on_interruption=False,
    )
