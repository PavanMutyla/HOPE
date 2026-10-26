"""
Contract tests for Atlas's board-tool adapters (sub_agents/atlas/board_tools.py).

Same contract as tests/contracts/test_tool_contract.py's Atlas filesystem
tools: every tool must be async, accept workspace as its first parameter
(even though board tools ignore it), and have a matching entry in
BOARD_TOOL_SCHEMAS.
"""

import inspect

import pytest

import sub_agents.atlas.board_tools as board_tools
from sub_agents.atlas.board_tools import BOARD_TOOL_DISPATCH, BOARD_TOOL_SCHEMAS

BOARD_TOOL_FUNCTIONS = [
    board_tools.add_task,
    board_tools.update_task,
    board_tools.toggle_task,
    board_tools.delete_task,
    board_tools.get_tasks,
    board_tools.get_quick_note,
    board_tools.update_quick_note,
    board_tools.get_location_and_time,
    board_tools.get_weather,
]

BOARD_TOOL_NAMES = {fn.__name__ for fn in BOARD_TOOL_FUNCTIONS}


# ─── Schema contract ─────────────────────────────────────────────

@pytest.mark.contract
def test_board_tool_schemas_is_a_list():
    assert isinstance(BOARD_TOOL_SCHEMAS, list)
    assert len(BOARD_TOOL_SCHEMAS) == 9


@pytest.mark.contract
def test_every_board_schema_has_type_function():
    for schema in BOARD_TOOL_SCHEMAS:
        assert schema.get("type") == "function"


@pytest.mark.contract
def test_every_board_schema_has_nonempty_description():
    for schema in BOARD_TOOL_SCHEMAS:
        desc = schema["function"].get("description", "")
        assert len(desc) > 0, f"Tool {schema['function'].get('name')} has empty description"


@pytest.mark.contract
def test_board_schema_names_match_function_names():
    schema_names = {s["function"]["name"] for s in BOARD_TOOL_SCHEMAS}
    assert schema_names == BOARD_TOOL_NAMES


@pytest.mark.contract
def test_board_dispatch_matches_schema_names():
    assert set(BOARD_TOOL_DISPATCH.keys()) == BOARD_TOOL_NAMES


# ─── Function contract ───────────────────────────────────────────

@pytest.mark.contract
@pytest.mark.parametrize("fn", BOARD_TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_board_tool_is_async(fn):
    assert inspect.iscoroutinefunction(fn), f"{fn.__name__} must be async"


@pytest.mark.contract
@pytest.mark.parametrize("fn", BOARD_TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_board_tool_first_param_is_workspace(fn):
    params = list(inspect.signature(fn).parameters.keys())
    assert params[0] == "workspace", f"{fn.__name__}'s first parameter must be 'workspace'"


@pytest.mark.contract
def test_board_tools_never_expose_agent_param_to_the_model():
    """Attribution is injected by the adapter (hardcoded 'atlas'), never
    trusted from the model — no schema should declare an 'agent' property."""
    for schema in BOARD_TOOL_SCHEMAS:
        assert "agent" not in schema["function"]["parameters"].get("properties", {})
