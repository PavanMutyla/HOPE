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
    kokoro_voice_id: str = "af_heart"
    kokoro_atlas_voice_id: str = "af_bella"
    llm_context_limit: int = 128000  # fallback only; real window is looked up per-model via litellm
    context_summarize_threshold: float = 0.9
    context_keep_recent: int = 6
    summarizer_model: str = "gpt-4o-mini"  # OpenAI model used to compress context
    # Every path below is absolute, anchored to this file's directory rather
    # than the process CWD. Two processes read them from two different working
    # directories (hope.py from the repo root, the dashboard from dashboard/),
    # and a relative path silently resolves to two different files: the
    # dashboard would read an empty database it created itself and show an
    # empty history, with nothing failing anywhere.
    episodic_db_path: str = str(_REPO_ROOT / "data_store/episodic_memory/episodic.db")
    episodic_media_dir: str = str(_REPO_ROOT / "data_store/episodic_memory/media")
    chroma_persist_dir: str = str(_REPO_ROOT / "data_store/episodic_memory/chroma")
    semantic_persist_dir: str = str(_REPO_ROOT / "data_store/semantic_memory/chroma")
    semantic_history_db_path: str = str(_REPO_ROOT / "data_store/semantic_memory/history.db")
    procedures_dir: str = str(_REPO_ROOT / "procedures")
    blackboard_db_path: str = str(_REPO_ROOT / "data_store/coordination/blackboard.db")
    board_db_path: str = str(_REPO_ROOT / "data_store/board/board.db")
    # Absolute for the same reason as board_db_path: hope.py writes it, the
    # dashboard process (CWD dashboard/) reads it.
    live_db_path: str = str(_REPO_ROOT / "data_store/live/live.db")
    # Empty/None (the default) means "detect from the network" — see
    # memory/board/live.py:_resolve_location(). Set these in .env only to
    # override auto-detection (e.g. IP geolocation guesses wrong behind a VPN).
    home_city: str = ""
    home_lat: float | None = None
    home_lon: float | None = None
    dashboard_autostart: bool = True
    dashboard_open_browser: bool = True  # open a browser tab once the dashboard answers
    hope_log_path: str = str(_REPO_ROOT / "data_store/logs/hope.log")
    # ── Internet access (read-only) ──
    # Search goes through a self-hosted meta-search engine, never a search
    # vendor's API. "degoog" or "searxng" — see tools/web/search.py.
    search_provider: str = "degoog"
    degoog_url: str = "http://localhost:4444"
    degoog_api_key: str = ""  # only if the instance protects /api/search
    searxng_url: str = "http://localhost:8888"
    # Start a local degoog with HOPE (Bun, else Docker) — see tools/web/degoog_service.py.
    degoog_autostart: bool = True
    degoog_dir: str = str(_REPO_ROOT / "data_store/degoog")
    # ── Dynamically spawned sub-agents ──
    max_live_subagents: int = 5  # hard cap, enforced in code, not the prompt
    research_llm_model: str = "gpt-4o-mini"
    research_max_researchers: int = 4
    research_max_tool_calls: int = 12  # per researcher
    research_dir: str = str(_REPO_ROOT / "data_store/research")


settings = Settings()
