import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General Settings
    APP_NAME: str = Field(default="QA Test Case Generator")
    ENV: str = Field(default="development")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # Relational Database Settings (SQLite)
    DATABASE_URL: str = Field(default="sqlite:///./sql_app.db")

    # Document Database Settings (MongoDB)
    MONGODB_URI: str = Field(default="mongodb://localhost:27017")
    MONGODB_DB_NAME: str = Field(default="qa_generator")

    # LLM Service Configuration
    LLM_PROVIDER: str = Field(default="mock")  # "gemini", "openai", "mock"
    LLM_MODEL: str = Field(default="gemini-1.5-flash")
    GEMINI_API_KEY: str | None = Field(default=None)
    OPENAI_API_KEY: str | None = Field(default=None)

    # Local storage paths (relative to workspace root)
    DOCUMENTS_DIR: str = Field(default="documents")
    GENERATED_DIR: str = Field(default="generated")

    @property
    def documents_path(self) -> Path:
        path = Path(self.DOCUMENTS_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def generated_path(self) -> Path:
        path = Path(self.GENERATED_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Instantiate the global settings object
settings = Settings()
