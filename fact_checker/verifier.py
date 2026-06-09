from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    claim: str
    verdict: Literal["Supported", "Refuted", "Inconclusive"]
    confidence: float
    sources: list[str]
    reasoning: str
    grounding_used: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Source policy
# ---------------------------------------------------------------------------

_BLACKLISTED_DOMAINS: list[str] = [
    # Known misinformation / conspiracy outlets
    "infowars.com", "naturalnews.com", "beforeitsnews.com", "realrawnews.com",
    "whatdoesitmean.com", "newspunch.com", "veteranstoday.com", "activistpost.com",
    "thegatewaypundit.com", "oann.com", "breitbart.com",
    # Social media platforms
    "facebook.com", "twitter.com", "x.com", "tiktok.com", "instagram.com",
    "threads.net", "reddit.com", "4chan.org", "t.me", "telegram.me",
    # Forums and discussion boards
    "quora.com", "yahoo.answers.com",
    # Video commentary
    "youtube.com", "youtu.be",
]

_SYSTEM_PROMPT = """\
You are a strict, neutral fact-checking assistant. Evaluate whether a factual \
claim is supported or refuted by the evidence provided.

SOURCE RELIABILITY TIERS — apply these when evaluating evidence:

TIER A (highest trust — use for verification):
- Peer-reviewed journals (pubmed, ncbi, nature, science, thelancet, etc.)
- Government and official statistical agencies (nasa.gov, cdc.gov, who.int, etc.)
- Wire services used for straight reporting only (apnews.com, reuters.com)
- Major encyclopaedias (britannica.com, encyclopedia.com)
- Wikipedia is acceptable as a secondary cross-reference only, not primary evidence

TIER B (conditional — use for reported facts only, not opinion or analysis):
- Major mainstream outlets (bbc.com, nytimes.com, theguardian.com, washingtonpost.com)
- Must be straight news reporting, not opinion/editorial/analysis sections
- Require cross-verification with at least one Tier A source

TIER C (unreliable — do not use as evidence):
- Social media posts (Facebook, Twitter/X, TikTok, Instagram, Threads, Reddit)
- AI-generated articles or summaries
- Personal blogs without citations
- Forums and discussion boards (Reddit, 4chan, Quora)
- YouTube commentary channels
- Propaganda or state-sponsored outlets
- Any of these domains: infowars.com, naturalnews.com, beforeitsnews.com,
  realrawnews.com, thegatewaypundit.com, breitbart.com, zerohedge.com

VERDICT RULES:
- SUPPORTED: at least one Tier A source confirms the claim, or two independent
  Tier B sources confirm with no contradicting evidence
- REFUTED: at least one Tier A source contradicts, or consistent contradiction
  across multiple Tier B sources
- INCONCLUSIVE: evidence is only from Tier C sources, evidence is contradictory,
  or insufficient credible evidence exists — confidence must be 0.3 or lower
- Never express personal opinion
- Never cite Tier C sources as supporting evidence

Respond in this exact format:
VERDICT: <Supported|Refuted|Inconclusive>
CONFIDENCE: <float between 0.0 and 1.0>
REASONING: <one to three sentences, objective tone, cite source tiers used>
"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _filter_blacklisted(evidence: list[str]) -> tuple[list[str], list[str]]:
    """Split evidence into allowed and blacklisted items."""
    allowed: list[str] = []
    blocked: list[str] = []
    for item in evidence:
        is_blocked = any(domain in item for domain in _BLACKLISTED_DOMAINS)
        if is_blocked:
            blocked.append(item)
        else:
            allowed.append(item)
    return allowed, blocked


def _build_prompt(claim: str, evidence: list[str]) -> str:
    allowed, blocked = _filter_blacklisted(evidence)

    if blocked:
        logger.warning(
            "Filtered %d blacklisted source(s) from evidence: %s",
            len(blocked),
            blocked,
        )

    evidence_block = (
        "\n".join(f"- {e}" for e in allowed)
        if allowed
        else "No credible external evidence was retrieved."
    )
    return (
        f"Claim to verify:\n{claim}\n\n"
        f"Evidence snippets (pre-filtered for credibility):\n{evidence_block}\n\n"
        "Evaluate the claim using the evidence above and the source tiers defined "
        "in your instructions."
    )


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_response(
    raw: str,
) -> tuple[Literal["Supported", "Refuted", "Inconclusive"], float, str]:
    verdict: Literal["Supported", "Refuted", "Inconclusive"] = "Inconclusive"
    confidence: float = 0.0
    reasoning: str = raw.strip()

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("VERDICT:"):
            raw_verdict = line.split(":", 1)[1].strip().capitalize()
            if raw_verdict in {"Supported", "Refuted", "Inconclusive"}:
                verdict = raw_verdict  # type: ignore[assignment]
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
    """Verifies claims using Groq with tier-weighted source evaluation."""

    def __init__(self, config: MergedConfig) -> None:
        self._config = config

    def verify_claim(self, claim: str, evidence: list[str]) -> VerificationResult:
        prompt = _build_prompt(claim, evidence)
        allowed, _ = _filter_blacklisted(evidence)
        sources = [e for e in allowed if e.startswith("http")]

        try:
            response = httpx.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self._config.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._config.groq_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 512,
                },
                timeout=httpx.Timeout(30.0),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Groq API HTTP error for claim %r: %s", claim, exc)
            return VerificationResult(
                claim=claim, verdict="Inconclusive", confidence=0.0,
                sources=sources,
                reasoning="Verification could not be completed due to an API error.",
                grounding_used=False, error=str(exc),
            )
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("Groq API request failed for claim %r: %s", claim, exc)
            return VerificationResult(
                claim=claim, verdict="Inconclusive", confidence=0.0,
                sources=sources,
                reasoning="Verification could not be completed due to a network error.",
                grounding_used=False, error=str(exc),
            )

        try:
            data = response.json()
            raw_text: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.error("Failed to parse Groq response for claim %r: %s", claim, exc)
            return VerificationResult(
                claim=claim, verdict="Inconclusive", confidence=0.0,
                sources=sources, reasoning="Groq returned an unparseable response.",
                grounding_used=False, error=str(exc),
            )

        if not raw_text:
            return VerificationResult(
                claim=claim, verdict="Inconclusive", confidence=0.0,
                sources=sources, reasoning="Groq returned an empty response.",
                grounding_used=False, error="Empty response from model",
            )

        verdict, confidence, reasoning = _parse_response(raw_text)

        return VerificationResult(
            claim=claim, verdict=verdict, confidence=confidence,
            sources=sources, reasoning=reasoning,
            grounding_used=False, error=None,
        )
