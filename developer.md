# Developer Reference — Fact-Checker

Single source of truth for all architectural decisions.
Last updated: June 2026

---

## 1. Project Overview

A modular, CLI-based fact-checking pipeline that:
1. Accepts claims as typed text, a text file, or a fetched URL
2. Searches for evidence via the Serper API (Google Search)
3. Verifies each claim against evidence using Groq (llama-3.1-8b-instant)
4. Applies a source reliability tier system and domain blacklist
5. Outputs a formatted console report and saves JSON + Markdown session files

---

## 2. Directory Structure
fact_checker/
+-- main.py           # CLI entry point — argparse, stdout/stderr routing
+-- agent.py          # Orchestration — coordinates search, extraction, verification
+-- search.py         # Serper API client — query execution with retry
+-- extractor.py      # Claim extraction from raw text via regex sentence splitting
+-- verifier.py       # Groq verification, source tier policy, blacklist filter
+-- persistence.py    # Session directory creation, JSON + Markdown + console report
+-- fetcher.py        # URL fetching and HTML-to-text extraction via BeautifulSoup
+-- utils.py          # Shared helpers: async_retry decorator, timestamp generation
+-- config.py         # MergedConfig dataclass — loads .env, applies defaults, validates
+-- tests/
+-- conftest.py
+-- test_agent.py
+-- test_extractor.py
+-- test_fetcher.py
+-- test_persistence.py
+-- test_search.py
+-- test_verifier.py
run.py                # Interactive menu launcher
launcher.bat          # Double-click shortcut — activates venv and runs run.py
open_shell.bat        # Double-click shortcut — opens activated PowerShell
sessions/             # Runtime output — auto-created, never committed
.env                  # Secrets — never committed

---

## 3. Technology Stack

| Component | Library / Service | Version |
|---|---|---|
| HTTP client | httpx | 0.28.1 |
| HTML parsing | beautifulsoup4 | 4.12.3 |
| Search API | Serper (google.serper.dev) | REST |
| LLM verification | Groq (llama-3.1-8b-instant) | REST |
| Config loading | python-dotenv | 1.0.1 |
| Testing | pytest + pytest-cov + pytest-asyncio | 8.2.0 |
| Type checking | mypy (strict) | 1.10.0 |
| Formatting | black + isort | 24.4.2 / 5.13.2 |
| Python | CPython | >= 3.10 |

---

## 4. Environment Variables

Stored in .env at project root. Never committed to git.

| Variable | Required | Default | Description |
|---|---|---|---|
| GROQ_API_KEY | Yes | — | Groq API key (console.groq.com) |
| GROQ_MODEL | No | llama-3.1-8b-instant | Groq model name |
| SERPER_API_KEY | Yes | — | Serper API key (serper.dev) |
| SERPER_TIMEOUT | No | 15.0 | Search request timeout (seconds) |
| SERPER_MAX_RETRIES | No | 3 | Max retries per search request |
| SESSIONS_DIR | No | ./sessions | Directory for session output |
| LOG_LEVEL | No | INFO | Python logging level |

Example .env:
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
SERPER_API_KEY=abc123...
LOG_LEVEL=INFO

---

## 5. Pipeline Flow
Input (--claim / --file / --url)
¦
?
fetcher.py          fetch_url_text()       [--url only]
¦
?
extractor.py        extract_claims()       regex sentence split, cap at 10
¦
?
for each claim:
¦
?
search.py       SearchClient.search()  Serper API ? up to 10 results
¦
?
agent.py        _extract_evidence()    interleave URLs + snippets, cap at 5
¦
?
verifier.py     _filter_blacklisted()  remove blacklisted domains
_build_prompt()        build tiered evidence prompt
Verifier.verify_claim() POST to Groq ? parse response
¦
?
VerificationResult (dataclass)
¦
?
persistence.py      write_session()        sessions/<timestamp>/session.json
sessions/<timestamp>/report.md
¦
?
main.py             render_console_report() or JSON ? stdout

---

## 6. Configuration Module (config.py)

load_config() is called once at CLI startup. It:
- Loads .env via python-dotenv
- Validates all required keys — raises ConfigError if absent
- Type-validates float and int fields — raises ConfigError on bad values
- Validates LOG_LEVEL against the allowed set
- Returns a frozen MergedConfig dataclass

ConfigError is a custom exception caught at the outermost CLI boundary in main.py.

Constants defined in config.py:
- GROQ_API_URL — Groq chat completions endpoint
- SERPER_API_URL — Serper search endpoint
- GROQ_MODEL_DEFAULT — fallback model name
- SERPER_TIMEOUT_DEFAULT — 15.0 seconds
- SERPER_MAX_RETRIES_DEFAULT — 3 attempts

---

## 7. Search Module (search.py)

SearchClient wraps the Serper API. Key behaviours:
- initialise() is a no-op (logs readiness) — exists for pipeline symmetry
- _do_search() is decorated with @async_retry(max_attempts=3) from utils.py
- Retry backoff: 1s, 2s, 4s on httpx.HTTPError, httpx.TimeoutException, OSError
- Returns list of dicts with keys: url, content, 	itle
- Returns empty list on total failure — never raises to the caller

---

## 8. Extractor Module (extractor.py)

Pure function — no I/O, no network.

- Splits text on sentence-ending punctuation ([.!?]) followed by whitespace
- Filters fragments shorter than 20 characters
- Caps output at 10 claims to bound downstream API costs
- Returns empty list for empty/whitespace input

---

## 9. Verifier Module (verifier.py)

Central policy enforcement module. Contains:

### VerificationResult dataclass
`python
@dataclass
class VerificationResult:
    claim: str
    verdict: Literal["Supported", "Refuted", "Inconclusive"]
    confidence: float        # 0.0–1.0
    sources: list[str]       # filtered, credible URLs only
    reasoning: str           # objective, cites source tiers
    grounding_used: bool     # always False (Groq has no grounding API)
    error: str | None        # non-None if verification failed
`

### Source Blacklist (_BLACKLISTED_DOMAINS)
Applied in _filter_blacklisted() before building the Groq prompt.
Blocked categories:
- Misinformation outlets (infowars.com, naturalnews.com, etc.)
- Social media (facebook.com, twitter.com, x.com, instagram.com, tiktok.com, reddit.com, etc.)
- Forums (quora.com, 4chan.org)
- Video commentary (youtube.com, youtu.be)
- Messaging platforms (t.me, telegram.me)

Blacklisted sources are logged as warnings and excluded from both the prompt and the sources list in VerificationResult.

### Source Tier System (in _SYSTEM_PROMPT)
Tier A — highest trust:
- Peer-reviewed journals (pubmed, ncbi, nature, science)
- Government agencies (nasa.gov, cdc.gov, who.int)
- Wire services for straight reporting (apnews.com, reuters.com)
- Major encyclopaedias (britannica.com)
- Wikipedia (secondary cross-reference only)

Tier B — conditional:
- Major mainstream outlets (bbc.com, nytimes.com, theguardian.com)
- Straight news reporting only — not opinion/editorial/analysis
- Require cross-verification with at least one Tier A source

Tier C — unreliable (never cited as evidence):
- All blacklisted domains
- AI-generated content
- Personal blogs without citations
- Propaganda outlets

### Verdict Rules (enforced via prompt)
- SUPPORTED: =1 Tier A source confirms, OR =2 independent Tier B sources with no contradiction
- REFUTED: =1 Tier A contradicts, OR consistent contradiction across Tier B sources
- INCONCLUSIVE: only Tier C evidence, contradictory evidence, or insufficient — confidence = 0.3

### Groq API call
- Model: llama-3.1-8b-instant (configurable via GROQ_MODEL)
- Temperature: 0.0 (deterministic)
- Max tokens: 512
- Timeout: 30 seconds
- Never raises — all exceptions captured in VerificationResult.error

---

## 10. Fetcher Module (fetcher.py)

etch_url_text(url) is an async function that:
- Validates URL scheme (http/https only)
- Sends GET with a browser User-Agent header
- Raises FetchError on HTTP errors, timeouts, unsupported content types
- Parses HTML with BeautifulSoup (html.parser)
- Strips noise tags: script, style, noscript, nav, footer, header, aside, form, button, iframe, img, svg
- Prefers <article> or <main> elements for better signal-to-noise
- Collapses whitespace
- Truncates to 8,000 characters to keep Groq prompts within token limits
- Raises FetchError if no readable text is found

Known limitations:
- Facebook, Twitter/X, and most social media require login — returns 400/403
- Wikipedia blocks automated requests — returns 403
- Sites using JavaScript rendering (SPAs) return empty or minimal content

---

## 11. Persistence Module (persistence.py)

### write_session()
- Creates sessions/<YYYYMMDD_HHMMSS_ffffff>/ with os.chmod(0o700)
- Writes session.json — list of VerificationResult dicts
- Writes eport.md — human-readable Markdown
- Returns the session directory Path

### render_console_report()
- Returns a plain-text formatted string
- Uses emoji verdicts: ? Supported / ? Refuted / ?? Inconclusive
- Printed to stdout by main.py

### Session directory naming
Microsecond-precision timestamp from utils.make_timestamp():
20260608_143201_847293 — prevents collisions on multi-claim runs

---

## 12. Utils Module (utils.py)

### make_timestamp()
Returns datetime.now().strftime("%Y%m%d_%H%M%S_%f") — safe for directory names.

### async_retry decorator
`python
@async_retry(max_attempts=3, backoff=(1.0, 2.0, 4.0), exceptions=(httpx.HTTPError,))
async def my_func(): ...
`
- Retries on specified exception types only
- Logs warning on each retry with attempt number and delay
- Logs error when all attempts exhausted
- Re-raises the last exception after max attempts

---

## 13. stdout / stderr Routing

Critical for pipeline composability:
- **stderr** — all progress, status, warnings, errors, INFO logs
- **stdout** — final output only (console report, JSON, or session path)

This means python -m fact_checker.main --claim "..." 2> produces clean stdout-only output suitable for piping or redirection.

---

## 14. CLI Reference (main.py)
python -m fact_checker.main [INPUT] [--output MODE]
INPUT (required, mutually exclusive):
--claim TEXT    One or more sentences to verify directly
--file PATH     Path to a plain-text file
--url URL       URL of a web page to fetch and verify
--output MODE (optional, default: report):
report          Human-readable console report (default)
json            Structured JSON array
file            Session directory path only

Examples:
python -m fact_checker.main --claim "The moon landing was faked."
python -m fact_checker.main --file post.txt --output json
python -m fact_checker.main --url "https://apnews.com/article/..." --output report

---

## 15. Interactive Launcher (run.py)

Menu-driven interface — no command-line knowledge required.
python run.py

Or double-click launcher.bat.

Options:
1. Paste text — enter claims, finish with a dot (.) on its own line
2. Enter URL — fetches and verifies the page
3. Load file — path to a .txt file
4. Quit

---

## 16. Testing
pytest                    # run all tests with coverage
pytest -v                 # verbose output
pytest tests/test_verifier.py   # single module
mypy fact_checker\        # strict type checking

Coverage threshold: 80% (enforced in CI via --cov-fail-under=80).
main.py is excluded from coverage measurement (CLI wiring only).

Test strategy:
- All external I/O mocked — no live network calls in tests
- httpx calls mocked via unittest.mock.patch
- Groq API mocked via fake response dicts
- File I/O uses 	mp_path pytest fixture

---

## 17. Coding Standards

- Python 3.10+ — uses match statements, X | Y union types, rom __future__ import annotations
- mypy strict mode — zero errors required, # type: ignore forbidden except with justification
- black line length 100
- isort profile: black
- Granular exception handling — never bare except Exception except at the outermost CLI boundary
- All functions fully annotated

---

## 18. Known Limitations and Future Work

| Limitation | Notes |
|---|---|
| Facebook/social media URLs | Require login — use paste mode instead |
| JavaScript-rendered pages | BeautifulSoup cannot execute JS |
| Extractor uses regex | May split incorrectly on abbreviations (e.g. "Dr. Smith") |
| Groq has no grounding API | grounding_used is always False |
| Serper free tier | 2,500 queries/month — monitor usage |
| Groq free tier | 14,400 requests/day on llama-3.1-8b-instant |
| Max 10 claims per run | Hardcoded in extractor — increase _MAX_CLAIMS if needed |
| Source blacklist is domain-level | Article-level reliability varies within domains |
