# Implementation Tasks

1. Add new CLI arguments for console article output and validate their default behavior in parser tests.
2. Define a single stdout rendering contract for article blocks that includes title, URL, and raw body text.
3. Implement the output renderer in `jakpost_scraper/output.py` without changing the existing JSON or Markdown writers.
4. Wire the new console output path into `jakpost_scraper/cli.py` so it runs only when the new flags are explicitly enabled.
5. Ensure stdout output remains deterministic for zero, one, or many scraped articles, including paywalled teaser cases.
6. Verify the new mode composes correctly with existing flags such as `--no-summary`, `--limit`, and authenticated scraping.
7. Add focused tests for parser behavior and rendered stdout content.
8. Add or extend an orchestration-level test covering a run that emits article text to stdout.
9. Update README usage examples and option descriptions for the new console mode.
10. Run the relevant test slices for CLI and output behavior, then run the full test suite if the touched slice passes.