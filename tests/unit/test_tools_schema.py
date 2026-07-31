"""Unit tests for tools/schema.py — pydantic argument models + function_schema() helper."""

import pytest
from pydantic import ValidationError

from tools.schema import (
    CheckPlansArgs,
    ConnectToAtlasArgs,
    ConsultAgentsArgs,
    DelegateToAtlasArgs,
    RecallMemoryArgs,
    SaveProcedureArgs,
    function_schema,
)


@pytest.mark.unit
def test_function_schema_maps_required_field_properties():
    schema = function_schema("delegate_to_atlas", "desc", DelegateToAtlasArgs)
    assert schema.name == "delegate_to_atlas"
    assert schema.description == "desc"
    assert schema.properties["task"]["type"] == "string"
    assert schema.required == ["task"]


@pytest.mark.unit
def test_function_schema_empty_model_has_no_required_fields():
    schema = function_schema("connect_to_atlas", "desc", ConnectToAtlasArgs)
    assert schema.properties == {}
    assert schema.required == []


@pytest.mark.unit
def test_function_schema_omits_optional_fields_from_required():
    schema = function_schema("recall_memory", "desc", RecallMemoryArgs)
    assert schema.required == ["query"]
    assert "agent_name" in schema.properties


@pytest.mark.unit
def test_function_schema_array_field_has_string_items():
    schema = function_schema("save_procedure", "desc", SaveProcedureArgs)
    assert schema.properties["steps"]["type"] == "array"
    assert schema.properties["steps"]["items"]["type"] == "string"


# ─── Model validation ──────────────────────────────────────────────

@pytest.mark.unit
def test_delegate_to_atlas_args_requires_task():
    with pytest.raises(ValidationError):
        DelegateToAtlasArgs()


@pytest.mark.unit
def test_recall_memory_args_agent_name_defaults_to_none():
    args = RecallMemoryArgs(query="what did we discuss")
    assert args.agent_name is None


@pytest.mark.unit
def test_check_plans_args_all_fields_optional():
    args = CheckPlansArgs()
    assert args.agent_name is None
    assert args.status is None


@pytest.mark.unit
def test_consult_agents_args_requires_agent_names_and_message():
    args = ConsultAgentsArgs(agent_names=["atlas"], message="status?")
    assert args.agent_names == ["atlas"]
    assert args.message == "status?"


@pytest.mark.unit
def test_consult_agents_args_rejects_missing_message():
    with pytest.raises(ValidationError):
        ConsultAgentsArgs(agent_names=["atlas"])
