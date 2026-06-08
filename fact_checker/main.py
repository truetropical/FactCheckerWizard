from __future__ import annotations

import argparse
import asyncio
import json
import sys

from fact_checker.agent import Agent
from fact_checker.config import ConfigError, load_config
from fact_checker.verifier import VerificationResult


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _result_to_stdout_dict(r: VerificationResult) -> dict[str, object]:
    return {
        "claim": r.claim,
        "verdict": r.verdict,
        "confidence": r.confidence,
        "grounding_used": r.grounding_used,
        "sources": r.sources,
        "reasoning": r.reasoning,
        "error": r.error,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fact-checker",
        description="Verify factual claims using SearXNG + Gemini grounding.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--claim",
        metavar="TEXT",
        help="One or more sentences containing claims to verify.",
    )
    group.add_argument(
        "--file",
        metavar="PATH",
        help="Path to a plain-text file whose contents will be verified.",
    )
    parser.add_argument(
        "--output",
        choices=["json", "file"],
        default="json",
        help=(
            "json: print structured JSON to stdout (default). "
            "file: print only the session directory path to stdout."
        ),
    )
    return parser


def _load_text(args: argparse.Namespace) -> str:
    if args.claim:
        return str(args.claim)
    try:
        with open(args.file, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"Error reading file '{args.file}': {exc}", file=sys.stderr)
        sys.exit(1)


async def _async_main(args: argparse.Namespace) -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    text = _load_text(args)
    agent = Agent(config)
    results = await agent.run(text)

    if args.output == "file":
        # session_dir already printed to stderr by agent; derive from results
        # The session path was already emitted to stderr — nothing extra needed.
        pass
    else:
        payload = [_result_to_stdout_dict(r) for r in results]
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:  # outermost boundary — user-friendly message only
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
