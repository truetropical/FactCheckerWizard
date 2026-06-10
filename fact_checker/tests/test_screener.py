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


SOURCE = "The Philippines had inflation of 6.0% in 2023. The country grew by 5.6%."


def test_screen_pass1_returns_self_contained(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    sentences = [
        "The Philippine economy grew by 6.4% in 2023.",
        "Many experts believe things will improve.",
        "However, the situation remains uncertain.",
        "Inflation reached 6.8% in May 2023.",
        "Water is wet.",
    ]
    body = str([
        "The Philippine economy grew by 6.4% in 2023.",
        "Inflation reached 6.8% in May 2023.",
    ]).replace("'", '"')
    mock_resp = _mock_response(body)
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(sentences, config, source_text=SOURCE)
    assert isinstance(result, list)
    assert "The Philippine economy grew by 6.4% in 2023." in result


def test_screen_pass2_triggered_when_fewer_than_5(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    sentences = [
        "The Philippine economy grew by 6.4% in 2023.",
        "Inflation averaged 6.0% in 2023.",
        "Many experts believe things will improve.",
    ]
    pass1_body = str(["The Philippine economy grew by 6.4% in 2023."]).replace("'", '"')
    pass2_body = str(["The Philippines inflation averaged 6.0% in 2023."]).replace("'", '"')
    mock1 = _mock_response(pass1_body)
    mock2 = _mock_response(pass2_body)
    with patch("fact_checker.screener.httpx.post", side_effect=[mock1, mock2]):
        result = screen_claims(sentences, config, source_text=SOURCE)
    assert len(result) == 2
    assert "The Philippine economy grew by 6.4% in 2023." in result
    assert "The Philippines inflation averaged 6.0% in 2023." in result


def test_screen_caps_at_five(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    body = str(["A.", "B.", "C.", "D.", "E.", "F."]).replace("'", '"')
    mock_resp = _mock_response(body)
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(["x"] * 10, config, source_text=SOURCE)
    assert len(result) <= 5


def test_screen_falls_back_on_empty_response(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("")
    sentences = ["Claim one.", "Claim two.", "Claim three."]
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(sentences, config, source_text=SOURCE)
    assert isinstance(result, list)


def test_screen_falls_back_on_invalid_json(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("not valid json")
    sentences = ["Claim one.", "Claim two."]
    with patch("fact_checker.screener.httpx.post", return_value=mock_resp):
        result = screen_claims(sentences, config, source_text=SOURCE)
    assert isinstance(result, list)


def test_screen_skips_short_input(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    sentences = ["Only one claim here."]
    with patch("fact_checker.screener.httpx.post") as mock_post:
        result = screen_claims(sentences, config, source_text=SOURCE)
    mock_post.assert_not_called()
    assert result == sentences


def test_screen_empty_input_returns_empty(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    result = screen_claims([], config, source_text=SOURCE)
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
        result = screen_claims(sentences, config, source_text=SOURCE)
    assert isinstance(result, list)
