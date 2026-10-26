"""Unit tests for tools/registry.py — schema declarations and wiring contracts."""

import pytest
from tools.registry import (
    ALL_SCHEMAS,
    check_plans_schema,
    claim_task_schema,
    connect_to_atlas_schema,
    consult_agents_schema,
    delegate_to_atlas_schema,
    disable_team_mode_schema,
    enable_team_mode_schema,
    get_active_tasks_schema,
    get_signals_schema,
    handback_to_hope_schema,
    post_task_schema,
    recall_memory_schema,
    recall_procedure_schema,
    recall_semantic_schema,
    record_procedure_outcome_schema,
    save_procedure_schema,
    send_signal_schema,
    update_task_status_schema,
)


@pytest.mark.unit
def test_all_schemas_contains_exactly_twenty_seven_tools():
    assert len(ALL_SCHEMAS) == 27


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
        "consult_agents",
        "enable_team_mode",
        "disable_team_mode",
        "post_task",
        "claim_task",
        "update_task_status",
        "get_active_tasks",
        "send_signal",
        "get_signals",
        "add_task",
        "update_task",
        "toggle_task",
        "delete_task",
        "get_tasks",
        "get_quick_note",
        "update_quick_note",
        "get_location_and_time",
        "get_weather",
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


@pytest.mark.unit
def test_consult_agents_schema_requires_agent_names_and_message():
    assert set(consult_agents_schema.required) == {"agent_names", "message"}


@pytest.mark.unit
def test_consult_agents_schema_agent_names_is_string_array():
    agent_names_property = consult_agents_schema.properties["agent_names"]
    assert agent_names_property["type"] == "array"
    assert agent_names_property["items"]["type"] == "string"


@pytest.mark.unit
def test_consult_agents_schema_message_is_string_type():
    assert consult_agents_schema.properties["message"]["type"] == "string"


@pytest.mark.unit
def test_enable_team_mode_schema_has_no_required_parameters():
    assert enable_team_mode_schema.required == []


@pytest.mark.unit
def test_disable_team_mode_schema_has_no_required_parameters():
    assert disable_team_mode_schema.required == []


@pytest.mark.unit
def test_enable_team_mode_schema_description_mentions_team():
    assert "team" in enable_team_mode_schema.description.lower()


@pytest.mark.unit
def test_disable_team_mode_schema_description_mentions_team():
    assert "team" in disable_team_mode_schema.description.lower()


@pytest.mark.unit
def test_post_task_schema_requires_only_description():
    assert post_task_schema.required == ["description"]


@pytest.mark.unit
def test_post_task_schema_description_property_is_string_type():
    assert post_task_schema.properties["description"]["type"] == "string"


@pytest.mark.unit
def test_claim_task_schema_requires_only_task_id():
    assert claim_task_schema.required == ["task_id"]


@pytest.mark.unit
def test_update_task_status_schema_requires_task_id_and_status():
    assert set(update_task_status_schema.required) == {"task_id", "status"}


@pytest.mark.unit
def test_update_task_status_schema_has_optional_detail_property():
    assert "detail" in update_task_status_schema.properties
    assert "detail" not in update_task_status_schema.required


@pytest.mark.unit
def test_get_active_tasks_schema_has_no_required_parameters():
    assert get_active_tasks_schema.required == []


@pytest.mark.unit
def test_get_active_tasks_schema_has_agent_name_property():
    assert "agent_name" in get_active_tasks_schema.properties


@pytest.mark.unit
def test_send_signal_schema_requires_to_agent_and_payload():
    assert set(send_signal_schema.required) == {"to_agent", "payload"}


@pytest.mark.unit
def test_get_signals_schema_has_no_required_parameters():
    assert get_signals_schema.required == []


@pytest.mark.unit
def test_get_signals_schema_has_optional_agent_name_property():
    assert "agent_name" in get_signals_schema.properties
    assert "agent_name" not in get_signals_schema.required
