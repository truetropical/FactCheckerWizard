from __future__ import annotations

import argparse
import asyncio
import json
import sys

from fact_checker.agent import Agent, ClaimPair
from fact_checker.config import ConfigError, load_config
from fact_checker.fetcher import FetchError, fetch_url_text
from fact_checker.persistence import render_console_report


def _pair_to_dict(p: ClaimPair) -> dict[str, object]:
    return {
        "original_claim": p.original_claim,
        "sharpened_claim": p.sharpened_claim,
        "original_verdict": p.original_result.verdict,
        "original_confidence": p.original_result.confidence,
        "original_reasoning": p.original_result.reasoning,
        "original_sources": p.original_result.sources,
        "sharpened_verdict": p.sharpened_result.verdict,
        "sharpened_confidence": p.sharpened_result.confidence,
        "sharpened_reasoning": p.sharpened_result.reasoning,
        "sharpened_sources": p.sharpened_result.sources,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fact-checker",
        description="Verify factual claims using Serper + Groq.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--claim", metavar="TEXT",
                       help="One or more sentences containing claims to verify.")
    group.add_argument("--file", metavar="PATH",
                       help="Path to a plain-text file whose contents will be verified.")
    group.add_argument("--url", metavar="URL",
                       help="URL of a web page or post to fetch and fact-check.")
    parser.add_argument(
        "--output", choices=["json", "report", "file"], default="report",
        help="report: human-readable (default). json: structured JSON. file: session path only.",
    )
    return parser


async def _load_text(args: argparse.Namespace) -> str:
    if args.claim:
        return str(args.claim)
    if args.url:
        print(f"Fetching URL: {args.url}", file=sys.stderr, flush=True)
        try:
            return await fetch_url_text(args.url)
        except FetchError as exc:
            print(f"Error fetching URL: {exc}", file=sys.stderr)
            sys.exit(1)
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

    text = await _load_text(args)
    agent = Agent(config)
    pairs = await agent.run(text)

    match args.output:
        case "report":
            print(render_console_report(pairs))
        case "json":
            print(json.dumps([_pair_to_dict(p) for p in pairs], indent=2,
                             ensure_ascii=False))
        case "file":
            pass


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
