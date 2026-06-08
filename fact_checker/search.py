from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx

from fact_checker.config import FALLBACK_INSTANCES, MergedConfig
from fact_checker.utils import async_retry

logger = logging.getLogger(__name__)

_INSTANCE_CACHE_FILE = Path("./sessions/.instance_cache.json")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def _check_instance_latency(
    client: httpx.AsyncClient,
    url: str,
    timeout: float,
) -> tuple[str, float] | None:
    """Return (url, latency_seconds) if the instance is healthy, else None."""
    endpoints = ["/healthz", "/stats", "/"]
    for endpoint in endpoints:
        try:
            method = "GET" if endpoint in ("/healthz", "/stats") else "HEAD"
            start = time.monotonic()
            response = await client.request(
                method,
                f"{url.rstrip('/')}{endpoint}",
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            )
            elapsed = time.monotonic() - start
            if response.status_code < 300:
                logger.debug("Instance %s healthy via %s (%.2fs)", url, endpoint, elapsed)
                return url, elapsed
        except (httpx.HTTPError, httpx.TimeoutException, OSError):
            continue
    logger.warning("Instance %s failed all health checks — skipping", url)
    return None


async def _rank_instances(
    instances: list[str],
    health_timeout: float,
) -> list[str]:
    """Return instances sorted by ascending latency (fastest first)."""
    async with httpx.AsyncClient() as client:
        tasks = [_check_instance_latency(client, url, health_timeout) for url in instances]
        results = await asyncio.gather(*tasks)

    ranked = sorted(
        (r for r in results if r is not None),
        key=lambda x: x[1],
    )
    return [url for url, _ in ranked]


# ---------------------------------------------------------------------------
# Instance cache
# ---------------------------------------------------------------------------


def _load_cached_instances() -> list[str]:
    try:
        data = json.loads(_INSTANCE_CACHE_FILE.read_text(encoding="utf-8"))
        instances: list[str] = data.get("instances", [])
        logger.info("Loaded %d instances from cache", len(instances))
        return instances
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load instance cache: %s", exc)
        return []


def _save_cached_instances(instances: list[str]) -> None:
    try:
        _INSTANCE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _INSTANCE_CACHE_FILE.write_text(
            json.dumps({"instances": instances}, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not save instance cache: %s", exc)


# ---------------------------------------------------------------------------
# Dynamic discovery
# ---------------------------------------------------------------------------


async def _fetch_dynamic_instances(url: str, timeout: float) -> list[str]:
    """Fetch and parse the live instance list from searx.space."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=httpx.Timeout(timeout))
            response.raise_for_status()
            data = response.json()
            instances: list[str] = list(data.get("instances", {}).keys())
            logger.info("Fetched %d instances from %s", len(instances), url)
            return instances
    except (httpx.HTTPError, httpx.TimeoutException, OSError, json.JSONDecodeError) as exc:
        logger.warning("Dynamic instance fetch failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# SearchClient
# ---------------------------------------------------------------------------


class SearchClient:
    """Manages SearXNG instance selection and query execution."""

    def __init__(self, config: MergedConfig) -> None:
        self._config = config
        self._instances: list[str] = []
        self._current_index: int = 0

    async def initialise(self) -> None:
        """Resolve, health-check, and rank instances. Must be called before search()."""
        base = list(FALLBACK_INSTANCES)

        if self._config.instances_url:
            dynamic = await _fetch_dynamic_instances(
                self._config.instances_url,
                self._config.searxng_health_timeout,
            )
            # Merge: union, deduplicated, preserving order
            seen: set[str] = set(base)
            for url in dynamic:
                if url not in seen:
                    base.append(url)
                    seen.add(url)

        logger.info("Running health checks against %d instances...", len(base))
        ranked = await _rank_instances(base, self._config.searxng_health_timeout)

        if ranked:
            self._instances = ranked
            _save_cached_instances(ranked)
            logger.info("Using %d healthy instance(s); primary: %s", len(ranked), ranked[0])
        else:
            logger.warning("All health checks failed — falling back to instance cache")
            self._instances = _load_cached_instances()

        if not self._instances:
            logger.error("No usable SearXNG instances available")

    @property
    def _primary(self) -> str | None:
        return self._instances[self._current_index] if self._instances else None

    def _rotate(self) -> None:
        """Advance to the next healthy instance."""
        if self._instances:
            self._current_index = (self._current_index + 1) % len(self._instances)
            logger.warning("Rotating to next instance: %s", self._instances[self._current_index])

    @async_retry(max_attempts=3, exceptions=(httpx.HTTPError, httpx.TimeoutException, OSError))
    async def _do_search(self, instance: str, query: str) -> list[dict[str, str]]:
        """Execute a single search request against one instance."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{instance.rstrip('/')}/search",
                params={"q": query, "format": "json", "language": "en"},
                timeout=httpx.Timeout(self._config.searxng_timeout),
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()
            results: list[dict[str, str]] = data.get("results", [])
            return results

    async def search(self, query: str) -> list[dict[str, str]]:
        """Search for query, rotating instances on failure.

        Returns:
            List of result dicts with at minimum 'url' and 'content' keys.
            Returns empty list if all instances fail.
        """
        if not self._instances:
            logger.error("search() called but no instances are available")
            return []

        attempts = len(self._instances)
        for _ in range(attempts):
            instance = self._primary
            if instance is None:
                break
            try:
                results = await self._do_search(instance, query)
                logger.info(
                    "Search '%s' returned %d result(s) from %s",
                    query,
                    len(results),
                    instance,
                )
                return results
            except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
                logger.warning("Instance %s failed during search: %s", instance, exc)
                self._rotate()

        logger.error("All instances failed for query: %r", query)
        return []
