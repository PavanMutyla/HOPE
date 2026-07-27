import asyncio


from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import FunctionCallResultProperties
from pipecat.services.llm_service import FunctionCallParams

from sub_agents.atlas.agent import Atlas


from core.voice.agent_state import agent_state
from core.voice.orchestrator import VoiceOrchestrator

atlas = Atlas()

# ── Tool schemas exposed to HOPE's LLM ────────────────────────────────────────

delegate_to_atlas_schema = FunctionSchema(
    name="delegate_to_atlas",
    description=(
        "Delegate a filesystem task to Atlas. Use whenever Pavan asks to create, "
        "read, edit, or delete files or folders. Pass a clear natural-language "
        "description of the task."
    ),
    properties={
        "task": {
            "type": "string",
            "description": "Natural language description of the filesystem task.",
        }
    },
    required=["task"],
)

connect_to_atlas_schema = FunctionSchema(
    name="connect_to_atlas",
    description=(
        "Switch the active voice to Atlas so Pavan can speak directly with Atlas. "
        "Use when Pavan says 'connect me to Atlas', 'let me talk to Atlas', or similar."
    ),
    properties={},
    required=[],
)

handback_to_hope_schema = FunctionSchema(
    name="handback_to_hope",
    description=(
        "Hand the active voice back to HOPE. "
        "Use when Pavan says 'HOPE take over', 'back to HOPE', 'thanks Atlas', or similar."
    ),
    properties={},
    required=[],
)

recall_memory_schema = FunctionSchema(
    name="recall_memory",
    description=(
        "Search past conversation history (episodic memory) for relevant context "
        "from earlier sessions. Defaults to searching your own history; pass "
        "agent_name to search a specific agent's history instead, or 'all' to "
        "search everyone's history."
    ),
    properties={
        "query": {
            "type": "string",
            "description": "Natural language description of what to recall.",
        },
        "agent_name": {
            "type": "string",
            "description": (
                "Whose history to search: 'hope', 'atlas', or 'all'. "
                "Omit to search your own history."
            ),
        },
    },
    required=["query"],
)

ALL_SCHEMAS = [
    delegate_to_atlas_schema,
    connect_to_atlas_schema,
    handback_to_hope_schema,
    recall_memory_schema,
]

# ── Handlers ──────────────────────────────────────────────────────────────────

async def delegate_to_atlas_handler(params: FunctionCallParams) -> None:
    task = params.arguments["task"]
    await params.result_callback(
        "Task received. Atlas is on it.",
        properties=FunctionCallResultProperties(is_final=False),
    )
    asyncio.create_task(atlas.run(task, params.result_callback))


def _make_connect_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        await orchestrator.switch_to("atlas")
        await params.result_callback("Connecting you to Atlas now.")
    return handler


def _make_handback_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        await orchestrator.switch_to("hope")
        await params.result_callback("HOPE is back.")
    return handler


def _make_recall_memory_handler(orchestrator: "VoiceOrchestrator"):
    async def handler(params: FunctionCallParams) -> None:
        query = params.arguments["query"]
        agent_name = params.arguments.get("agent_name") or agent_state.active
        agent = None if agent_name == "all" else agent_name

        episodes = await asyncio.to_thread(
            orchestrator.bundle.episodic_memory.query, query, 5, agent
        )

        if not episodes:
            await params.result_callback("No matching memories found.")
            return

        summary_text = "\n".join(f"- ({episode.agent}) {episode.summary}" for episode in episodes)
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
