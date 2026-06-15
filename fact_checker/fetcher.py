from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_JINA_BASE_URL: str = 'https://r.jina.ai/'
_FETCH_TIMEOUT: float = 30.0
_MAX_TEXT_LENGTH: int = 8000


class FetchError(Exception):
    """Raised when a URL cannot be fetched or parsed."""


async def fetch_url_text(url: str) -> str:
    """Fetch a URL and return its main readable text content via Jina Reader.

    Jina Reader (r.jina.ai) handles JavaScript rendering, bot detection,
    paywalls, and returns clean text from any public URL.
    No API key required.

    Args:
        url: The URL to fetch. Must be http or https.

    Returns:
        Cleaned plain text extracted from the page.

    Raises:
        FetchError: If the request fails or no text can be extracted.
    """
    if not url.startswith(('http://', 'https://')):
        raise FetchError(f'Invalid URL scheme - only http/https supported: {url!r}')

    jina_url = f'{_JINA_BASE_URL}{url}'
    logger.info('Fetching via Jina Reader: %s', url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                jina_url,
                timeout=httpx.Timeout(_FETCH_TIMEOUT),
                follow_redirects=True,
                headers={
                    'Accept': 'text/plain',
                    'X-Return-Format': 'text',
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FetchError(f'Jina Reader HTTP error for {url}: {exc}') from exc
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise FetchError(f'Jina Reader network error for {url}: {exc}') from exc

    raw_text = response.text.strip()

    if not raw_text:
        raise FetchError(f'Jina Reader returned empty content for URL: {url}')

    cleaned = raw_text
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned).strip()

    if len(cleaned) > _MAX_TEXT_LENGTH:
        logger.warning(
            'Page text truncated from %d to %d chars for URL: %s',
            len(cleaned),
            _MAX_TEXT_LENGTH,
            url,
        )
        cleaned = cleaned[:_MAX_TEXT_LENGTH]

    logger.info('Extracted %d chars from %s via Jina Reader', len(cleaned), url)
    return cleaned
