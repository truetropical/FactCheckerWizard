from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fact_checker.fetcher import FetchError, fetch_url_text


@pytest.mark.asyncio
async def test_fetch_returns_text() -> None:
    html = b"<html><body><p>The Earth is round. Scientists confirm this fact.</p></body></html>"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = html.decode()
    mock_response.raise_for_status = MagicMock()

    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        text = await fetch_url_text("https://example.com")

    assert "Earth is round" in text
    assert "<" not in text  # no HTML tags in output


@pytest.mark.asyncio
async def test_fetch_strips_script_tags() -> None:
    html = "<html><body><script>alert('xss')</script><p>Real content here for testing.</p></body></html>"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        text = await fetch_url_text("https://example.com")

    assert "alert" not in text
    assert "Real content" in text


@pytest.mark.asyncio
async def test_fetch_invalid_scheme_raises() -> None:
    with pytest.raises(FetchError, match="Invalid URL scheme"):
        await fetch_url_text("ftp://example.com")


@pytest.mark.asyncio
async def test_fetch_http_error_raises() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    mock_response.headers = {"content-type": "text/html"}
    mock_response.status_code = 404

    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
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

        with pytest.raises(FetchError, match="Network error"):
            await fetch_url_text("https://example.com")


@pytest.mark.asyncio
async def test_fetch_unsupported_content_type_raises() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status = MagicMock()

    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        with pytest.raises(FetchError, match="Unsupported content type"):
            await fetch_url_text("https://example.com/doc.pdf")


@pytest.mark.asyncio
async def test_fetch_empty_body_raises() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><body></body></html>"
    mock_response.raise_for_status = MagicMock()

    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        with pytest.raises(FetchError, match="No readable text"):
            await fetch_url_text("https://example.com")


@pytest.mark.asyncio
async def test_fetch_truncates_long_text() -> None:
    long_paragraph = "This is a verifiable factual sentence. " * 300  # ~12k chars
    html = f"<html><body><p>{long_paragraph}</p></body></html>"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("fact_checker.fetcher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        text = await fetch_url_text("https://example.com")

    assert len(text) <= 8000
