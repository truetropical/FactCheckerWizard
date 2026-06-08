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

FALLBACK_INSTANCES: list[str] = [
    "https://search.im-in.space",
    "https://searx.tsmdt.de",
    "https://paulgo.io",
    "https://searx.ro",
    "https://searxng.deggo.fyi",
    "https://search.rhscz.eu",
    "https://search.zina.dev",
    "https://search.ethibox.fr",
    "https://search.pereira.is",
    "https://searx.namejeff.xyz",
    "https://searx.tuxcloud.net",
    "https://search.2b9t.xyz",
]

SEARXNG_TIMEOUT_DEFAULT: float = 15.0
SEARXNG_HEALTH_TIMEOUT_DEFAULT: float = 5.0
SEARXNG_MAX_RETRIES_DEFAULT: int = 3
GROQ_MODEL_DEFAULT: str = "llama-3.1-8b-instant"
LOG_LEVEL_DEFAULT: str = "INFO"
GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when a required config key is missing or fails type validation."""


# ---------------------------------------------------------------------------
# MergedConfig
# ---------------------------------------------------------------------------


@dataclass
class MergedConfig:
    groq_api_key: str
    groq_model: str
    searxng_timeout: float
    searxng_health_timeout: float
    searxng_max_retries: int
    sessions_dir: Path
    instances_url: str | None
    log_level: str


def _require_env(key: str) -> str:
    """Return the value of a required environment variable or raise ConfigError."""
    value = os.environ.get(key)
    if not value:
        raise ConfigError(
            f"Required environment variable '{key}' is missing or empty. "
            f"Add it to your .env file."
        )
    return value


def _parse_float(key: str, raw: str) -> float:
    """Parse a float env var value or raise ConfigError."""
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(
            f"Environment variable '{key}' must be a float, got: {raw!r}"
        )


def _parse_int(key: str, raw: str) -> int:
    """Parse an int env var value or raise ConfigError."""
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(
            f"Environment variable '{key}' must be an integer, got: {raw!r}"
        )


def load_config() -> MergedConfig:
    """Load, validate, and return a MergedConfig.

    Raises ConfigError if any required key is absent or any value fails
    type validation. Called once at CLI startup.
    """
    groq_api_key = _require_env("GROQ_API_KEY")
    groq_model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)

    raw_timeout = os.environ.get("SEARXNG_TIMEOUT")
    searxng_timeout = (
        _parse_float("SEARXNG_TIMEOUT", raw_timeout)
        if raw_timeout is not None
        else SEARXNG_TIMEOUT_DEFAULT
    )

    raw_health = os.environ.get("SEARXNG_HEALTH_TIMEOUT")
    searxng_health_timeout = (
        _parse_float("SEARXNG_HEALTH_TIMEOUT", raw_health)
        if raw_health is not None
        else SEARXNG_HEALTH_TIMEOUT_DEFAULT
    )

    raw_retries = os.environ.get("SEARXNG_MAX_RETRIES")
    searxng_max_retries = (
        _parse_int("SEARXNG_MAX_RETRIES", raw_retries)
        if raw_retries is not None
        else SEARXNG_MAX_RETRIES_DEFAULT
    )

    sessions_dir = Path(os.environ.get("SESSIONS_DIR", "./sessions"))
    instances_url: str | None = os.environ.get("SEARXNG_INSTANCES_URL") or None

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
        searxng_timeout=searxng_timeout,
        searxng_health_timeout=searxng_health_timeout,
        searxng_max_retries=searxng_max_retries,
        sessions_dir=sessions_dir,
        instances_url=instances_url,
        log_level=log_level_raw,
    )
