from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fact_checker.search import SearchClient, _check_instance_latency, _load_cached_instances


def test_load_cached_instances_missing_file(tmp_path: object) -> None:
    result = _load_cached_instances()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_check_instance_latency_healthy() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="ok")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await _check_instance_latency(client, "https://example.com", 5.0)
    assert result is not None
    url, latency = result
    assert url == "https://example.com"
    assert latency >= 0.0


@pytest.mark.asyncio
async def test_check_instance_latency_unhealthy() -> None:
    def raise_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(raise_error)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await _check_instance_latency(client, "https://dead.example.com", 5.0)
    assert result is None


@pytest.mark.asyncio
async def test_search_returns_results(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    payload = {"results": [{"url": "https://result.com", "content": "Some fact."}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = SearchClient(config)
    client._instances = ["https://example-searxng.com"]
    client._current_index = 0

    with patch("fact_checker.search.httpx.AsyncClient") as mock_cls:
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        mock_async_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_async_client

        results = await client.search("test query")

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_no_instances_returns_empty(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    client = SearchClient(config)
    client._instances = []
    results = await client.search("anything")
    assert results == []
