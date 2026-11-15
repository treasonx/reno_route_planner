"""Runtime settings from environment variables. Keys are SecretStr (redacted by default)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    wu_api_key: SecretStr | None = None
    ndot_api_key: SecretStr | None = None
    passcheck_sources: Literal["live", "fixtures"] = "live"
    log_level: str = "INFO"
    static_dir: Path = Path("/app/static")
