from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fact_checker.fetcher import FetchError, fetch_url_text


def _mock_response(text: str, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_fetch_returns_text() -> None:
    mock_resp = _mock_response("The Earth is round. Scientists confirm this fact.")
    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        text = await fetch_url_text("https://example.com")
    assert "Earth is round" in text


@pytest.mark.asyncio
async def test_fetch_invalid_scheme_raises() -> None:
    with pytest.raises(FetchError, match="Invalid URL scheme"):
        await fetch_url_text("ftp://example.com")


@pytest.mark.asyncio
async def test_fetch_http_error_raises() -> None:
    mock_resp = _mock_response("")
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=MagicMock()
    )
    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        with pytest.raises(FetchError, match="HTTP error"):
            await fetch_url_text("https://example.com")


@pytest.mark.asyncio
async def test_fetch_timeout_raises() -> None:
    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_cls.return_value = mock_client
        with pytest.raises(FetchError, match="network error"):
            await fetch_url_text("https://example.com")


@pytest.mark.asyncio
async def test_fetch_empty_body_raises() -> None:
    mock_resp = _mock_response("")
    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        with pytest.raises(FetchError, match="empty content"):
            await fetch_url_text("https://example.com")


@pytest.mark.asyncio
async def test_fetch_truncates_long_text() -> None:
    long_text = "This is a verifiable factual sentence. " * 300
    mock_resp = _mock_response(long_text)
    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        text = await fetch_url_text("https://example.com")
    assert len(text) <= 8000


@pytest.mark.asyncio
async def test_fetch_uses_jina_url() -> None:
    mock_resp = _mock_response("Some article content here.")
    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        await fetch_url_text("https://example.com/article")
    call_url = mock_client.get.call_args[0][0]
    assert call_url == "https://r.jina.ai/https://example.com/article"
