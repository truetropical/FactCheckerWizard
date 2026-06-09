from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fact_checker.sharpener import sharpen_claim


def _mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return response


def test_sharpen_returns_list(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response('["Donald Trump has been convicted of a sexual offense."]')
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = sharpen_claim("Trump is a pedophile.", config)
    assert isinstance(result, list)
    assert len(result) == 1


def test_sharpen_returns_multiple_subclaims(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response('["Subclaim A.", "Subclaim B.", "Subclaim C."]')
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = sharpen_claim("X is corrupt.", config)
    assert len(result) == 3


def test_sharpen_caps_at_three(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response('["A.", "B.", "C.", "D.", "E."]')
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = sharpen_claim("Something.", config)
    assert len(result) <= 3


def test_sharpen_falls_back_on_empty_response(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("")
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = sharpen_claim("Original claim here.", config)
    assert result == ["Original claim here."]


def test_sharpen_falls_back_on_invalid_json(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("not valid json at all")
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = sharpen_claim("Original claim here.", config)
    assert result == ["Original claim here."]


def test_sharpen_falls_back_on_network_error(config: object) -> None:
    import httpx
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    with patch("fact_checker.sharpener.httpx.post", side_effect=httpx.TimeoutException("timeout")):
        result = sharpen_claim("Original claim here.", config)
    assert result == ["Original claim here."]