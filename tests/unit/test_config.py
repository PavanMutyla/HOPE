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
