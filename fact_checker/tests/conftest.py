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
        groq_api_key="test-groq-key",
        groq_model="llama-3.1-8b-instant",
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
        grounding_used=False,
        error=None,
    )


# ---------------------------------------------------------------------------
# Mock Groq response
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_groq_response() -> MagicMock:
    """A fake httpx.Response simulating a successful Groq API response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        "VERDICT: Supported\n"
                        "CONFIDENCE: 0.95\n"
                        "REASONING: Evidence confirms the claim.\n"
                    )
                }
            }
        ]
    }
    response.raise_for_status = MagicMock()
    return response
