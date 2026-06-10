from __future__ import annotations

import json
import logging

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)

_SCREENER_PROMPT = (
    "You are a fact-checking claim screener. "
    "You receive a list of sentences extracted from a text. "
    "Your task is to identify and return the best candidates for fact-checking.\n\n"
    "SELECTION RULES - a sentence qualifies ONLY if ALL of these are true:\n"
    "1. It makes a specific, falsifiable factual assertion\n"
    "2. It can be verified independently using public sources\n"
    "3. It is a single atomic claim - not a compound of multiple facts\n"
    "4. It contains concrete specifics: names, numbers, dates, places, or documented events\n"
    "5. It is not opinion, commentary, transition, background, or context\n\n"
    "REJECT these types:\n"
    "- Opinions and editorials (e.g. many believe, critics say, it seems)\n"
    "- Vague assertions without specifics (e.g. the economy is struggling)\n"
    "- Transition sentences (e.g. however, meanwhile, in addition)\n"
    "- Quotes without verifiable attribution\n"
    "- Background or historical context sentences\n"
    "- Sentences that are components of a larger claim already in the list\n\n"
    "PRIORITY ORDER - rank qualifying sentences by:\n"
    "1. Most specific and measurable (statistics, percentages, named events)\n"
    "2. Most likely to be disputed or misinformation\n"
    "3. Most significant impact if false\n\n"
    "Return ONLY the top 5 qualifying sentences in priority order. "
    "If fewer than 5 qualify, return only those that qualify. "
    "If none qualify, return an empty array.\n\n"
    "OUTPUT FORMAT - return ONLY a JSON array of strings, no preamble, no explanation:\n"
    '["sentence one", "sentence two"]\n\n'
    "Copy the sentences EXACTLY as they appear in the input. Do not rewrite them."
)


def screen_claims(sentences: list[str], config: MergedConfig) -> list[str]:
    """Filter and rank sentences to find the top 5 fact-checkable claims.

    Sends all extracted sentences to Groq in a single call. Returns only
    those that are specific, atomic, and independently verifiable.

    Args:
        sentences: Raw sentences from extractor.py.
        config: MergedConfig providing Groq credentials.

    Returns:
        List of up to 5 sentences selected for fact-checking.
        Returns original list (capped at 5) on failure.
    """
    if not sentences:
        return []

    if len(sentences) <= 2:
        logger.info("Screener: only %d sentence(s) - skipping screening", len(sentences))
        return sentences[:5]

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    user_message = f"Screen these sentences and return the top 5 fact-checkable claims:\n\n{numbered}"

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
                    {"role": "system", "content": _SCREENER_PROMPT},
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
            logger.warning("Screener returned empty response - using original sentences")
            return sentences[:5]

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

        if not isinstance(result, list):
            logger.warning("Screener returned non-list - using original sentences")
            return sentences[:5]

        cleaned = [s.strip() for s in result if isinstance(s, str) and s.strip()][:5]

        if not cleaned:
            logger.warning("Screener returned no qualifying claims - using original sentences")
            return sentences[:5]

        logger.info(
            "Screener: %d sentences -> %d qualifying claim(s)",
            len(sentences),
            len(cleaned),
        )
        return cleaned

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Screener network error: %s - using original sentences", exc)
        return sentences[:5]
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        logger.warning("Screener parse error: %s - using original sentences", exc)
        return sentences[:5]
