from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from fact_checker.config import MergedConfig
from fact_checker.extractor import extract_claims
from fact_checker.persistence import write_session
from fact_checker.search import SearchClient
from fact_checker.sharpener import sharpen_claim
from fact_checker.verifier import VerificationResult, Verifier

logger = logging.getLogger(__name__)

_EVIDENCE_RESULTS_PER_CLAIM: int = 5


# ---------------------------------------------------------------------------
# ClaimPair
# ---------------------------------------------------------------------------


@dataclass
class ClaimPair:
    original_claim: str
    subclaims: list[str]
    original_result: VerificationResult
    subclaim_results: list[VerificationResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------


def _extract_evidence(results: list[dict[str, str]]) -> list[str]:
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

    async def run(self, text: str) -> list[ClaimPair]:
        """Run the full pipeline: extract, sharpen, search, verify, persist.

        Args:
            text: Raw input text containing one or more factual claims.

        Returns:
            List of ClaimPair objects, one per extracted claim.
        """
        print("Initialising search...", file=sys.stderr, flush=True)
        await self._search.initialise()

        print("Extracting claims...", file=sys.stderr, flush=True)
        claims = extract_claims(text)

        if not claims:
            print("No verifiable claims found in input.", file=sys.stderr, flush=True)
            return []

        print(f"Found {len(claims)} claim(s) to verify.", file=sys.stderr, flush=True)

        pairs: list[ClaimPair] = []

        for i, claim in enumerate(claims, start=1):
            print(
                f"\nClaim {i} of {len(claims)}: {claim[:80]}",
                file=sys.stderr, flush=True,
            )

            # --- Sharpen into subclaims ---
            print("  Decomposing into subclaims...", file=sys.stderr, flush=True)
            subclaims = sharpen_claim(claim, self._config)
            for j, sc in enumerate(subclaims, start=1):
                print(f"  [{j}] {sc[:80]}", file=sys.stderr, flush=True)

            # --- Verify original ---
            print("  Verifying original claim...", file=sys.stderr, flush=True)
            orig_results = await self._search.search(claim)
            orig_evidence = _extract_evidence(orig_results)
            original_result = self._verifier.verify_claim(claim, orig_evidence)
            print(
                f"  Original: {original_result.verdict} "
                f"({original_result.confidence:.0%})",
                file=sys.stderr, flush=True,
            )

            # --- Verify each subclaim ---
            subclaim_results: list[VerificationResult] = []
            for j, subclaim in enumerate(subclaims, start=1):
                print(
                    f"  Subclaim {j}/{len(subclaims)}: verifying...",
                    file=sys.stderr, flush=True,
                )
                if subclaim == claim:
                    sc_evidence = orig_evidence
                else:
                    sc_results = await self._search.search(subclaim)
                    sc_evidence = _extract_evidence(sc_results)
                sc_result = self._verifier.verify_claim(subclaim, sc_evidence)
                subclaim_results.append(sc_result)
                print(
                    f"  Subclaim {j}: {sc_result.verdict} "
                    f"({sc_result.confidence:.0%})",
                    file=sys.stderr, flush=True,
                )

            pairs.append(ClaimPair(
                original_claim=claim,
                subclaims=subclaims,
                original_result=original_result,
                subclaim_results=subclaim_results,
            ))

        print("\nWriting session report...", file=sys.stderr, flush=True)
        session_dir: Path = write_session(pairs, self._config)
        print(f"Session saved: {session_dir}", file=sys.stderr, flush=True)

        return pairs
