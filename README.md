# Jakarta Post Scraper & Summarizer

A Python CLI that discovers articles published on
[The Jakarta Post](https://www.thejakartapost.com) since the last run,
scrapes their full text, summarizes them with Claude, and writes JSON files
plus a Markdown report.

## Requirements

- Python 3.11+
- The `claude` CLI installed and authenticated (used by the Claude Agent SDK).
  Run with `--no-summary` to skip this requirement.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Usage

The scraper is triggered manually:

```bash
jakpost-scrape                       # scrape since last run (24h on first run)
jakpost-scrape --dry-run             # list what would be scraped
jakpost-scrape --no-summary          # scrape only, skip summarization
jakpost-scrape --since 48h           # override the window (also accepts ISO dates)
jakpost-scrape --summary-mode digest # per-article | digest | both
jakpost-scrape --limit 5             # cap article count
jakpost-scrape --sections business   # restrict sections
```

## How it works

1. Reads `state.json` for the last-run timestamp (first run looks back 24h).
2. Walks The Jakarta Post's Google News sitemaps to find articles in the window.
3. Scrapes each article's full text (paywalled articles yield the teaser).
4. Summarizes via the Claude Agent SDK (`per-article`, `digest`, or `both`).
5. Writes `data/articles/<run-id>.json`, `data/summaries/<run-id>.json`, and
   `reports/<run-id>.md`, then advances `state.json`.

Configuration lives in `config.yaml`. See
`docs/superpowers/specs/2026-05-20-jakpost-scraper-design.md` for the full design.

## Tests

```bash
python -m pytest
```

The suite uses no live network and makes no live Claude calls.
