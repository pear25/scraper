from datetime import datetime, timezone

import pytest

from jakpost_scraper.models import Article
from jakpost_scraper import summarizer

PUB = datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc)


def _article(url: str) -> Article:
    return Article(
        url=url, title="Title", section="business", published_at=PUB,
        authors=["Reporter"], body="Body.", is_paywalled=False,
        lead_image_url=None, scraped_at=PUB,
    )


@pytest.fixture
def fake_claude(monkeypatch):
    calls: list[str] = []

    async def _fake(prompt: str, model: str) -> str:
        calls.append(prompt)
        return f"OUTPUT[{len(calls)}]"

    monkeypatch.setattr(summarizer, "_ask_claude", _fake)
    return calls


def test_digest_mode_returns_only_digest(fake_claude):
    summaries = summarizer.summarize(
        [_article("https://example.com/a.html")], "digest", "claude-haiku-4-5", 2)
    assert len(summaries) == 1
    assert summaries[0].kind == "digest"


def test_both_mode_returns_per_article_and_digest(fake_claude):
    summaries = summarizer.summarize(
        [_article("https://example.com/a.html"),
         _article("https://example.com/b.html")],
        "both", "claude-haiku-4-5", 2)
    kinds = sorted(s.kind for s in summaries)
    assert kinds == ["digest", "per-article", "per-article"]


def test_digest_covers_all_article_urls(fake_claude):
    summaries = summarizer.summarize(
        [_article("https://example.com/a.html"),
         _article("https://example.com/b.html")],
        "digest", "claude-haiku-4-5", 2)
    digest = summaries[0]
    assert set(digest.article_urls) == {
        "https://example.com/a.html", "https://example.com/b.html"}


def test_digest_batches_when_over_limit(fake_claude, monkeypatch):
    monkeypatch.setattr(summarizer, "DIGEST_BATCH_SIZE", 2)
    articles = [_article(f"https://example.com/{i}.html") for i in range(5)]
    summaries = summarizer.summarize(articles, "digest", "claude-haiku-4-5", 3)
    assert len(summaries) == 1 and summaries[0].kind == "digest"
    assert summaries[0].error is None
    # 5 per-article calls + 3 partial digests (2+2+1) + 1 merge = 9 calls.
    assert len(fake_claude) == 9


def test_digest_failure_recorded(monkeypatch):
    call = {"n": 0}

    async def _flaky(prompt: str, model: str) -> str:
        call["n"] += 1
        if "briefing" in prompt:  # digest prompt
            raise RuntimeError("digest failed")
        return "per-article ok"

    monkeypatch.setattr(summarizer, "_ask_claude", _flaky)
    summaries = summarizer.summarize(
        [_article("https://example.com/a.html")], "both", "claude-haiku-4-5", 1)
    per_article = [s for s in summaries if s.kind == "per-article"]
    digest = [s for s in summaries if s.kind == "digest"][0]
    assert per_article[0].error is None
    assert digest.error is not None and "digest failed" in digest.error
