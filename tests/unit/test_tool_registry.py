"""Unit tests for tools/registry.py — schema declarations and wiring contracts."""

import pytest
from tools.registry import (
    ALL_SCHEMAS,
    check_plans_schema,
    connect_to_atlas_schema,
    delegate_to_atlas_schema,
    handback_to_hope_schema,
    recall_memory_schema,
    recall_procedure_schema,
    recall_semantic_schema,
    record_procedure_outcome_schema,
    save_procedure_schema,
)


@pytest.mark.unit
def test_all_schemas_contains_exactly_nine_tools():
    assert len(ALL_SCHEMAS) == 9


@pytest.mark.unit
def test_all_schemas_names_are_correct():
    names = {s.name for s in ALL_SCHEMAS}
    assert names == {
        "delegate_to_atlas",
        "connect_to_atlas",
        "handback_to_hope",
        "recall_memory",
        "recall_semantic",
        "save_procedure",
        "recall_procedure",
        "record_procedure_outcome",
        "check_plans",
    }


@pytest.mark.unit
def test_all_schema_names_are_unique():
    names = [s.name for s in ALL_SCHEMAS]
    assert len(names) == len(set(names))


@pytest.mark.unit
def test_all_schemas_have_nonempty_descriptions():
    for schema in ALL_SCHEMAS:
        assert isinstance(schema.description, str)
        assert len(schema.description) > 0, f"{schema.name} has empty description"


@pytest.mark.unit
def test_delegate_schema_has_task_property():
    assert "task" in delegate_to_atlas_schema.properties


@pytest.mark.unit
def test_delegate_schema_requires_task():
    assert "task" in delegate_to_atlas_schema.required


@pytest.mark.unit
def test_delegate_schema_task_property_is_string_type():
    assert delegate_to_atlas_schema.properties["task"]["type"] == "string"


@pytest.mark.unit
def test_connect_schema_has_no_required_parameters():
    assert connect_to_atlas_schema.required == []


@pytest.mark.unit
def test_handback_schema_has_no_required_parameters():
    assert handback_to_hope_schema.required == []


@pytest.mark.unit
def test_delegate_schema_description_mentions_filesystem():
    lower = delegate_to_atlas_schema.description.lower()
    assert "file" in lower or "filesystem" in lower or "folder" in lower


@pytest.mark.unit
def test_connect_schema_description_mentions_atlas():
    assert "Atlas" in connect_to_atlas_schema.description


@pytest.mark.unit
def test_handback_schema_description_mentions_hope():
    assert "HOPE" in handback_to_hope_schema.description


@pytest.mark.unit
def test_recall_memory_schema_has_query_property():
    assert "query" in recall_memory_schema.properties
    assert recall_memory_schema.properties["query"]["type"] == "string"


@pytest.mark.unit
def test_recall_memory_schema_requires_only_query():
    assert recall_memory_schema.required == ["query"]


@pytest.mark.unit
def test_recall_memory_schema_has_optional_agent_name_property():
    assert "agent_name" in recall_memory_schema.properties
    assert "agent_name" not in recall_memory_schema.required


@pytest.mark.unit
def test_recall_semantic_schema_has_query_property():
    assert "query" in recall_semantic_schema.properties
    assert recall_semantic_schema.properties["query"]["type"] == "string"


@pytest.mark.unit
def test_recall_semantic_schema_requires_only_query():
    assert recall_semantic_schema.required == ["query"]


@pytest.mark.unit
def test_recall_semantic_schema_has_optional_agent_name_property():
    assert "agent_name" in recall_semantic_schema.properties
    assert "agent_name" not in recall_semantic_schema.required


@pytest.mark.unit
def test_save_procedure_schema_requires_name_description_and_steps():
    assert set(save_procedure_schema.required) == {"name", "description", "steps"}


@pytest.mark.unit
def test_save_procedure_schema_steps_is_string_array():
    steps_property = save_procedure_schema.properties["steps"]
    assert steps_property["type"] == "array"
    assert steps_property["items"]["type"] == "string"


@pytest.mark.unit
def test_recall_procedure_schema_requires_only_query():
    assert recall_procedure_schema.required == ["query"]


@pytest.mark.unit
def test_recall_procedure_schema_has_optional_agent_name_property():
    assert "agent_name" in recall_procedure_schema.properties
    assert "agent_name" not in recall_procedure_schema.required


@pytest.mark.unit
def test_record_procedure_outcome_schema_requires_name_and_success():
    assert set(record_procedure_outcome_schema.required) == {"name", "success"}


@pytest.mark.unit
def test_record_procedure_outcome_schema_success_is_boolean():
    assert record_procedure_outcome_schema.properties["success"]["type"] == "boolean"


@pytest.mark.unit
def test_check_plans_schema_has_no_required_parameters():
    assert check_plans_schema.required == []


@pytest.mark.unit
def test_check_plans_schema_has_agent_name_and_status_properties():
    assert "agent_name" in check_plans_schema.properties
    assert "status" in check_plans_schema.properties
