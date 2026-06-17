"""
Contract tests for Atlas filesystem tools.

Every tool must be async, accept workspace as its first parameter,
and have a matching entry in TOOL_SCHEMAS. This contract applies to
all future sub-agent tools — subclass ToolContractBase for each one.
"""

import inspect
from pathlib import Path

import pytest

import sub_agents.atlas.tools as atlas_tools
from sub_agents.atlas.tools import TOOL_SCHEMAS

ATLAS_TOOL_FUNCTIONS = [
    atlas_tools.read_file,
    atlas_tools.write_file,
    atlas_tools.edit_file,
    atlas_tools.delete_file,
    atlas_tools.list_directory,
    atlas_tools.create_directory,
    atlas_tools.delete_directory,
    atlas_tools.delete_all_in_directory,
]

ATLAS_TOOL_NAMES = {fn.__name__ for fn in ATLAS_TOOL_FUNCTIONS}


# ─── Schema contract ─────────────────────────────────────────────

@pytest.mark.contract
def test_tool_schemas_is_a_list():
    assert isinstance(TOOL_SCHEMAS, list)
    assert len(TOOL_SCHEMAS) > 0


@pytest.mark.contract
def test_every_schema_has_type_function():
    for schema in TOOL_SCHEMAS:
        assert schema.get("type") == "function", (
            f"Schema for {schema} missing 'type': 'function'"
        )


@pytest.mark.contract
def test_every_schema_has_name():
    for schema in TOOL_SCHEMAS:
        name = schema["function"].get("name")
        assert isinstance(name, str) and len(name) > 0


@pytest.mark.contract
def test_every_schema_has_nonempty_description():
    for schema in TOOL_SCHEMAS:
        desc = schema["function"].get("description", "")
        assert len(desc) > 0, f"Tool {schema['function'].get('name')} has empty description"


@pytest.mark.contract
def test_every_schema_has_parameters():
    for schema in TOOL_SCHEMAS:
        params = schema["function"].get("parameters")
        assert isinstance(params, dict), (
            f"Tool {schema['function'].get('name')} missing parameters schema"
        )


@pytest.mark.contract
def test_schema_names_match_function_names():
    schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert schema_names == ATLAS_TOOL_NAMES, (
        f"Schema names {schema_names} don't match function names {ATLAS_TOOL_NAMES}"
    )


# ─── Function contract ───────────────────────────────────────────

@pytest.mark.contract
@pytest.mark.parametrize("fn", ATLAS_TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_tool_is_async(fn):
    assert inspect.iscoroutinefunction(fn), f"{fn.__name__} must be async"


@pytest.mark.contract
@pytest.mark.parametrize("fn", ATLAS_TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_tool_first_param_is_workspace(fn):
    params = list(inspect.signature(fn).parameters.keys())
    assert params[0] == "workspace", (
        f"{fn.__name__}'s first parameter must be 'workspace: Path'"
    )


# ─── Security contract ───────────────────────────────────────────

@pytest.mark.contract
def test_safe_path_rejects_parent_traversal():
    """Path traversal outside the workspace must raise PermissionError."""
    from sub_agents.atlas.tools import _safe_path

    workspace = Path("/tmp/test-workspace")
    with pytest.raises(PermissionError):
        _safe_path(workspace, "../../etc/passwd")


@pytest.mark.contract
def test_safe_path_rejects_absolute_escape():
    """Absolute paths that escape the workspace must raise PermissionError."""
    from sub_agents.atlas.tools import _safe_path

    workspace = Path("/tmp/test-workspace")
    with pytest.raises(PermissionError):
        _safe_path(workspace, "/etc/passwd")


@pytest.mark.contract
def test_safe_path_allows_valid_relative_path():
    """A normal relative path inside the workspace must resolve without error."""
    from sub_agents.atlas.tools import _safe_path

    workspace = Path("/tmp/test-workspace")
    result = _safe_path(workspace, "subdir/file.txt")
    assert str(result).startswith(str(workspace.resolve()))
