from datetime import datetime, timezone
from pathlib import Path

import pytest

from jakpost_scraper.discovery import (
    DiscoveryError, compute_window, discover, parse_since_arg,
)
from jakpost_scraper.http_client import HttpClient

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
INDEX_URL = "https://www.thejakartapost.com/sitemap.xml"
BIZ_URL = "https://www.thejakartapost.com/business/news/sitemap.xml"
POL_URL = "https://www.thejakartapost.com/news/politics/news/sitemap.xml"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("jakpost_scraper.http_client.time.sleep", lambda s: None)


def _client():
    return HttpClient(timeout=5, retries=2, request_delay=0)


# --- window logic ---

def test_compute_window_first_run_uses_24h():
    since, until = compute_window(None, None, NOW, lookback_buffer_minutes=20)
    assert until == NOW
    assert since == datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)


def test_compute_window_subsequent_run_subtracts_buffer():
    last = datetime(2026, 5, 20, 9, 0, 0, tzinfo=timezone.utc)
    since, until = compute_window(last, None, NOW, lookback_buffer_minutes=20)
    assert since == datetime(2026, 5, 20, 8, 40, 0, tzinfo=timezone.utc)


def test_compute_window_since_override_skips_buffer():
    override = datetime(2026, 5, 18, 0, 0, 0, tzinfo=timezone.utc)
    since, until = compute_window(NOW, override, NOW, lookback_buffer_minutes=20)
    assert since == override


def test_parse_since_arg_duration():
    assert parse_since_arg("24h", NOW) == datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_since_arg("3d", NOW) == datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_since_arg_iso_date():
    assert parse_since_arg("2026-05-19", NOW) == datetime(2026, 5, 19, 0, 0, 0, tzinfo=timezone.utc)


# --- sitemap discovery ---

def _mock_all_sitemaps(httpx_mock):
    httpx_mock.add_response(url=INDEX_URL,
                            content=(FIXTURES / "sitemap_index.xml").read_bytes())
    httpx_mock.add_response(url=BIZ_URL,
                            content=(FIXTURES / "news_sitemap_business.xml").read_bytes())
    httpx_mock.add_response(url=POL_URL,
                            content=(FIXTURES / "news_sitemap_politics.xml").read_bytes())


def test_discover_filters_by_window_seen_adv_and_dedup(httpx_mock):
    _mock_all_sitemaps(httpx_mock)
    since = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    seen = {"https://www.thejakartapost.com/news/politics/2026/05/20/already-seen.html"}
    with _client() as client:
        articles, skipped = discover(client, "all", since, NOW, seen)
    urls = sorted(a.url for a in articles)
    assert urls == [
        "https://www.thejakartapost.com/business/2026/05/20/in-window-one.html",
        "https://www.thejakartapost.com/business/2026/05/20/in-window-two.html",
        "https://www.thejakartapost.com/news/politics/2026/05/20/politics-one.html",
    ]
    assert skipped == []


def test_discover_section_filter(httpx_mock):
    httpx_mock.add_response(url=INDEX_URL,
                            content=(FIXTURES / "sitemap_index.xml").read_bytes())
    httpx_mock.add_response(url=BIZ_URL,
                            content=(FIXTURES / "news_sitemap_business.xml").read_bytes())
    since = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    with _client() as client:
        articles, skipped = discover(client, ["business"], since, NOW, set())
    assert all(a.section == "business" for a in articles)
    assert len(articles) == 2


def test_discover_skips_unreachable_section(httpx_mock):
    httpx_mock.add_response(url=INDEX_URL,
                            content=(FIXTURES / "sitemap_index.xml").read_bytes())
    httpx_mock.add_response(url=BIZ_URL,
                            content=(FIXTURES / "news_sitemap_business.xml").read_bytes())
    for _ in range(2):
        httpx_mock.add_response(url=POL_URL, status_code=503)
    since = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    with _client() as client:
        articles, skipped = discover(client, "all", since, NOW, set())
    assert skipped == ["news/politics"]
    assert len(articles) == 2


def test_discover_raises_when_index_unreachable(httpx_mock):
    for _ in range(2):
        httpx_mock.add_response(url=INDEX_URL, status_code=503)
    since = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    with _client() as client:
        with pytest.raises(DiscoveryError):
            discover(client, "all", since, NOW, set())


def test_discover_warns_when_no_news_sitemaps(httpx_mock, capsys):
    empty_index = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b'<sitemap><loc>https://www.thejakartapost.com/business/web/sitemap.xml'
        b'</loc></sitemap></sitemapindex>'
    )
    httpx_mock.add_response(url=INDEX_URL, content=empty_index)
    since = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    with _client() as client:
        articles, skipped = discover(client, "all", since, NOW, set())
    assert articles == []
    assert "structure may have changed" in capsys.readouterr().err
