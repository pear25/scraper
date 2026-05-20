# The Jakarta Post Scraper & Summarizer — Design

**Date:** 2026-05-20
**Status:** Approved design — ready for implementation planning

## 1. Overview

A Python CLI tool that, on each manual run, discovers articles published on
The Jakarta Post since the last run, scrapes their full text, summarizes them
via Claude (using the Claude Agent SDK), and writes both the raw articles and
the summaries to disk. A persisted state file records the last successful run
timestamp so each run processes only new articles.

The pipeline: **discover → scrape full text → summarize → output**, gated by a
state file for timestamps and deduplication.

## 2. Requirements

Gathered during brainstorming:

| Topic | Decision |
|---|---|
| Scrape scope | All publicly-accessible sections. Paywalled articles → teaser-only or skipped (configurable). |
| Summary format | Configurable: `per-article`, `digest`, or `both`. |
| Output & storage | JSON files (raw articles + summaries) plus a Markdown report per run. A state file holds timestamps and the dedup set. |
| Time window | Since the last successful trigger; first run falls back to the last 24h. No upper cap on the window. |
| Tech stack | Python. |
| Claude access | Claude Agent SDK — drives the `claude` CLI as a subprocess, using existing Claude auth. |
| Trigger | Manual — a CLI command. |

## 3. Prerequisites

- **Python 3.11+** (modern typing, `asyncio`).
- **The `claude` CLI installed and authenticated** — required by the Claude
  Agent SDK. The tool runs a preflight check before scraping when
  summarization is enabled.

## 4. Approach

**Article discovery via Google News sitemaps.** The Jakarta Post's sitemap
index (`https://www.thejakartapost.com/sitemap.xml`) is a sitemap index
linking ~26 per-section `news/sitemap.xml` files. These are Google News
sitemaps: they contain only recently published articles (~last 48h), and each
`<url>` entry carries a `<news:publication_date>`. This is the only discovery
method that delivers comprehensive section coverage together with reliable
publish timestamps.

Alternatives considered and rejected:

- **RSS feed** (`rss.thejakartapost.com/home`) — holds only 20 items with
  teaser-only descriptions; cannot cover a full day across all sections.
- **HTML section-page crawling** — fragile (breaks on layout changes), messy
  pagination, no publish date until each article is fetched.

`robots.txt` permits crawling all news content and sitemaps (`Allow: /`; only
login/test pages are disallowed) and sets no `Crawl-delay`. The tool
self-throttles anyway as a courtesy.

## 5. Architecture & project layout

A Python package with one module per pipeline stage, each independently
testable.

```
jakpost_scraper/
├── jakpost_scraper/
│   ├── __init__.py
│   ├── cli.py            # entry point: arg parsing + orchestration
│   ├── config.py         # defaults ← config.yaml ← CLI overrides
│   ├── state.py          # read/write state.json (last run, seen URLs)
│   ├── discovery.py      # sitemap index → news sitemaps → URLs+pubdates → window filter
│   ├── scraper.py        # article URL → fetch+parse → Article
│   ├── summarizer.py     # articles → Claude Agent SDK → summaries
│   ├── output.py         # write articles JSON + summaries JSON + Markdown report
│   ├── models.py         # dataclasses: Article, Summary, RunResult
│   └── http_client.py    # shared HTTP session: retries, timeout, UA, politeness delay
├── tests/
│   ├── fixtures/         # saved sitemap XML + article HTML samples
│   ├── test_config.py
│   ├── test_state.py
│   ├── test_discovery.py
│   ├── test_scraper.py
│   ├── test_summarizer.py
│   ├── test_output.py
│   └── test_integration.py
├── data/articles/        # raw scraped articles, timestamped JSON
├── data/summaries/       # summaries, timestamped JSON
├── reports/              # Markdown report per run
├── config.yaml           # user config
├── state.json            # last-run timestamp + seen-URL set (created on first run)
├── pyproject.toml        # deps + `jakpost-scrape` console script
└── README.md
```

**Module responsibilities:**

- **`cli.py`** — parses arguments, loads config and state, orchestrates the run
  sequence, prints progress, sets the process exit code.
- **`config.py`** — resolves configuration from defaults, `config.yaml`, and
  CLI overrides; validates values.
- **`state.py`** — reads and writes `state.json` (last-run timestamp, seen-URL
  set); handles first-run, corruption, retention pruning, atomic writes.
- **`discovery.py`** — computes the time window (§9) as a pure function,
  fetches the sitemap index, selects news sitemaps, parses article URLs +
  publication dates, filters by time window and seen URLs.
- **`scraper.py`** — fetches and parses an article page into an `Article`;
  detects paywalled content.
- **`summarizer.py`** — summarizes articles via the Claude Agent SDK in the
  configured mode.
- **`output.py`** — writes the raw-articles JSON, summaries JSON, and Markdown
  report.
- **`models.py`** — the `Article`, `Summary`, and `RunResult` dataclasses.
- **`http_client.py`** — a shared HTTP client with retries, timeout, a
  descriptive User-Agent, and a politeness delay.

**Dependencies:** `httpx` (HTTP), `beautifulsoup4` + `lxml` (HTML/XML parsing),
`python-dateutil` (date parsing), `pyyaml` (config), `claude-agent-sdk`
(summarization). Dev: `pytest`, `pytest-httpx`.

## 6. Configuration

`config.yaml` (all keys optional; defaults shown):

```yaml
sections: all              # "all" or a list of section identifiers
summary_mode: both         # per-article | digest | both
model: claude-haiku-4-5    # Claude model for summarization
paywall: keep-teaser       # keep-teaser | skip
request_delay: 1.0         # seconds between HTTP requests
concurrency: 4             # max concurrent article fetches / summary calls
lookback_buffer_minutes: 20
seen_url_retention_days: 30
http_timeout: 15           # seconds
http_retries: 3            # attempts per request
data_dir: ./data
reports_dir: ./reports
state_file: ./state.json
```

**Precedence:** built-in defaults < `config.yaml` < CLI flags. `config.py`
validates values (e.g. `summary_mode` is one of the three allowed strings;
numeric fields are positive) and fails fast with a clear message on bad input.

A **section identifier** is the path portion of a news sitemap URL — e.g.
`https://www.thejakartapost.com/news/politics/news/sitemap.xml` →
`news/politics`. `sections: all` includes every news sitemap found in the
index.

## 7. CLI interface

The manual trigger is the `jakpost-scrape` command (a console script declared
in `pyproject.toml`).

| Invocation | Behavior |
|---|---|
| `jakpost-scrape` | Normal run: window since the last trigger (24h fallback), scrape, summarize, output, advance state. |
| `--since <value>` | Override the window start. Accepts an ISO date/datetime or a duration like `24h` / `3d`. Bypasses the lookback buffer. |
| `--dry-run` | Discover and print what *would* be scraped; no scraping, summarizing, or state write. |
| `--no-summary` | Scrape and save raw articles only; skip summarization. |
| `--summary-mode per-article\|digest\|both` | Override `config.summary_mode`. |
| `--limit N` | Process at most N articles (testing aid). |
| `--sections <list>` | Restrict to specific section identifiers (testing aid). |

## 8. Run flow

One `jakpost-scrape` invocation:

1. **Load config** — defaults ← `config.yaml` ← CLI flags.
2. **Load state** — read `state.json` for `last_run_at` (UTC) and `seen_urls`.
   First run: file absent.
3. **Preflight** — if summarization will run, verify the `claude` CLI is
   present and authenticated; fail fast *before* scraping otherwise.
4. **Determine window** — see §9.
5. **Discovery** — sitemap index → news sitemaps (filtered by
   `config.sections`) → parse `<loc>` + `<news:publication_date>` → keep
   `pubdate ∈ [since, until]` → drop URLs already in `seen_urls` → deduped list
   of `(url, pubdate, section)`.
6. **Scrape** — fetch and parse each URL into an `Article`. `--dry-run` stops
   here and prints the list; `--limit` caps the count.
7. **Persist raw articles** — write `data/articles/<run-id>.json`
   *immediately*, before summarizing, so scrape work is never lost.
8. **Summarize** — feed `Article`s to the summarizer in the configured mode.
   Skipped on `--no-summary`.
9. **Output** — write `data/summaries/<run-id>.json` and
   `reports/<run-id>.md`.
10. **Update state** (on success only) — set `last_run_at = until`, add scraped
    URLs to `seen_urls`, prune entries older than `seen_url_retention_days`,
    write `state.json` atomically.

`<run-id>` is the run-start UTC timestamp with filename-safe punctuation, e.g.
`2026-05-20T08-30-00Z`.

## 9. Time-window logic

- `until` = the run-start time (UTC).
- `since`:
  - If `--since` is given → that exact value (no buffer applied).
  - Else if `last_run_at` exists → `last_run_at − lookback_buffer_minutes`.
  - Else (first run) → `until − 24h`.
- The window `[since, until]` is **inclusive** at both ends.

**Boundary safety.** State advances to the run-*start* time (`until`), and
`since` subtracts a small lookback buffer (default 20 min). The buffer catches
articles that appear in the sitemap *after* the previous run already fetched it
(sitemap propagation lag). The `seen_urls` set makes the resulting overlap
free — overlapping articles are recognized and skipped, never re-scraped or
re-summarized. State advances **only on a successful run**, so a failed run
never loses the window.

## 10. Data model

Dataclasses in `models.py`. All datetimes are timezone-aware UTC.

**`Article`**
- `url: str`
- `title: str`
- `section: str`
- `published_at: datetime`
- `authors: list[str]`
- `body: str` — full plain text; the visible teaser if paywalled
- `is_paywalled: bool`
- `lead_image_url: str | None`
- `scraped_at: datetime`

**`Summary`**
- `kind: str` — `per-article` or `digest`
- `text: str` — the summary (per-article) or the digest Markdown
- `model: str`
- `generated_at: datetime`
- `article_urls: list[str]` — one entry for a per-article summary; many for a
  digest
- `error: str | None` — set if the summarization call failed for this item

**`RunResult`**
- `run_id: str`
- `since: datetime`, `until: datetime`
- `summary_mode: str`
- Counts: `discovered`, `scraped`, `failed`, `skipped_paywall`
- `skipped_sections: list[str]` — section sitemaps that failed to fetch
- `articles: list[Article]`, `summaries: list[Summary]`

## 11. File formats

**`state.json`**

```json
{
  "last_run_at": "2026-05-20T08:30:00Z",
  "seen_urls": [
    {"url": "https://www.thejakartapost.com/...", "seen_at": "2026-05-20T08:30:00Z"}
  ]
}
```

`seen_at` enables retention pruning. Written atomically (temp file + rename).

**`data/articles/<run-id>.json`** — run metadata (`run_id`, `since`, `until`,
counts) plus an `articles` array of serialized `Article` records.

**`data/summaries/<run-id>.json`** — run metadata, `summary_mode`, a
`per_article` array, and a `digest` object (whichever the mode produced).

**`reports/<run-id>.md`** — human-readable:
- Header: time window, counts (discovered / scraped / failed / skipped
  paywall), summary mode.
- The digest (if produced).
- Per-article entries: title, link, section, published time, summary;
  paywalled articles flagged; failed-to-scrape URLs and failed-to-summarize
  items listed explicitly.

## 12. Discovery details

- Fetch the sitemap index. Select only children whose URL matches
  `*/news/sitemap.xml` (the Google News variants) — skip the `/web/` and
  `/images/` variants.
- `config.sections` selects which news sitemaps to fetch; `all` fetches every
  one.
- Each news sitemap is a `<urlset>` whose `<url>` entries contain `<loc>` and a
  `<news:news>` block with `<news:publication_date>` (ISO 8601) and
  `<news:title>`. Parse with `lxml`, handling the `news:` XML namespace.
- Normalize every publication date to UTC.
- Filter to the time window; drop URLs present in `seen_urls`; dedupe URLs that
  appear in more than one section sitemap.

## 13. Scraping details

**Article extraction** — layered, most-stable-source-first:

1. Prefer JSON-LD (`<script type="application/ld+json">`, `NewsArticle`) for
   title, publication date, and authors.
2. Fall back to OpenGraph / `article:*` meta tags.
3. Fall back to CSS selectors.

The body is the article content container with `<p>` text concatenated and
ads / related-links / scripts stripped. `lead_image_url` comes from
`og:image`.

**Paywall handling** — detect the JP Premium marker (a paywall element, or a
truncated body with a subscribe call-to-action) and set `is_paywalled`.
`config.paywall`:
- `keep-teaser` (default) — save the visible teaser text, flagged.
- `skip` — exclude the article entirely.

Kept paywalled articles are saved and summarized like any other; the report
flags them so a short summary is expected.

**HTTP client & politeness** (`http_client.py`) — a shared `httpx` client with:
- a descriptive User-Agent identifying the bot,
- a ~15s timeout (`config.http_timeout`),
- retries with exponential backoff on timeouts, 5xx, and 429 — honoring
  `Retry-After` — up to `config.http_retries` attempts,
- a `config.request_delay` pause between requests.

Article fetches run through a thread pool bounded by `config.concurrency`.

## 14. Summarization

Uses the **Claude Agent SDK** (`claude-agent-sdk`), which drives the `claude`
CLI. The SDK's `query()` is async; `summarizer.py` wraps it and exposes a
synchronous entry point to the CLI via `asyncio.run`.

**Call configuration** — `ClaudeAgentOptions` with **no tools and no file
access** (pure text-in / text-out), a **static system prompt** defining the
summarizer role (identical across calls, so it is cache-friendly), and
`model = config.model` (default `claude-haiku-4-5` — fast and capable for news
summaries; raise to a Sonnet model for higher quality).

Model output is plain text / Markdown — never parsed as JSON — which removes a
class of failure modes.

**Modes** (they compose):

- **`per-article`** — one `query()` per article (concurrency-bounded with an
  `asyncio.Semaphore`), producing a concise summary (~3 sentences) each. The
  prompt contains the article title and body.
- **`digest`** — compute the per-article summaries first, then feed *those
  summaries* (not the full bodies) into one `query()` that produces a
  theme-grouped daily briefing. Feeding summaries keeps the digest prompt
  small regardless of article count.
- **`both`** — keep the per-article summaries *and* the digest (the digest is
  effectively free once computed).

**Digest size guard** — if the combined per-article summaries are still too
large for one call, chunk them into batches → partial digests → a final merge
pass.

**Failure handling** — a failed per-article `query()` retries once, then
records a `Summary` with `error` set and continues. A failed digest leaves the
per-article summaries intact; the report notes the digest is unavailable.

## 15. Error handling

| Failure | Behavior |
|---|---|
| Sitemap *index* fetch fails | Fatal — abort after retries, no state update (discovery is impossible). |
| One *section* sitemap fails | Skip that section, log a warning, continue; record it in `RunResult.skipped_sections`. |
| One article fetch/parse fails | HTTP-level retries, then skip and log, increment `failed_count`. Run continues. |
| `claude` CLI missing / unauthenticated | Preflight check at startup (when summarizing) — fail fast *before* scraping. |
| Summarizer call fails | Per-article: retry once → record failed `Summary`, continue. Digest: per-article summaries already saved; report notes digest unavailable. |
| `state.json` corrupt | Abort with a clear error — do not silently treat as first-run (which would re-scrape 24h). User may delete the file to intentionally reset. |
| Empty window (0 new articles) | Valid outcome — write a "0 new articles" report, advance `last_run_at`, exit 0. |
| Interrupted mid-run | Raw articles are written only after all scraping; state advances only at the very end → the next run cleanly redoes the window. Crash-safe. |

Raw articles are persisted *before* summarization, and `state.json` is written
atomically (temp file + rename).

**Cross-run retry of failed articles is deliberately out of scope (YAGNI).**
Failed-to-scrape URLs are listed explicitly in the report, so a window can be
recovered manually with `--since`.

## 16. Edge cases

- **Duplicate URLs** across multiple section sitemaps → deduped in discovery.
- **Timezones** — sitemap dates may be `+0700` or `Z`; all timestamps are
  normalized to UTC on parse.
- **`seen_urls` growth** → pruned by `seen_url_retention_days` (default 30,
  safely longer than any realistic window).
- **Window boundary** — `[since, until]` is inclusive; `seen_urls` absorbs the
  overlap harmlessly.
- **Site structure change** — if discovery finds zero news sitemaps, log a
  prominent warning (it likely indicates the site changed) and treat the run
  as an empty window.
- **Oversized digest** — handled by the chunk → partial-digest → merge guard
  (§14).

## 17. Testing strategy

Test-driven development (`test-driven-development` skill) applies during
implementation. No live network or live Claude calls anywhere in the suite.

- **Fixtures** committed under `tests/fixtures/`: a real sitemap index XML, a
  section news sitemap XML, and several article HTML pages (regular and
  paywalled).
- **`discovery`** — `news:` namespace parsing; window filtering (inside,
  outside, on the boundary); seen-URL exclusion; cross-sitemap dedup; section
  selection.
- **`scraper`** — field extraction; JSON-LD → meta → selector fallback;
  paywall detection; resilience to malformed HTML.
- **`state`** — read/write round-trip; first-run (absent file); corrupt-file
  handling; retention pruning; atomic write.
- **`config`** — precedence (defaults < yaml < CLI); validation of bad values.
- **`summarizer`** — Agent SDK `query()` mocked; prompt construction per mode;
  concurrency cap; per-article → digest composition; failure / retry path.
- **`output`** — JSON shapes; Markdown report structure (digest section,
  per-article entries, paywall flags, failed lists).
- **Window logic** (covered in `test_discovery.py`) — `since` / `until` /
  buffer / first-run / `--since` override, with an injectable "now".
- **Integration** — end-to-end with all HTTP mocked via `pytest-httpx` and the
  summarizer mocked: discover → scrape → summarize → output → state advance,
  then a second run proving dedup and window advance.

## 18. Out of scope

- Automated scheduling (cron, daemons) — the trigger is manual by design.
- Cross-run retry queue for failed articles.
- A web UI or email/Slack delivery of reports.
- Bypassing the paywall.
- Sites other than The Jakarta Post.
