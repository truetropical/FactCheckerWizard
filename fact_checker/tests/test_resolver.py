from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fact_checker.resolver import resolve_references


def _mock_response(body: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": body}}]
    }
    return response


SOURCE_PH = "The Philippines had inflation of 6.0% in 2023. The country grew by 5.6%."
SOURCE_MS = "Microsoft acquired Activision for 69 billion dollars."
SOURCE_MH = "The Philippines signed the Maharlika fund into law."


def test_resolve_substitutes_ambiguous_reference(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claims = ["The country grew by 5.6% in 2023."]
    resolved = ["The Philippines grew by 5.6% in 2023."]
    mock_resp = _mock_response(str(resolved).replace("'", '"'))
    with patch("fact_checker.resolver.httpx.post", return_value=mock_resp):
        result = resolve_references(SOURCE_PH, claims, config)
    assert result == resolved


def test_resolve_unchanged_when_no_ambiguity(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claims = ["Microsoft acquired Activision for 69 billion dollars."]
    mock_resp = _mock_response(str(claims).replace("'", '"'))
    with patch("fact_checker.resolver.httpx.post", return_value=mock_resp):
        result = resolve_references(SOURCE_MS, claims, config)
    assert result == claims


def test_resolve_falls_back_on_empty_response(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claims = ["The country had 6% inflation."]
    mock_resp = _mock_response("")
    with patch("fact_checker.resolver.httpx.post", return_value=mock_resp):
        result = resolve_references(SOURCE_PH, claims, config)
    assert result == claims


def test_resolve_falls_back_on_wrong_count(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claims = ["Claim one.", "Claim two."]
    mock_resp = _mock_response('["Only one item."]')
    with patch("fact_checker.resolver.httpx.post", return_value=mock_resp):
        result = resolve_references("Some source text.", claims, config)
    assert result == claims


def test_resolve_falls_back_on_invalid_json(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claims = ["The fund was capitalized at 50 billion."]
    mock_resp = _mock_response("not valid json")
    with patch("fact_checker.resolver.httpx.post", return_value=mock_resp):
        result = resolve_references(SOURCE_MH, claims, config)
    assert result == claims


def test_resolve_falls_back_on_network_error(config: object) -> None:
    import httpx
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    claims = ["The country signed the law."]
    with patch(
        "fact_checker.resolver.httpx.post",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        result = resolve_references(SOURCE_MH, claims, config)
    assert result == claims


def test_resolve_empty_claims_returns_empty(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    result = resolve_references("Some source text.", [], config)
    assert result == []


def test_resolve_multiple_claims(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    source = "The Philippines signed the Maharlika fund into law. The country had 6% inflation."
    claims = ["The country signed the fund into law.", "It had 6% inflation."]
    resolved = [
        "The Philippines signed the Maharlika fund into law.",
        "The Philippines had 6% inflation.",
    ]
    mock_resp = _mock_response(str(resolved).replace("'", '"'))
    with patch("fact_checker.resolver.httpx.post", return_value=mock_resp):
        result = resolve_references(source, claims, config)
    assert result[0] == resolved[0]
    assert result[1] == resolved[1]
