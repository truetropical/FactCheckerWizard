from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fact_checker.search import SearchClient


@pytest.mark.asyncio
async def test_initialise_logs_ready(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    client = SearchClient(config)
    await client.initialise()


@pytest.mark.asyncio
async def test_search_returns_results(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    payload = {
        "organic": [
            {"link": "https://example.com", "snippet": "Some fact.", "title": "Example"}
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status = MagicMock()

    with patch("fact_checker.search.httpx.AsyncClient") as mock_cls:
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_async_client

        client = SearchClient(config)
        results = await client.search("test query")

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"
    assert results[0]["content"] == "Some fact."


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    with patch("fact_checker.search.httpx.AsyncClient") as mock_cls:
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "403", request=MagicMock(), response=MagicMock()
            )
        )
        mock_cls.return_value = mock_async_client

        client = SearchClient(config)
        results = await client.search("test query")

    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_timeout(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    with patch("fact_checker.search.httpx.AsyncClient") as mock_cls:
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        mock_cls.return_value = mock_async_client

        client = SearchClient(config)
        results = await client.search("test query")

    assert results == []
