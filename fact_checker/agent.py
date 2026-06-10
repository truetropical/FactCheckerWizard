from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from fact_checker.config import MergedConfig
from fact_checker.extractor import extract_claims
from fact_checker.persistence import write_session
from fact_checker.resolver import resolve_references
from fact_checker.screener import screen_claims
from fact_checker.search import SearchClient
from fact_checker.sharpener import process_claim
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
        """Run the full pipeline: extract, screen, resolve, normalize, search, verify, persist.

        Pipeline:
        1. Extract all sentences (cap at 100)
        2. Screen: one Groq call selects top 5 atomic verifiable claims
        3. Resolve: one Groq call substitutes ambiguous references using source context
        4. For each claim: normalize query, search, verify
        5. Decomposition is skipped - screener selects atomic claims only
        6. Persist and return

        Args:
            text: Raw input text of any length.

        Returns:
            List of ClaimPair objects, one per verified claim.
        """
        print("Initialising search...", file=sys.stderr, flush=True)
        await self._search.initialise()

        # --- Stage 1: Extract sentences ---
        print("Extracting sentences...", file=sys.stderr, flush=True)
        all_sentences = extract_claims(text)

        if not all_sentences:
            print("No verifiable claims found in input.", file=sys.stderr, flush=True)
            return []

        print(
            f"Extracted {len(all_sentences)} sentence(s).",
            file=sys.stderr, flush=True,
        )

        # --- Stage 2: Screen for top 5 atomic claims ---
        print("Screening for top fact-checkable claims...", file=sys.stderr, flush=True)
        screened = screen_claims(all_sentences, self._config)

        if not screened:
            print("No fact-checkable claims found after screening.", file=sys.stderr, flush=True)
            return []

        print(
            f"Selected {len(screened)} claim(s) for verification.",
            file=sys.stderr, flush=True,
        )

        # --- Stage 3: Resolve ambiguous references ---
        print("Resolving references...", file=sys.stderr, flush=True)
        claims = resolve_references(text, screened, self._config)

        pairs: list[ClaimPair] = []

        for i, claim in enumerate(claims, start=1):
            print(
                f"\nClaim {i} of {len(claims)}: {claim[:80]}",
                file=sys.stderr, flush=True,
            )

            # --- Stage 4: Normalize (no decomposition) ---
            print("  Normalizing...", file=sys.stderr, flush=True)
            processed = process_claim(claim, self._config)

            # Screener selected atomic claims so decomposition should not trigger.
            # If it does anyway, skip subclaims and use only the first item.
            if len(processed) > 1:
                logger.warning(
                    "Decomposition triggered on screened claim %r - skipping subclaims",
                    claim,
                )
            search_query = processed[0]

            if search_query != claim:
                print(
                    f"  Normalized: {search_query[:80]}",
                    file=sys.stderr, flush=True,
                )
            else:
                print("  Claim is already precise.", file=sys.stderr, flush=True)

            # --- Stage 5: Search + verify ---
            print("  Searching for evidence...", file=sys.stderr, flush=True)
            search_results = await self._search.search(search_query)
            evidence = _extract_evidence(search_results)

            print("  Verifying...", file=sys.stderr, flush=True)
            result = self._verifier.verify_claim(claim, evidence)
            print(
                f"  Result: {result.verdict} ({result.confidence:.0%})",
                file=sys.stderr, flush=True,
            )

            # No subclaims - screener ensures atomic claims
            pairs.append(ClaimPair(
                original_claim=claim,
                subclaims=[],
                original_result=result,
                subclaim_results=[],
            ))

        print("\nWriting session report...", file=sys.stderr, flush=True)
        session_dir: Path = write_session(pairs, self._config)
        print(f"Session saved: {session_dir}", file=sys.stderr, flush=True)

        return pairs

