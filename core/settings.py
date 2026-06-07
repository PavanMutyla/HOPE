from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str
    cartesia_api_key: str
    cartesia_voice_id: str
    user_name: str
    log_level: str
    stt_model: str
    llm_model: str



settings = Settings()
