import json
from datetime import datetime, timezone

from jakpost_scraper.config import Config
from jakpost_scraper.models import Article, RunResult, Summary
from jakpost_scraper.output import (
    write_articles_json, write_summaries_json, write_markdown_report,
)

SINCE = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


def _article(url: str) -> Article:
    return Article(
        url=url, title="Green roadmap", section="business", published_at=UNTIL,
        authors=["Reporter"], body="Body.", is_paywalled=False,
        is_premium=False, is_truncated=False,
        lead_image_url=None, scraped_at=UNTIL,
    )


def _result(tmp_path) -> tuple[RunResult, Config]:
    cfg = Config(data_dir=str(tmp_path / "data"),
                 reports_dir=str(tmp_path / "reports"))
    result = RunResult(run_id="2026-05-20T12-00-00Z", since=SINCE, until=UNTIL,
                       summary_mode="both", discovered=2, scraped=1)
    result.articles = [_article("https://example.com/a.html")]
    result.failed_urls = ["https://example.com/gone.html"]
    result.summaries = [
        Summary(kind="per-article", text="A summary.", model="m",
                generated_at=UNTIL, article_urls=["https://example.com/a.html"]),
        Summary(kind="digest", text="The digest.", model="m",
                generated_at=UNTIL, article_urls=["https://example.com/a.html"]),
    ]
    return result, cfg


def test_write_articles_json(tmp_path):
    result, cfg = _result(tmp_path)
    path = write_articles_json(result, cfg)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["run_id"] == "2026-05-20T12-00-00Z"
    assert data["failed"] == 1
    assert len(data["articles"]) == 1
    assert data["articles"][0]["url"] == "https://example.com/a.html"


def test_write_summaries_json(tmp_path):
    result, cfg = _result(tmp_path)
    path = write_summaries_json(result, cfg)
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data["per_article"]) == 1
    assert data["digest"]["text"] == "The digest."


def test_write_markdown_report(tmp_path):
    result, cfg = _result(tmp_path)
    path = write_markdown_report(result, cfg)
    text = open(path, encoding="utf-8").read()
    assert "## Daily Digest" in text
    assert "The digest." in text
    assert "Green roadmap" in text
    assert "A summary." in text
    assert "https://example.com/gone.html" in text


def test_report_shows_premium_capture_counts(tmp_path):
    from datetime import datetime, timezone
    from jakpost_scraper.config import Config
    from jakpost_scraper.models import Article, RunResult
    from jakpost_scraper.output import write_markdown_report

    when = datetime(2026, 5, 20, tzinfo=timezone.utc)

    def _a(is_premium, is_truncated):
        return Article(url="u" + str(id((is_premium, is_truncated))),
                       title="t", section="s", published_at=when, authors=[],
                       body="b", is_paywalled=is_truncated,
                       is_premium=is_premium, is_truncated=is_truncated,
                       lead_image_url=None, scraped_at=when)

    result = RunResult(run_id="2026-05-20T00-00-00Z", since=when, until=when,
                       summary_mode="digest")
    result.articles = [_a(True, False), _a(True, True), _a(False, False)]
    result.scraped = 3
    result.premium_full = 1

    cfg = Config(reports_dir=str(tmp_path))
    path = write_markdown_report(result, cfg)
    text = open(path, encoding="utf-8").read()
    assert "Premium captured in full:** 1" in text


def test_report_handles_zero_articles(tmp_path):
    cfg = Config(data_dir=str(tmp_path / "data"),
                 reports_dir=str(tmp_path / "reports"))
    result = RunResult(run_id="2026-05-20T12-00-00Z", since=SINCE, until=UNTIL,
                       summary_mode="both", discovered=0, scraped=0)
    text = open(write_markdown_report(result, cfg), encoding="utf-8").read()
    assert "No new articles" in text
