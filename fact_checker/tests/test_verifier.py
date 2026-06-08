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
# Verifier.verify_claim integration tests (mocked Gemini)
# ---------------------------------------------------------------------------


def test_verify_claim_supported(
    config: object,
    mock_gemini_client: MagicMock,
    sample_claim: str,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    verifier = Verifier(config)
    verifier._client = mock_gemini_client
    result = verifier.verify_claim(sample_claim, ["https://example.com evidence text"])
    assert isinstance(result, VerificationResult)
    assert result.verdict == "Supported"
    assert result.confidence == pytest.approx(0.95)
    assert result.grounding_used is True
    assert result.error is None


def test_verify_claim_api_error_returns_inconclusive(
    config: object,
    sample_claim: str,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    verifier = Verifier(config)
    bad_client = MagicMock()
    bad_client.models.generate_content.side_effect = RuntimeError("API down")
    verifier._client = bad_client
    result = verifier.verify_claim(sample_claim, [])
    assert result.verdict == "Inconclusive"
    assert result.confidence == pytest.approx(0.0)
    assert result.error is not None
    assert "API down" in result.error


def test_verify_claim_no_grounding_uses_searxng_urls(
    config: object,
    sample_claim: str,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    response = MagicMock()
    response.candidates = []
    response.text = "VERDICT: Inconclusive\nCONFIDENCE: 0.1\nREASONING: No grounding."

    client = MagicMock()
    client.models.generate_content.return_value = response

    verifier = Verifier(config)
    verifier._client = client

    evidence = ["https://searxng-source.com/page", "Some snippet text"]
    result = verifier.verify_claim(sample_claim, evidence)
    assert result.grounding_used is False
    assert "https://searxng-source.com/page" in result.sources
