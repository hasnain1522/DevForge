from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM configuration
    llm_api_key: str = "not-configured"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""  # empty = OpenAI default; set for Ollama

    # Database
    database_url: str = "sqlite:///./devforge.db"

    # Application
    app_name: str = "DevForge"
    debug: bool = False


settings = Settings()
