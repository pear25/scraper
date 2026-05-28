# Jakarta Post Scraper & Summarizer

A command-line tool that discovers articles published on
[The Jakarta Post](https://www.thejakartapost.com) since the last run,
scrapes their full text, summarizes them with Claude, and writes JSON files
plus a Markdown report.

## Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex
```

The installer downloads [`uv`](https://github.com/astral-sh/uv) (a small
standalone tool that handles Python for you), then installs `jakpost-scrape`
into an isolated environment and puts it on your PATH. No prior Python
install required.

**Optional — summarization:** install the
[`claude` CLI](https://docs.claude.com/en/docs/claude-code/quickstart) and
run `claude login`. The scraper works without it if you pass `--no-summary`.

## Usage

```bash
jakpost-scrape                       # scrape since last run (24h on first run)
jakpost-scrape --dry-run             # list what would be scraped
jakpost-scrape --no-summary          # scrape only, skip summarization
jakpost-scrape --since 48h           # override the window (also accepts ISO dates)
jakpost-scrape --summary-mode digest # per-article | digest | both
jakpost-scrape --console-output article-text # print title + URL + raw body to stdout
jakpost-scrape --limit 5             # cap article count
jakpost-scrape --sections business   # restrict sections
jakpost-scrape --upgrade             # print the upgrade command
```

## Configuration file locations

The first time you run `jakpost-scrape`, it writes a default `config.yaml`
under your OS's standard app-config directory:

| OS      | Config                                                      | State + data                                     | Reports                                    |
|---------|-------------------------------------------------------------|--------------------------------------------------|--------------------------------------------|
| macOS   | `~/Library/Application Support/jakpost-scraper/config.yaml` | `~/Library/Application Support/jakpost-scraper/` | `~/Documents/jakpost-reports/`             |
| Linux   | `~/.config/jakpost-scraper/config.yaml`                     | `~/.local/share/jakpost-scraper/`                | `~/Documents/jakpost-reports/`             |
| Windows | `%APPDATA%\jakpost-scraper\config.yaml`                     | `%APPDATA%\jakpost-scraper\`                     | `%USERPROFILE%\Documents\jakpost-reports\` |

You can override any path:

- `--config PATH`, `--data-dir DIR`, `--reports-dir DIR` — per-run.
- `JAKPOST_CONFIG`, `JAKPOST_DATA_DIR`, `JAKPOST_REPORTS_DIR` — environment.
- If `config.yaml` exists in your current directory, the tool uses it
  (preserves the "run from a project folder" workflow).

Resolution order: CLI flag > env var > cwd > platform default.

## How it works

1. Reads `state.json` for the last-run timestamp (first run looks back 24h).
2. Walks The Jakarta Post's Google News sitemaps to find articles in the window.
3. Scrapes each article's full text (paywalled articles yield the teaser).
4. Summarizes via the Claude Agent SDK (`per-article`, `digest`, or `both`).
5. Writes `<data-dir>/articles/<run-id>.json`,
   `<data-dir>/summaries/<run-id>.json`, and `<reports-dir>/<run-id>.md`,
   then advances `state.json`.

`--console-output article-text` keeps those file outputs and also writes
each scraped article to stdout with its title, URL, and raw body text.

See `docs/superpowers/specs/2026-05-20-jakpost-scraper-design.md` for the
full design.

## Upgrading

```bash
jakpost-scrape --upgrade       # prints the upgrade command
uv tool upgrade jakpost-scraper
```

Or re-run the installer one-liner — it's idempotent.

## Uninstalling

```bash
uv tool uninstall jakpost-scraper
```

This removes the command. Config, state, and reports stay where they are —
delete those directories manually if you want a clean wipe.

## Authenticated scraping (premium articles)

By default the scraper runs as a guest, so premium articles return only a
teaser. To capture full premium article bodies, log in with your own Jakarta
Post account.

Set credentials in environment variables:

```bash
export JAKPOST_EMAIL=you@example.com
export JAKPOST_PASSWORD=your-password
```

Then enable in `config.yaml` (`auth_enabled: true`) or pass `--auth` on a
single run. The scraper logs in over HTTP on first use and caches the
session, reusing it on later runs. When the session expires, the run aborts
with a message — re-run with `--reauth` to log in again.

Authentication is opt-in: with `auth_enabled: false` (the default) the
scraper behaves as a guest.

## Develop from source

```bash
git clone https://github.com/pear25/scraper.git jakpost-scraper
cd jakpost-scraper
python -m pip install -e ".[dev]"
python -m pytest
jakpost-scrape --help
```

When run from a directory containing `config.yaml`, the tool reads that
local file and writes state/data/reports under that directory — matching
the development workflow.
