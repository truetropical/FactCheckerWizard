from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fact_checker.verifier import VerificationResult, Verifier, _parse_response


# ---------------------------------------------------------------------------
# _parse_response unit tests
# ---------------------------------------------------------------------------


def test_parse_supported() -> None:
    raw = "VERDICT: Supported\nCONFIDENCE: 0.9\nREASONING: Strong evidence found."
    verdict, confidence, reasoning = _parse_response(raw)
    assert verdict == "Supported"
    assert confidence == pytest.approx(0.9)
    assert reasoning == "Strong evidence found."


def test_parse_refuted() -> None:
    raw = "VERDICT: Refuted\nCONFIDENCE: 0.8\nREASONING: Claim contradicted by sources."
    verdict, confidence, reasoning = _parse_response(raw)
    assert verdict == "Refuted"
    assert confidence == pytest.approx(0.8)


def test_parse_inconclusive_default() -> None:
    raw = "VERDICT: Inconclusive\nCONFIDENCE: 0.2\nREASONING: Insufficient evidence."
    verdict, confidence, reasoning = _parse_response(raw)
    assert verdict == "Inconclusive"
    assert confidence == pytest.approx(0.2)


def test_parse_clamps_confidence() -> None:
    raw = "VERDICT: Supported\nCONFIDENCE: 1.5\nREASONING: Over-confident."
    _, confidence, _ = _parse_response(raw)
    assert confidence == pytest.approx(1.0)


def test_parse_bad_confidence_defaults_zero() -> None:
    raw = "VERDICT: Supported\nCONFIDENCE: not-a-number\nREASONING: Test."
    _, confidence, _ = _parse_response(raw)
    assert confidence == pytest.approx(0.0)


def test_parse_unknown_verdict_defaults_inconclusive() -> None:
    raw = "VERDICT: Maybe\nCONFIDENCE: 0.5\nREASONING: Test."
    verdict, _, _ = _parse_response(raw)
    assert verdict == "Inconclusive"


# ---------------------------------------------------------------------------
# Verifier.verify_claim tests (mocked httpx)
# ---------------------------------------------------------------------------


def test_verify_claim_supported(
    config: object,
    mock_groq_response: MagicMock,
    sample_claim: str,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    verifier = Verifier(config)
    with patch("fact_checker.verifier.httpx.post", return_value=mock_groq_response):
        result = verifier.verify_claim(sample_claim, ["https://example.com evidence text"])
    assert isinstance(result, VerificationResult)
    assert result.verdict == "Supported"
    assert result.confidence == pytest.approx(0.95)
    assert result.grounding_used is False
    assert result.error is None


def test_verify_claim_http_error_returns_inconclusive(
    config: object,
    sample_claim: str,
) -> None:
    import httpx
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    verifier = Verifier(config)
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=MagicMock()
    )
    with patch("fact_checker.verifier.httpx.post", return_value=mock_response):
        result = verifier.verify_claim(sample_claim, [])
    assert result.verdict == "Inconclusive"
    assert result.error is not None


def test_verify_claim_network_error_returns_inconclusive(
    config: object,
    sample_claim: str,
) -> None:
    import httpx
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    verifier = Verifier(config)
    with patch("fact_checker.verifier.httpx.post", side_effect=httpx.TimeoutException("timeout")):
        result = verifier.verify_claim(sample_claim, [])
    assert result.verdict == "Inconclusive"
    assert result.error is not None


def test_verify_claim_uses_searxng_urls_as_sources(
    config: object,
    mock_groq_response: MagicMock,
    sample_claim: str,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    verifier = Verifier(config)
    evidence = ["https://searxng-source.com/page", "Some snippet text"]
    with patch("fact_checker.verifier.httpx.post", return_value=mock_groq_response):
        result = verifier.verify_claim(sample_claim, evidence)
    assert "https://searxng-source.com/page" in result.sources
    assert result.grounding_used is False
