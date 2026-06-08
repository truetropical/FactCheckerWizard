"""
Interactive launcher for the Fact-Checker.
Run with: python run.py
Double-click launcher: launcher.bat
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path


BANNER = """
============================================================
  FACT-CHECKER  |  Powered by Serper + Groq
============================================================
"""

MENU = """
What would you like to fact-check?

  [1] Paste text or claims directly
  [2] Enter a URL to fetch and check
  [3] Load from a text file
  [4] Quit

Enter choice (1-4): """


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _run_checker(args: list[str]) -> None:
    """Invoke the fact-checker CLI and stream output directly to the terminal."""
    cmd = [sys.executable, "-m", "fact_checker.main"] + args
    # stderr goes to terminal so progress is visible; stdout is the report
    result = subprocess.run(cmd, check=False)
    if result.returncode not in (0, 130):
        print(f"\n[ERROR] Fact-checker exited with code {result.returncode}")


def _pause() -> None:
    input("\nPress Enter to return to the menu...")


def _choice_paste() -> None:
    print("\nPaste your text below.")
    print("When done, enter a single dot (.) on a new line and press Enter.\n")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".":
            break
        lines.append(line)

    text = "\n".join(lines).strip()
    if not text:
        print("[!] No text entered.")
        _pause()
        return

    _run_checker(["--claim", text, "--output", "report"])
    _pause()


def _choice_url() -> None:
    url = input("\nEnter URL: ").strip()
    if not url:
        print("[!] No URL entered.")
        _pause()
        return
    if not url.startswith(("http://", "https://")):
        print("[!] URL must start with http:// or https://")
        _pause()
        return
    _run_checker(["--url", url, "--output", "report"])
    _pause()


def _choice_file() -> None:
    path = input("\nEnter file path: ").strip().strip('"')
    if not Path(path).exists():
        print(f"[!] File not found: {path}")
        _pause()
        return
    _run_checker(["--file", path, "--output", "report"])
    _pause()


def main() -> None:
    while True:
        _clear()
        print(BANNER)
        choice = input(MENU).strip()

        match choice:
            case "1":
                _choice_paste()
            case "2":
                _choice_url()
            case "3":
                _choice_file()
            case "4":
                print("\nGoodbye.\n")
                sys.exit(0)
            case _:
                print("[!] Invalid choice.")
                _pause()


if __name__ == "__main__":
    main()
