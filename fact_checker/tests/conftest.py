from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fact_checker.config import MergedConfig
from fact_checker.verifier import VerificationResult


# ---------------------------------------------------------------------------
# Shared config fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def config(tmp_path: Path) -> MergedConfig:
    return MergedConfig(
        gemini_api_key="test-key",
        gemini_model="gemini-2.0-flash",
        searxng_timeout=15.0,
        searxng_health_timeout=5.0,
        searxng_max_retries=3,
        sessions_dir=tmp_path / "sessions",
        instances_url=None,
        log_level="INFO",
    )


# ---------------------------------------------------------------------------
# Shared claim fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_claim() -> str:
    return "The Eiffel Tower is located in Paris, France."


@pytest.fixture
def sample_verification_result(sample_claim: str) -> VerificationResult:
    return VerificationResult(
        claim=sample_claim,
        verdict="Supported",
        confidence=0.95,
        sources=["https://example.com/eiffel"],
        reasoning="Multiple sources confirm the Eiffel Tower is in Paris.",
        grounding_used=True,
        error=None,
    )


# ---------------------------------------------------------------------------
# Mock Gemini client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_gemini_response() -> MagicMock:
    """A fake Gemini response with grounding metadata and structured text."""
    chunk = MagicMock()
    chunk.web.uri = "https://example.com/source"

    metadata = MagicMock()
    metadata.grounding_chunks = [chunk]

    candidate = MagicMock()
    candidate.grounding_metadata = metadata

    response = MagicMock()
    response.candidates = [candidate]
    response.text = (
        "VERDICT: Supported\n"
        "CONFIDENCE: 0.95\n"
        "REASONING: Evidence confirms the claim.\n"
    )
    return response


@pytest.fixture
def mock_gemini_client(mock_gemini_response: MagicMock) -> MagicMock:
    """A fake genai.Client whose models.generate_content returns mock_gemini_response."""
    client = MagicMock()
    client.models.generate_content.return_value = mock_gemini_response
    return client
