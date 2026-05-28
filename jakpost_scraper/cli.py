"""Command-line entry point and run orchestration."""

import argparse
import os
import sys

from .auth import AuthError, ensure_session
from .config import Config, ConfigError, load_config
from .discovery import DiscoveryError, compute_window, discover, parse_since_arg
from .http_client import HttpClient
from .models import RunResult, dt_to_iso, now_utc
from .output import (
    render_articles_text, report_path, write_articles_json,
    write_markdown_report, write_summaries_json,
)
from .progress import log, phase, progress
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
    parser.add_argument("--console-output", choices=["article-text"],
                        help="Also write scraped articles to stdout")
    parser.add_argument("--limit", type=int,
                        help="Process at most N articles (testing aid)")
    parser.add_argument("--sections",
                        help="Comma-separated section identifiers (testing aid)")
    parser.add_argument("--auth", dest="auth", action="store_true", default=None,
                        help="Enable authenticated scraping for this run")
    parser.add_argument("--no-auth", dest="auth", action="store_false",
                        help="Disable authenticated scraping for this run")
    parser.add_argument("--reauth", action="store_true",
                        help="Force a fresh login even if a session is cached")
    parser.add_argument("--reset-state", action="store_true",
                        help="Delete state.json so the next run re-fetches all articles")
    return parser


def cli_overrides(args: argparse.Namespace) -> dict:
    """Extract config overrides (summary_mode, sections, auth) from parsed args."""
    overrides: dict = {}
    if args.summary_mode is not None:
        overrides["summary_mode"] = args.summary_mode
    if args.sections is not None:
        overrides["sections"] = [s.strip() for s in args.sections.split(",")
                                 if s.strip()]
    if args.auth is not None:
        overrides["auth_enabled"] = args.auth
    return overrides


def _session_looks_dead(articles: list) -> bool:
    """True if a majority of premium articles came back truncated — the signal
    that an authenticated session has expired mid-run (see D-005)."""
    premium = [a for a in articles if a.is_premium]
    if not premium:
        return False
    truncated = sum(1 for a in premium if a.is_truncated)
    return truncated > len(premium) / 2


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

    cookies = None
    if config.auth_enabled:
        with phase("Authentication") as ph:
            cookies = ensure_session(config, force_reauth=args.reauth)
            ph["summary"] = "session ready"

    with HttpClient(config.http_timeout, config.http_retries,
                    config.request_delay, cookies=cookies) as http:
        with phase("Article Discovery") as ph:
            log(f"Window: {dt_to_iso(since)}  →  {dt_to_iso(until)}")
            discovered, skipped_sections = discover(
                http, config.sections, since, until, set(state.seen_urls))
            result.skipped_sections = skipped_sections
            result.discovered = len(discovered)
            if args.limit is not None:
                discovered = discovered[:args.limit]
                log(f"--limit {args.limit}: trimming to first "
                    f"{len(discovered)} article(s)")
            skipped_note = (f", {len(skipped_sections)} section(s) skipped"
                            if skipped_sections else "")
            ph["summary"] = f"{result.discovered} article(s) discovered{skipped_note}"
        if args.dry_run:
            for item in discovered:
                print(f"{dt_to_iso(item.published_at)}  {item.section}  {item.url}")
            return result
        with phase("Article Scrape") as ph:
            log(f"Scraping {len(discovered)} article(s) with "
                f"concurrency={config.concurrency}, paywall={config.paywall}...")
            articles, failed_urls, skipped_paywall = scrape_articles(
                http, discovered, config.concurrency, config.paywall,
                on_progress=lambda done, total, url, ok: progress(
                    done, total, f"{'scraped' if ok else 'FAILED '} {url}"))
            ph["summary"] = (
                f"{len(articles)} kept, {len(skipped_paywall)} paywalled, "
                f"{len(failed_urls)} failed")
        if config.auth_enabled and _session_looks_dead(articles):
            raise AuthError(
                "Most premium articles came back truncated — the session has "
                "likely expired. Re-run with --reauth to log in again.")

    result.articles = articles
    result.scraped = len(articles)
    result.failed_urls = failed_urls
    result.skipped_paywall = len(skipped_paywall)
    result.premium_full = sum(
        1 for a in articles if a.is_premium and not a.is_truncated)

    write_articles_json(result, config)  # persist before summarizing
    log(f"Wrote raw articles JSON ({result.scraped} article(s)).")
    if do_summarize:
        with phase("Summarization") as ph:
            log(f"Summarizing {len(articles)} article(s) in mode="
                f"{config.summary_mode} with model={config.model}...")
            result.summaries = summarize(
                articles, config.summary_mode, config.model, config.concurrency,
                on_progress=lambda done, total, url, ok: progress(
                    done, total,
                    f"{'summarized' if ok else 'FAILED    '} {url}"),
                on_digest=lambda stage: log(
                    "  Building digest..." if stage == "start"
                    else "  Digest complete."))
            errors = sum(1 for s in result.summaries if s.error)
            ph["summary"] = f"{len(result.summaries)} summary record(s), {errors} error(s)"
    with phase("Write Outputs") as ph:
        write_summaries_json(result, config)
        write_markdown_report(result, config)
        ph["summary"] = f"report → {report_path(result, config)}"
    if args.console_output == "article-text":
        rendered = render_articles_text(result.articles)
        if rendered:
            print(rendered)

    if args.limit is not None:
        print("Note: --limit was set — this is a non-destructive sample run; "
              "state was not advanced.", file=sys.stderr)
        return result

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
        if args.reset_state:
            try:
                os.remove(config.state_file)
                print(f"State reset: {config.state_file} deleted. "
                      "Next run will re-fetch all articles.", file=sys.stderr)
            except FileNotFoundError:
                print(f"State already clear (no {config.state_file} found).",
                      file=sys.stderr)
            return 0
        state = load_state(config.state_file)
        result = run(config, state, args)
    except (ConfigError, StateError, DiscoveryError, PreflightError,
            AuthError) as e:
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
