import asyncio


from pipecat.frames.frames import FunctionCallResultProperties
from pipecat.services.llm_service import FunctionCallParams

from sub_agents.atlas.agent import Atlas


from core.voice.agent_state import agent_state
from core.voice.orchestrator import VoiceOrchestrator
from tools.schema import (
    CheckPlansArgs,
    ConnectToAtlasArgs,
    ConsultAgentsArgs,
    DelegateToAtlasArgs,
    HandbackToHopeArgs,
    RecallMemoryArgs,
    RecallProcedureArgs,
    RecallSemanticArgs,
    RecordProcedureOutcomeArgs,
    SaveProcedureArgs,
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
