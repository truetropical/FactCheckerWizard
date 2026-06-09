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
        section: list[str] = []
        section.append(f"\nCLAIM {i} OF {len(pairs)}")
        section.append("")

        # --- Original ---
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

        # --- Subclaims ---
        if pair.subclaim_results:
            single = (
                len(pair.subclaims) == 1
                and pair.subclaims[0] == pair.original_claim
            )
            if single:
                section.append("")
                section.append("SUBCLAIMS: (claim was already precise - no decomposition needed)")
            else:
                for j, (sc, sc_result) in enumerate(
                    zip(pair.subclaims, pair.subclaim_results), start=1
                ):
                    section.append("")
                    section.append(f"SUBCLAIM {j}:")
                    section.append(f"  {sc}")
                    section.append("")
                    section.append(f"  Verdict:    {sc_result.verdict}")
                    section.append(f"  Confidence: {sc_result.confidence:.0%}")
                    section.append(f"  Reasoning:  {sc_result.reasoning}")
                    if sc_result.sources:
                        section.append("  Sources:")
                        for url in sc_result.sources:
                            section.append(f"    - {url}")
                    if sc_result.error:
                        section.append(f"  Error: {sc_result.error}")

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

        single = (
            len(pair.subclaims) == 1
            and pair.subclaims[0] == pair.original_claim
        )
        if single:
            lines += ["### Subclaims", "", "*(already precise - no decomposition needed)*", ""]
        else:
            lines.append("### Subclaims")
            lines.append("")
            for j, (sc, sc_result) in enumerate(
                zip(pair.subclaims, pair.subclaim_results), start=1
            ):
                lines += [
                    f"#### Subclaim {j}",
                    "",
                    f"> {sc}",
                    "",
                    f"**Verdict:** {sc_result.verdict}  ",
                    f"**Confidence:** {sc_result.confidence:.0%}  ",
                    "",
                    f"**Reasoning:** {sc_result.reasoning}",
                    "",
                ]
                if sc_result.sources:
                    lines.append("**Sources:**")
                    for url in sc_result.sources:
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
            "subclaims": p.subclaims,
            "original_result": _result_to_dict(p.original_result),
            "subclaim_results": [_result_to_dict(r) for r in p.subclaim_results],
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
