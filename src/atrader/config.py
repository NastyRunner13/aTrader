"""Application settings, read from environment variables and an optional `.env` file.

Runtime state (databases, caches, checkpoints) defaults to a per-user application
data directory outside the OneDrive-synced repository; see docs/06.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from platformdirs import user_data_dir
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATRADER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Model gateway (OpenRouter, free routes only) -----------------------------------
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "ATRADER_OPENROUTER_API_KEY"),
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    quick_model: str = "openrouter/free"
    deep_model: str = "openrouter/free"
    # Zero-priced model IDs without the ":free" suffix that the user has reviewed.
    model_allowlist: list[str] = Field(default_factory=list)
    # The account's daily free-model allowance and the part held back for follow-ups
    # and ambiguous attempts (docs/08). Raise the limit only if the account allows it.
    daily_request_limit: int = 50
    daily_request_reserve: int = 10
    max_concurrent_requests: int = 2
    request_timeout_s: float = 300.0  # reasoning models can take minutes on long prompts
    # For reasoning models this budget covers the hidden reasoning and the answer, so it
    # is generous; free routes cost nothing per token, only time.
    max_output_tokens: int = 8000
    # Requested from models that support OpenRouter's `reasoning` parameter. None leaves
    # the model's default. Reasoning text is excluded from responses either way.
    reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = "low"
    temperature: float = 0.2

    # --- Storage -------------------------------------------------------------------------
    data_dir: Path = Field(default_factory=lambda: Path(user_data_dir("atrader", appauthor=False)))
    reports_dir: Path = Path("reports")

    # --- Data retrieval ------------------------------------------------------------------
    http_min_interval_s: float = 1.0
    price_history_sessions: int = 300
    announcement_lookback_days: int = 120
    news_lookback_days: int = 14
    enable_gdelt_news: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / "atrader.sqlite3"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def usable_daily_requests(self) -> int:
        return max(0, self.daily_request_limit - self.daily_request_reserve)

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.cache_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
