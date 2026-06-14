import asyncio
from typing import TYPE_CHECKING

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import FunctionCallResultProperties, TTSUpdateSettingsFrame
from pipecat.services.cartesia.tts import CartesiaTTSSettings
from pipecat.services.llm_service import FunctionCallParams

from atlas.agent import Atlas
from atlas.voice_prompt import ATLAS_VOICE_PROMPT
from core.agent_state import agent_state
from core.prompt import SYSTEM_PROMPT
from settings import settings

from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.openai.llm import OpenAILLMService

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

ALL_SCHEMAS = [delegate_to_atlas_schema, connect_to_atlas_schema, handback_to_hope_schema]

# ── Handlers ──────────────────────────────────────────────────────────────────

async def delegate_to_atlas_handler(params: FunctionCallParams) -> None:
    task = params.arguments["task"]
    await params.result_callback(
        "Task received. Atlas is on it.",
        properties=FunctionCallResultProperties(is_final=False),
    )
    asyncio.create_task(atlas.run(task, params.result_callback))


def _make_connect_handler(context: "LLMContext"):
    async def handler(params: FunctionCallParams) -> None:
        msgs = list(context.messages)
        msgs[0] = {"role": "system", "content": ATLAS_VOICE_PROMPT}
        context.set_messages(msgs)
        agent_state.active = "atlas"
        await params.llm.push_frame(
            TTSUpdateSettingsFrame(delta=CartesiaTTSSettings(voice=settings.atlas_voice_id))
        )
        await params.result_callback("Connecting you to Atlas now.")
    return handler


def _make_handback_handler(context: "LLMContext"):
    async def handler(params: FunctionCallParams) -> None:
        msgs = list(context.messages)
        msgs[0] = {"role": "system", "content": SYSTEM_PROMPT}
        context.set_messages(msgs)
        agent_state.active = "hope"
        await params.llm.push_frame(
            TTSUpdateSettingsFrame(delta=CartesiaTTSSettings(voice=settings.cartesia_voice_id))
        )
        await params.result_callback("HOPE is back.")
    return handler


# ── Wiring ────────────────────────────────────────────────────────────────────

def setup(llm: "OpenAILLMService", context: "LLMContext") -> None:
    """Register all tools on HOPE's LLM. Called once from hope.py after services are created."""
    llm.register_function(
        "delegate_to_atlas",
        delegate_to_atlas_handler,
        cancel_on_interruption=False,
    )
    llm.register_function(
        "connect_to_atlas",
        _make_connect_handler(context),
        cancel_on_interruption=False,
    )
    llm.register_function(
        "handback_to_hope",
        _make_handback_handler(context),
        cancel_on_interruption=False,
    )
