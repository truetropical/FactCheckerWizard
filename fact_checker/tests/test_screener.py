from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fact_checker.screener import screen_claims


def _mock_response(body: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": body}}]
    }
    return response


def test_screen_returns_top_claims(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    sentences = [
        "The Philippine economy grew by 6.4% in 2023.",
        "Many experts believe things will improve.",
        "However, the situation remains uncertain.",
        "Inflation reached 6.8% in May 2023.",
        "Water is wet.",
    ]
    body = '["The Philippine economy grew by 6.4% in 2023.", "Inflation reached 6.8% in May 2023."]'
    mock_resp = _mock_response(body)
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(sentences, config)
    assert isinstance(result, list)
    assert len(result) == 2
    assert "The Philippine economy grew by 6.4% in 2023." in result


def test_screen_caps_at_five(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    body = '["A.", "B.", "C.", "D.", "E.", "F."]'
    mock_resp = _mock_response(body)
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(["x"] * 10, config)
    assert len(result) <= 5


def test_screen_falls_back_on_empty_response(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("")
    sentences = ["Claim one.", "Claim two.", "Claim three."]
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(sentences, config)
    assert result == sentences[:5]


def test_screen_falls_back_on_invalid_json(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("not valid json")
    sentences = ["Claim one.", "Claim two."]
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(sentences, config)
    assert result == sentences[:5]


def test_screen_skips_short_input(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    sentences = ["Only one claim here."]
    with patch("fact_checker.screener.httpx.post") as mock_post:
        result = screen_claims(sentences, config)
    mock_post.assert_not_called()
    assert result == sentences


def test_screen_empty_input_returns_empty(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    result = screen_claims([], config)
    assert result == []


def test_screen_falls_back_on_network_error(config: object) -> None:
    import httpx
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    sentences = ["Claim one.", "Claim two.", "Claim three."]
    with patch(
        "fact_checker.screener.httpx.post",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        result = screen_claims(sentences, config)
    assert result == sentences[:5]
