"""Unit tests for core/agents/spec.py — the template tool allowlist is enforced in code."""

import pytest
from pydantic import ValidationError

from core.agents.spec import SubAgentSpec


def _spec(**overrides):
    fields = dict(
        template="researcher",
        objective="Find X",
        output_format="Markdown",
        boundaries="Not Y",
        tools=["web_search", "read_url"],
        max_tool_calls=5,
    )
    fields.update(overrides)
    return SubAgentSpec(**fields)


@pytest.mark.unit
def test_researcher_spec_with_read_only_tools_is_valid():
    assert _spec().tools == ["web_search", "read_url"]


@pytest.mark.unit
@pytest.mark.parametrize("tool", ["write_file", "delete_directory", "update_quick_note", "delegate_to_atlas"])
def test_researcher_spec_rejects_any_tool_beyond_read_only(tool):
    with pytest.raises(ValidationError):
        _spec(tools=["web_search", tool])


@pytest.mark.unit
def test_unknown_template_is_rejected():
    with pytest.raises(ValidationError):
        _spec(template="hacker", tools=[])


@pytest.mark.unit
def test_tool_budget_must_be_positive():
    with pytest.raises(ValidationError):
        _spec(max_tool_calls=0)
