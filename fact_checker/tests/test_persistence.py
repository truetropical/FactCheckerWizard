from __future__ import annotations

import json
from pathlib import Path

import pytest

from fact_checker.persistence import write_session
from fact_checker.verifier import VerificationResult


def test_write_session_creates_directory(
    config: object,
    sample_verification_result: VerificationResult,
    tmp_path: Path,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    session_dir = write_session([sample_verification_result], config)
    assert session_dir.exists()
    assert session_dir.is_dir()


def test_write_session_creates_json(
    config: object,
    sample_verification_result: VerificationResult,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    session_dir = write_session([sample_verification_result], config)
    json_file = session_dir / "session.json"
    assert json_file.exists()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["verdict"] == "Supported"
    assert data[0]["claim"] == sample_verification_result.claim


def test_write_session_creates_markdown(
    config: object,
    sample_verification_result: VerificationResult,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    session_dir = write_session([sample_verification_result], config)
    md_file = session_dir / "report.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "Fact-Check Report" in content
    assert "Supported" in content
    assert sample_verification_result.claim in content


def test_write_session_unique_dirs(
    config: object,
    sample_verification_result: VerificationResult,
) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    dir1 = write_session([sample_verification_result], config)
    dir2 = write_session([sample_verification_result], config)
    assert dir1 != dir2


def test_write_session_empty_results(config: object) -> None:
    from fact_checker.config import MergedConfig
    assert isinstance(config, MergedConfig)
    session_dir = write_session([], config)
    json_file = session_dir / "session.json"
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data == []
