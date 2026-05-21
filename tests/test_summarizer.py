from datetime import datetime, timezone

import pytest

from jakpost_scraper.models import Article
from jakpost_scraper import summarizer

PUB = datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc)


def _article(url: str, title: str = "Title", paywalled: bool = False) -> Article:
    return Article(
        url=url, title=title, section="business", published_at=PUB,
        authors=["Reporter"], body="Article body text.", is_paywalled=paywalled,
        is_premium=paywalled, is_truncated=paywalled,
        lead_image_url=None, scraped_at=PUB,
    )


@pytest.fixture
def fake_claude(monkeypatch):
    """Replace the Claude call with a deterministic fake; record prompts."""
    calls: list[str] = []

    async def _fake(prompt: str, model: str) -> str:
        calls.append(prompt)
        return f"SUMMARY[{len(calls)}]"

    monkeypatch.setattr(summarizer, "_ask_claude", _fake)
    return calls


def test_per_article_one_summary_each(fake_claude):
    articles = [_article("https://example.com/a.html"),
                _article("https://example.com/b.html")]
    summaries = summarizer.summarize(articles, "per-article", "claude-haiku-4-5", 2)
    assert len(summaries) == 2
    assert all(s.kind == "per-article" for s in summaries)
    assert {s.article_urls[0] for s in summaries} == {
        "https://example.com/a.html", "https://example.com/b.html"}
    assert all(s.error is None for s in summaries)


def test_per_article_prompt_notes_paywall(fake_claude):
    summarizer.summarize([_article("https://example.com/p.html", paywalled=True)],
                         "per-article", "claude-haiku-4-5", 1)
    assert "paywalled" in fake_claude[0].lower()


def test_empty_articles_returns_empty():
    assert summarizer.summarize([], "per-article", "claude-haiku-4-5", 2) == []


def test_per_article_failure_recorded(monkeypatch):
    async def _boom(prompt: str, model: str) -> str:
        raise RuntimeError("claude exploded")

    monkeypatch.setattr(summarizer, "_ask_claude", _boom)
    summaries = summarizer.summarize([_article("https://example.com/a.html")],
                                     "per-article", "claude-haiku-4-5", 1)
    assert len(summaries) == 1
    assert summaries[0].error is not None
    assert "claude exploded" in summaries[0].error
