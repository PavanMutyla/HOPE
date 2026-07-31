"""Unit tests for the pydantic coordination-pool models — strictness and
immutability, since these are the typed contract on top of the SQLite schema
in memory/coordination/migrations/0001_init.sql."""

import pydantic
import pytest

from memory.coordination.schema import Signal, Task


@pytest.mark.unit
def test_task_requires_all_non_defaulted_fields():
    task = Task(
        task_id="task_1", description="do the thing", status="open",
        created_by="hope", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    assert task.task_id == "task_1"
    assert task.owner_agent is None
    assert task.payload is None


@pytest.mark.unit
def test_task_is_frozen():
    task = Task(
        task_id="task_1", description="do the thing", status="open",
        created_by="hope", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(pydantic.ValidationError):
        task.status = "claimed"


@pytest.mark.unit
def test_task_strict_mode_rejects_type_coercion():
    with pytest.raises(pydantic.ValidationError):
        Task(
            task_id="task_1", description="do the thing", status="open",
            created_by="hope", created_at="2026-01-01T00:00:00Z", updated_at=123,
        )


@pytest.mark.unit
def test_signal_requires_all_non_defaulted_fields():
    signal = Signal(
        id="sig_1", from_agent="hope", to_agent="atlas", payload="hello",
        created_at="2026-01-01T00:00:00Z",
    )
    assert signal.id == "sig_1"
    assert signal.read_at is None


@pytest.mark.unit
def test_signal_is_frozen():
    signal = Signal(
        id="sig_1", from_agent="hope", to_agent="atlas", payload="hello",
        created_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(pydantic.ValidationError):
        signal.read_at = "2026-01-02T00:00:00Z"


@pytest.mark.unit
def test_signal_strict_mode_rejects_type_coercion():
    with pytest.raises(pydantic.ValidationError):
        Signal(
            id="sig_1", from_agent="hope", to_agent="atlas", payload="hello",
            created_at=123,
        )
