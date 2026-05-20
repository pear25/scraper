"""Core data types and datetime helpers. All datetimes are UTC-aware."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from dateutil import parser as _dateparser


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Return dt as a timezone-aware UTC datetime (naive input assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value: str) -> datetime:
    """Parse an arbitrary date string into a UTC datetime."""
    return to_utc(_dateparser.parse(value))


def dt_to_iso(dt: datetime) -> str:
    """Serialize a datetime as a UTC ISO-8601 string ending in Z."""
    return to_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_to_dt(value: str) -> datetime:
    """Parse an ISO-8601 string back into a UTC datetime."""
    return parse_date(value)


@dataclass
class Article:
    url: str
    title: str
    section: str
    published_at: datetime
    authors: list[str]
    body: str
    is_paywalled: bool
    lead_image_url: str | None
    scraped_at: datetime

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "section": self.section,
            "published_at": dt_to_iso(self.published_at),
            "authors": list(self.authors),
            "body": self.body,
            "is_paywalled": self.is_paywalled,
            "lead_image_url": self.lead_image_url,
            "scraped_at": dt_to_iso(self.scraped_at),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(
            url=d["url"],
            title=d["title"],
            section=d["section"],
            published_at=iso_to_dt(d["published_at"]),
            authors=list(d["authors"]),
            body=d["body"],
            is_paywalled=d["is_paywalled"],
            lead_image_url=d["lead_image_url"],
            scraped_at=iso_to_dt(d["scraped_at"]),
        )


@dataclass
class Summary:
    kind: str  # "per-article" or "digest"
    text: str
    model: str
    generated_at: datetime
    article_urls: list[str]
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "text": self.text,
            "model": self.model,
            "generated_at": dt_to_iso(self.generated_at),
            "article_urls": list(self.article_urls),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Summary":
        return cls(
            kind=d["kind"],
            text=d["text"],
            model=d["model"],
            generated_at=iso_to_dt(d["generated_at"]),
            article_urls=list(d["article_urls"]),
            error=d.get("error"),
        )


@dataclass
class RunResult:
    run_id: str
    since: datetime
    until: datetime
    summary_mode: str
    discovered: int = 0
    scraped: int = 0
    skipped_paywall: int = 0
    skipped_sections: list[str] = field(default_factory=list)
    failed_urls: list[str] = field(default_factory=list)
    articles: list[Article] = field(default_factory=list)
    summaries: list[Summary] = field(default_factory=list)
