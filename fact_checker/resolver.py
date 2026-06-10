from __future__ import annotations

import json
import logging

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)

_RESOLVER_PROMPT = 'You are a fact-checking context resolver. You receive the original source text and a list of claims extracted from it. Some claims contain ambiguous references such as pronouns or vague nouns that lose their meaning when read without the surrounding text.\n\nAMBIGUOUS REFERENCES TO RESOLVE:\n- Pronouns: he, she, they, it, his, her, their, its\n- Vague nouns: the country, the government, the company, the fund, the president, the minister, the agency, the city, the region, the organization, the law, the act\n- Demonstratives: this, that, these, those (when used as subject or object)\n- Relative references: the former, the latter, the same, the other\n\nRULES:\n- Replace each ambiguous reference with the specific named entity from the source text\n- Do not change any other part of the claim\n- Do not add information that is not present in the source text\n- If a claim has no ambiguous references, return it exactly unchanged\n- If the referent cannot be determined from the source text, return the claim unchanged\n- Preserve all numbers, dates, percentages, and proper nouns exactly as written\n\nOUTPUT FORMAT - return ONLY a JSON array of resolved claim strings in the same order as the input claims, no preamble, no explanation:\n["resolved claim one", "resolved claim two"]'


def resolve_references(
    source_text: str,
    claims: list[str],
    config: MergedConfig,
) -> list[str]:
    """Resolve ambiguous references in claims using the original source text as context.

    Args:
        source_text: The original full text submitted by the user.
        claims: List of selected claims from the screener.
        config: MergedConfig providing Groq credentials.

    Returns:
        List of claims with ambiguous references resolved.
        Returns original claims unchanged on any failure.
    """
    if not claims:
        return []

    numbered_claims = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
    context = source_text[:3000].strip()

    user_message = (
        f"SOURCE TEXT (for context only):\n{context}\n\n"
        f"CLAIMS TO RESOLVE:\n{numbered_claims}"
    )

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
                    {"role": "system", "content": _RESOLVER_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.0,
                "max_tokens": 1024,
            },
            timeout=httpx.Timeout(30.0),
        )
        response.raise_for_status()
        data = response.json()
        raw: str = data["choices"][0]["message"]["content"].strip()

        if not raw:
            logger.warning("Resolver returned empty response - using original claims")
            return claims

        if "`" in raw:
            parts = raw.split("`")
            for part in parts:
                if part.startswith("json"):
                    part = part[4:]
                part = part.strip()
                if part.startswith("["):
                    raw = part
                    break

        result: list[str] = json.loads(raw)

        if not isinstance(result, list) or len(result) != len(claims):
            logger.warning(
                "Resolver returned %d items for %d claims - using original claims",
                len(result) if isinstance(result, list) else 0,
                len(claims),
            )
            return claims

        resolved = [
            r.strip() if isinstance(r, str) and r.strip() else claims[i]
            for i, r in enumerate(result)
        ]

        for orig, res in zip(claims, resolved):
            if orig != res:
                logger.info("Resolved: %r -> %r", orig, res)
            else:
                logger.debug("Unchanged: %r", orig)

        return resolved

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Resolver network error: %s - using original claims", exc)
        return claims
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        logger.warning("Resolver parse error: %s - using original claims", exc)
        return claims
