from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROQ_MODEL_DEFAULT: str = "llama-3.1-8b-instant"
LOG_LEVEL_DEFAULT: str = "INFO"
GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
SERPER_API_URL: str = "https://google.serper.dev/search"
SERPER_TIMEOUT_DEFAULT: float = 15.0
SERPER_MAX_RETRIES_DEFAULT: int = 3


class ConfigError(Exception):
    pass


@dataclass
class MergedConfig:
    groq_api_key: str
    groq_model: str
    serper_api_key: str
    serper_timeout: float
    serper_max_retries: int
    sessions_dir: Path
    log_level: str


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ConfigError(
            f"Required environment variable '{key}' is missing or empty. "
            f"Add it to your .env file."
        )
    return value


def _parse_float(key: str, raw: str) -> float:
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(
            f"Environment variable '{key}' must be a float, got: {raw!r}"
        )


def _parse_int(key: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(
            f"Environment variable '{key}' must be an integer, got: {raw!r}"
        )


def load_config() -> MergedConfig:
    groq_api_key = _require_env("GROQ_API_KEY")
    groq_model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)
    serper_api_key = _require_env("SERPER_API_KEY")

    raw_timeout = os.environ.get("SERPER_TIMEOUT")
    serper_timeout = (
        _parse_float("SERPER_TIMEOUT", raw_timeout)
        if raw_timeout is not None
        else SERPER_TIMEOUT_DEFAULT
    )

    raw_retries = os.environ.get("SERPER_MAX_RETRIES")
    serper_max_retries = (
        _parse_int("SERPER_MAX_RETRIES", raw_retries)
        if raw_retries is not None
        else SERPER_MAX_RETRIES_DEFAULT
    )

    sessions_dir = Path(os.environ.get("SESSIONS_DIR", "./sessions"))

    log_level_raw = os.environ.get("LOG_LEVEL", LOG_LEVEL_DEFAULT).upper()
    if log_level_raw not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError(
            f"LOG_LEVEL must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL, "
            f"got: {log_level_raw!r}"
        )

    logging.basicConfig(level=getattr(logging, log_level_raw))

    return MergedConfig(
        groq_api_key=groq_api_key,
        groq_model=groq_model,
        serper_api_key=serper_api_key,
        serper_timeout=serper_timeout,
        serper_max_retries=serper_max_retries,
        sessions_dir=sessions_dir,
        log_level=log_level_raw,
    )
