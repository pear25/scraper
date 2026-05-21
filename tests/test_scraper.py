from datetime import datetime, timezone
from pathlib import Path

from jakpost_scraper.scraper import parse_article

FIXTURES = Path(__file__).parent / "fixtures"
FALLBACK = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)


def _free_html():
    return (FIXTURES / "article_free.html").read_text(encoding="utf-8")


def _paywalled_html():
    return (FIXTURES / "article_paywalled.html").read_text(encoding="utf-8")


def test_parse_free_article_fields():
    art = parse_article("https://example.com/free.html", _free_html(),
                        "business", FALLBACK)
    assert art.title == "Indonesia unveils new green energy roadmap"
    assert art.section == "business"
    assert art.published_at == datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc)
    assert art.authors == ["Reporter One"]
    assert art.is_paywalled is False
    assert art.lead_image_url == "https://img.jakpost.net/c/2026/05/20/free_large.jpg"


def test_parse_free_article_body_includes_dropcap_and_strips_junk():
    art = parse_article("https://example.com/free.html", _free_html(),
                        "business", FALLBACK)
    assert art.body.startswith("The government announced a new roadmap")
    assert "renewable capacity by 2030" in art.body
    assert "ADVERTISEMENT JUNK" not in art.body
    assert "POPULAR ARTICLES JUNK" not in art.body


def test_parse_paywalled_article_detected():
    art = parse_article("https://example.com/pay.html", _paywalled_html(),
                        "business", FALLBACK)
    assert art.is_paywalled is True
    assert art.body.startswith("Bank Indonesia raised its benchmark rate")
    assert "Subscribe to read" not in art.body


def test_parse_article_falls_back_when_no_jsonld():
    html = (
        '<html><head>'
        '<meta property="og:title" content="Fallback Title - Business - The Jakarta Post"/>'
        '</head><body><div class="tjp-single__content">'
        '<p>Only paragraph.</p></div></body></html>'
    )
    art = parse_article("https://example.com/x.html", html, "world", FALLBACK)
    assert art.title == "Fallback Title"
    assert art.published_at == FALLBACK
    assert art.authors == []
    assert art.body == "Only paragraph."


def _premium_full_html():
    return (FIXTURES / "article_premium_full.html").read_text(encoding="utf-8")


def test_paywalled_article_is_premium_and_truncated():
    art = parse_article("https://example.com/pay.html", _paywalled_html(),
                        "business", FALLBACK)
    assert art.is_premium is True
    assert art.is_truncated is True
    assert art.is_paywalled is True


def test_premium_full_article_is_premium_but_not_truncated():
    art = parse_article("https://example.com/full.html", _premium_full_html(),
                        "business", FALLBACK)
    assert art.is_premium is True
    assert art.is_truncated is False
    assert art.is_paywalled is False
    assert art.body.startswith("Bank Indonesia raised its benchmark rate")
    assert "persistent inflation pressure" in art.body


def test_free_article_is_neither_premium_nor_truncated():
    art = parse_article("https://example.com/free.html", _free_html(),
                        "business", FALLBACK)
    assert art.is_premium is False
    assert art.is_truncated is False
    assert art.is_paywalled is False
