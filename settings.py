from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored at this file's location (repo root), not the process's CWD — the
# dashboard is a separate process that runs from dashboard/, and both .env
# discovery and the board DB path below need to resolve the same regardless
# of which process imports settings.
_REPO_ROOT = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str
    cartesia_api_key: str
    cartesia_voice_id: str
    user_name: str
    log_level: str
    stt_model: str
    llm_model: str
    llm_provider: str  # litellm provider prefix for context-window lookup (openai, anthropic, ollama, ...)
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str
    atlas_llm_model: str
    atlas_workspace: str
    atlas_voice_id: str
    kokoro_voice_id: str = "af_heart"
    kokoro_atlas_voice_id: str = "af_bella"
    llm_context_limit: int = 128000  # fallback only; real window is looked up per-model via litellm
    context_summarize_threshold: float = 0.9
    context_keep_recent: int = 6
    summarizer_model: str = "gpt-4o-mini"  # OpenAI model used to compress context
    episodic_db_path: str = "data_store/episodic_memory/episodic.db"
    episodic_media_dir: str = "data_store/episodic_memory/media"
    chroma_persist_dir: str = "data_store/episodic_memory/chroma"
    semantic_persist_dir: str = "data_store/semantic_memory/chroma"
    semantic_history_db_path: str = "data_store/semantic_memory/history.db"
    procedures_dir: str = "procedures"
    blackboard_db_path: str = "data_store/coordination/blackboard.db"
    board_db_path: str = str(_REPO_ROOT / "data_store/board/board.db")
    # Empty/None (the default) means "detect from the network" — see
    # memory/board/live.py:_resolve_location(). Set these in .env only to
    # override auto-detection (e.g. IP geolocation guesses wrong behind a VPN).
    home_city: str = ""
    home_lat: float | None = None
    home_lon: float | None = None
    dashboard_autostart: bool = True
    hope_log_path: str = str(_REPO_ROOT / "data_store/logs/hope.log")


settings = Settings()
