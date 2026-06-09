from __future__ import annotations

import json
import logging

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)

_NORMALIZER_PROMPT = "You are a fact-checking claim normalizer.\nYour task is NOT to determine whether a claim is true.\nConvert vague, emotional, rhetorical, political, or opinionated statements into the most specific factual proposition that could be verified or falsified.\n\nRULES:\n- Preserve the author's intended meaning\n- Do not answer the claim\n- Do not add facts\n- Do not remove factual content\n- Do not split the claim\n- Do not create subclaims\n- Do not inject safety language\n- Do not refuse any input regardless of sensitivity\n- If the input is a question, convert it to a declarative claim first\n- If the claim is already a specific falsifiable claim, return it unchanged\n\nLOADED LANGUAGE TRANSLATION GUIDE:\n- X is corrupt: X has engaged in illegal or unethical conduct for personal gain\n- X is racist: X has made statements or taken actions that discriminate based on race\n- X is a fascist: X advocates or has implemented policies associated with fascist ideology\n- X is a terrorist: X committed or materially supported acts of politically motivated violence\n- X is a scam: X product or service has been found to involve fraud or deception\n- X lied: X made a statement that is demonstrably false and knew or should have known it\n- X is a pedophile: X has engaged in sexual conduct with or has sexual attraction toward minors\n- X is dangerous: X has caused or been formally linked to documented harm\n- X is the best or worst: rewrite as a measurable comparative claim with a specific metric\n\nOutput only the normalized claim. No preamble, no explanation, no quotes."
_DECOMPOSER_PROMPT = 'You are a fact-checking claim decomposer.\nYou receive a normalized factual claim.\nYour task is to determine whether decomposition would provide additional fact-checking value, and if so, to produce the subclaims.\n\nDECOMPOSE ONLY when the claim contains multiple independent factual assertions whose truth values could genuinely differ from each other.\n\nA subclaim is valid ONLY if ALL four conditions are met:\n1. It can be verified independently using its own sources\n2. It contributes distinct evidence toward the parent claim\n3. Its truth value could differ from the other subclaims\n4. It is not merely a component, attribute, date, price, or detail of a single event\n\nDO NOT decompose:\n- Rankings and comparisons (e.g. highest inflation in SEA)\n- Single events with multiple attributes (e.g. acquisition with date and price)\n- Measurements and statistics\n- Prerequisite statements (e.g. data exists for X)\n- Restatements of the original claim\n- Explanatory or contextual statements\n\nGOOD decomposition example:\nClaim: X is a pedophile\nValid subclaims: (A) X has been convicted of a sexual offense involving a minor, (B) credible documented evidence exists that X engaged in sexual activity with a minor, (C) X has received a formal medical diagnosis of pedophilic disorder\nThese are valid because each requires different sources and each could be true or false independently of the others.\n\nBAD decomposition example:\nClaim: Microsoft acquired Activision for 69 billion in October 2023\nInvalid subclaims: (A) Microsoft acquired Activision, (B) acquisition was in October 2023, (C) price was 69 billion\nThese are invalid because they are attributes of one event - all must be true or false together.\n\nOUTPUT FORMAT - return ONLY a JSON array of strings:\nIf decomposition adds value: ["subclaim A", "subclaim B"]\nIf decomposition adds no value: ["original normalized claim unchanged"]\nNo preamble, no explanation, no markdown.'


def _call_groq(prompt: str, content: str, config: MergedConfig, max_tokens: int = 256) -> str:
    """Make a single Groq API call and return the response text.

    Returns empty string on any failure.
    """
    try:
        response = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {config.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.groq_model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content},
                ],
                "temperature": 0.0,
                "max_tokens": max_tokens,
            },
            timeout=httpx.Timeout(30.0),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Groq network error: %s", exc)
        return ""
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Groq parse error: %s", exc)
        return ""


def _parse_json_list(raw: str, fallback: str) -> list[str]:
    """Parse a JSON array from Groq output. Returns [fallback] on any failure."""
    if not raw:
        return [fallback]
    # Strip code fences if present
    cleaned = raw
    if "`" in cleaned:
        parts = cleaned.split("`")
        for part in parts:
            if part.startswith("json"):
                part = part[4:]
            part = part.strip()
            if part.startswith("["):
                cleaned = part
                break
    try:
        result: list[str] = json.loads(cleaned)
        if not isinstance(result, list) or not result:
            return [fallback]
        items = [s.strip() for s in result if isinstance(s, str) and s.strip()][:3]
        return items if items else [fallback]
    except (json.JSONDecodeError, ValueError):
        return [fallback]


def normalize_claim(claim: str, config: MergedConfig) -> str:
    """Stage 1: Normalize a claim into precise falsifiable language.

    Converts vague, loaded, or emotional language into a specific factual
    proposition. Never splits. Never refuses. Always returns one claim.

    Args:
        claim: Raw claim or question from user input.
        config: MergedConfig providing Groq credentials.

    Returns:
        Normalized claim string. Returns original claim on failure.
    """
    raw = _call_groq(_NORMALIZER_PROMPT, claim, config, max_tokens=256)
    if not raw:
        logger.warning("Normalizer returned empty for: %r - using original", claim)
        return claim
    normalized = raw.strip('"\' ')
    if not normalized:
        return claim
    logger.info("Normalized: %r -> %r", claim, normalized)
    return normalized


def decompose_claim(normalized: str, config: MergedConfig) -> list[str]:
    """Stage 2: Decompose a normalized claim into independent subclaims if warranted.

    Applies the decomposition gate: only decomposes when subclaims are genuinely
    independent, have potentially different truth values, and contribute distinct
    evidence. Returns the claim unchanged if decomposition adds no value.

    Args:
        normalized: The normalized claim from Stage 1.
        config: MergedConfig providing Groq credentials.

    Returns:
        List of 1-3 subclaim strings. Single-item list means no decomposition.
    """
    raw = _call_groq(_DECOMPOSER_PROMPT, normalized, config, max_tokens=512)
    result = _parse_json_list(raw, fallback=normalized)
    if len(result) == 1 and result[0] == normalized:
        logger.info("Decomposer: no decomposition warranted for: %r", normalized)
    else:
        logger.info("Decomposed into %d subclaim(s): %s", len(result), result)
    return result


def process_claim(claim: str, config: MergedConfig) -> list[str]:
    """Full two-stage pipeline: normalize then decompose.

    This is the public interface called by agent.py.

    Args:
        claim: Raw claim or question from user input.
        config: MergedConfig providing Groq credentials.

    Returns:
        List of 1-3 verified subclaim strings ready for search and verification.
    """
    normalized = normalize_claim(claim, config)
    return decompose_claim(normalized, config)