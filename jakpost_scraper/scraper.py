"""Article page scraping and field extraction."""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from bs4 import BeautifulSoup

from .discovery import DiscoveredArticle
from .http_client import HttpClient
from .models import Article, now_utc, parse_date, to_utc

_ARTICLE_TYPES = {"NewsArticle", "Article", "ReportageNewsArticle"}
_BODY_CONTAINER = "div.tjp-single__content"
_BODY_JUNK = (
    "script, style, figure, "
    "div.tjp-single__content-ads, div.tjp-single__content-list, "
    "div.tjp-paywall, div.tjp-premium, div.tjp-newsletter-box"
)


def parse_article(url: str, html: str, section: str,
                  fallback_published_at: datetime) -> Article:
    """Parse a Jakarta Post article page into an Article."""
    soup = BeautifulSoup(html, "lxml")
    jsonld = _extract_jsonld(soup)
    title = _extract_title(soup, jsonld)
    published_at = _extract_published_at(jsonld, fallback_published_at)
    authors = _extract_authors(jsonld)
    lead_image = _extract_lead_image(soup, jsonld)
    is_premium = _detect_premium(jsonld)  # before body extraction mutates soup
    is_truncated = _detect_truncated(soup)
    body = _extract_body(soup)
    return Article(
        url=url,
        title=title,
        section=section,
        published_at=published_at,
        authors=authors,
        body=body,
        is_paywalled=is_truncated,
        is_premium=is_premium,
        is_truncated=is_truncated,
        lead_image_url=lead_image,
        scraped_at=now_utc(),
    )


def _extract_jsonld(soup: BeautifulSoup) -> dict:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if isinstance(item, dict) and item.get("@type") in _ARTICLE_TYPES:
                return item
    return {}


def _extract_title(soup: BeautifulSoup, jsonld: dict) -> str:
    if jsonld.get("headline"):
        return str(jsonld["headline"]).strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].split(" - ")[0].strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _extract_published_at(jsonld: dict, fallback: datetime) -> datetime:
    raw = jsonld.get("datePublished")
    if raw:
        try:
            return parse_date(str(raw))
        except (ValueError, OverflowError):
            pass
    return to_utc(fallback)


def _extract_authors(jsonld: dict) -> list[str]:
    author = jsonld.get("author")
    if author is None:
        return []
    items = author if isinstance(author, list) else [author]
    names: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]).strip())
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def _extract_lead_image(soup: BeautifulSoup, jsonld: dict) -> str | None:
    img = jsonld.get("image")
    if isinstance(img, dict) and img.get("url"):
        return str(img["url"])
    if isinstance(img, list) and img:
        first = img[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])
        if isinstance(first, str):
            return first
    if isinstance(img, str):
        return img
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]
    return None


def _detect_premium(jsonld: dict) -> bool:
    """True if the article is gated content (JSON-LD isAccessibleForFree=false)."""
    flag = jsonld.get("isAccessibleForFree")
    if flag is None:
        return False
    return str(flag).strip().lower() in ("false", "0", "no")


def _detect_truncated(soup: BeautifulSoup) -> bool:
    """True if this fetched page did not return the full body (paywall block present)."""
    return soup.select_one("div.tjp-paywall") is not None


def _extract_body(soup: BeautifulSoup) -> str:
    content = soup.select_one(_BODY_CONTAINER)
    if content is None:
        return ""
    for junk in content.select(_BODY_JUNK):
        junk.decompose()
    # Merge the drop-cap letter into the first paragraph.
    char = content.select_one(".tjp-opening__char")
    txt = content.select_one("p.tjp-opening__txt")
    if char is not None and txt is not None:
        # Prepend the letter directly to the first text node to avoid spaces.
        letter = char.get_text()
        first_text = txt.find(string=True)
        if first_text is not None:
            first_text.replace_with(letter + first_text)
        else:
            txt.insert(0, letter)
        char.decompose()
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in content.find_all("p")
    ]
    return "\n\n".join(p for p in paragraphs if p)


def scrape_articles(http: HttpClient, discovered: list[DiscoveredArticle],
                    concurrency: int, paywall_mode: str,
                    on_progress: Callable[[int, int, str, bool], None] | None = None
                    ) -> tuple[list[Article], list[str], list[str]]:
    """Fetch and parse discovered articles concurrently.

    Returns (articles, failed_urls, skipped_paywall_urls). With
    paywall_mode="skip", paywalled articles are excluded and their URLs go to
    skipped_paywall_urls; with "keep-teaser" they are kept in articles.

    on_progress, if given, is invoked as (done, total, url, ok) each time an
    article fetch completes — ok is False when the fetch raised.
    """
    if not discovered:
        return [], [], []

    results: dict[str, Article] = {}
    failed_urls: list[str] = []
    total = len(discovered)

    def _fetch(item: DiscoveredArticle) -> Article:
        html = http.get(item.url).text
        return parse_article(item.url, html, item.section, item.published_at)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        future_map = {pool.submit(_fetch, d): d for d in discovered}
        for done, future in enumerate(as_completed(future_map), start=1):
            item = future_map[future]
            try:
                results[item.url] = future.result()
                ok = True
            except Exception:  # noqa: BLE001 - any failure means skip this article
                failed_urls.append(item.url)
                ok = False
            if on_progress is not None:
                on_progress(done, total, item.url, ok)

    articles: list[Article] = []
    skipped_paywall_urls: list[str] = []
    for item in discovered:  # preserve discovery order
        article = results.get(item.url)
        if article is None:
            continue
        if article.is_paywalled and paywall_mode == "skip":
            skipped_paywall_urls.append(article.url)
        else:
            articles.append(article)

    failed_urls.sort()
    return articles, failed_urls, skipped_paywall_urls
