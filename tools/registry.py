import asyncio

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from atlas.agent import Atlas

atlas = Atlas()

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


async def delegate_to_atlas_handler(params: FunctionCallParams) -> None:
    task = params.arguments["task"]
    asyncio.create_task(atlas.run(task, params.result_callback))
