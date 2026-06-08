from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fact_checker.agent import Agent, ClaimPair, _extract_evidence
from fact_checker.verifier import VerificationResult


def test_extract_evidence_pulls_url_and_content() -> None:
    results = [{"url": "https://example.com", "content": "Some snippet."}]
    evidence = _extract_evidence(results)
    assert "https://example.com" in evidence
    assert "Some snippet." in evidence


def test_extract_evidence_skips_empty_fields() -> None:
    results = [{"url": "", "content": ""}]
    evidence = _extract_evidence(results)
    assert evidence == []


def test_extract_evidence_caps_at_five() -> None:
    results = [{"url": f"https://example.com/{i}", "content": f"Snippet {i}."} for i in range(10)]
    evidence = _extract_evidence(results)
    assert len(evidence) <= 10


@pytest.mark.asyncio
async def test_agent_run_returns_pairs(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    fake_result = VerificationResult(
        claim="The Earth orbits the Sun.",
        verdict="Supported",
        confidence=0.99,
        sources=["https://nasa.gov"],
        reasoning="Well established astronomical fact.",
        grounding_used=False,
        error=None,
    )

    with (
        patch("fact_checker.agent.SearchClient") as mock_search_cls,
        patch("fact_checker.agent.Verifier") as mock_verifier_cls,
        patch("fact_checker.agent.sharpen_claim", return_value="The Earth orbits the Sun."),
        patch("fact_checker.agent.write_session") as mock_write,
    ):
        mock_search = AsyncMock()
        mock_search.initialise = AsyncMock()
        mock_search.search = AsyncMock(return_value=[
            {"url": "https://nasa.gov", "content": "Earth orbits Sun."}
        ])
        mock_search_cls.return_value = mock_search

        mock_verifier = MagicMock()
        mock_verifier.verify_claim.return_value = fake_result
        mock_verifier_cls.return_value = mock_verifier

        mock_write.return_value = config.sessions_dir / "20250608_120000_000000"

        agent = Agent(config)
        pairs = await agent.run("The Earth orbits the Sun.")

    assert len(pairs) == 1
    assert isinstance(pairs[0], ClaimPair)
    assert pairs[0].original_result.verdict == "Supported"


@pytest.mark.asyncio
async def test_agent_run_empty_text_returns_empty(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)

    with (
        patch("fact_checker.agent.SearchClient") as mock_search_cls,
        patch("fact_checker.agent.Verifier"),
        patch("fact_checker.agent.sharpen_claim", return_value=""),
        patch("fact_checker.agent.write_session"),
    ):
        mock_search = AsyncMock()
        mock_search.initialise = AsyncMock()
        mock_search_cls.return_value = mock_search

        agent = Agent(config)
        pairs = await agent.run("")

    assert pairs == []
