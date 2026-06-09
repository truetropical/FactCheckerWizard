from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fact_checker.sharpener import normalize_claim, decompose_claim, process_claim


def _mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return response


def test_normalize_returns_string(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("Donald Trump has engaged in sexual conduct with a minor.")
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = normalize_claim("Trump is a pedophile.", config)
    assert isinstance(result, str)
    assert len(result) > 0


def test_normalize_falls_back_on_empty(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("")
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = normalize_claim("Original claim.", config)
    assert result == "Original claim."


def test_normalize_falls_back_on_network_error(config: object) -> None:
    import httpx
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    with patch("fact_checker.sharpener.httpx.post", side_effect=httpx.TimeoutException("t")):
        result = normalize_claim("Original claim.", config)
    assert result == "Original claim."


def test_decompose_returns_list(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response('["Subclaim A.", "Subclaim B.", "Subclaim C."]')
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = decompose_claim("Some loaded claim.", config)
    assert isinstance(result, list)
    assert len(result) == 3


def test_decompose_no_split_returns_single(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claim = "The Philippines had the highest inflation in SEA in 2023."
    mock_resp = _mock_response('["The Philippines had the highest inflation in SEA in 2023."]')
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = decompose_claim(claim, config)
    assert result == [claim]


def test_decompose_caps_at_three(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response('["A.", "B.", "C.", "D.", "E."]')
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = decompose_claim("Something.", config)
    assert len(result) <= 3


def test_decompose_falls_back_on_invalid_json(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    mock_resp = _mock_response("not valid json")
    with patch("fact_checker.sharpener.httpx.post", return_value=mock_resp):
        result = decompose_claim("Original claim.", config)
    assert result == ["Original claim."]


def test_process_claim_returns_list(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    norm_resp = _mock_response("Normalized claim.")
    decomp_resp = _mock_response('["Subclaim A.", "Subclaim B."]')
    with patch("fact_checker.sharpener.httpx.post", side_effect=[norm_resp, decomp_resp]):
        result = process_claim("Vague claim.", config)
    assert isinstance(result, list)
    assert len(result) == 2
