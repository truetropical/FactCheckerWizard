from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from google import genai
from google.genai import types

from fact_checker.config import MergedConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    claim: str
    verdict: Literal["Supported", "Refuted", "Inconclusive"]
    confidence: float          # 0.0–1.0; 0.0 if evidence is absent or contradictory
    sources: list[str]         # Gemini grounding citations if available, else SearXNG URLs
    reasoning: str             # Human-readable explanation, objective tone
    grounding_used: bool       # True if groundingMetadata was present and used
    error: str | None = None   # Non-None if verification failed due to an exception


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a neutral fact-checking assistant. Your task is to evaluate whether a \
factual claim is supported or refuted by available evidence.

Respond in this exact format:
VERDICT: <Supported|Refuted|Inconclusive>
CONFIDENCE: <float between 0.0 and 1.0>
REASONING: <one to three sentences, objective tone, no editorialising>

Rules:
- If evidence is contradictory or insufficient, verdict must be Inconclusive \
and confidence must be 0.3 or lower.
- Never express personal opinion.
- Base your verdict solely on the evidence provided.
"""


def _build_prompt(claim: str, evidence: list[str]) -> str:
    evidence_block = (
        "\n".join(f"- {e}" for e in evidence)
        if evidence
        else "No external evidence was retrieved."
    )
    return (
        f"Claim to verify:\n{claim}\n\n"
        f"Evidence snippets:\n{evidence_block}\n\n"
        "Evaluate the claim using the evidence above and your grounded search results."
    )


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_response(
    raw: str,
) -> tuple[Literal["Supported", "Refuted", "Inconclusive"], float, str]:
    """Parse the structured text response from Gemini into (verdict, confidence, reasoning)."""
    verdict: Literal["Supported", "Refuted", "Inconclusive"] = "Inconclusive"
    confidence: float = 0.0
    reasoning: str = raw.strip()

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("VERDICT:"):
            raw_verdict = line.split(":", 1)[1].strip()
            if raw_verdict in {"Supported", "Refuted", "Inconclusive"}:
                verdict = raw_verdict  # type: ignore[assignment]  # narrowed by membership check
        elif line.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.0
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return verdict, confidence, reasoning


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


class Verifier:
    """Verifies claims using Gemini with optional Google Search grounding."""

    def __init__(self, config: MergedConfig) -> None:
        self._config = config
        self._client = genai.Client(api_key=config.gemini_api_key)

    def verify_claim(self, claim: str, evidence: list[str]) -> VerificationResult:
        """Verify a single claim against provided evidence snippets.

        Args:
            claim: The factual assertion to verify.
            evidence: List of evidence strings gathered by search.py + extractor.py.

        Returns:
            A VerificationResult. Never raises — errors are captured in .error.
        """
        prompt = _build_prompt(claim, evidence)

        try:
            response = self._client.models.generate_content(
                model=self._config.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.0,
                ),
            )
        except Exception as exc:  # outermost catch — never let a Gemini error crash the pipeline
            logger.error("Gemini API call failed for claim %r: %s", claim, exc)
            return VerificationResult(
                claim=claim,
                verdict="Inconclusive",
                confidence=0.0,
                sources=[],
                reasoning="Verification could not be completed due to an API error.",
                grounding_used=False,
                error=str(exc),
            )

        # Extract grounding metadata
        grounding_used = False
        sources: list[str] = []

        try:
            metadata = response.candidates[0].grounding_metadata
            if metadata and metadata.grounding_chunks:
                grounding_used = True
                for chunk in metadata.grounding_chunks:
                    if chunk.web and chunk.web.uri:
                        sources.append(chunk.web.uri)
        except (AttributeError, IndexError):
            metadata = None

        if not grounding_used:
            logger.warning(
                "[WARN] Grounding metadata absent — key may be free-tier or feature disabled"
            )

        # Fall back to SearXNG-derived evidence URLs if grounding not available
        if not sources:
            sources = [e for e in evidence if e.startswith("http")]

        # Parse the text response
        raw_text = ""
        try:
            raw_text = response.text or ""
        except (AttributeError, ValueError):
            pass

        if not raw_text:
            logger.error("Empty response text from Gemini for claim: %r", claim)
            return VerificationResult(
                claim=claim,
                verdict="Inconclusive",
                confidence=0.0,
                sources=sources,
                reasoning="Gemini returned an empty response.",
                grounding_used=grounding_used,
                error="Empty response from model",
            )

        verdict, confidence, reasoning = _parse_response(raw_text)

        return VerificationResult(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            sources=sources,
            reasoning=reasoning,
            grounding_used=grounding_used,
            error=None,
        )
