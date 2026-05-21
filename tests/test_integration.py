"""End-to-end test: all network mocked, summarizer mocked. No live calls."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from jakpost_scraper import cli, summarizer
from jakpost_scraper.config import Config
from jakpost_scraper.state import load_state

FIXTURES = Path(__file__).parent / "fixtures"
# Fixed so the fixture article dates (2026-05-20) fall inside the run window.
FIXED_NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
INDEX_URL = "https://www.thejakartapost.com/sitemap.xml"
BIZ_URL = "https://www.thejakartapost.com/business/news/sitemap.xml"
POL_URL = "https://www.thejakartapost.com/news/politics/news/sitemap.xml"
# All four in-window, non-advertorial articles across the two news sitemaps.
ARTICLE_URLS = [
    "https://www.thejakartapost.com/business/2026/05/20/in-window-one.html",
    "https://www.thejakartapost.com/business/2026/05/20/in-window-two.html",
    "https://www.thejakartapost.com/news/politics/2026/05/20/politics-one.html",
    "https://www.thejakartapost.com/news/politics/2026/05/20/already-seen.html",
]


@pytest.fixture(autouse=True)
def patched_env(monkeypatch):
    monkeypatch.setattr("jakpost_scraper.http_client.time.sleep", lambda s: None)
    monkeypatch.setattr(cli, "now_utc", lambda: FIXED_NOW)
    monkeypatch.setattr(cli, "preflight_check", lambda: None)

    async def _fake_claude(prompt: str, model: str) -> str:
        return "FAKE SUMMARY"

    monkeypatch.setattr(summarizer, "_ask_claude", _fake_claude)


def _add_sitemaps(httpx_mock):
    httpx_mock.add_response(
        url=INDEX_URL, content=(FIXTURES / "sitemap_index.xml").read_bytes())
    httpx_mock.add_response(
        url=BIZ_URL, content=(FIXTURES / "news_sitemap_business.xml").read_bytes())
    httpx_mock.add_response(
        url=POL_URL, content=(FIXTURES / "news_sitemap_politics.xml").read_bytes())


def _add_articles(httpx_mock):
    free_html = (FIXTURES / "article_free.html").read_text(encoding="utf-8")
    for url in ARTICLE_URLS:
        httpx_mock.add_response(url=url, text=free_html)


def _config(tmp_path) -> Config:
    return Config(
        request_delay=0,
        data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
        state_file=str(tmp_path / "state.json"),
    )


def _args(**overrides):
    defaults = dict(since=None, dry_run=False, no_summary=False,
                    summary_mode=None, limit=None, sections=None,
                    reauth=False, auth=None)
    defaults.update(overrides)
    return type("Args", (), defaults)()


def test_end_to_end_first_run_then_dedup(httpx_mock, tmp_path):
    config = _config(tmp_path)

    # First run: discovers 4 in-window articles, scrapes and summarizes them.
    _add_sitemaps(httpx_mock)
    _add_articles(httpx_mock)
    result = cli.run(config, load_state(config.state_file), _args())

    assert result.discovered == 4
    assert result.scraped == 4
    assert os.path.exists(config.state_file)

    report = open(cli.report_path(result, config), encoding="utf-8").read()
    assert "FAKE SUMMARY" in report
    articles_file = os.path.join(config.data_dir, "articles",
                                 f"{result.run_id}.json")
    data = json.loads(open(articles_file, encoding="utf-8").read())
    assert len(data["articles"]) == 4

    # Second run with an explicit --since covering the same articles: they are
    # in the window by time but all in seen_urls, so dedup yields nothing new.
    _add_sitemaps(httpx_mock)
    result2 = cli.run(config, load_state(config.state_file),
                      _args(since="2026-05-19"))
    assert result2.discovered == 0
    assert result2.scraped == 0


def test_dry_run_writes_no_state(httpx_mock, tmp_path):
    config = _config(tmp_path)
    _add_sitemaps(httpx_mock)  # dry-run discovers but never fetches articles
    result = cli.run(config, load_state(config.state_file), _args(dry_run=True))
    assert result.discovered == 4
    assert not os.path.exists(config.state_file)


def test_authenticated_run_captures_full_premium_body(tmp_path, httpx_mock,
                                                      monkeypatch):
    login_url = "https://www.thejakartapost.com/user/account/login"
    monkeypatch.setenv("JAKPOST_EMAIL", "user@example.com")
    monkeypatch.setenv("JAKPOST_PASSWORD", "secret")

    # Mock the login GET then POST
    httpx_mock.add_response(
        url=login_url,
        text=(FIXTURES / "login_page.html").read_text(encoding="utf-8"))
    httpx_mock.add_response(
        url=login_url, status_code=302,
        headers={"set-cookie": "laravel_session=authed; Path=/"})

    # Mock sitemaps and serve premium_full for all article pages
    _add_sitemaps(httpx_mock)
    premium_html = (FIXTURES / "article_premium_full.html").read_text(encoding="utf-8")
    for url in ARTICLE_URLS:
        httpx_mock.add_response(url=url, text=premium_html)

    config = Config(
        request_delay=0,
        data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
        state_file=str(tmp_path / "state.json"),
        auth_enabled=True,
        auth_login_url=login_url,
        auth_cookies_file=str(tmp_path / "cookies.json"),
    )
    state = load_state(config.state_file)
    args = _args(no_summary=True)

    result = cli.run(config, state, args)

    assert result.scraped >= 1
    # Every article from premium_full.html is premium and not truncated
    assert all(a.is_premium is True for a in result.articles)
    assert all(a.is_truncated is False for a in result.articles)
    assert result.premium_full == result.scraped


def test_limit_run_does_not_advance_state(httpx_mock, tmp_path):
    config = _config(tmp_path)
    _add_sitemaps(httpx_mock)
    free_html = (FIXTURES / "article_free.html").read_text(encoding="utf-8")
    # --limit 2 scrapes only the first two discovered articles (business sitemap).
    httpx_mock.add_response(
        url="https://www.thejakartapost.com/business/2026/05/20/in-window-one.html",
        text=free_html)
    httpx_mock.add_response(
        url="https://www.thejakartapost.com/business/2026/05/20/in-window-two.html",
        text=free_html)
    result = cli.run(config, load_state(config.state_file), _args(limit=2))
    assert result.discovered == 4
    assert result.scraped == 2
    assert not os.path.exists(config.state_file)
