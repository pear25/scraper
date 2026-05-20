from datetime import datetime, timezone
from pathlib import Path

import pytest

from jakpost_scraper.discovery import DiscoveredArticle
from jakpost_scraper.http_client import HttpClient
from jakpost_scraper.scraper import scrape_articles

FIXTURES = Path(__file__).parent / "fixtures"
PUB = datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc)
FREE_URL = "https://www.thejakartapost.com/business/2026/05/20/free.html"
PAY_URL = "https://www.thejakartapost.com/business/2026/05/20/pay.html"
GONE_URL = "https://www.thejakartapost.com/business/2026/05/20/gone.html"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("jakpost_scraper.http_client.time.sleep", lambda s: None)


def _client():
    return HttpClient(timeout=5, retries=2, request_delay=0)


def _discovered():
    return [
        DiscoveredArticle(FREE_URL, PUB, "business"),
        DiscoveredArticle(PAY_URL, PUB, "business"),
        DiscoveredArticle(GONE_URL, PUB, "business"),
    ]


def _mock(httpx_mock):
    httpx_mock.add_response(
        url=FREE_URL, text=(FIXTURES / "article_free.html").read_text(encoding="utf-8"))
    httpx_mock.add_response(
        url=PAY_URL, text=(FIXTURES / "article_paywalled.html").read_text(encoding="utf-8"))
    for _ in range(2):
        httpx_mock.add_response(url=GONE_URL, status_code=503)


def test_scrape_keep_teaser_includes_paywalled(httpx_mock):
    _mock(httpx_mock)
    with _client() as client:
        articles, failed, skipped_pw = scrape_articles(
            client, _discovered(), concurrency=2, paywall_mode="keep-teaser")
    assert {a.url for a in articles} == {FREE_URL, PAY_URL}
    assert failed == [GONE_URL]
    assert skipped_pw == []


def test_scrape_skip_mode_drops_paywalled(httpx_mock):
    _mock(httpx_mock)
    with _client() as client:
        articles, failed, skipped_pw = scrape_articles(
            client, _discovered(), concurrency=2, paywall_mode="skip")
    assert {a.url for a in articles} == {FREE_URL}
    assert skipped_pw == [PAY_URL]
    assert failed == [GONE_URL]


def test_scrape_empty_input():
    with _client() as client:
        articles, failed, skipped_pw = scrape_articles(
            client, [], concurrency=2, paywall_mode="keep-teaser")
    assert articles == [] and failed == [] and skipped_pw == []
