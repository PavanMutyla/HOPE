"""Unit tests for memory/procedural_memory/store.py — ProceduralMemory reads
and writes procedures as plain markdown files with YAML frontmatter, no
database and no embedding step. Uses pytest's tmp_path for full isolation
from the real procedures/ directory."""

import pytest

from memory.procedural_memory.store import ProceduralMemory

pytestmark = pytest.mark.unit


@pytest.fixture
def pm(tmp_path):
    return ProceduralMemory(base_dir=tmp_path)


def test_save_returns_an_active_procedure_with_defaults(pm):
    procedure = pm.save("atlas", "Restart Audio", "when audio hangs", ["check device", "kill process"])

    assert procedure.name == "restart-audio"
    assert procedure.agent == "atlas"
    assert procedure.status == "active"
    assert procedure.steps == ["check device", "kill process"]
    assert procedure.success_count == 0
    assert procedure.failure_count == 0
    assert procedure.last_used_at is None
    assert procedure.source == "manual"


def test_save_slugifies_the_name_for_the_filename(pm, tmp_path):
    pm.save("atlas", "Restart Audio Service!!", "desc", ["a"])

    assert (tmp_path / "atlas" / "restart-audio-service.md").exists()


def test_save_refuses_to_overwrite_an_existing_active_procedure(pm):
    pm.save("atlas", "restart-audio", "desc", ["a"])

    with pytest.raises(ValueError, match="already exists and is active"):
        pm.save("atlas", "restart-audio", "different desc", ["b"])


def test_save_allows_reuse_of_a_name_once_deprecated(pm):
    pm.save("atlas", "restart-audio", "desc", ["a"])
    pm.deprecate("atlas", "restart-audio")

    procedure = pm.save("atlas", "restart-audio", "new desc", ["b", "c"])

    assert procedure.status == "active"
    assert procedure.steps == ["b", "c"]


def test_get_returns_none_for_a_missing_procedure(pm):
    assert pm.get("atlas", "does-not-exist") is None


def test_get_round_trips_steps_exactly(pm):
    steps = ["First, check the thing.", "Then fix it.", "Finally, verify."]
    pm.save("atlas", "some-task", "desc", steps)

    procedure = pm.get("atlas", "some-task")

    assert procedure.steps == steps


def test_list_all_defaults_to_active_status_only(pm):
    pm.save("atlas", "one", "desc", ["a"])
    pm.save("atlas", "two", "desc", ["a"])
    pm.deprecate("atlas", "two")

    names = {p.name for p in pm.list_all(agent="atlas")}

    assert names == {"one"}


def test_list_all_with_status_none_returns_everything(pm):
    pm.save("atlas", "one", "desc", ["a"])
    pm.save("atlas", "two", "desc", ["a"])
    pm.deprecate("atlas", "two")

    names = {p.name for p in pm.list_all(agent="atlas", status=None)}

    assert names == {"one", "two"}


def test_list_all_with_no_agent_aggregates_across_known_agents(pm):
    pm.save("atlas", "atlas-task", "desc", ["a"])
    pm.save("hope", "hope-task", "desc", ["a"])

    names = {p.name for p in pm.list_all()}

    assert names == {"atlas-task", "hope-task"}


def test_list_all_on_empty_store_returns_empty_list(pm):
    assert pm.list_all() == []
    assert pm.list_all(agent="atlas") == []


def test_recall_ranks_by_keyword_overlap(pm):
    pm.save("atlas", "restart-audio", "restart the audio pipeline when it hangs", ["a"])
    pm.save("atlas", "clean-downloads", "delete old files in the downloads folder", ["b"])

    results = pm.recall("the audio pipeline is hanging, please restart it", agent="atlas")

    assert [p.name for p in results] == ["restart-audio"]


def test_recall_respects_k(pm):
    for i in range(5):
        pm.save("atlas", f"task-{i}", "cleanup files in the workspace", ["a"])

    results = pm.recall("cleanup files workspace", agent="atlas", k=2)

    assert len(results) == 2


def test_recall_returns_empty_for_no_overlap(pm):
    pm.save("atlas", "restart-audio", "restart the audio pipeline", ["a"])

    assert pm.recall("bake a cake", agent="atlas") == []


def test_recall_ignores_deprecated_procedures(pm):
    pm.save("atlas", "restart-audio", "restart the audio pipeline", ["a"])
    pm.deprecate("atlas", "restart-audio")

    assert pm.recall("restart the audio pipeline", agent="atlas") == []


def test_record_outcome_increments_success_count(pm):
    pm.save("atlas", "restart-audio", "desc", ["a"])

    updated = pm.record_outcome("atlas", "restart-audio", success=True)

    assert updated.success_count == 1
    assert updated.failure_count == 0
    assert updated.last_used_at is not None


def test_record_outcome_increments_failure_count(pm):
    pm.save("atlas", "restart-audio", "desc", ["a"])

    updated = pm.record_outcome("atlas", "restart-audio", success=False)

    assert updated.success_count == 0
    assert updated.failure_count == 1


def test_record_outcome_accumulates_across_calls(pm):
    pm.save("atlas", "restart-audio", "desc", ["a"])

    pm.record_outcome("atlas", "restart-audio", success=True)
    pm.record_outcome("atlas", "restart-audio", success=True)
    updated = pm.record_outcome("atlas", "restart-audio", success=False)

    assert updated.success_count == 2
    assert updated.failure_count == 1


def test_record_outcome_raises_for_missing_procedure(pm):
    with pytest.raises(ValueError, match="No procedure"):
        pm.record_outcome("atlas", "does-not-exist", success=True)


def test_deprecate_flips_status_and_sets_superseded_by(pm):
    pm.save("atlas", "restart-audio", "desc", ["a"])

    updated = pm.deprecate("atlas", "restart-audio", superseded_by="restart-audio-v2")

    assert updated.status == "deprecated"
    assert updated.superseded_by == "restart-audio-v2"


def test_deprecate_raises_for_missing_procedure(pm):
    with pytest.raises(ValueError, match="No procedure"):
        pm.deprecate("atlas", "does-not-exist")


def test_saved_file_is_plain_readable_markdown(pm, tmp_path):
    pm.save("atlas", "restart-audio", "restart the audio pipeline", ["check device", "kill process"])

    text = (tmp_path / "atlas" / "restart-audio.md").read_text()

    assert text.startswith("---\n")
    assert "status: active" in text
    assert "1. check device" in text
    assert "2. kill process" in text
