"""Command-line entry point and run orchestration."""

import argparse
import sys

from .config import Config, ConfigError, load_config
from .discovery import DiscoveryError, compute_window, discover, parse_since_arg
from .http_client import HttpClient
from .models import RunResult, dt_to_iso, now_utc
from .output import (
    report_path, write_articles_json, write_markdown_report, write_summaries_json,
)
from .scraper import scrape_articles
from .state import State, StateError, load_state, prune_seen, save_state
from .summarizer import PreflightError, preflight_check, summarize

CONFIG_PATH = "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jakpost-scrape",
        description="Scrape and summarize The Jakarta Post articles.",
    )
    parser.add_argument("--since",
                        help="Window start: an ISO date or a duration like 24h/3d")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be scraped; no scrape/summarize/state write")
    parser.add_argument("--no-summary", action="store_true",
                        help="Scrape and save raw articles only; skip summarization")
    parser.add_argument("--summary-mode", choices=["per-article", "digest", "both"],
                        help="Override the configured summary mode")
    parser.add_argument("--limit", type=int,
                        help="Process at most N articles (testing aid)")
    parser.add_argument("--sections",
                        help="Comma-separated section identifiers (testing aid)")
    return parser


def cli_overrides(args: argparse.Namespace) -> dict:
    """Extract config overrides (summary_mode, sections) from parsed args."""
    overrides: dict = {}
    if args.summary_mode is not None:
        overrides["summary_mode"] = args.summary_mode
    if args.sections is not None:
        overrides["sections"] = [s.strip() for s in args.sections.split(",")
                                 if s.strip()]
    return overrides


def run(config: Config, state: State, args: argparse.Namespace) -> RunResult:
    """Execute one scrape/summarize/output run. Returns the RunResult."""
    now = now_utc()
    run_id = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    do_summarize = not args.no_summary

    if do_summarize and not args.dry_run:
        preflight_check()

    since_override = parse_since_arg(args.since, now) if args.since else None
    since, until = compute_window(state.last_run_at, since_override, now,
                                  config.lookback_buffer_minutes)
    result = RunResult(run_id=run_id, since=since, until=until,
                       summary_mode=config.summary_mode)

    with HttpClient(config.http_timeout, config.http_retries,
                    config.request_delay) as http:
        discovered, skipped_sections = discover(
            http, config.sections, since, until, set(state.seen_urls))
        result.skipped_sections = skipped_sections
        result.discovered = len(discovered)
        if args.limit is not None:
            discovered = discovered[:args.limit]
        if args.dry_run:
            for item in discovered:
                print(f"{dt_to_iso(item.published_at)}  {item.section}  {item.url}")
            return result
        articles, failed_urls, skipped_paywall = scrape_articles(
            http, discovered, config.concurrency, config.paywall)

    result.articles = articles
    result.scraped = len(articles)
    result.failed_urls = failed_urls
    result.skipped_paywall = len(skipped_paywall)

    write_articles_json(result, config)  # persist before summarizing
    if do_summarize:
        result.summaries = summarize(articles, config.summary_mode,
                                     config.model, config.concurrency)
    write_summaries_json(result, config)
    write_markdown_report(result, config)

    state.last_run_at = until
    for article in articles:
        state.seen_urls[article.url] = until
    for url in skipped_paywall:
        state.seen_urls[url] = until
    prune_seen(state, config.seen_url_retention_days, now)
    save_state(config.state_file, state)
    return result


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the pipeline, return a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(CONFIG_PATH, cli_overrides(args))
        state = load_state(config.state_file)
        result = run(config, state, args)
    except (ConfigError, StateError, DiscoveryError, PreflightError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"Done: scraped {result.scraped}/{result.discovered} article(s), "
              f"{len(result.summaries)} summary record(s) → "
              f"{report_path(result, config)}", file=sys.stderr)
    return 0


def cli_entry() -> None:
    """Console-script entry point declared in pyproject.toml."""
    sys.exit(main())
