from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from fact_checker.config import MergedConfig
from fact_checker.utils import make_timestamp
from fact_checker.verifier import VerificationResult

if TYPE_CHECKING:
    from fact_checker.agent import ClaimPair

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verdict_emoji(verdict: str) -> str:
    match verdict:
        case "Supported":
            return "Supported"
        case "Refuted":
            return "Refuted"
        case _:
            return "Inconclusive"


def _result_to_dict(result: VerificationResult) -> dict[str, object]:
    return dataclasses.asdict(result)


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------


def render_console_report(pairs: list[ClaimPair]) -> str:
    if not pairs:
        return "No claims were verified."

    sections: list[str] = []
    sections.append("=" * 70)
    sections.append("FACT-CHECK REPORT")
    sections.append(f"Claims checked: {len(pairs)}")
    sections.append("=" * 70)

    for i, pair in enumerate(pairs, start=1):
        r_orig = pair.original_result
        r_sharp = pair.sharpened_result
        same_claim = pair.original_claim == pair.sharpened_claim

        section: list[str] = []
        section.append(f"\nCLAIM {i} OF {len(pairs)}")
        section.append("")
        section.append("ORIGINAL CLAIM:")
        section.append(f"  {pair.original_claim}")
        section.append("")
        section.append(f"  Verdict:    {r_orig.verdict}")
        section.append(f"  Confidence: {r_orig.confidence:.0%}")
        section.append(f"  Reasoning:  {r_orig.reasoning}")
        if r_orig.sources:
            section.append("  Sources:")
            for url in r_orig.sources:
                section.append(f"    - {url}")
        if r_orig.error:
            section.append(f"  Error: {r_orig.error}")

        section.append("")

        if same_claim:
            section.append("SHARPENED CLAIM: (unchanged - already precise or unfalsifiable)")
        else:
            section.append("SHARPENED CLAIM:")
            section.append(f"  {pair.sharpened_claim}")
            section.append("")
            section.append(f"  Verdict:    {r_sharp.verdict}")
            section.append(f"  Confidence: {r_sharp.confidence:.0%}")
            section.append(f"  Reasoning:  {r_sharp.reasoning}")
            if r_sharp.sources:
                section.append("  Sources:")
                for url in r_sharp.sources:
                    section.append(f"    - {url}")
            if r_sharp.error:
                section.append(f"  Error: {r_sharp.error}")

        section.append("\n" + "-" * 70)
        sections.append("\n".join(section))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _render_markdown(pairs: list[ClaimPair]) -> str:
    lines: list[str] = [
        "# Fact-Check Report",
        "",
        f"**Claims checked:** {len(pairs)}",
        "",
        "---",
        "",
    ]

    for i, pair in enumerate(pairs, start=1):
        r_orig = pair.original_result
        r_sharp = pair.sharpened_result
        same_claim = pair.original_claim == pair.sharpened_claim

        lines += [f"## Claim {i}", ""]
        lines += [
            "### Original Claim",
            "",
            f"> {pair.original_claim}",
            "",
            f"**Verdict:** {r_orig.verdict}  ",
            f"**Confidence:** {r_orig.confidence:.0%}  ",
            "",
            f"**Reasoning:** {r_orig.reasoning}",
            "",
        ]
        if r_orig.sources:
            lines.append("**Sources:**")
            for url in r_orig.sources:
                lines.append(f"- {url}")
            lines.append("")

        if same_claim:
            lines += ["### Sharpened Claim", "", "*(unchanged - already precise)*", ""]
        else:
            lines += [
                "### Sharpened Claim",
                "",
                f"> {pair.sharpened_claim}",
                "",
                f"**Verdict:** {r_sharp.verdict}  ",
                f"**Confidence:** {r_sharp.confidence:.0%}  ",
                "",
                f"**Reasoning:** {r_sharp.reasoning}",
                "",
            ]
            if r_sharp.sources:
                lines.append("**Sources:**")
                for url in r_sharp.sources:
                    lines.append(f"- {url}")
                lines.append("")

        lines += ["---", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Session writer
# ---------------------------------------------------------------------------


def write_session(
    pairs: list[ClaimPair],
    config: MergedConfig,
) -> Path:
    timestamp = make_timestamp()
    session_dir = config.sessions_dir / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(session_dir, 0o700)

    json_path = session_dir / "session.json"
    payload = [
        {
            "original_claim": p.original_claim,
            "sharpened_claim": p.sharpened_claim,
            "original_result": _result_to_dict(p.original_result),
            "sharpened_result": _result_to_dict(p.sharpened_result),
        }
        for p in pairs
    ]
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote JSON report: %s", json_path)

    md_path = session_dir / "report.md"
    md_path.write_text(_render_markdown(pairs), encoding="utf-8")
    logger.info("Wrote Markdown report: %s", md_path)

    return session_dir
