from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path

from fact_checker.config import MergedConfig
from fact_checker.utils import make_timestamp
from fact_checker.verifier import VerificationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verdict_emoji(verdict: str) -> str:
    match verdict:
        case "Supported":
            return "✅"
        case "Refuted":
            return "❌"
        case _:
            return "⚠️"


def _result_to_dict(result: VerificationResult) -> dict[str, object]:
    return dataclasses.asdict(result)


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------


def render_console_report(results: list[VerificationResult]) -> str:
    """Render a plain-text human-readable report suitable for terminal output."""
    if not results:
        return "No claims were verified."

    sections: list[str] = []
    sections.append("=" * 60)
    sections.append("FACT-CHECK REPORT")
    sections.append(f"Claims checked: {len(results)}")
    sections.append("=" * 60)

    for i, r in enumerate(results, start=1):
        emoji = _verdict_emoji(r.verdict)
        section: list[str] = []
        section.append(f"\nCLAIM {i} OF {len(results)}")
        section.append(f"{r.claim}")
        section.append("")
        section.append(f"Verdict:    {emoji} {r.verdict}")
        section.append(f"Confidence: {r.confidence:.0%}")
        section.append("")
        section.append(f"Reasoning:")
        section.append(f"  {r.reasoning}")

        if r.sources:
            section.append("")
            section.append("Sources:")
            for url in r.sources:
                section.append(f"  - {url}")

        if r.error:
            section.append("")
            section.append(f"Error: {r.error}")

        section.append("\n" + "-" * 60)
        sections.append("\n".join(section))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _render_markdown(results: list[VerificationResult]) -> str:
    lines: list[str] = [
        "# Fact-Check Report",
        "",
        f"**Claims checked:** {len(results)}",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(results, start=1):
        emoji = _verdict_emoji(r.verdict)
        lines += [
            f"## Claim {i}",
            "",
            f"> {r.claim}",
            "",
            f"**Verdict:** {emoji} {r.verdict}  ",
            f"**Confidence:** {r.confidence:.0%}  ",
            f"**Grounding used:** {'Yes' if r.grounding_used else 'No'}  ",
            "",
            f"**Reasoning:** {r.reasoning}",
            "",
        ]

        if r.sources:
            lines.append("**Sources:**")
            for url in r.sources:
                lines.append(f"- {url}")
            lines.append("")

        if r.error:
            lines += [f"**Error:** {r.error}", ""]

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Session writer
# ---------------------------------------------------------------------------


def write_session(
    results: list[VerificationResult],
    config: MergedConfig,
) -> Path:
    timestamp = make_timestamp()
    session_dir = config.sessions_dir / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(session_dir, 0o700)

    json_path = session_dir / "session.json"
    payload = [_result_to_dict(r) for r in results]
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote JSON report: %s", json_path)

    md_path = session_dir / "report.md"
    md_path.write_text(_render_markdown(results), encoding="utf-8")
    logger.info("Wrote Markdown report: %s", md_path)

    return session_dir
