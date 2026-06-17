"""Unit tests for tools/registry.py — schema declarations and wiring contracts."""

import pytest
from tools.registry import (
    ALL_SCHEMAS,
    connect_to_atlas_schema,
    delegate_to_atlas_schema,
    handback_to_hope_schema,
)


@pytest.mark.unit
def test_all_schemas_contains_exactly_three_tools():
    assert len(ALL_SCHEMAS) == 3


@pytest.mark.unit
def test_all_schemas_names_are_correct():
    names = {s.name for s in ALL_SCHEMAS}
    assert names == {"delegate_to_atlas", "connect_to_atlas", "handback_to_hope"}


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
