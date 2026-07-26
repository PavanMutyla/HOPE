from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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


settings = Settings()
