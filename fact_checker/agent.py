from __future__ import annotations

import logging
import sys
from pathlib import Path

from fact_checker.config import MergedConfig
from fact_checker.extractor import extract_claims
from fact_checker.persistence import write_session
from fact_checker.search import SearchClient
from fact_checker.verifier import VerificationResult, Verifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Evidence gathering
# ---------------------------------------------------------------------------

_EVIDENCE_RESULTS_PER_CLAIM: int = 5


def _extract_evidence(results: list[dict[str, str]]) -> list[str]:
    """Pull URL and snippet text out of raw SearXNG result dicts.

    Returns a flat list interleaving URLs and content snippets so the
    verifier prompt has both provenance and substance.
    """
    evidence: list[str] = []
    for r in results[:_EVIDENCE_RESULTS_PER_CLAIM]:
        url = r.get("url", "").strip()
        content = r.get("content", "").strip()
        if url:
            evidence.append(url)
        if content:
            evidence.append(content)
    return evidence


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Agent:
    """Orchestrates the full fact-checking pipeline for a given input text."""

    def __init__(self, config: MergedConfig) -> None:
        self._config = config
        self._search = SearchClient(config)
        self._verifier = Verifier(config)

    async def run(self, text: str) -> list[VerificationResult]:
        """Run the full pipeline: extract → search → verify → persist.

        Progress messages are streamed to stderr in real time.

        Args:
            text: Raw input text containing one or more factual claims.

        Returns:
            List of VerificationResult objects, one per extracted claim.
        """
        # --- Stage 1: initialise search ---
        print("Initialising search instances...", file=sys.stderr, flush=True)
        await self._search.initialise()

        # --- Stage 2: extract claims ---
        print("Extracting claims...", file=sys.stderr, flush=True)
        claims = extract_claims(text)

        if not claims:
            print("No verifiable claims found in input.", file=sys.stderr, flush=True)
            return []

        print(f"Found {len(claims)} claim(s) to verify.", file=sys.stderr, flush=True)

        # --- Stage 3: search + verify each claim ---
        results: list[VerificationResult] = []

        for i, claim in enumerate(claims, start=1):
            print(
                f"Verifying claim {i} of {len(claims)}: {claim[:80]}...",
                file=sys.stderr,
                flush=True,
            )

            search_results = await self._search.search(claim)
            evidence = _extract_evidence(search_results)

            result = self._verifier.verify_claim(claim, evidence)
            results.append(result)

            verdict_line = (
                f"  → {result.verdict} "
                f"(confidence: {result.confidence:.0%}, "
                f"grounding: {'yes' if result.grounding_used else 'no'})"
            )
            print(verdict_line, file=sys.stderr, flush=True)

        # --- Stage 4: persist ---
        print("Writing session report...", file=sys.stderr, flush=True)
        session_dir: Path = write_session(results, self._config)
        print(f"Session saved: {session_dir}", file=sys.stderr, flush=True)

        return results
