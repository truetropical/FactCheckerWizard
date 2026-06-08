from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fact_checker.config import MergedConfig
from fact_checker.verifier import VerificationResult


@pytest.fixture
def config(tmp_path: Path) -> MergedConfig:
    return MergedConfig(
        groq_api_key="test-groq-key",
        groq_model="llama-3.1-8b-instant",
        serper_api_key="test-serper-key",
        serper_timeout=15.0,
        serper_max_retries=3,
        sessions_dir=tmp_path / "sessions",
        log_level="INFO",
    )


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


@pytest.fixture
def mock_groq_response() -> MagicMock:
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
