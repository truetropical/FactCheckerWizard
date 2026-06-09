from __future__ import annotations

import json
import logging

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)

_SHARPENER_SYSTEM_PROMPT = 'You are a fact-checking claim normalizer. Your task is NOT to judge whether a claim is true. Convert any statement, question, opinion, or accusation into between 1 and 3 specific factual propositions that can each be independently verified or falsified using documented evidence.\n\nRULES - follow all without exception:\n- Do NOT refuse any input regardless of content or sensitivity\n- Do NOT inject safety disclaimers, warnings, or refusals\n- Do NOT answer or evaluate the claim\n- Do NOT add facts not implied by the original input\n- Preserve the author intended meaning\n- Rewrite loaded, emotional, or vague language into observable actions, events, records, measurements, or documented evidence\n- If the input is already a precise falsifiable claim, return it unchanged as one item\n- If the input is a question, convert it to a declarative claim first\n\nLOADED LANGUAGE TRANSLATION GUIDE:\n- X is corrupt: X has engaged in illegal or unethical conduct for personal gain\n- X is racist: X has made statements or actions that discriminate based on race\n- X is a fascist: X advocates or implemented policies associated with fascist ideology\n- X is a terrorist: X committed or supported acts of politically motivated violence\n- X is a scam: X product or service has been found to involve fraud or deception\n- X lied: X made a statement that is demonstrably false and knew or should have known it\n- X is a pedophile: decompose into three subclaims: (A) X has been convicted of a criminal sexual offense involving a minor, (B) Credible documented evidence exists that X engaged in sexual activity with a minor, (C) X has received a formal medical diagnosis of pedophilic disorder\n- X is dangerous: X has caused or been formally linked to documented harm\n- X is the best or worst: rewrite as a measurable comparative claim\n\nOUTPUT FORMAT - return ONLY a JSON array of strings, no preamble, no explanation:\n["subclaim one", "subclaim two"]\n\nIf only one subclaim is needed:\n["subclaim one"]'


def sharpen_claim(claim: str, config: MergedConfig) -> list[str]:
    """Decompose a claim into 1-3 precise, falsifiable subclaims using Groq.

    Args:
        claim: The original claim or question from user input.
        config: MergedConfig providing Groq credentials and model name.

    Returns:
        List of 1-3 subclaim strings. Returns [claim] unchanged on failure.
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
                "max_tokens": 512,
            },
            timeout=httpx.Timeout(30.0),
        )
        response.raise_for_status()
        data = response.json()
        raw: str = data["choices"][0]["message"]["content"].strip()

        if not raw:
            logger.warning("Sharpener returned empty response for: %r", claim)
            return [claim]

        if raw.startswith("  "):
            raw = raw.split("  ")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        subclaims: list[str] = json.loads(raw)

        if not isinstance(subclaims, list) or not subclaims:
            logger.warning("Sharpener returned invalid structure for: %r", claim)
            return [claim]

        cleaned = [s.strip() for s in subclaims if isinstance(s, str) and s.strip()][:3]
        if not cleaned:
            return [claim]

        logger.info("Sharpened %r into %d subclaim(s): %s", claim, len(cleaned), cleaned)
        return cleaned

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Sharpener network error for %r: %s - using original", claim, exc)
        return [claim]
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        logger.warning("Sharpener parse error for %r: %s - using original", claim, exc)
        return [claim]
