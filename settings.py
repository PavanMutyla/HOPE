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
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str
    atlas_llm_model: str
    atlas_workspace: str
    atlas_voice_id: str


settings = Settings()
