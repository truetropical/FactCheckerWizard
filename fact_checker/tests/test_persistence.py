from __future__ import annotations

import json
from pathlib import Path

import pytest

from fact_checker.agent import ClaimPair
from fact_checker.persistence import write_session, render_console_report
from fact_checker.verifier import VerificationResult


def _make_result(claim: str, verdict: str = "Supported") -> VerificationResult:
    return VerificationResult(
        claim=claim,
        verdict=verdict,  # type: ignore[arg-type]
        confidence=0.95,
        sources=["https://example.com"],
        reasoning="Test reasoning.",
        grounding_used=False,
        error=None,
    )


def _make_pair(original: str, subclaims: list[str] | None = None) -> ClaimPair:
    if subclaims is None:
        subclaims = [original]
    return ClaimPair(
        original_claim=original,
        subclaims=subclaims,
        original_result=_make_result(original),
        subclaim_results=[_make_result(sc) for sc in subclaims],
    )


def test_write_session_creates_directory(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    pair = _make_pair("The Eiffel Tower is in Paris, France.")
    session_dir = write_session([pair], config)
    assert session_dir.exists()
    assert session_dir.is_dir()


def test_write_session_creates_json(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    pair = _make_pair("The Eiffel Tower is in Paris, France.")
    session_dir = write_session([pair], config)
    json_file = session_dir / "session.json"
    assert json_file.exists()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["original_claim"] == pair.original_claim
    assert data[0]["original_result"]["verdict"] == "Supported"


def test_write_session_creates_markdown(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    pair = _make_pair("The Eiffel Tower is in Paris, France.")
    session_dir = write_session([pair], config)
    md_file = session_dir / "report.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "Fact-Check Report" in content
    assert "Supported" in content


def test_write_session_unique_dirs(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    pair = _make_pair("The Eiffel Tower is in Paris, France.")
    dir1 = write_session([pair], config)
    dir2 = write_session([pair], config)
    assert dir1 != dir2


def test_write_session_empty_results(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    session_dir = write_session([], config)
    json_file = session_dir / "session.json"
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data == []


def test_render_console_shows_subclaims(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    pair = _make_pair(
        "X is corrupt.",
        subclaims=[
            "X has engaged in illegal conduct for personal gain.",
            "X has been formally investigated for corruption.",
        ],
    )
    report = render_console_report([pair])
    assert "ORIGINAL CLAIM" in report
    assert "SUBCLAIM 1" in report
    assert "SUBCLAIM 2" in report
