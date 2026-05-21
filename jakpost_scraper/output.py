"""Write run artifacts: raw articles JSON, summaries JSON, Markdown report."""

import json
import os

from .config import Config
from .models import RunResult, dt_to_iso


def articles_path(result: RunResult, config: Config) -> str:
    return os.path.join(config.data_dir, "articles", f"{result.run_id}.json")


def summaries_path(result: RunResult, config: Config) -> str:
    return os.path.join(config.data_dir, "summaries", f"{result.run_id}.json")


def report_path(result: RunResult, config: Config) -> str:
    return os.path.join(config.reports_dir, f"{result.run_id}.md")


def write_articles_json(result: RunResult, config: Config) -> str:
    """Write the raw scraped articles to data/articles/<run-id>.json."""
    path = articles_path(result, config)
    _write_json(path, {
        **_run_metadata(result),
        "failed_urls": result.failed_urls,
        "articles": [a.to_dict() for a in result.articles],
    })
    return path


def write_summaries_json(result: RunResult, config: Config) -> str:
    """Write the summaries to data/summaries/<run-id>.json."""
    path = summaries_path(result, config)
    digest = next((s for s in result.summaries if s.kind == "digest"), None)
    _write_json(path, {
        **_run_metadata(result),
        "per_article": [s.to_dict() for s in result.summaries
                        if s.kind == "per-article"],
        "digest": digest.to_dict() if digest else None,
    })
    return path


def write_markdown_report(result: RunResult, config: Config) -> str:
    """Write the human-readable Markdown report to reports/<run-id>.md."""
    path = report_path(result, config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(_render_report(result)))
    return path


def _run_metadata(result: RunResult) -> dict:
    return {
        "run_id": result.run_id,
        "since": dt_to_iso(result.since),
        "until": dt_to_iso(result.until),
        "summary_mode": result.summary_mode,
        "discovered": result.discovered,
        "scraped": result.scraped,
        "failed": len(result.failed_urls),
        "skipped_paywall": result.skipped_paywall,
        "skipped_sections": result.skipped_sections,
    }


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _render_report(result: RunResult) -> list[str]:
    lines: list[str] = [
        "# The Jakarta Post — News Summary",
        "",
        f"**Window:** {dt_to_iso(result.since)} → {dt_to_iso(result.until)}  ",
        (f"**Discovered:** {result.discovered}  |  **Scraped:** {result.scraped}"
         f"  |  **Failed:** {len(result.failed_urls)}  |  "
         f"**Skipped (paywall):** {result.skipped_paywall}  |  "
         f"**Premium captured in full:** {result.premium_full}  "),
        f"**Summary mode:** {result.summary_mode}",
        "",
    ]
    if result.scraped == 0:
        lines += ["_No new articles in this window._", ""]

    digest = next((s for s in result.summaries if s.kind == "digest"), None)
    if digest is not None:
        lines += ["## Daily Digest", ""]
        lines.append(f"_Digest unavailable: {digest.error}_"
                     if digest.error else digest.text)
        lines.append("")

    per_article = [s for s in result.summaries if s.kind == "per-article"]
    if per_article:
        lines += ["## Articles", ""]
        by_url = {a.url: a for a in result.articles}
        for summary in per_article:
            url = summary.article_urls[0] if summary.article_urls else ""
            article = by_url.get(url)
            lines.append(f"### {article.title if article else url or 'Untitled'}")
            if article is not None:
                meta = [article.section, dt_to_iso(article.published_at)]
                if article.is_paywalled:
                    meta.append("paywalled (teaser)")
                lines.append(f"_{' · '.join(meta)}_  ")
            lines += [f"<{url}>", ""]
            lines.append(f"_Summary unavailable: {summary.error}_"
                         if summary.error else summary.text)
            lines.append("")

    if result.failed_urls:
        lines += ["## Failed to scrape", ""]
        lines += [f"- {u}" for u in result.failed_urls]
        lines.append("")
    if result.skipped_sections:
        lines += ["## Skipped sections (sitemap fetch failed)", ""]
        lines += [f"- {s}" for s in result.skipped_sections]
        lines.append("")
    return lines
