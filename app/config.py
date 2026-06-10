from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Autonomous GitHub Code Review Agent"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_max_tokens: int = 4096
    anthropic_temperature: float = 0.1

    github_token: str = ""
    github_webhook_secret: str = ""
    github_api_url: str = "https://api.github.com"

    chroma_path: str = "./.chroma"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    collection_prefix: str = "github_review_agent"
    repo_workspace: str = "./.repos"

    max_patch_characters: int = 80_000
    max_context_chunks: int = 8
    request_timeout_seconds: float = 45.0
    retry_attempts: int = Field(default=3, ge=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
