"""
Interactive launcher for the Fact-Checker.
Run with: python run.py
Double-click launcher: launcher.bat
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"

BANNER = """
============================================================
  FACT-CHECKER  |  Powered by Serper + Groq
============================================================"""

MENU = """
What would you like to fact-check?

  [1] Paste text or claims directly
  [2] Enter a URL to fetch and check
  [3] Load from a text file
  [4] API Key Settings
  [5] Quit

Enter choice (1-5): """

API_KEY_INFO = """
============================================================
  WHERE TO GET FREE API KEYS
============================================================

  GROQ API KEY (required - free, no credit card needed)
  ---------------------------------------------------------
  1. Go to: https://console.groq.com
  2. Sign up with email or Google
  3. Click "API Keys" in the left sidebar
  4. Click "Create API Key"
  5. Copy the key (starts with gsk_...)
  Free tier: 14,400 requests/day on llama-3.3-70b-versatile

  SERPER API KEY (required - free, no credit card needed)
  ---------------------------------------------------------
  1. Go to: https://serper.dev
  2. Sign up with email or Google
  3. Your API key is shown on the dashboard immediately
  4. Copy the key
  Free tier: 2,500 searches/month

============================================================
"""


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _read_env() -> dict[str, str]:
    """Read current .env file into a dict."""
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _write_env(env: dict[str, str]) -> None:
    """Write dict back to .env file."""
    lines = [
        f"GROQ_API_KEY={env.get('GROQ_API_KEY', '')}",
        f"GROQ_MODEL={env.get('GROQ_MODEL', 'llama-3.3-70b-versatile')}",
        f"SERPER_API_KEY={env.get('SERPER_API_KEY', '')}",
        f"LOG_LEVEL={env.get('LOG_LEVEL', 'INFO')}",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _keys_configured() -> bool:
    """Return True if both required API keys are present and non-empty."""
    env = _read_env()
    return bool(env.get("GROQ_API_KEY")) and bool(env.get("SERPER_API_KEY"))


def _setup_api_keys(first_run: bool = False) -> None:
    """Interactive API key configuration screen."""
    _clear()
    print(BANNER)

    if first_run:
        print("\n  Welcome! Before you can use the Fact-Checker, you need")
        print("  two free API keys. This only takes a few minutes.\n")

    print(API_KEY_INFO)

    env = _read_env()

    # --- Groq key ---
    current_groq = env.get("GROQ_API_KEY", "")
    if current_groq:
        masked = current_groq[:8] + "..." + current_groq[-4:]
        print(f"  Current Groq key: {masked}")
    else:
        print("  Current Groq key: NOT SET")

    groq_input = input("  Enter new Groq API key (or press Enter to keep current): ").strip()
    if groq_input:
        env["GROQ_API_KEY"] = groq_input
        print("  Groq key updated.")
    elif not current_groq:
        print("  [!] Groq key is required.")

    print()

    # --- Serper key ---
    current_serper = env.get("SERPER_API_KEY", "")
    if current_serper:
        masked = current_serper[:4] + "..." + current_serper[-4:]
        print(f"  Current Serper key: {masked}")
    else:
        print("  Current Serper key: NOT SET")

    serper_input = input("  Enter new Serper API key (or press Enter to keep current): ").strip()
    if serper_input:
        env["SERPER_API_KEY"] = serper_input
        print("  Serper key updated.")
    elif not current_serper:
        print("  [!] Serper key is required.")

    print()

    # --- Model selection ---
    current_model = env.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    print(f"  Current model: {current_model}")
    print("  Available models:")
    print("    [1] llama-3.3-70b-versatile  (recommended - best accuracy)")
    print("    [2] llama-3.1-8b-instant     (faster - lower accuracy)")
    print("    [3] Keep current")
    model_choice = input("  Select model (1-3, or Enter to keep current): ").strip()
    match model_choice:
        case "1":
            env["GROQ_MODEL"] = "llama-3.3-70b-versatile"
            print("  Model set to llama-3.3-70b-versatile.")
        case "2":
            env["GROQ_MODEL"] = "llama-3.1-8b-instant"
            print("  Model set to llama-3.1-8b-instant.")
        case _:
            pass

    _write_env(env)
    print("\n  Settings saved.")

    if not _keys_configured():
        print("  [!] Warning: one or more required keys are missing.")
        print("      The fact-checker will not work until both keys are set.")

    _pause()


def _run_checker(args: list[str]) -> None:
    """Invoke the fact-checker CLI and stream output directly to the terminal."""
    cmd = [sys.executable, "-m", "fact_checker.main"] + args
    result = subprocess.run(cmd, check=False)
    if result.returncode not in (0, 130):
        print(f"\n[ERROR] Fact-checker exited with code {result.returncode}")


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
    # Auto-detect single claim to skip screener
    sentences = [s.strip() for s in text.replace("?", ".").replace("!", ".").split(".") if len(s.strip()) > 20]
    if len(sentences) <= 1:
        _run_checker(["--claim", text, "--output", "report", "--no-screen"])
    else:
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
    # First run check - show setup if keys are missing
    if not _keys_configured():
        _setup_api_keys(first_run=True)

    while True:
        _clear()
        print(BANNER)
        choice = input(MENU).strip()

        match choice:
            case "1":
                _clear()
                _choice_paste()
            case "2":
                _clear()
                _choice_url()
            case "3":
                _clear()
                _choice_file()
            case "4":
                _setup_api_keys(first_run=False)
            case "5":
                print("\nGoodbye.\n")
                sys.exit(0)
            case _:
                print("[!] Invalid choice.")
                _pause()


if __name__ == "__main__":
    main()
