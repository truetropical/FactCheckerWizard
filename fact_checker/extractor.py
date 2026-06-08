from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum character length for a sentence to be considered a claim candidate
_MIN_CLAIM_LENGTH: int = 20

# Maximum number of claims to extract per input text
_MAX_CLAIMS: int = 10


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_claims(text: str) -> list[str]:
    """Extract a list of discrete, verifiable factual claims from raw text.

    Strategy:
    - Split on sentence boundaries (. ! ?)
    - Filter out fragments that are too short to be meaningful
    - Strip excess whitespace
    - Cap at _MAX_CLAIMS to keep downstream API costs bounded

    Args:
        text: Raw input text supplied by the user or pipeline.

    Returns:
        A list of claim strings, each representing one verifiable assertion.
        Returns an empty list if no valid claims are found.
    """
    if not text or not text.strip():
        logger.warning("extract_claims received empty or whitespace-only input")
        return []

    # Split on sentence-ending punctuation followed by whitespace or end-of-string
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    claims: list[str] = []
    for sentence in raw_sentences:
        cleaned = sentence.strip()
        if len(cleaned) >= _MIN_CLAIM_LENGTH:
            claims.append(cleaned)
        else:
            logger.debug("Skipping short fragment: %r", cleaned)

    if not claims:
        logger.warning("No claims extracted from input text")
        return []

    if len(claims) > _MAX_CLAIMS:
        logger.warning(
            "Extracted %d claims — truncating to %d", len(claims), _MAX_CLAIMS
        )
        claims = claims[:_MAX_CLAIMS]

    logger.info("Extracted %d claim(s)", len(claims))
    return claims
