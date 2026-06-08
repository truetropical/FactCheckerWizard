from __future__ import annotations

import logging

import httpx

from fact_checker.config import SERPER_API_URL, MergedConfig
from fact_checker.utils import async_retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SearchClient
# ---------------------------------------------------------------------------


class SearchClient:
    """Executes web searches via the Serper API (Google Search)."""

    def __init__(self, config: MergedConfig) -> None:
        self._config = config

    async def initialise(self) -> None:
        """No-op for Serper — no instance management needed."""
        logger.info("SearchClient ready (Serper API)")

    @async_retry(max_attempts=3, exceptions=(httpx.HTTPError, httpx.TimeoutException, OSError))
    async def _do_search(self, query: str) -> list[dict[str, str]]:
        """Execute a single search request against Serper API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SERPER_API_URL,
                headers={
                    "X-API-KEY": self._config.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": 10},
                timeout=httpx.Timeout(self._config.serper_timeout),
            )
            response.raise_for_status()
            data = response.json()

        results: list[dict[str, str]] = []
        for item in data.get("organic", []):
            results.append({
                "url": item.get("link", ""),
                "content": item.get("snippet", ""),
                "title": item.get("title", ""),
            })
        return results

    async def search(self, query: str) -> list[dict[str, str]]:
        """Search for query via Serper API.

        Returns:
            List of result dicts with 'url', 'content', and 'title' keys.
            Returns empty list on failure.
        """
        try:
            results = await self._do_search(query)
            logger.info("Search '%s' returned %d result(s)", query, len(results))
            return results
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            logger.error("Serper search failed for query %r: %s", query, exc)
            return []
