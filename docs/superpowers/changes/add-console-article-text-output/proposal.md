# Proposal: Add Console Article Text Output

## Why

The current CLI has two output paths:

- `--dry-run` prints discovery metadata only.
- A normal run writes JSON artifacts and a Markdown report to disk.

There is no mode that prints scraped article content directly to stdout in a
shell-friendly format. That makes simple workflows harder than they need to be,
especially when a user wants to:

- inspect scraped text immediately without opening generated files,
- pipe article text into other command-line tools, or
- capture article text in a terminal session together with enough metadata to
  identify the source.

## What Changes

- Add a new explicit console output mode for scraped articles.
- Expose that mode through CLI flags rather than implicit behavior changes.
- Print each article's title and URL together with its raw body text in a
  stable stdout format.
- Keep the current file outputs as the default behavior so existing runs and
  automation remain unchanged.
- Add parser, output-rendering, and end-to-end CLI tests for the new mode.
- Update README usage examples to show how to use the console format.

## Impact

- Affected code:
  - `jakpost_scraper/cli.py`
  - `jakpost_scraper/output.py`
  - `README.md`
  - `tests/test_cli.py`
  - `tests/test_output.py`
  - a run-level integration test if stdout emission is wired at orchestration level
- User impact:
  - Users gain a direct stdout path for raw article text with source metadata.
  - Existing file-based workflows continue to work unchanged unless the new
    flags are used.
- Operational impact:
  - The feature is low risk because it is opt-in and does not alter scraping,
    summarization, or persistence semantics by default.