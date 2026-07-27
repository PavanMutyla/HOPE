"""Unit tests for sub_agents.atlas.agent._normalize_message — converts OpenAI
SDK message objects (and plain dicts) into the dict shape episodic.create_episode()
reads via .get()."""

from unittest.mock import MagicMock

import pytest

from sub_agents.atlas.agent import _normalize_message


@pytest.mark.unit
def test_normalize_message_passes_through_plain_dict():
    message = {"role": "user", "content": "list the files"}

    assert _normalize_message(message) is message


@pytest.mark.unit
def test_normalize_message_converts_sdk_object_without_tool_calls():
    sdk_message = MagicMock()
    sdk_message.role = "assistant"
    sdk_message.content = "Done."
    sdk_message.tool_calls = None

    result = _normalize_message(sdk_message)

    assert result == {"role": "assistant", "content": "Done.", "tool_calls": None}


@pytest.mark.unit
def test_normalize_message_converts_sdk_object_with_tool_calls():
    tool_call = MagicMock()
    tool_call.model_dump.return_value = {"id": "call_1", "type": "function"}
    sdk_message = MagicMock()
    sdk_message.role = "assistant"
    sdk_message.content = None
    sdk_message.tool_calls = [tool_call]

    result = _normalize_message(sdk_message)

    assert result == {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "call_1", "type": "function"}],
    }
