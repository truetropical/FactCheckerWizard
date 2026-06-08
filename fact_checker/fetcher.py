from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FETCH_TIMEOUT: float = 15.0
_MAX_TEXT_LENGTH: int = 8000  # chars — keeps Groq prompt within token limits

# Tags whose contents are never useful for fact-checking
_STRIP_TAGS: list[str] = [
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "button", "iframe", "img", "svg",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FetchError(Exception):
    """Raised when a URL cannot be fetched or parsed."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_url_text(url: str) -> str:
    """Fetch a URL and return its main readable text content.

    Strips HTML tags, navigation, scripts, and other noise. Truncates to
    _MAX_TEXT_LENGTH characters to keep downstream prompts manageable.

    Args:
        url: The URL to fetch. Must be http or https.

    Returns:
        Cleaned plain text extracted from the page.

    Raises:
        FetchError: If the request fails or no text can be extracted.
    """
    if not url.startswith(("http://", "https://")):
        raise FetchError(f"Invalid URL scheme — only http/https supported: {url!r}")

    logger.info("Fetching URL: %s", url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                timeout=httpx.Timeout(_FETCH_TIMEOUT),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    )
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FetchError(f"HTTP error fetching {url}: {exc}") from exc
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise FetchError(f"Network error fetching {url}: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise FetchError(
            f"Unsupported content type {content_type!r} for URL: {url}"
        )

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:
        raise FetchError(f"Failed to parse HTML from {url}: {exc}") from exc

    # Remove noise tags in-place
    for tag in soup(list(_STRIP_TAGS)):
        tag.decompose()

    # Prefer <article> or <main> if present — better signal-to-noise
    body = soup.find("article") or soup.find("main") or soup.body or soup

    raw_text = body.get_text(separator=" ", strip=True)

    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", raw_text).strip()

    if not cleaned:
        raise FetchError(f"No readable text found at URL: {url}")

    if len(cleaned) > _MAX_TEXT_LENGTH:
        logger.warning(
            "Page text truncated from %d to %d chars for URL: %s",
            len(cleaned),
            _MAX_TEXT_LENGTH,
            url,
        )
        cleaned = cleaned[:_MAX_TEXT_LENGTH]

    logger.info("Extracted %d chars from %s", len(cleaned), url)
    return cleaned

