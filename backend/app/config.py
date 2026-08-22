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
    # How much context window (in tokens) Ollama allocates per generation.
    # Left unset, Ollama defaults to ~2048-4096 depending on the model,
    # which is too small for judge calls (they read all 8 answers in one
    # prompt) and silently truncates the response mid-JSON instead of
    # erroring — that's the actual cause of "Could not extract JSON from
    # judge response" crashes, not malformed output.
    ollama_num_ctx: int = 8192
    # Separate from num_ctx: caps how many tokens the model may GENERATE
    # in one response. Some models default this fairly low, which alone
    # truncates a multi-item judge JSON array even with num_ctx raised.
    ollama_num_predict: int = 2048

    # LLM provider — "ollama" (local, default, free, slow on CPU-only
    # hardware) or "groq" (hosted, free tier, fast — good for judges or
    # for escaping slow/flaky local inference entirely). Everything
    # else (Agent, Judge, Evolution) is written against a common
    # interface and doesn't know or care which provider is active.
    llm_provider: str = "ollama"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: int = 60
    # Groq's equivalent of num_predict — max tokens generated per call.
    groq_max_tokens: int = 2048
    # Free-tier accounts cap how many requests can be in flight at once,
    # separate from (and much lower than) the per-minute limit — firing
    # all 8 agents concurrently trips this even though 11 total calls
    # is nowhere near 30 RPM. This throttles our own concurrency to stay
    # under that, without touching Agent/Judge/Evolution or how they
    # fire requests (still full asyncio.gather concurrency upstream).
    groq_max_concurrency: int = 3
    # How many times to retry a single call after a 429, honoring
    # Groq's `retry-after` header (falls back to this many seconds if
    # the header is missing).
    groq_max_retries: int = 5
    groq_retry_fallback_seconds: float = 5.0
    groq_min_interval_seconds: float = 1.5

    # Database
    database_path: str = "./data/arena.db"

    # Peer voting (Phase 7) — off by default; the spec explicitly wants
    # this testable both ways, not baked on.
    peer_voting_enabled: bool = False
    peer_vote_weight: float = 0.3

    # Dev convenience — both off (None) by default, zero effect on normal
    # runs or existing tests. Meant for iterating fast on slow/CPU-only
    # local hardware: dev_model_override pins every agent to one model
    # (no Ollama model-swap thrashing, and lets you point agents at
    # something tiny like llama3.2:1b for speed); dev_agent_limit runs a
    # smaller roster (e.g. 3) instead of all 8.
    dev_model_override: str | None = None
    dev_agent_limit: int | None = None
    # Judges need to follow a strict JSON schema, which small models
    # (e.g. llama3.2:1b) are unreliable at — they'll sometimes invent
    # their own field names or drop required commas. This lets judges
    # (and evolution, which has the same structured-output requirement)
    # use a more capable model than the fast one agents run on, without
    # falling back to Ollama's arbitrary "first installed model" pick.
    # Falls back to dev_model_override, then normal resolution, if unset.
    dev_judge_model_override: str | None = None
    # Judges normally run concurrently (asyncio.gather) — fine on a GPU
    # or a machine with cores to spare. On CPU-only hardware, 3 judges
    # firing at once just split the same limited throughput three ways
    # and each one crawls; running them one at a time often finishes
    # the whole batch faster, not slower. Off by default (unchanged
    # behavior) — opt in on slow hardware.
    dev_judges_sequential: bool = False

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