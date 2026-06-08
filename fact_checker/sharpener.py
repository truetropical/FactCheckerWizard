from __future__ import annotations

import logging

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)

_SHARPENER_SYSTEM_PROMPT = """\
You are a claim precision editor. Your sole task is to rewrite a vague, \
ambiguous, or unfalsifiable claim into its most precise, empirically \
falsifiable form without changing its core meaning or intent.

Rules:
- The rewritten claim must be checkable against peer-reviewed literature, \
  official statistics, or documented historical record
- Do not add information that was not implied by the original claim
- Do not make the claim easier or harder to verify, only make it more precise
- If the original claim is about proof or evidence, keep it about proof or evidence
- If the original claim is metaphysical or philosophical and cannot be made \
  falsifiable, return it unchanged
- Return ONLY the rewritten claim with no explanation, no preamble, no quotes
"""


def sharpen_claim(claim: str, config: MergedConfig) -> str:
    """Rewrite a claim into its most precise, falsifiable form using Groq.

    Args:
        claim: The original claim as extracted from user input.
        config: MergedConfig providing Groq credentials and model name.

    Returns:
        The sharpened claim string. Returns the original claim unchanged
        if sharpening fails or produces an empty response.
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
                    {"role": "system", "content": _SHARPENER_SYSTEM_PROMPT},
                    {"role": "user", "content": claim},
                ],
                "temperature": 0.0,
                "max_tokens": 256,
            },
            timeout=httpx.Timeout(30.0),
        )
        response.raise_for_status()
        data = response.json()
        sharpened: str = data["choices"][0]["message"]["content"].strip()
        if not sharpened:
            logger.warning("Sharpener returned empty response for claim: %r", claim)
            return claim
        logger.info("Sharpened: %r", sharpened)
        return sharpened
    except (httpx.HTTPError, httpx.TimeoutException, KeyError, IndexError, ValueError) as exc:
        logger.warning("Claim sharpening failed for %r: %s - using original", claim, exc)
        return claim
