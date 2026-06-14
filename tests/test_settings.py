import pytest
from pydantic import ValidationError
from settings import Settings


def test_raises_when_openai_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "voice-id")
    monkeypatch.setenv("USER_NAME", "Pavan")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    with pytest.raises(ValidationError, match="openai_api_key"):
        Settings(_env_file=None)


def test_raises_when_cartesia_key_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    monkeypatch.setenv("CARTESIA_VOICE_ID", "voice-id")
    monkeypatch.setenv("USER_NAME", "Pavan")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    with pytest.raises(ValidationError, match="cartesia_api_key"):
        Settings(_env_file=None)


def test_raises_when_both_keys_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_all_values_accessible(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("CARTESIA_API_KEY", "cart-test")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "custom-voice-id")
    monkeypatch.setenv("USER_NAME", "Pavan")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    s = Settings(_env_file=None)
    assert s.openai_api_key == "sk-test"
    assert s.cartesia_api_key == "cart-test"
    assert s.cartesia_voice_id == "custom-voice-id"
    assert s.user_name == "Pavan"
    assert s.log_level == "INFO"
