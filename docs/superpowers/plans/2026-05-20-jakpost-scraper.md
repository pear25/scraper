# Jakarta Post Scraper & Summarizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that, on each manual run, discovers Jakarta Post articles published since the last run, scrapes their full text, summarizes them via the Claude Agent SDK, and writes JSON files plus a Markdown report.

**Architecture:** A `jakpost_scraper` package with one module per pipeline stage (config → state → discovery → scraper → summarizer → output), wired together by `cli.py`. Discovery walks The Jakarta Post's Google News sitemaps; a `state.json` file records the last-run timestamp and a seen-URL set so each run only processes new articles.

**Tech Stack:** Python 3.11+, `httpx` (HTTP), `beautifulsoup4` + `lxml` (HTML/XML parsing), `python-dateutil` (dates), `pyyaml` (config), `claude-agent-sdk` (summarization), `pytest` + `pytest-httpx` (tests).

**Spec:** `docs/superpowers/specs/2026-05-20-jakpost-scraper-design.md`

---

## Conventions

- TDD: write the failing test first, watch it fail, implement, watch it pass, commit.
- All datetimes are timezone-aware UTC.
- Run tests with `python -m pytest`. Run from the repo root.
- Each task ends with a commit. Never commit failing code.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `jakpost_scraper/__init__.py`
- Create: `.gitignore`
- Create: `config.yaml`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Create the project files**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "jakpost-scraper"
version = "0.1.0"
description = "Scrape and summarize The Jakarta Post articles"
requires-python = ">=3.11"
dependencies = [
    "httpx",
    "beautifulsoup4",
    "lxml",
    "python-dateutil",
    "pyyaml",
    "claude-agent-sdk",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-httpx"]

[project.scripts]
jakpost-scrape = "jakpost_scraper.cli:cli_entry"

[tool.setuptools]
packages = ["jakpost_scraper"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`jakpost_scraper/__init__.py`:

```python
"""Scrape and summarize The Jakarta Post articles."""

__version__ = "0.1.0"
```

`.gitignore`:

```
__pycache__/
*.egg-info/
.pytest_cache/
.venv/
venv/
data/
reports/
state.json
```

`config.yaml`:

```yaml
# Jakarta Post scraper configuration. All keys are optional; defaults shown.
sections: all              # "all" or a list of section identifiers
summary_mode: both         # per-article | digest | both
model: claude-haiku-4-5    # Claude model for summarization
paywall: keep-teaser       # keep-teaser | skip
request_delay: 1.0         # seconds between HTTP requests
concurrency: 4             # max concurrent article fetches / summary calls
lookback_buffer_minutes: 20
seen_url_retention_days: 30
http_timeout: 15           # seconds
http_retries: 3            # attempts per request
data_dir: ./data
reports_dir: ./reports
state_file: ./state.json
```

`tests/test_smoke.py`:

```python
def test_package_imports():
    import jakpost_scraper

    assert jakpost_scraper.__version__ == "0.1.0"
```

- [ ] **Step 2: Install the package and dev dependencies**

Run: `python -m pip install -e ".[dev]"`
Expected: installs httpx, beautifulsoup4, lxml, python-dateutil, pyyaml, claude-agent-sdk, pytest, pytest-httpx, and `jakpost-scraper` in editable mode, ending with `Successfully installed ...`.

- [ ] **Step 3: Run the smoke test**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS — `test_package_imports`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml jakpost_scraper/__init__.py .gitignore config.yaml tests/test_smoke.py
git commit -m "chore: scaffold jakpost_scraper package"
```

---

### Task 2: Test fixtures

Hand-crafted fixtures that faithfully reproduce The Jakarta Post's real
sitemap and article structure (verified against thejakartapost.com on
2026-05-20). Tests assert against these, so the suite is fully deterministic.

**Files:**
- Create: `tests/fixtures/sitemap_index.xml`
- Create: `tests/fixtures/news_sitemap_business.xml`
- Create: `tests/fixtures/news_sitemap_politics.xml`
- Create: `tests/fixtures/article_free.html`
- Create: `tests/fixtures/article_paywalled.html`

- [ ] **Step 1: Create the sitemap fixtures**

`tests/fixtures/sitemap_index.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.thejakartapost.com/business/news/sitemap.xml</loc></sitemap>
  <sitemap><loc>https://www.thejakartapost.com/business/web/sitemap.xml</loc></sitemap>
  <sitemap><loc>https://www.thejakartapost.com/business/images/sitemap.xml</loc></sitemap>
  <sitemap><loc>https://www.thejakartapost.com/news/politics/news/sitemap.xml</loc></sitemap>
  <sitemap><loc>https://www.thejakartapost.com/news/politics/web/sitemap.xml</loc></sitemap>
</sitemapindex>
```

`tests/fixtures/news_sitemap_business.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/business/2026/05/20/in-window-one.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-20T10:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[In window one]]></news:title>
    </news:news>
  </url>
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/business/2026/05/20/in-window-two.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-20T08:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[In window two]]></news:title>
    </news:news>
  </url>
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/business/2026/05/18/too-old.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-18T09:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[Too old]]></news:title>
    </news:news>
  </url>
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/adv/2026/05/20/sponsored-content.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-20T09:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[Sponsored content]]></news:title>
    </news:news>
  </url>
</urlset>
```

`tests/fixtures/news_sitemap_politics.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/news/politics/2026/05/20/politics-one.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-20T11:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[Politics one]]></news:title>
    </news:news>
  </url>
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/business/2026/05/20/in-window-one.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-20T10:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[In window one duplicate]]></news:title>
    </news:news>
  </url>
  <url>
    <loc>
      <![CDATA[https://www.thejakartapost.com/news/politics/2026/05/20/already-seen.html]]>
    </loc>
    <news:news>
      <news:publication><news:name><![CDATA[ The Jakarta Post ]]></news:name><news:language><![CDATA[ en ]]></news:language></news:publication>
      <news:publication_date><![CDATA[2026-05-20T07:00:00+07:00]]></news:publication_date>
      <news:title><![CDATA[Already seen]]></news:title>
    </news:news>
  </url>
</urlset>
```

- [ ] **Step 2: Create the article fixtures**

`tests/fixtures/article_free.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta property="og:title" content="Indonesia unveils new green energy roadmap - Business - The Jakarta Post" />
  <meta property="og:image" content="https://img.jakpost.net/c/2026/05/20/free_large.jpg" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "Indonesia unveils new green energy roadmap",
    "datePublished": "2026-05-20T10:00:00+07:00",
    "dateModified": "2026-05-20T11:30:00+07:00",
    "isAccessibleForFree": "true",
    "author": [{"@type": "Person", "name": "Reporter One"}],
    "image": {"@type": "ImageObject", "url": "https://img.jakpost.net/c/2026/05/20/free_large.jpg"}
  }
  </script>
</head>
<body>
  <h1 class="tjp-title">Indonesia unveils new green energy roadmap</h1>
  <div class="tjp-single__content">
    <div class="tjp-single__content-ads">ADVERTISEMENT JUNK</div>
    <div class="tjp-opening">
      <h1 class="tjp-opening__char">T</h1>
      <p class="tjp-opening__txt">he government announced a new roadmap on Wednesday.</p>
    </div>
    <p>The plan targets a major increase in renewable capacity by 2030.</p>
    <p>Officials said funding would come from a mix of public and private sources.</p>
    <div class="tjp-single__content-list tjp-single__content-list--popular">POPULAR ARTICLES JUNK</div>
  </div>
</body>
</html>
```

`tests/fixtures/article_paywalled.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta property="og:title" content="BI hikes key interest rate by 50 bps - Business - The Jakarta Post" />
  <meta property="og:image" content="https://img.jakpost.net/c/2026/05/20/pay_large.jpg" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "BI hikes key interest rate by 50 bps",
    "datePublished": "2026-05-20T08:00:00+07:00",
    "dateModified": "2026-05-20T09:00:00+07:00",
    "isAccessibleForFree": "false",
    "author": [{"@type": "Person", "name": "Reporter Two"}],
    "image": {"@type": "ImageObject", "url": "https://img.jakpost.net/c/2026/05/20/pay_large.jpg"}
  }
  </script>
</head>
<body>
  <h1 class="tjp-title">BI hikes key interest rate by 50 bps</h1>
  <div class="tjp-single__content">
    <div class="tjp-opening">
      <h1 class="tjp-opening__char">B</h1>
      <p class="tjp-opening__txt">ank Indonesia raised its benchmark rate on Wednesday.</p>
    </div>
    <div class="tjp-paywall">
      <div class="tjp-paywall__box">Subscribe to read the full article.</div>
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 3: Verify the fixtures are well-formed**

Run: `python -c "from lxml import etree; [etree.parse(f'tests/fixtures/{n}') for n in ('sitemap_index.xml','news_sitemap_business.xml','news_sitemap_politics.xml')]; print('XML OK')"`
Expected: prints `XML OK` with no exception.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures
git commit -m "test: add Jakarta Post sitemap and article fixtures"
```

---

### Task 3: Data models and datetime helpers

**Files:**
- Create: `jakpost_scraper/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.models'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS — all 7 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/models.py tests/test_models.py
git commit -m "feat: add data models and datetime helpers"
```

---

### Task 4: Configuration

**Files:**
- Create: `jakpost_scraper/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:

```python
import pytest

from jakpost_scraper.config import Config, ConfigError, load_config, validate_config


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {})
    assert cfg.summary_mode == "both"
    assert cfg.concurrency == 4
    assert cfg.sections == "all"


def test_yaml_overrides_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("summary_mode: digest\nconcurrency: 8\n")
    cfg = load_config(str(path), {})
    assert cfg.summary_mode == "digest"
    assert cfg.concurrency == 8


def test_cli_overrides_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("summary_mode: digest\n")
    cfg = load_config(str(path), {"summary_mode": "per-article"})
    assert cfg.summary_mode == "per-article"


def test_cli_none_values_ignored(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {"summary_mode": None})
    assert cfg.summary_mode == "both"


def test_unknown_yaml_key_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("bogus_key: 1\n")
    with pytest.raises(ConfigError, match="Unknown config key"):
        load_config(str(path), {})


def test_invalid_summary_mode_rejected():
    with pytest.raises(ConfigError, match="summary_mode"):
        validate_config(Config(summary_mode="nonsense"))


def test_negative_concurrency_rejected():
    with pytest.raises(ConfigError, match="concurrency"):
        validate_config(Config(concurrency=0))


def test_sections_list_accepted():
    validate_config(Config(sections=["business", "news/politics"]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.config'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/config.py`:

```python
"""Configuration: defaults, YAML file, and CLI overrides."""

import os
from dataclasses import dataclass, fields

import yaml

SUMMARY_MODES = ("per-article", "digest", "both")
PAYWALL_MODES = ("keep-teaser", "skip")


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class Config:
    sections: object = "all"  # "all" or list[str]
    summary_mode: str = "both"
    model: str = "claude-haiku-4-5"
    paywall: str = "keep-teaser"
    request_delay: float = 1.0
    concurrency: int = 4
    lookback_buffer_minutes: int = 20
    seen_url_retention_days: int = 30
    http_timeout: int = 15
    http_retries: int = 3
    data_dir: str = "./data"
    reports_dir: str = "./reports"
    state_file: str = "./state.json"


def load_config(config_path: str | None, cli_overrides: dict) -> Config:
    """Build a Config from defaults, an optional YAML file, then CLI overrides."""
    values: dict = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise ConfigError(f"{config_path} must contain a YAML mapping")
        values.update(loaded)

    known = {f.name for f in fields(Config)}
    for key in values:
        if key not in known:
            raise ConfigError(f"Unknown config key: {key}")

    values.update({k: v for k, v in cli_overrides.items() if v is not None})
    cfg = Config(**values)
    validate_config(cfg)
    return cfg


def validate_config(cfg: Config) -> None:
    """Raise ConfigError if any field holds an invalid value."""
    if cfg.summary_mode not in SUMMARY_MODES:
        raise ConfigError(f"summary_mode must be one of {SUMMARY_MODES}")
    if cfg.paywall not in PAYWALL_MODES:
        raise ConfigError(f"paywall must be one of {PAYWALL_MODES}")
    for name in ("concurrency", "http_retries", "http_timeout",
                 "lookback_buffer_minutes", "seen_url_retention_days"):
        if getattr(cfg, name) < 1:
            raise ConfigError(f"{name} must be >= 1")
    if cfg.request_delay < 0:
        raise ConfigError("request_delay must be >= 0")
    if cfg.sections != "all" and not isinstance(cfg.sections, list):
        raise ConfigError('sections must be "all" or a list')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS — all 8 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/config.py tests/test_config.py
git commit -m "feat: add configuration loading and validation"
```

---

### Task 5: State management

**Files:**
- Create: `jakpost_scraper/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_state.py`:

```python
from datetime import datetime, timezone

import pytest

from jakpost_scraper.state import State, StateError, load_state, save_state, prune_seen


def test_load_missing_file_is_first_run(tmp_path):
    state = load_state(str(tmp_path / "state.json"))
    assert state.last_run_at is None
    assert state.seen_urls == {}


def test_save_then_load_round_trip(tmp_path):
    path = str(tmp_path / "state.json")
    original = State(
        last_run_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        seen_urls={"https://example.com/a.html":
                   datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)},
    )
    save_state(path, original)
    loaded = load_state(path)
    assert loaded.last_run_at == original.last_run_at
    assert loaded.seen_urls == original.seen_urls


def test_corrupt_file_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not valid json")
    with pytest.raises(StateError):
        load_state(str(path))


def test_prune_seen_drops_old_entries():
    now = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    state = State(
        last_run_at=now,
        seen_urls={
            "https://example.com/old.html": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "https://example.com/new.html": datetime(2026, 5, 19, tzinfo=timezone.utc),
        },
    )
    prune_seen(state, retention_days=30, now=now)
    assert "https://example.com/old.html" not in state.seen_urls
    assert "https://example.com/new.html" in state.seen_urls


def test_save_is_atomic_leaves_no_temp_files(tmp_path):
    path = str(tmp_path / "state.json")
    save_state(path, State())
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "state.json"]
    assert leftovers == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.state'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/state.py`:

```python
"""Persistent run state: last-run timestamp and the seen-URL set."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import dt_to_iso, iso_to_dt, to_utc


class StateError(Exception):
    """Raised when an existing state file cannot be parsed."""


@dataclass
class State:
    last_run_at: datetime | None = None
    seen_urls: dict[str, datetime] = field(default_factory=dict)


def load_state(path: str) -> State:
    """Load state from path. A missing file is a valid first run."""
    if not os.path.exists(path):
        return State()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        last = data.get("last_run_at")
        seen = {
            entry["url"]: iso_to_dt(entry["seen_at"])
            for entry in data.get("seen_urls", [])
        }
        return State(
            last_run_at=iso_to_dt(last) if last else None,
            seen_urls=seen,
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        raise StateError(f"Cannot parse state file {path}: {e}") from e


def save_state(path: str, state: State) -> None:
    """Write state to path atomically (temp file + rename)."""
    data = {
        "last_run_at": dt_to_iso(state.last_run_at) if state.last_run_at else None,
        "seen_urls": [
            {"url": url, "seen_at": dt_to_iso(seen_at)}
            for url, seen_at in sorted(state.seen_urls.items())
        ],
    }
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def prune_seen(state: State, retention_days: int, now: datetime) -> None:
    """Drop seen-URL entries older than retention_days (mutates state)."""
    cutoff = to_utc(now) - timedelta(days=retention_days)
    state.seen_urls = {
        url: seen_at
        for url, seen_at in state.seen_urls.items()
        if to_utc(seen_at) >= cutoff
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS — all 5 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/state.py tests/test_state.py
git commit -m "feat: add state persistence with seen-URL pruning"
```

---

### Task 6: HTTP client

**Files:**
- Create: `jakpost_scraper/http_client.py`
- Test: `tests/test_http_client.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_http_client.py`:

```python
import pytest

from jakpost_scraper.http_client import HttpClient, HttpError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("jakpost_scraper.http_client.time.sleep", lambda s: None)


def _client():
    return HttpClient(timeout=5, retries=3, request_delay=0)


def test_get_returns_body_on_200(httpx_mock):
    httpx_mock.add_response(url="https://example.com/p", text="hello")
    with _client() as client:
        assert client.get("https://example.com/p").text == "hello"


def test_get_retries_then_succeeds(httpx_mock):
    httpx_mock.add_response(url="https://example.com/p", status_code=503)
    httpx_mock.add_response(url="https://example.com/p", text="ok")
    with _client() as client:
        assert client.get("https://example.com/p").text == "ok"


def test_get_raises_after_exhausting_retries(httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(url="https://example.com/p", status_code=503)
    with _client() as client:
        with pytest.raises(HttpError):
            client.get("https://example.com/p")


def test_get_raises_immediately_on_404(httpx_mock):
    httpx_mock.add_response(url="https://example.com/p", status_code=404)
    with _client() as client:
        with pytest.raises(HttpError):
            client.get("https://example.com/p")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_http_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.http_client'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/http_client.py`:

```python
"""Shared HTTP client with retries and a politeness delay."""

import time

import httpx

USER_AGENT = (
    "jakpost-scraper/0.1 (news summarizer bot; "
    "contact: configure in http_client.py)"
)
RETRY_STATUSES = {429, 500, 502, 503, 504}


class HttpError(Exception):
    """Raised when a request fails after all retries."""


class HttpClient:
    """Thread-safe HTTP client with retry/backoff and a per-request delay."""

    def __init__(self, timeout: int, retries: int, request_delay: float,
                 user_agent: str = USER_AGENT):
        self.retries = retries
        self.request_delay = request_delay
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def get(self, url: str) -> httpx.Response:
        """GET url, retrying transient failures. Raises HttpError on failure."""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            if self.request_delay:
                time.sleep(self.request_delay)
            try:
                response = self._client.get(url)
            except httpx.HTTPError as e:
                last_error = e
                time.sleep(2 ** attempt)
                continue
            if response.status_code in RETRY_STATUSES:
                last_error = HttpError(f"{url} returned {response.status_code}")
                time.sleep(_retry_after(response, 2 ** attempt))
                continue
            if response.status_code >= 400:
                raise HttpError(f"{url} returned {response.status_code}")
            return response
        raise HttpError(f"Failed to fetch {url}: {last_error}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _retry_after(response: httpx.Response, default: float) -> float:
    value = response.headers.get("Retry-After")
    if value and value.isdigit():
        return float(value)
    return default
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_http_client.py -v`
Expected: PASS — all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/http_client.py tests/test_http_client.py
git commit -m "feat: add HTTP client with retry and politeness delay"
```

---

### Task 7: Discovery (time window + sitemap parsing)

**Files:**
- Create: `jakpost_scraper/discovery.py`
- Test: `tests/test_discovery.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_discovery.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.discovery'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/discovery.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: PASS — all 10 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/discovery.py tests/test_discovery.py
git commit -m "feat: add discovery with time window and sitemap parsing"
```

---

### Task 8: Article extraction

**Files:**
- Create: `jakpost_scraper/scraper.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.scraper'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/scraper.py`:

```python
"""Article page scraping and field extraction."""

import json
from datetime import datetime

from bs4 import BeautifulSoup

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
    is_paywalled = _detect_paywall(soup, jsonld)  # before body extraction mutates soup
    body = _extract_body(soup)
    return Article(
        url=url,
        title=title,
        section=section,
        published_at=published_at,
        authors=authors,
        body=body,
        is_paywalled=is_paywalled,
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


def _detect_paywall(soup: BeautifulSoup, jsonld: dict) -> bool:
    flag = jsonld.get("isAccessibleForFree")
    if flag is not None:
        return str(flag).strip().lower() in ("false", "0", "no")
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
        txt.insert(0, char.get_text())
        char.decompose()
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in content.find_all("p")
    ]
    return "\n\n".join(p for p in paragraphs if p)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: PASS — all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/scraper.py tests/test_scraper.py
git commit -m "feat: add article extraction with JSON-LD and paywall detection"
```

---

### Task 9: Scrape orchestration

**Files:**
- Modify: `jakpost_scraper/scraper.py` (append `scrape_articles`)
- Test: `tests/test_scrape_articles.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_scrape_articles.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scrape_articles.py -v`
Expected: FAIL — `ImportError: cannot import name 'scrape_articles'`.

- [ ] **Step 3: Append the implementation to `jakpost_scraper/scraper.py`**

Add this import near the top of `jakpost_scraper/scraper.py`, after the existing imports:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

from .discovery import DiscoveredArticle
from .http_client import HttpClient
```

Append this function to the end of `jakpost_scraper/scraper.py`:

```python
def scrape_articles(http: HttpClient, discovered: list[DiscoveredArticle],
                    concurrency: int, paywall_mode: str
                    ) -> tuple[list[Article], list[str], list[str]]:
    """Fetch and parse discovered articles concurrently.

    Returns (articles, failed_urls, skipped_paywall_urls). With
    paywall_mode="skip", paywalled articles are excluded and their URLs go to
    skipped_paywall_urls; with "keep-teaser" they are kept in articles.
    """
    if not discovered:
        return [], [], []

    results: dict[str, Article] = {}
    failed_urls: list[str] = []

    def _fetch(item: DiscoveredArticle) -> Article:
        html = http.get(item.url).text
        return parse_article(item.url, html, item.section, item.published_at)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        future_map = {pool.submit(_fetch, d): d for d in discovered}
        for future in as_completed(future_map):
            item = future_map[future]
            try:
                results[item.url] = future.result()
            except Exception:  # noqa: BLE001 - any failure means skip this article
                failed_urls.append(item.url)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scraper.py tests/test_scrape_articles.py -v`
Expected: PASS — all 7 tests (4 from Task 8, 3 here).

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/scraper.py tests/test_scrape_articles.py
git commit -m "feat: add concurrent scrape orchestration with paywall handling"
```

---

### Task 10: Summarizer — per-article mode

**Files:**
- Create: `jakpost_scraper/summarizer.py`
- Test: `tests/test_summarizer.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_summarizer.py`:

```python
from datetime import datetime, timezone

import pytest

from jakpost_scraper.models import Article
from jakpost_scraper import summarizer

PUB = datetime(2026, 5, 20, 3, 0, 0, tzinfo=timezone.utc)


def _article(url: str, title: str = "Title", paywalled: bool = False) -> Article:
    return Article(
        url=url, title=title, section="business", published_at=PUB,
        authors=["Reporter"], body="Article body text.", is_paywalled=paywalled,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.summarizer'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/summarizer.py`:

```python
"""Summarize articles via the Claude Agent SDK."""

import asyncio
import shutil

from claude_agent_sdk import ClaudeAgentOptions, query

try:  # message types live in .types on most versions, top-level on some
    from claude_agent_sdk.types import AssistantMessage, TextBlock
except ImportError:  # pragma: no cover
    from claude_agent_sdk import AssistantMessage, TextBlock

from .models import Article, Summary, now_utc

SUMMARIZER_SYSTEM_PROMPT = (
    "You are a concise news summarizer for an Indonesian news digest. "
    "You write clear, factual, neutral summaries. You never invent facts "
    "beyond the provided text. Respond with summary text only — no preamble."
)
# Per-article summaries beyond this count are digested in batches.
DIGEST_BATCH_SIZE = 40


class PreflightError(Exception):
    """Raised when the environment cannot run summarization."""


def preflight_check() -> None:
    """Verify the `claude` CLI is installed (required by the Agent SDK)."""
    if shutil.which("claude") is None:
        raise PreflightError(
            "The `claude` CLI was not found on PATH. Install and authenticate "
            "Claude Code, or run with --no-summary."
        )


def summarize(articles: list[Article], mode: str, model: str,
              concurrency: int) -> list[Summary]:
    """Summarize articles in the given mode. Synchronous entry point."""
    if not articles:
        return []
    return asyncio.run(_run(articles, mode, model, concurrency))


async def _run(articles: list[Article], mode: str, model: str,
               concurrency: int) -> list[Summary]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    per_article = await asyncio.gather(
        *[_summarize_one(a, model, semaphore) for a in articles]
    )
    summaries: list[Summary] = []
    if mode in ("per-article", "both"):
        summaries.extend(per_article)
    if mode in ("digest", "both"):
        summaries.append(await _summarize_digest(per_article, model))
    return summaries


async def _summarize_one(article: Article, model: str,
                         semaphore: asyncio.Semaphore) -> Summary:
    async with semaphore:
        prompt = _per_article_prompt(article)
        try:
            text = await _retry(lambda: _ask_claude(prompt, model))
        except Exception as e:  # noqa: BLE001 - record failure, keep going
            return Summary(kind="per-article", text="", model=model,
                           generated_at=now_utc(), article_urls=[article.url],
                           error=str(e))
        return Summary(kind="per-article", text=text, model=model,
                       generated_at=now_utc(), article_urls=[article.url])


async def _ask_claude(prompt: str, model: str) -> str:
    """Send one prompt to Claude via the Agent SDK and return the text reply."""
    options = ClaudeAgentOptions(
        system_prompt=SUMMARIZER_SYSTEM_PROMPT,
        model=model,
        allowed_tools=[],
        max_turns=1,
    )
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
    return "".join(chunks).strip()


async def _retry(coro_factory, attempts: int = 2):
    """Await coro_factory(), retrying up to `attempts` times total."""
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await coro_factory()
        except Exception as e:  # noqa: BLE001 - retried below
            last_error = e
    raise last_error


def _per_article_prompt(article: Article) -> str:
    note = ""
    if article.is_paywalled:
        note = ("\n\nNote: only the article teaser is available because the "
                "full text is paywalled. Summarize what is provided.")
    return (
        "Summarize the following news article in 2-4 sentences. Focus on what "
        f"happened, who is involved, and why it matters.{note}\n\n"
        f"Title: {article.title}\n\n{article.body}"
    )
```

Note: `_summarize_digest` is added in Task 11; `_run` already calls it, so the
digest-mode tests are deferred to that task. Per-article and empty-input tests
pass now.

- [ ] **Step 4: Run the per-article tests**

Run: `python -m pytest tests/test_summarizer.py -v`
Expected: PASS — all 4 tests (none use digest mode).

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/summarizer.py tests/test_summarizer.py
git commit -m "feat: add per-article summarization via Claude Agent SDK"
```

---

### Task 11: Summarizer — digest and both modes

**Files:**
- Modify: `jakpost_scraper/summarizer.py` (append digest functions)
- Test: `tests/test_summarizer_digest.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_summarizer_digest.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_summarizer_digest.py -v`
Expected: FAIL — `AttributeError: module 'jakpost_scraper.summarizer' has no attribute '_summarize_digest'`.

- [ ] **Step 3: Append the implementation to `jakpost_scraper/summarizer.py`**

Append these functions to the end of `jakpost_scraper/summarizer.py`:

```python
async def _summarize_digest(per_article_summaries: list[Summary],
                            model: str) -> Summary:
    """Build one digest from per-article summaries, batching when large."""
    usable = [s for s in per_article_summaries if not s.error and s.text]
    article_urls = [url for s in usable for url in s.article_urls]
    if not usable:
        return Summary(kind="digest", text="", model=model,
                       generated_at=now_utc(), article_urls=article_urls,
                       error="no per-article summaries were available")
    try:
        if len(usable) <= DIGEST_BATCH_SIZE:
            prompt = _digest_prompt(usable)
        else:
            partials = await _partial_digests(usable, model)
            prompt = _merge_digests_prompt(partials)
        text = await _retry(lambda: _ask_claude(prompt, model))
    except Exception as e:  # noqa: BLE001 - record failure, keep per-article work
        return Summary(kind="digest", text="", model=model,
                       generated_at=now_utc(), article_urls=article_urls,
                       error=str(e))
    return Summary(kind="digest", text=text, model=model,
                   generated_at=now_utc(), article_urls=article_urls)


async def _partial_digests(usable: list[Summary], model: str) -> list[str]:
    partials: list[str] = []
    for start in range(0, len(usable), DIGEST_BATCH_SIZE):
        batch = usable[start:start + DIGEST_BATCH_SIZE]
        partials.append(
            await _retry(lambda b=batch: _ask_claude(_digest_prompt(b), model)))
    return partials


def _digest_prompt(summaries: list[Summary]) -> str:
    items = "\n\n".join(f"- {s.text}" for s in summaries)
    return (
        "Below are short summaries of news articles published in the last day. "
        "Write a daily news briefing: a one-paragraph overview at the top, then "
        "the stories grouped into themes under short Markdown headings. Keep it "
        f"tight and readable.\n\n{items}"
    )


def _merge_digests_prompt(partials: list[str]) -> str:
    joined = "\n\n---\n\n".join(partials)
    return (
        "Below are several partial news briefings covering different batches of "
        "articles from the same day. Merge them into one coherent briefing with "
        "a one-paragraph overview at the top and theme headings, removing "
        f"redundancy.\n\n{joined}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_summarizer.py tests/test_summarizer_digest.py -v`
Expected: PASS — all 9 tests (4 from Task 10, 5 here).

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/summarizer.py tests/test_summarizer_digest.py
git commit -m "feat: add digest and both summary modes with batching"
```

---

### Task 12: Output writing

**Files:**
- Create: `jakpost_scraper/output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_output.py`:

```python
import json
from datetime import datetime, timezone

from jakpost_scraper.config import Config
from jakpost_scraper.models import Article, RunResult, Summary
from jakpost_scraper.output import (
    write_articles_json, write_summaries_json, write_markdown_report,
)

SINCE = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


def _article(url: str) -> Article:
    return Article(
        url=url, title="Green roadmap", section="business", published_at=UNTIL,
        authors=["Reporter"], body="Body.", is_paywalled=False,
        lead_image_url=None, scraped_at=UNTIL,
    )


def _result(tmp_path) -> tuple[RunResult, Config]:
    cfg = Config(data_dir=str(tmp_path / "data"),
                 reports_dir=str(tmp_path / "reports"))
    result = RunResult(run_id="2026-05-20T12-00-00Z", since=SINCE, until=UNTIL,
                       summary_mode="both", discovered=2, scraped=1)
    result.articles = [_article("https://example.com/a.html")]
    result.failed_urls = ["https://example.com/gone.html"]
    result.summaries = [
        Summary(kind="per-article", text="A summary.", model="m",
                generated_at=UNTIL, article_urls=["https://example.com/a.html"]),
        Summary(kind="digest", text="The digest.", model="m",
                generated_at=UNTIL, article_urls=["https://example.com/a.html"]),
    ]
    return result, cfg


def test_write_articles_json(tmp_path):
    result, cfg = _result(tmp_path)
    path = write_articles_json(result, cfg)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["run_id"] == "2026-05-20T12-00-00Z"
    assert data["failed"] == 1
    assert len(data["articles"]) == 1
    assert data["articles"][0]["url"] == "https://example.com/a.html"


def test_write_summaries_json(tmp_path):
    result, cfg = _result(tmp_path)
    path = write_summaries_json(result, cfg)
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data["per_article"]) == 1
    assert data["digest"]["text"] == "The digest."


def test_write_markdown_report(tmp_path):
    result, cfg = _result(tmp_path)
    path = write_markdown_report(result, cfg)
    text = open(path, encoding="utf-8").read()
    assert "## Daily Digest" in text
    assert "The digest." in text
    assert "Green roadmap" in text
    assert "A summary." in text
    assert "https://example.com/gone.html" in text


def test_report_handles_zero_articles(tmp_path):
    cfg = Config(data_dir=str(tmp_path / "data"),
                 reports_dir=str(tmp_path / "reports"))
    result = RunResult(run_id="2026-05-20T12-00-00Z", since=SINCE, until=UNTIL,
                       summary_mode="both", discovered=0, scraped=0)
    text = open(write_markdown_report(result, cfg), encoding="utf-8").read()
    assert "No new articles" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_output.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.output'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/output.py`:

```python
"""Write run artifacts: raw articles JSON, summaries JSON, Markdown report."""

import json
import os

from .config import Config
from .models import RunResult, dt_to_iso


def articles_path(result: RunResult, config: Config) -> str:
    return os.path.join(config.data_dir, "articles", f"{result.run_id}.json")


def summaries_path(result: RunResult, config: Config) -> str:
    return os.path.join(config.data_dir, "summaries", f"{result.run_id}.json")


def report_path(result: RunResult, config: Config) -> str:
    return os.path.join(config.reports_dir, f"{result.run_id}.md")


def write_articles_json(result: RunResult, config: Config) -> str:
    """Write the raw scraped articles to data/articles/<run-id>.json."""
    path = articles_path(result, config)
    _write_json(path, {
        **_run_metadata(result),
        "failed_urls": result.failed_urls,
        "articles": [a.to_dict() for a in result.articles],
    })
    return path


def write_summaries_json(result: RunResult, config: Config) -> str:
    """Write the summaries to data/summaries/<run-id>.json."""
    path = summaries_path(result, config)
    digest = next((s for s in result.summaries if s.kind == "digest"), None)
    _write_json(path, {
        **_run_metadata(result),
        "per_article": [s.to_dict() for s in result.summaries
                        if s.kind == "per-article"],
        "digest": digest.to_dict() if digest else None,
    })
    return path


def write_markdown_report(result: RunResult, config: Config) -> str:
    """Write the human-readable Markdown report to reports/<run-id>.md."""
    path = report_path(result, config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(_render_report(result)))
    return path


def _run_metadata(result: RunResult) -> dict:
    return {
        "run_id": result.run_id,
        "since": dt_to_iso(result.since),
        "until": dt_to_iso(result.until),
        "summary_mode": result.summary_mode,
        "discovered": result.discovered,
        "scraped": result.scraped,
        "failed": len(result.failed_urls),
        "skipped_paywall": result.skipped_paywall,
        "skipped_sections": result.skipped_sections,
    }


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _render_report(result: RunResult) -> list[str]:
    lines: list[str] = [
        "# The Jakarta Post — News Summary",
        "",
        f"**Window:** {dt_to_iso(result.since)} → {dt_to_iso(result.until)}  ",
        (f"**Discovered:** {result.discovered}  |  **Scraped:** {result.scraped}"
         f"  |  **Failed:** {len(result.failed_urls)}  |  "
         f"**Skipped (paywall):** {result.skipped_paywall}  "),
        f"**Summary mode:** {result.summary_mode}",
        "",
    ]
    if result.scraped == 0:
        lines += ["_No new articles in this window._", ""]

    digest = next((s for s in result.summaries if s.kind == "digest"), None)
    if digest is not None:
        lines += ["## Daily Digest", ""]
        lines.append(f"_Digest unavailable: {digest.error}_"
                     if digest.error else digest.text)
        lines.append("")

    per_article = [s for s in result.summaries if s.kind == "per-article"]
    if per_article:
        lines += ["## Articles", ""]
        by_url = {a.url: a for a in result.articles}
        for summary in per_article:
            url = summary.article_urls[0] if summary.article_urls else ""
            article = by_url.get(url)
            lines.append(f"### {article.title if article else url or 'Untitled'}")
            if article is not None:
                meta = [article.section, dt_to_iso(article.published_at)]
                if article.is_paywalled:
                    meta.append("paywalled (teaser)")
                lines.append(f"_{' · '.join(meta)}_  ")
            lines += [f"<{url}>", ""]
            lines.append(f"_Summary unavailable: {summary.error}_"
                         if summary.error else summary.text)
            lines.append("")

    if result.failed_urls:
        lines += ["## Failed to scrape", ""]
        lines += [f"- {u}" for u in result.failed_urls]
        lines.append("")
    if result.skipped_sections:
        lines += ["## Skipped sections (sitemap fetch failed)", ""]
        lines += [f"- {s}" for s in result.skipped_sections]
        lines.append("")
    return lines
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_output.py -v`
Expected: PASS — all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/output.py tests/test_output.py
git commit -m "feat: add JSON and Markdown output writers"
```

---

### Task 13: CLI orchestration

**Files:**
- Create: `jakpost_scraper/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
from jakpost_scraper.cli import build_parser, cli_overrides


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.since is None
    assert args.dry_run is False
    assert args.no_summary is False
    assert args.summary_mode is None
    assert args.limit is None
    assert args.sections is None


def test_parser_flags():
    args = build_parser().parse_args(
        ["--since", "24h", "--dry-run", "--no-summary",
         "--summary-mode", "digest", "--limit", "5", "--sections", "business"])
    assert args.since == "24h"
    assert args.dry_run is True
    assert args.no_summary is True
    assert args.summary_mode == "digest"
    assert args.limit == 5
    assert args.sections == "business"


def test_cli_overrides_extracts_config_keys():
    args = build_parser().parse_args(
        ["--summary-mode", "both", "--sections", "business, news/politics"])
    overrides = cli_overrides(args)
    assert overrides["summary_mode"] == "both"
    assert overrides["sections"] == ["business", "news/politics"]


def test_cli_overrides_empty_when_no_flags():
    args = build_parser().parse_args([])
    assert cli_overrides(args) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jakpost_scraper.cli'`.

- [ ] **Step 3: Write the implementation**

`jakpost_scraper/cli.py`:

```python
"""Command-line entry point and run orchestration."""

import argparse
import sys

from .config import Config, ConfigError, load_config
from .discovery import DiscoveryError, compute_window, discover, parse_since_arg
from .http_client import HttpClient
from .models import RunResult, dt_to_iso, now_utc
from .output import (
    report_path, write_articles_json, write_markdown_report, write_summaries_json,
)
from .scraper import scrape_articles
from .state import State, StateError, load_state, prune_seen, save_state
from .summarizer import PreflightError, preflight_check, summarize

CONFIG_PATH = "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jakpost-scrape",
        description="Scrape and summarize The Jakarta Post articles.",
    )
    parser.add_argument("--since",
                        help="Window start: an ISO date or a duration like 24h/3d")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be scraped; no scrape/summarize/state write")
    parser.add_argument("--no-summary", action="store_true",
                        help="Scrape and save raw articles only; skip summarization")
    parser.add_argument("--summary-mode", choices=["per-article", "digest", "both"],
                        help="Override the configured summary mode")
    parser.add_argument("--limit", type=int,
                        help="Process at most N articles (testing aid)")
    parser.add_argument("--sections",
                        help="Comma-separated section identifiers (testing aid)")
    return parser


def cli_overrides(args: argparse.Namespace) -> dict:
    """Extract config overrides (summary_mode, sections) from parsed args."""
    overrides: dict = {}
    if args.summary_mode is not None:
        overrides["summary_mode"] = args.summary_mode
    if args.sections is not None:
        overrides["sections"] = [s.strip() for s in args.sections.split(",")
                                 if s.strip()]
    return overrides


def run(config: Config, state: State, args: argparse.Namespace) -> RunResult:
    """Execute one scrape/summarize/output run. Returns the RunResult."""
    now = now_utc()
    run_id = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    do_summarize = not args.no_summary

    if do_summarize and not args.dry_run:
        preflight_check()

    since_override = parse_since_arg(args.since, now) if args.since else None
    since, until = compute_window(state.last_run_at, since_override, now,
                                  config.lookback_buffer_minutes)
    result = RunResult(run_id=run_id, since=since, until=until,
                       summary_mode=config.summary_mode)

    with HttpClient(config.http_timeout, config.http_retries,
                    config.request_delay) as http:
        discovered, skipped_sections = discover(
            http, config.sections, since, until, set(state.seen_urls))
        result.skipped_sections = skipped_sections
        result.discovered = len(discovered)
        if args.limit is not None:
            discovered = discovered[:args.limit]
        if args.dry_run:
            for item in discovered:
                print(f"{dt_to_iso(item.published_at)}  {item.section}  {item.url}")
            return result
        articles, failed_urls, skipped_paywall = scrape_articles(
            http, discovered, config.concurrency, config.paywall)

    result.articles = articles
    result.scraped = len(articles)
    result.failed_urls = failed_urls
    result.skipped_paywall = len(skipped_paywall)

    write_articles_json(result, config)  # persist before summarizing
    if do_summarize:
        result.summaries = summarize(articles, config.summary_mode,
                                     config.model, config.concurrency)
    write_summaries_json(result, config)
    write_markdown_report(result, config)

    state.last_run_at = until
    for article in articles:
        state.seen_urls[article.url] = until
    for url in skipped_paywall:
        state.seen_urls[url] = until
    prune_seen(state, config.seen_url_retention_days, now)
    save_state(config.state_file, state)
    return result


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the pipeline, return a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(CONFIG_PATH, cli_overrides(args))
        state = load_state(config.state_file)
        result = run(config, state, args)
    except (ConfigError, StateError, DiscoveryError, PreflightError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"Done: scraped {result.scraped}/{result.discovered} article(s), "
              f"{len(result.summaries)} summary record(s) → "
              f"{report_path(result, config)}", file=sys.stderr)
    return 0


def cli_entry() -> None:
    """Console-script entry point declared in pyproject.toml."""
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS — all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/cli.py tests/test_cli.py
git commit -m "feat: add CLI parser and run orchestration"
```

---

### Task 14: Integration test and README

The integration test verifies the already-built system end to end; it drives
no new production code. The summarizer and `now_utc()` are patched so the run
is deterministic regardless of when the suite runs.

**Files:**
- Create: `tests/test_integration.py`
- Create: `README.md`

- [ ] **Step 1: Write the integration test**

`tests/test_integration.py`:

```python
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
                    summary_mode=None, limit=None, sections=None)
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
```

- [ ] **Step 2: Run the integration test**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS — both tests. This verifies the whole pipeline (discover →
scrape → summarize → output → state) and the dedup behavior on a second run.

- [ ] **Step 3: Create the README**

Create `README.md`:

````markdown
# Jakarta Post Scraper & Summarizer

A Python CLI that discovers articles published on
[The Jakarta Post](https://www.thejakartapost.com) since the last run,
scrapes their full text, summarizes them with Claude, and writes JSON files
plus a Markdown report.

## Requirements

- Python 3.11+
- The `claude` CLI installed and authenticated (used by the Claude Agent SDK).
  Run with `--no-summary` to skip this requirement.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Usage

The scraper is triggered manually:

```bash
jakpost-scrape                       # scrape since last run (24h on first run)
jakpost-scrape --dry-run             # list what would be scraped
jakpost-scrape --no-summary          # scrape only, skip summarization
jakpost-scrape --since 48h           # override the window (also accepts ISO dates)
jakpost-scrape --summary-mode digest # per-article | digest | both
jakpost-scrape --limit 5             # cap article count
jakpost-scrape --sections business   # restrict sections
```

## How it works

1. Reads `state.json` for the last-run timestamp (first run looks back 24h).
2. Walks The Jakarta Post's Google News sitemaps to find articles in the window.
3. Scrapes each article's full text (paywalled articles yield the teaser).
4. Summarizes via the Claude Agent SDK (`per-article`, `digest`, or `both`).
5. Writes `data/articles/<run-id>.json`, `data/summaries/<run-id>.json`, and
   `reports/<run-id>.md`, then advances `state.json`.

Configuration lives in `config.yaml`. See
`docs/superpowers/specs/2026-05-20-jakpost-scraper-design.md` for the full design.

## Tests

```bash
python -m pytest
```

The suite uses no live network and makes no live Claude calls.
````

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS — every test across all modules (smoke, models, config, state,
http_client, discovery, scraper, scrape_articles, summarizer, summarizer_digest,
output, cli, integration).

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py README.md
git commit -m "test: add end-to-end integration test; add README"
```

---

## Final verification

- [ ] Run `python -m pytest -v` — the entire suite passes.
- [ ] Run `jakpost-scrape --dry-run` against the live site — confirm it lists
  recent article URLs (this makes real HTTP requests but no Claude calls and
  writes no state).
- [ ] Confirm `git status` is clean and every task was committed.
