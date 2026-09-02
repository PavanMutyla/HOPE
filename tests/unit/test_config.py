"""Unit tests for settings.py — one test per required key."""

import pytest
from pydantic import ValidationError
from settings import Settings

REQUIRED_KEYS = [
    "OPENAI_API_KEY",
    "CARTESIA_API_KEY",
    "CARTESIA_VOICE_ID",
    "USER_NAME",
    "LOG_LEVEL",
    "STT_MODEL",
    "LLM_MODEL",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "ATLAS_LLM_MODEL",
    "ATLAS_WORKSPACE",
    "ATLAS_VOICE_ID",
]


@pytest.mark.unit
def test_loads_with_all_required_keys(fake_env):
    s = Settings(_env_file=None)
    assert s.openai_api_key == "test-openai-key-not-real"
    assert s.cartesia_api_key == "test-cartesia-key-not-real"
    assert s.cartesia_voice_id == "test-cartesia-voice-id"
    assert s.user_name == "TestUser"
    assert s.log_level == "INFO"
    assert s.stt_model == "whisper-1"
    assert s.llm_model == "gpt-4o"
    assert s.llm_provider == "openai"
    assert s.langfuse_public_key == "test-langfuse-pk"
    assert s.langfuse_secret_key == "test-langfuse-sk"
    assert s.langfuse_base_url == "https://cloud.langfuse.com"
    assert s.atlas_llm_model == "gpt-4o-mini"
    assert s.atlas_workspace == "/tmp/test-atlas-workspace"
    assert s.atlas_voice_id == "test-atlas-voice-id"
    assert s.kokoro_voice_id == "af_heart"
    assert s.kokoro_atlas_voice_id == "af_bella"


@pytest.mark.unit
def test_raises_on_missing_openai_api_key(fake_env, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_cartesia_api_key(fake_env, monkeypatch):
    monkeypatch.delenv("CARTESIA_API_KEY")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_cartesia_voice_id(fake_env, monkeypatch):
    monkeypatch.delenv("CARTESIA_VOICE_ID")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_user_name(fake_env, monkeypatch):
    monkeypatch.delenv("USER_NAME")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_log_level(fake_env, monkeypatch):
    monkeypatch.delenv("LOG_LEVEL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_stt_model(fake_env, monkeypatch):
    monkeypatch.delenv("STT_MODEL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_llm_model(fake_env, monkeypatch):
    monkeypatch.delenv("LLM_MODEL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_llm_provider(fake_env, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_langfuse_public_key(fake_env, monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_langfuse_secret_key(fake_env, monkeypatch):
    monkeypatch.delenv("LANGFUSE_SECRET_KEY")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_langfuse_base_url(fake_env, monkeypatch):
    monkeypatch.delenv("LANGFUSE_BASE_URL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_atlas_llm_model(fake_env, monkeypatch):
    monkeypatch.delenv("ATLAS_LLM_MODEL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_atlas_workspace(fake_env, monkeypatch):
    monkeypatch.delenv("ATLAS_WORKSPACE")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_raises_on_missing_atlas_voice_id(fake_env, monkeypatch):
    monkeypatch.delenv("ATLAS_VOICE_ID")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_kokoro_voice_id_defaults_to_af_heart(fake_env, monkeypatch):
    monkeypatch.delenv("KOKORO_VOICE_ID", raising=False)
    s = Settings(_env_file=None)
    assert s.kokoro_voice_id == "af_heart"


@pytest.mark.unit
def test_kokoro_atlas_voice_id_defaults_to_af_bella(fake_env, monkeypatch):
    monkeypatch.delenv("KOKORO_ATLAS_VOICE_ID", raising=False)
    s = Settings(_env_file=None)
    assert s.kokoro_atlas_voice_id == "af_bella"


@pytest.mark.unit
def test_kokoro_voice_id_can_be_overridden(fake_env, monkeypatch):
    monkeypatch.setenv("KOKORO_VOICE_ID", "am_puck")
    s = Settings(_env_file=None)
    assert s.kokoro_voice_id == "am_puck"


@pytest.mark.unit
def test_kokoro_atlas_voice_id_can_be_overridden(fake_env, monkeypatch):
    monkeypatch.setenv("KOKORO_ATLAS_VOICE_ID", "bm_george")
    s = Settings(_env_file=None)
    assert s.kokoro_atlas_voice_id == "bm_george"


@pytest.mark.unit
def test_env_example_keys_match_settings_fields(fake_env):
    """
    Every key in .env.example must map to a field in Settings.
    Catches drift between the template and the actual config.
    """
    from pathlib import Path

    env_example = Path(__file__).parents[2] / ".env.example"
    if not env_example.exists():
        pytest.skip(".env.example not found — skipping sync check")

    keys_in_example = {
        line.split("=")[0].strip().lower()
        for line in env_example.read_text().splitlines()
        if line.strip() and not line.startswith("#") and "=" in line
    }

    s = Settings(_env_file=None)
    settings_fields = set(s.model_fields.keys())

    for key in keys_in_example:
        assert key in settings_fields, (
            f"Key '{key}' is in .env.example but missing from Settings. "
            "Update settings.py or remove it from .env.example."
        )


@pytest.mark.unit
def test_llm_context_limit_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.llm_context_limit == 128000


@pytest.mark.unit
def test_context_summarize_threshold_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.context_summarize_threshold == 0.9


@pytest.mark.unit
def test_context_keep_recent_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.context_keep_recent == 6


@pytest.mark.unit
def test_episodic_db_path_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.episodic_db_path == "data_store/episodic_memory/episodic.db"


@pytest.mark.unit
def test_episodic_media_dir_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.episodic_media_dir == "data_store/episodic_memory/media"


@pytest.mark.unit
def test_chroma_persist_dir_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.chroma_persist_dir == "data_store/episodic_memory/chroma"


@pytest.mark.unit
def test_semantic_persist_dir_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.semantic_persist_dir == "data_store/semantic_memory/chroma"


@pytest.mark.unit
def test_semantic_history_db_path_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.semantic_history_db_path == "data_store/semantic_memory/history.db"


@pytest.mark.unit
def test_procedures_dir_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.procedures_dir == "procedures"


@pytest.mark.unit
def test_blackboard_db_path_default(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.blackboard_db_path == "data_store/coordination/blackboard.db"


# ─── dashboard / shared-board keys ──────────────────────────────
#
# These arrived with the dashboard and shared board but were never covered.
# All have defaults, so a rename or a broken default fails silently rather
# than raising ValidationError like the required keys above do — which is
# exactly why they need pinning here.
#
# conftest's pytest_configure points BOARD_DB_PATH and HOPE_LOG_PATH at a temp
# dir so importing dashboard/dashboard/state.py can't touch the real board.
# That env var would mask the default under test, hence the delenv.


@pytest.mark.unit
def test_board_db_path_defaults_next_to_the_other_data_stores(fake_env, monkeypatch):
    from pathlib import Path

    from settings import Settings

    monkeypatch.delenv("BOARD_DB_PATH", raising=False)
    s = Settings(_env_file=None)
    assert Path(s.board_db_path).parts[-3:] == ("data_store", "board", "board.db")


@pytest.mark.unit
def test_board_db_path_is_absolute(fake_env, monkeypatch):
    """The dashboard runs as its own process with dashboard/ as CWD, so a
    relative default here would resolve to two different files depending on
    which process opened it — the one bug this absolute path exists to avoid."""
    from pathlib import Path

    from settings import Settings

    monkeypatch.delenv("BOARD_DB_PATH", raising=False)
    s = Settings(_env_file=None)
    assert Path(s.board_db_path).is_absolute()


@pytest.mark.unit
def test_hope_log_path_defaults_under_data_store_and_is_absolute(fake_env, monkeypatch):
    from pathlib import Path

    from settings import Settings

    monkeypatch.delenv("HOPE_LOG_PATH", raising=False)
    s = Settings(_env_file=None)
    assert Path(s.hope_log_path).parts[-3:] == ("data_store", "logs", "hope.log")
    assert Path(s.hope_log_path).is_absolute()


@pytest.mark.unit
def test_dashboard_autostart_defaults_on(fake_env):
    from settings import Settings
    s = Settings(_env_file=None)
    assert s.dashboard_autostart is True


@pytest.mark.unit
def test_dashboard_autostart_can_be_turned_off(fake_env, monkeypatch):
    from settings import Settings

    monkeypatch.setenv("DASHBOARD_AUTOSTART", "false")
    s = Settings(_env_file=None)
    assert s.dashboard_autostart is False


@pytest.mark.unit
def test_home_location_defaults_to_autodetect(fake_env, monkeypatch):
    """Empty/None is the signal memory/board/live.py reads as 'detect from the
    network' — a non-empty default would silently pin everyone to one city."""
    from settings import Settings

    for key in ("HOME_CITY", "HOME_LAT", "HOME_LON"):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.home_city == ""
    assert s.home_lat is None
    assert s.home_lon is None


@pytest.mark.unit
def test_home_location_can_be_pinned(fake_env, monkeypatch):
    from settings import Settings

    monkeypatch.setenv("HOME_CITY", "Bengaluru")
    monkeypatch.setenv("HOME_LAT", "12.97")
    monkeypatch.setenv("HOME_LON", "77.59")
    s = Settings(_env_file=None)
    assert s.home_city == "Bengaluru"
    assert s.home_lat == 12.97
    assert s.home_lon == 77.59
