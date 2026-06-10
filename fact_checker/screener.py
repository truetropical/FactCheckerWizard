from __future__ import annotations

import json
import logging

import httpx

from fact_checker.config import GROQ_API_URL, MergedConfig

logger = logging.getLogger(__name__)

_PASS1_PROMPT = 'You are a fact-checking claim screener.\nYou receive a numbered list of sentences extracted from a text.\nSelect sentences that are ALREADY self-contained and independently verifiable WITHOUT needing any surrounding context.\n\nA sentence qualifies ONLY if ALL of these are true:\n1. It makes a specific, falsifiable factual assertion\n2. It can be verified independently using public sources AS WRITTEN\n3. It is a single atomic claim - not a compound of multiple facts\n4. It contains concrete specifics: names, numbers, dates, places, or documented events\n5. It is not opinion, commentary, transition, background, or context\n6. It has a clear, named subject - not a pronoun or vague noun like \'the country\', \'the government\', \'the fund\', \'he\', \'it\', \'they\'\n\nREJECT:\n- Opinions (many believe, critics say, experts think)\n- Vague assertions (the economy is struggling, things are getting worse)\n- Sentences with unnamed or ambiguous subjects\n- Transitions and connectors\n- Background or context sentences\n- Compound claims (contains two independent facts joined by a comma or \'and\')\n\nPRIORITY ORDER:\n1. Most specific and measurable (statistics, percentages, named events with dates)\n2. Most likely to be disputed or misinformation\n3. Most significant impact if false\n\nReturn up to 5 qualifying sentences in priority order.\nIf fewer than 5 qualify, return only those that qualify.\nIf none qualify, return an empty array.\n\nOUTPUT FORMAT - return ONLY a JSON array of strings, no preamble:\n["sentence one", "sentence two"]\n\nCopy sentences EXACTLY as they appear. Do not rewrite them.'
_PASS2_PROMPT = 'You are a fact-checking claim screener.\nPass 1 screening found fewer than 5 self-contained verifiable claims.\nYou now receive the FULL SOURCE TEXT and a list of REMAINING sentences that were not selected in Pass 1.\n\nYour task: identify sentences that WOULD be verifiable if their missing subject were inferred from the source text, and rewrite them with the correct subject added.\n\nA sentence qualifies for Pass 2 ONLY if:\n1. It contains a specific measurable fact (number, percentage, date, named event)\n2. Its subject can be unambiguously identified from the source text\n3. Once rewritten with the correct subject, it becomes independently verifiable\n4. It is not opinion, commentary, or transition\n\nREWRITING RULES:\n- Replace vague subjects (the country, it, they, the government, the fund) with the specific named entity from the source text\n- Do not add any other information\n- Do not change numbers, percentages, or dates\n- Keep the rewrite as close to the original as possible\n\nReturn ONLY the sentences needed to reach a total of SLOTS_NEEDED more claims.\nIf none qualify, return an empty array.\n\nOUTPUT FORMAT - return ONLY a JSON array of rewritten strings, no preamble:\n["rewritten sentence one", "rewritten sentence two"]'

_MAX_CLAIMS: int = 5


def _groq_call(
    prompt: str,
    user_message: str,
    config: MergedConfig,
) -> list[str]:
    """Make a single Groq call and parse the JSON list response."""
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
            return []

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
            return []
        return [s.strip() for s in result if isinstance(s, str) and s.strip()]

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Screener network error: %s", exc)
        return []
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        logger.warning("Screener parse error: %s", exc)
        return []


def screen_claims(
    sentences: list[str],
    config: MergedConfig,
    source_text: str = "",
) -> list[str]:
    """Filter and rank sentences to find the top 5 fact-checkable claims.

    Two-pass approach:
    Pass 1: Select self-contained, independently verifiable sentences (copy exactly).
    Pass 2: Only if Pass 1 found fewer than 5, consider sentences needing context
            inference. Rewrite with inferred subject from source text.

    Args:
        sentences: Raw sentences from extractor.py.
        config: MergedConfig providing Groq credentials.
        source_text: Original full text for context inference in Pass 2.

    Returns:
        List of up to 5 claim strings ready for verification.
        Returns original list (capped at 5) on failure.
    """
    if not sentences:
        return []

    if len(sentences) <= 2:
        logger.info("Screener: only %d sentence(s) - skipping screening", len(sentences))
        return sentences[:_MAX_CLAIMS]

    # --- Pass 1: self-contained claims ---
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    pass1_message = (
        f"Screen these sentences and return the top {_MAX_CLAIMS} "
        f"self-contained fact-checkable claims:\n\n{numbered}"
    )

    pass1_results = _groq_call(_PASS1_PROMPT, pass1_message, config)
    pass1_results = pass1_results[:_MAX_CLAIMS]

    logger.info(
        "Screener Pass 1: %d sentences -> %d self-contained claim(s)",
        len(sentences),
        len(pass1_results),
    )

    if len(pass1_results) >= _MAX_CLAIMS:
        return pass1_results

    # --- Pass 2: context-inferred claims ---
    slots_needed = _MAX_CLAIMS - len(pass1_results)
    logger.info(
        "Screener Pass 2: need %d more claim(s) - checking remaining sentences",
        slots_needed,
    )

    # Exclude sentences already selected in Pass 1
    selected_set = set(pass1_results)
    remaining = [s for s in sentences if s not in selected_set]

    if not remaining or not source_text:
        logger.info("Screener Pass 2: no remaining sentences or no source text")
        return pass1_results

    remaining_numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(remaining))
    context = source_text[:3000].strip()
    pass2_prompt = _PASS2_PROMPT.replace("SLOTS_NEEDED", str(slots_needed))
    pass2_message = (
        f"SOURCE TEXT:\n{context}\n\n"
        f"REMAINING SENTENCES (not yet selected):\n{remaining_numbered}\n\n"
        f"Return up to {slots_needed} rewritten claim(s) with inferred subjects."
    )

    pass2_results = _groq_call(pass2_prompt, pass2_message, config)
    pass2_results = pass2_results[:slots_needed]

    logger.info(
        "Screener Pass 2: %d additional claim(s) found",
        len(pass2_results),
    )

    final = pass1_results + pass2_results
    logger.info("Screener total: %d claim(s) selected", len(final))
    return final
