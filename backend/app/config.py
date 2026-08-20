"""
Centralized configuration for AI Arena.

All settings are loaded from environment variables / a .env file so that
nothing is hardcoded across the app. Import `settings` anywhere you need
a config value.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    evolve_on_elimination: bool = True

    # App
    app_name: str = "AI Arena"
    env: str = "development"
    log_level: str = "INFO"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_timeout_seconds: int = 60

    # Database
    database_path: str = "./data/arena.db"

    # Peer voting (Phase 7) — off by default; the spec explicitly wants
    # this testable both ways, not baked on.
    peer_voting_enabled: bool = False
    peer_vote_weight: float = 0.3

    @property
    def database_full_path(self) -> Path:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance so we only parse the environment once."""
    return Settings()


settings = get_settings()