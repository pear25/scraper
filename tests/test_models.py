from datetime import datetime, timezone

from jakpost_scraper.models import (
    Article, Summary, RunResult,
    now_utc, to_utc, parse_date, dt_to_iso, iso_to_dt,
)


def test_to_utc_makes_naive_datetime_aware():
    naive = datetime(2026, 5, 20, 12, 0, 0)
    result = to_utc(naive)
    assert result.tzinfo == timezone.utc


def test_parse_date_normalizes_offset_to_utc():
    result = parse_date("2026-05-20T10:00:00+07:00")
    assert result == datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc)


def test_iso_round_trip():
    dt = datetime(2026, 5, 20, 8, 30, 0, tzinfo=timezone.utc)
    assert dt_to_iso(dt) == "2026-05-20T08:30:00Z"
    assert iso_to_dt(dt_to_iso(dt)) == dt


def test_now_utc_is_aware():
    assert now_utc().tzinfo == timezone.utc


def test_article_to_dict_and_back():
    art = Article(
        url="https://example.com/a.html",
        title="A title",
        section="business",
        published_at=datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc),
        authors=["Jane Doe"],
        body="Body text.",
        is_paywalled=False,
        is_premium=False,
        is_truncated=False,
        lead_image_url="https://example.com/i.jpg",
        scraped_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
    )
    restored = Article.from_dict(art.to_dict())
    assert restored == art


def test_summary_to_dict_and_back():
    s = Summary(
        kind="per-article",
        text="Summary.",
        model="claude-haiku-4-5",
        generated_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        article_urls=["https://example.com/a.html"],
        error=None,
    )
    restored = Summary.from_dict(s.to_dict())
    assert restored == s


def test_run_result_defaults():
    r = RunResult(
        run_id="2026-05-20T12-00-00Z",
        since=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
        until=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        summary_mode="both",
    )
    assert r.discovered == 0
    assert r.failed_urls == []
    assert r.articles == []


def test_article_round_trip_with_now_utc_timestamps():
    ts = now_utc()
    art = Article(
        url="https://example.com/a.html", title="T", section="business",
        published_at=ts, authors=[], body="B", is_paywalled=True,
        is_premium=True, is_truncated=True,
        lead_image_url=None, scraped_at=ts,
    )
    assert Article.from_dict(art.to_dict()) == art


def test_article_round_trips_premium_and_truncated_fields():
    when = datetime(2026, 5, 20, 8, 0, 0, tzinfo=timezone.utc)
    art = Article(
        url="https://example.com/a",
        title="T",
        section="business",
        published_at=when,
        authors=["R"],
        body="body",
        is_paywalled=True,
        is_premium=True,
        is_truncated=True,
        lead_image_url=None,
        scraped_at=when,
    )
    d = art.to_dict()
    assert d["is_premium"] is True
    assert d["is_truncated"] is True
    restored = Article.from_dict(d)
    assert restored.is_premium is True
    assert restored.is_truncated is True
    assert restored.is_paywalled is True
