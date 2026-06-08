from __future__ import annotations

import pytest

from fact_checker.extractor import extract_claims


def test_extract_single_claim() -> None:
    text = "The Eiffel Tower is located in Paris, France."
    claims = extract_claims(text)
    assert len(claims) == 1
    assert claims[0] == "The Eiffel Tower is located in Paris, France."


def test_extract_multiple_claims() -> None:
    text = "Water boils at 100 degrees Celsius. The moon orbits the Earth. Penguins live in Antarctica."
    claims = extract_claims(text)
    assert len(claims) == 3


def test_empty_input_returns_empty() -> None:
    assert extract_claims("") == []


def test_whitespace_only_returns_empty() -> None:
    assert extract_claims("   \n\t  ") == []


def test_short_fragments_filtered() -> None:
    # Each fragment is under _MIN_CLAIM_LENGTH (20 chars)
    text = "Yes. No. Ok. Sure."
    claims = extract_claims(text)
    assert claims == []


def test_max_claims_cap() -> None:
    # Generate 15 sentences — should be capped at 10
    sentences = [f"This is verifiable factual sentence number {i}." for i in range(15)]
    text = " ".join(sentences)
    claims = extract_claims(text)
    assert len(claims) == 10


def test_mixed_punctuation() -> None:
    text = "Is the sky blue? Yes, the sky is blue! Scientists confirm this fact."
    claims = extract_claims(text)
    assert len(claims) >= 2
