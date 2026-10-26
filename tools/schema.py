"""Pydantic argument schemas for every tool in tools/registry.py.

Single source of truth for each tool's parameters: FunctionSchema.properties/
required (what HOPE's LLM sees) are derived from these via model_json_schema(),
and handlers parse params.arguments through the same model instead of hand-
indexing a raw dict.
"""

from typing import Literal

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pydantic import BaseModel, Field

BoardListType = Literal["today", "planned", "pending"]


def function_schema(name: str, description: str, args_model: type[BaseModel]) -> FunctionSchema:
    """Build a pipecat FunctionSchema from a pydantic model's JSON schema."""
    json_schema = args_model.model_json_schema()
    return FunctionSchema(
        name=name,
        description=description,
        properties=json_schema.get("properties", {}),
        required=json_schema.get("required", []),
    )


class DelegateToAtlasArgs(BaseModel):
    task: str = Field(description="Natural language description of the filesystem task.")


class ConnectToAtlasArgs(BaseModel):
    pass


class HandbackToHopeArgs(BaseModel):
    pass


class RecallMemoryArgs(BaseModel):
    query: str = Field(description="Natural language description of what to recall.")
    agent_name: str | None = Field(
        default=None,
        description=(
            "Whose history to search: 'hope', 'atlas', or 'all'. "
            "Omit to search your own history."
        ),
    )


class RecallSemanticArgs(BaseModel):
    query: str = Field(description="Natural language description of what to recall.")
    agent_name: str | None = Field(
        default=None,
        description=(
            "Whose private facts to search: 'hope' or 'atlas'. "
            "Omit to search the shared pool everyone can see."
        ),
    )


class SaveProcedureArgs(BaseModel):
    name: str = Field(description="Short name for the procedure, e.g. 'restart audio service'.")
    description: str = Field(description="One-line description of when this procedure applies.")
    steps: list[str] = Field(description="Ordered list of steps that make up the procedure.")


class RecallProcedureArgs(BaseModel):
    query: str = Field(description="Natural language description of the task you're about to do.")
    agent_name: str | None = Field(
        default=None,
        description="Whose procedures to search: 'hope' or 'atlas'. Omit to search your own.",
    )


class RecordProcedureOutcomeArgs(BaseModel):
    name: str = Field(description="Name of the procedure, as returned by recall_procedure.")
    success: bool = Field(description="Whether following the procedure worked this time.")


class CheckPlansArgs(BaseModel):
    agent_name: str | None = Field(
        default=None,
        description="Whose plans to check: 'hope', 'atlas', or 'all'. Omit to check your own.",
    )
    status: str | None = Field(
        default=None,
        description=(
            "Filter by status: 'pending', 'completed', 'abandoned', or 'superseded'. "
            "Omit to see pending plans."
        ),
    )


class ConsultAgentsArgs(BaseModel):
    agent_names: list[str] = Field(description="Names of the agents to consult, e.g. ['atlas'].")
    message: str = Field(description="The question or task to send to each agent.")


class EnableTeamModeArgs(BaseModel):
    pass


class DisableTeamModeArgs(BaseModel):
    pass


class PostTaskArgs(BaseModel):
    description: str = Field(description="Natural language description of the task to post.")


class ClaimTaskArgs(BaseModel):
    task_id: str = Field(description="The task_id returned by post_task or get_active_tasks.")


class UpdateTaskStatusArgs(BaseModel):
    task_id: str = Field(description="The task_id to update.")
    status: str = Field(
        description="New status: 'in_progress', 'completed', or 'failed'."
    )
    detail: str | None = Field(
        default=None,
        description="Optional detail about the outcome, e.g. a result summary or error message.",
    )


class GetActiveTasksArgs(BaseModel):
    agent_name: str | None = Field(
        default=None,
        description="Filter to tasks owned by this agent. Omit to see every active task.",
    )


class SendSignalArgs(BaseModel):
    to_agent: str = Field(description="Name of the agent to send the message to.")
    payload: str = Field(description="The message content.")


class GetSignalsArgs(BaseModel):
    agent_name: str | None = Field(
        default=None,
        description="Whose unread signals to check. Omit to check your own.",
    )


class AddTaskArgs(BaseModel):
    list_type: BoardListType = Field(
        description="Which board list to add to: 'today', 'planned', or 'pending'."
    )
    text: str = Field(description="The task text.")


class UpdateTaskArgs(BaseModel):
    item_id: int = Field(description="The task's id, as returned by add_task or get_tasks.")
    text: str = Field(description="The new text for the task.")


class ToggleTaskArgs(BaseModel):
    item_id: int = Field(description="The task's id, as returned by add_task or get_tasks.")


class DeleteTaskArgs(BaseModel):
    item_id: int = Field(description="The task's id, as returned by add_task or get_tasks.")


class GetTasksArgs(BaseModel):
    list_type: BoardListType = Field(
        description="Which board list to read: 'today', 'planned', or 'pending'."
    )


class GetQuickNoteArgs(BaseModel):
    pass


class UpdateQuickNoteArgs(BaseModel):
    content: str = Field(description="The full new content of the shared quick notes.")


class GetLocationAndTimeArgs(BaseModel):
    pass


class GetWeatherArgs(BaseModel):
    pass
