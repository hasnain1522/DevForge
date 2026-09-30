from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM configuration
    llm_provider: str = "openai"
    llm_api_key: str = "not-configured"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Authentication
    auth_secret: str = Field(default="", validation_alias="AUTH_SECRET")
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")
    auth_session_hours: int = Field(default=24, validation_alias="AUTH_SESSION_HOURS")

    # Database
    database_url: str = "sqlite:///./devforge.db"

    # Application
    app_name: str = "DevForge"
    debug: bool = False
    environment: str = Field(default="development", validation_alias="DEVFORGE_ENV")

    @model_validator(mode="after")
    def validate_production_database(self):
        if self.environment == "production" and self.database_url.startswith("sqlite"):
            raise ValueError("Production requires persistent DATABASE_URL; SQLite is not supported in production")
        return self


settings = Settings()
