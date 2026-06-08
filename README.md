# Fact-Checker

A local CLI fact-checking tool that verifies factual claims using real web search evidence and AI analysis.

Built with Python, Serper (Google Search API), and Groq (llama-3.1-8b-instant).

---

## What it does

1. Takes a claim, a block of text, or a URL as input
2. Searches the web for evidence using the Serper API
3. Filters out unreliable sources (social media, forums, misinformation outlets)
4. Sends the claim and credible evidence to Groq for analysis
5. Returns a verdict: Supported, Refuted, or Inconclusive — with sources and reasoning

---

## Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- A free Groq API key — https://console.groq.com
- A free Serper API key — https://serper.dev

### 2. Clone and set up
cd D:\Dev
git clone <repo-url> FactChecker
cd FactChecker
python -m venv .venv
..venv\Scripts\Activate.ps1
pip install -r requirements.txt

### 3. Configure

Create a .env file in the project root:
GROQ_API_KEY=your_groq_key_here
SERPER_API_KEY=your_serper_key_here
GROQ_MODEL=llama-3.1-8b-instant
LOG_LEVEL=INFO

### 4. Run

Double-click launcher.bat — or from an activated PowerShell:
python run.py

---

## Usage

### Interactive launcher (recommended)
python run.py

Presents a menu:
[1] Paste text or claims directly
[2] Enter a URL to fetch and check
[3] Load from a text file
[4] Quit

For option 1, paste your text then enter a single dot (.) on a new line to submit.

### Command line
python -m fact_checker.main --claim "The Great Wall of China is visible from space."
python -m fact_checker.main --file mypost.txt
python -m fact_checker.main --url "https://apnews.com/article/..."
python -m fact_checker.main --claim "..." --output json

### Facebook / social media posts

Social media requires login and cannot be fetched directly. Copy the post text,
paste it into a .txt file, then run:
python -m fact_checker.main --file post.txt

Or use option 1 in the interactive launcher and paste the text directly.

---

## Output

### Console report (default)
============================================================
FACT-CHECK REPORT
Claims checked: 1
CLAIM 1 OF 1
The Great Wall of China is visible from space.
Verdict:    ? Refuted
Confidence: 100%
Reasoning:
The claim is contradicted by multiple Tier A sources including NASA and
peer-reviewed research. No credible evidence supports visibility from orbit.
Sources:

https://www.nasa.gov/image-article/great-wall/
https://pmc.ncbi.nlm.nih.gov/articles/PMC3972694/
https://en.wikipedia.org/wiki/Artificial_structures_visible_from_space



### Session files

Every run saves to sessions/<timestamp>/:
- session.json — full structured results
- eport.md — Markdown version of the report

---

## Source Reliability Policy

The verifier applies a three-tier source system:

**Tier A — Trusted for verification**
Peer-reviewed journals, government agencies (NASA, CDC, WHO), wire services
(AP, Reuters), and major encyclopaedias.

**Tier B — Conditional**
Major mainstream outlets (BBC, NYT, Guardian) for straight news reporting only.
Opinion, editorial, and analysis sections are excluded.

**Tier C — Not used as evidence**
Social media posts, forums, AI-generated content, personal blogs, YouTube
commentary, and propaganda outlets.

Blacklisted domains are automatically filtered from evidence before verification.
A warning is logged when a blacklisted source is removed.

---

## Project Structure
fact_checker/
+-- main.py         CLI entry point
+-- agent.py        Pipeline orchestrator
+-- search.py       Serper API client
+-- extractor.py    Claim extraction
+-- verifier.py     Groq verification + source policy
+-- persistence.py  Session files + console report
+-- fetcher.py      URL fetching + HTML parsing
+-- utils.py        Retry logic + timestamps
+-- config.py       Configuration + validation
+-- tests/          39 tests, 91% coverage
run.py              Interactive launcher
launcher.bat        Double-click to launch
open_shell.bat      Double-click for activated PowerShell

---

## Development
Run tests
pytest
Type checking
mypy fact_checker\
Format code
black fact_checker
isort fact_checker\

Coverage threshold is enforced at 80%. All tests mock external APIs —
no live network calls are made during testing.

See developer.md for full architectural reference.

---

## Limitations

- Social media URLs (Facebook, Twitter, Instagram) require login and cannot be fetched
- JavaScript-rendered pages are not supported
- Maximum 10 claims extracted per input
- Serper free tier: 2,500 queries/month
- Groq free tier: 14,400 requests/day

---

## License

MIT
