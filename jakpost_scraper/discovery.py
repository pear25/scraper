"""Article discovery: time-window computation and Google News sitemap parsing."""

import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from lxml import etree

from .http_client import HttpClient, HttpError
from .models import parse_date, to_utc

SITEMAP_INDEX_URL = "https://www.thejakartapost.com/sitemap.xml"
SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}
_NEWS_SITEMAP_RE = re.compile(r"/news/sitemap\.xml$")
_DURATION_RE = re.compile(r"(\d+)([hd])")
# Advertorial/sponsored content, not news — excluded from discovery.
EXCLUDED_PATH_SEGMENTS = ("/adv/",)


class DiscoveryError(Exception):
    """Raised when discovery cannot proceed (the sitemap index is unavailable)."""


@dataclass
class DiscoveredArticle:
    url: str
    published_at: datetime
    section: str


def parse_since_arg(value: str, now: datetime) -> datetime:
    """Parse a --since value: a duration like '24h'/'3d', or an ISO date."""
    match = _DURATION_RE.fullmatch(value.strip())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        delta = timedelta(hours=amount) if unit == "h" else timedelta(days=amount)
        return to_utc(now) - delta
    return parse_date(value)


def compute_window(last_run_at: datetime | None, since_override: datetime | None,
                   now: datetime, lookback_buffer_minutes: int
                   ) -> tuple[datetime, datetime]:
    """Return the (since, until) window for this run."""
    until = to_utc(now)
    if since_override is not None:
        since = to_utc(since_override)
    elif last_run_at is not None:
        since = to_utc(last_run_at) - timedelta(minutes=lookback_buffer_minutes)
    else:
        since = until - timedelta(hours=24)
    return since, until


def discover(http: HttpClient, sections, since: datetime, until: datetime,
             seen_urls: set[str], index_url: str = SITEMAP_INDEX_URL
             ) -> tuple[list[DiscoveredArticle], list[str]]:
    """Discover articles in [since, until]. Returns (articles, skipped_sections)."""
    try:
        index_xml = http.get(index_url).content
    except HttpError as e:
        raise DiscoveryError(f"Cannot fetch sitemap index: {e}") from e

    news_sitemaps = [
        url for url in _parse_sitemap_index(index_xml)
        if _NEWS_SITEMAP_RE.search(url)
    ]
    if sections != "all":
        wanted = set(sections)
        news_sitemaps = [
            url for url in news_sitemaps
            if _section_from_sitemap_url(url) in wanted
        ]

    if not news_sitemaps:
        print("WARNING: no news sitemaps found in the sitemap index — "
              "The Jakarta Post's sitemap structure may have changed.",
              file=sys.stderr)

    discovered: dict[str, DiscoveredArticle] = {}
    skipped: list[str] = []
    for sitemap_url in news_sitemaps:
        section = _section_from_sitemap_url(sitemap_url)
        try:
            sitemap_xml = http.get(sitemap_url).content
        except HttpError:
            skipped.append(section)
            continue
        for url, published_at in _parse_news_sitemap(sitemap_xml):
            if url in seen_urls or url in discovered:
                continue
            if any(seg in url for seg in EXCLUDED_PATH_SEGMENTS):
                continue
            if since <= published_at <= until:
                discovered[url] = DiscoveredArticle(url, published_at, section)
    return list(discovered.values()), skipped


def _section_from_sitemap_url(url: str) -> str:
    """Derive a section identifier from a news sitemap URL."""
    path = url.split("://", 1)[-1].split("/", 1)[-1]  # drop scheme + host
    return _NEWS_SITEMAP_RE.sub("", path).strip("/")


def _parse_sitemap_index(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    return [
        loc.text.strip()
        for loc in root.findall("sm:sitemap/sm:loc", namespaces=SITEMAP_NS)
        if loc.text
    ]


def _parse_news_sitemap(xml_bytes: bytes) -> list[tuple[str, datetime]]:
    root = etree.fromstring(xml_bytes)
    results: list[tuple[str, datetime]] = []
    for url_el in root.findall("sm:url", namespaces=SITEMAP_NS):
        loc = url_el.find("sm:loc", namespaces=SITEMAP_NS)
        pub = url_el.find("news:news/news:publication_date", namespaces=SITEMAP_NS)
        if loc is None or loc.text is None or pub is None or pub.text is None:
            continue
        results.append((loc.text.strip(), parse_date(pub.text.strip())))
    return results
