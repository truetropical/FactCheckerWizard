from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typing helpers
# ---------------------------------------------------------------------------

P = ParamSpec("P")
T = TypeVar("T")

# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


def make_timestamp() -> str:
    """Return a microsecond-precision timestamp string safe for directory names.

    Example: '20250608_143201_847293'
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)


def async_retry(
    max_attempts: int = 3,
    backoff: tuple[float, ...] = RETRY_BACKOFF_SECONDS,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator — retry an async function with exponential backoff.

    Args:
        max_attempts: Total number of attempts (including the first call).
        backoff: Sleep durations in seconds between attempts. Must have at
                 least `max_attempts - 1` elements.
        exceptions: Exception types that trigger a retry. All others propagate
                    immediately.

    Usage::

        @async_retry(max_attempts=3, exceptions=(httpx.HTTPError,))
        async def fetch(...) -> ...:
            ...
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "All %d attempts failed for '%s': %s",
                            max_attempts,
                            func.__name__,
                            exc,
                        )
                        raise
                    delay = backoff[attempt - 1] if attempt - 1 < len(backoff) else backoff[-1]
                    logger.warning(
                        "Attempt %d/%d failed for '%s': %s — retrying in %.1fs",
                        attempt,
                        max_attempts,
                        func.__name__,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            # Unreachable — satisfies mypy
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
