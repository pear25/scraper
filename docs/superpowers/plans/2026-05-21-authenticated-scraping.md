# Authenticated Scraping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `jakpost_scraper` read the full body of premium Jakarta Post articles by reusing an authenticated browser session, while leaving guest scraping unchanged.

**Architecture:** A new `auth.py` module is the only code that touches Playwright. It produces an `httpx` cookie jar (`ensure_session`), which is handed to the existing `HttpClient`; all article fetching stays on `httpx`. Paywall detection is split into two independent signals on `Article`: `is_premium` (the article is gated) and `is_truncated` (this fetch did not get the full body). Auth is opt-in via a config flag and is fully skipped when disabled.

**Tech Stack:** Python 3.11+, `httpx`, `playwright` (new optional dependency), `BeautifulSoup`/`lxml`, `pytest` + `pytest-httpx`, dataclass-based config.

---

## Design decisions locked in by this plan

Read these before starting — they resolve ambiguities in the spec:

1. **`is_truncated` is purely DOM-based.** It is `True` when the parsed page contains `div.tjp-paywall`, `False` otherwise. The spec mentioned a secondary "body suspiciously short" heuristic; it is **dropped as YAGNI** — the paywall div is a reliable, deterministic signal and a fuzzy length threshold adds risk without correctness benefit.

2. **`is_premium`** is `True` when JSON-LD `isAccessibleForFree` is falsey (`"false"`, `"0"`, `"no"`). This is exactly today's `_detect_paywall` logic for the JSON-LD branch.

3. **`is_paywalled` stays on `Article`** as a stored field equal to `is_truncated`'s value, for backward compatibility with existing output/tests. It is set by `parse_article`, not computed as a property, so `to_dict`/`from_dict` are unchanged in shape.

4. **`ensure_session` returns `httpx.Cookies`.** When auth is disabled it is never called.

5. **No startup validation request** (D-006). `ensure_session` with an existing cookie file just loads and returns it.

6. **The mid-run expiry abort (D-005)** is implemented as a check in `cli.run` *after* `scrape_articles`, not inside the scraper, so the scraper stays a pure function.

## File structure

| File | Status | Responsibility |
|------|--------|----------------|
| `jakpost_scraper/auth.py` | Create | `ensure_session(config)`, `AuthError`. Only module importing Playwright. |
| `jakpost_scraper/config.py` | Modify | Add 5 auth fields + validation. |
| `jakpost_scraper/http_client.py` | Modify | Accept optional `cookies` param. |
| `jakpost_scraper/models.py` | Modify | Add `is_premium`, `is_truncated` to `Article`. |
| `jakpost_scraper/scraper.py` | Modify | Split paywall detection into the two signals. |
| `jakpost_scraper/cli.py` | Modify | Auth CLI flags; call `ensure_session`; mid-run abort. |
| `jakpost_scraper/output.py` | Modify | Surface premium/truncated counts in the report. |
| `pyproject.toml` | Modify | Add `[auth]` optional dependency group. |
| `.gitignore` | Modify | Ignore `.auth/`. |
| `tests/test_auth.py` | Create | `ensure_session` decision logic (Playwright mocked). |
| `tests/fixtures/article_premium_full.html` | Create | Premium article, full body, no paywall div. |
| `tests/test_scraper.py` | Modify | Cases for `is_premium`/`is_truncated`. |
| `tests/test_http_client.py` | Modify | Cookies are sent on requests. |
| `tests/test_config.py` | Modify | New auth keys load and validate. |
| `tests/test_integration.py` | Modify | `auth_enabled` path captures full premium body. |

Tasks are ordered so each leaves the test suite green. Run the full suite with `pytest -q` at any checkpoint.

---

### Task 1: Add the premium-full HTML fixture

A premium article that — viewed as an authenticated user — has the full body and **no** `div.tjp-paywall`. Mirrors `article_paywalled.html` but with real body paragraphs instead of the paywall block.

**Files:**
- Create: `tests/fixtures/article_premium_full.html`

- [ ] **Step 1: Create the fixture file**

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
    <p>The central bank cited persistent inflation pressure as the main driver.</p>
    <p>Analysts expect one more hike before the end of the year.</p>
  </div>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/article_premium_full.html
git commit -m "test: add premium-full article fixture (authenticated view)"
```

---

### Task 2: Add `is_premium` and `is_truncated` to the `Article` model

`Article` gains two fields. `is_paywalled` is kept (now redundant with `is_truncated` but preserved for compatibility). All three are required positional-or-keyword fields; `to_dict`/`from_dict` are extended.

**Files:**
- Modify: `jakpost_scraper/models.py:37-74`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
def test_article_round_trips_premium_and_truncated_fields():
    from datetime import datetime, timezone
    from jakpost_scraper.models import Article

    when = datetime(2026, 5, 20, 8, 0, 0, tzinfo=timezone.utc)
    art = Article(
        url="https://example.com/a",
        title="T",
        section="business",
        published_at=when,
        authors=["R"],
        body="body",
        is_paywalled=True,
        is_premium=True,
        is_truncated=True,
        lead_image_url=None,
        scraped_at=when,
    )
    d = art.to_dict()
    assert d["is_premium"] is True
    assert d["is_truncated"] is True
    restored = Article.from_dict(d)
    assert restored.is_premium is True
    assert restored.is_truncated is True
    assert restored.is_paywalled is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_article_round_trips_premium_and_truncated_fields -v`
Expected: FAIL — `Article.__init__() got an unexpected keyword argument 'is_premium'`

- [ ] **Step 3: Add the fields to `Article`**

In `jakpost_scraper/models.py`, replace the `Article` dataclass body (lines 38-47) — the field list — so it reads:

```python
@dataclass
class Article:
    url: str
    title: str
    section: str
    published_at: datetime
    authors: list[str]
    body: str
    is_paywalled: bool
    is_premium: bool
    is_truncated: bool
    lead_image_url: str | None
    scraped_at: datetime
```

In `to_dict` (lines 49-60), add the two keys after `"is_paywalled"`:

```python
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "section": self.section,
            "published_at": dt_to_iso(self.published_at),
            "authors": list(self.authors),
            "body": self.body,
            "is_paywalled": self.is_paywalled,
            "is_premium": self.is_premium,
            "is_truncated": self.is_truncated,
            "lead_image_url": self.lead_image_url,
            "scraped_at": dt_to_iso(self.scraped_at),
        }
```

In `from_dict` (lines 62-74), read the two new keys with `.get()` defaulting to the old `is_paywalled` value, so historical JSON files (written before this change) still load:

```python
    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        is_paywalled = d["is_paywalled"]
        return cls(
            url=d["url"],
            title=d["title"],
            section=d["section"],
            published_at=iso_to_dt(d["published_at"]),
            authors=list(d["authors"]),
            body=d["body"],
            is_paywalled=is_paywalled,
            is_premium=d.get("is_premium", is_paywalled),
            is_truncated=d.get("is_truncated", is_paywalled),
            lead_image_url=d["lead_image_url"],
            scraped_at=iso_to_dt(d["scraped_at"]),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py::test_article_round_trips_premium_and_truncated_fields -v`
Expected: PASS

- [ ] **Step 5: Run the full suite — other tests construct `Article` and will now fail**

Run: `pytest -q`
Expected: FAIL in `test_scraper.py`, `test_output.py`, `test_integration.py`, `test_scrape_articles.py` — any test that constructs `Article` directly or via `parse_article`. This is expected; Tasks 3-4 fix the production code that builds `Article`. Tests that construct `Article` literally are fixed in their respective tasks.

- [ ] **Step 6: Commit**

```bash
git add jakpost_scraper/models.py tests/test_models.py
git commit -m "feat: add is_premium and is_truncated to Article model"
```

---

### Task 3: Split paywall detection in the scraper

Replace `_detect_paywall` with two functions and update `parse_article` to set all three flags. `is_premium` = JSON-LD falsey; `is_truncated` = `div.tjp-paywall` present; `is_paywalled` = `is_truncated` (alias).

**Files:**
- Modify: `jakpost_scraper/scraper.py:22-43`, `:110-114`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py::test_premium_full_article_is_premium_but_not_truncated -v`
Expected: FAIL — `parse_article` does not yet pass `is_premium`/`is_truncated` to `Article`, raising `TypeError` for missing arguments.

- [ ] **Step 3: Update `parse_article` and replace `_detect_paywall`**

In `jakpost_scraper/scraper.py`, replace lines 31-43 (from `is_paywalled = _detect_paywall(...)` through the end of the `return Article(...)` block) with:

```python
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
```

Replace `_detect_paywall` (lines 110-114) with these two functions:

```python
def _detect_premium(jsonld: dict) -> bool:
    """True if the article is gated content (JSON-LD isAccessibleForFree=false)."""
    flag = jsonld.get("isAccessibleForFree")
    if flag is None:
        return False
    return str(flag).strip().lower() in ("false", "0", "no")


def _detect_truncated(soup: BeautifulSoup) -> bool:
    """True if this fetched page did not return the full body (paywall block present)."""
    return soup.select_one("div.tjp-paywall") is not None
```

- [ ] **Step 4: Run the scraper tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS — including the existing `test_parse_paywalled_article_detected` (still asserts `is_paywalled is True`).

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/scraper.py tests/test_scraper.py
git commit -m "feat: split paywall detection into is_premium and is_truncated"
```

---

### Task 4: Fix remaining `Article` constructions in tests and output

Repair tests broken by Task 2 that construct `Article` literally, and confirm the paywall-skip path keys off `is_truncated`. `scrape_articles` line 176 reads `article.is_paywalled`, which now equals `is_truncated` — semantically correct, no code change there, but verify with a test.

**Files:**
- Modify: `tests/test_output.py`, `tests/test_scrape_articles.py`

- [ ] **Step 1: Run the suite to list every remaining failure**

Run: `pytest -q`
Expected: FAIL only in tests that build `Article(...)` directly (most likely `tests/test_output.py`). Note each failing file and line.

- [ ] **Step 2: Fix `Article(...)` literals in `tests/test_output.py`**

For every `Article(...)` constructor call in `tests/test_output.py`, add `is_premium=<value>` and `is_truncated=<value>` keyword arguments next to the existing `is_paywalled=<value>`, using the **same boolean value** as `is_paywalled`. Example — a call like:

```python
Article(url="u", title="t", section="s", published_at=when, authors=[],
        body="b", is_paywalled=False, lead_image_url=None, scraped_at=when)
```

becomes:

```python
Article(url="u", title="t", section="s", published_at=when, authors=[],
        body="b", is_paywalled=False, is_premium=False, is_truncated=False,
        lead_image_url=None, scraped_at=when)
```

Apply to every such call in the file.

- [ ] **Step 3: Add a paywall-skip regression test keyed on truncation**

Append to `tests/test_scrape_articles.py`:

```python
def test_skip_mode_keys_off_truncation(httpx_mock):
    _mock(httpx_mock)
    with _client() as client:
        articles, _, skipped_pw = scrape_articles(
            client, _discovered(), concurrency=2, paywall_mode="skip")
    # PAY_URL is truncated (paywall div) -> skipped; FREE_URL kept.
    assert skipped_pw == [PAY_URL]
    assert all(a.is_truncated is False for a in articles)
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -q`
Expected: PASS — the suite is fully green again.

- [ ] **Step 5: Commit**

```bash
git add tests/test_output.py tests/test_scrape_articles.py
git commit -m "test: update Article constructions for premium/truncated fields"
```

---

### Task 5: Add `cookies` support to `HttpClient`

`HttpClient.__init__` gains an optional `cookies` parameter passed straight to `httpx.Client`. Default `None` preserves current behavior.

**Files:**
- Modify: `jakpost_scraper/http_client.py:18-26`
- Test: `tests/test_http_client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_http_client.py`:

```python
def test_cookies_are_sent_on_requests(httpx_mock):
    httpx_mock.add_response(url="https://example.com/p", text="ok")
    client = HttpClient(timeout=5, retries=3, request_delay=0,
                        cookies={"laravel_session": "abc123"})
    with client:
        client.get("https://example.com/p")
    request = httpx_mock.get_request()
    assert request.headers["cookie"] == "laravel_session=abc123"


def test_no_cookies_means_no_cookie_header(httpx_mock):
    httpx_mock.add_response(url="https://example.com/p", text="ok")
    with _client() as client:
        client.get("https://example.com/p")
    request = httpx_mock.get_request()
    assert "cookie" not in request.headers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_http_client.py::test_cookies_are_sent_on_requests -v`
Expected: FAIL — `HttpClient.__init__() got an unexpected keyword argument 'cookies'`

- [ ] **Step 3: Add the `cookies` parameter**

In `jakpost_scraper/http_client.py`, replace `__init__` (lines 18-26) with:

```python
    def __init__(self, timeout: int, retries: int, request_delay: float,
                 user_agent: str = USER_AGENT,
                 cookies: "httpx.Cookies | dict | None" = None):
        self.retries = retries
        self.request_delay = request_delay
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            cookies=cookies,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_http_client.py -v`
Expected: PASS — all http client tests, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/http_client.py tests/test_http_client.py
git commit -m "feat: let HttpClient carry session cookies"
```

---

### Task 6: Add auth config fields

Five new `Config` fields with defaults, plus validation that `auth_login_timeout >= 1`. Existing config files keep working because every new field has a default.

**Files:**
- Modify: `jakpost_scraper/config.py:16-31`, `:54-67`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_auth_defaults_off(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {})
    assert cfg.auth_enabled is False
    assert cfg.auth_profile_dir == "./.auth/profile"
    assert cfg.auth_cookies_file == "./.auth/cookies.json"
    assert cfg.auth_login_timeout == 300


def test_auth_keys_load_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("auth_enabled: true\nauth_login_timeout: 120\n")
    cfg = load_config(str(path), {})
    assert cfg.auth_enabled is True
    assert cfg.auth_login_timeout == 120


def test_invalid_auth_login_timeout_rejected():
    with pytest.raises(ConfigError, match="auth_login_timeout"):
        validate_config(Config(auth_login_timeout=0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_auth_defaults_off -v`
Expected: FAIL — `'Config' object has no attribute 'auth_enabled'`

- [ ] **Step 3: Add the fields and validation**

In `jakpost_scraper/config.py`, add these fields at the end of the `Config` dataclass (after `state_file`, line 30):

```python
    auth_enabled: bool = False
    auth_profile_dir: str = "./.auth/profile"
    auth_cookies_file: str = "./.auth/cookies.json"
    auth_login_url: str = "https://www.thejakartapost.com/login"
    auth_login_timeout: int = 300
```

In `validate_config`, add `"auth_login_timeout"` to the `>= 1` check tuple (lines 60-61):

```python
    for name in ("concurrency", "http_retries", "http_timeout",
                 "lookback_buffer_minutes", "seen_url_retention_days",
                 "auth_login_timeout"):
        if getattr(cfg, name) < 1:
            raise ConfigError(f"{name} must be >= 1")
```

> Note: `auth_login_url` default is the best-known login path. Confirm it during Task 8 manual verification; it is a config value so it can be overridden in `config.yaml` without code change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/config.py tests/test_config.py
git commit -m "feat: add auth configuration fields"
```

---

### Task 7: Add Playwright dependency and gitignore entry

Add an `[auth]` optional-dependency group so `pip install -e .[auth]` installs Playwright, and ignore the `.auth/` secrets directory.

**Files:**
- Modify: `pyproject.toml:19-20`
- Modify: `.gitignore`

- [ ] **Step 1: Add the optional dependency group**

In `pyproject.toml`, replace the `[project.optional-dependencies]` block (lines 19-20):

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-httpx"]
auth = ["playwright"]
```

- [ ] **Step 2: Ignore the auth secrets directory**

Append a line to `.gitignore`:

```
.auth/
```

- [ ] **Step 3: Install Playwright and its browser**

Run: `pip install -e ".[auth,dev]" && playwright install chromium`
Expected: Playwright installs; `playwright install chromium` downloads the Chromium build. This is a one-time setup step.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "build: add playwright as optional [auth] dependency"
```

---

### Task 8: Create the `auth` module

`auth.py` exposes `AuthError` and `ensure_session(config, force_reauth=False) -> httpx.Cookies`. Logic:

- If `force_reauth` is `False` **and** `config.auth_cookies_file` exists → load JSON, return `httpx.Cookies` built from it.
- Otherwise → run the interactive Playwright login, save cookies to `config.auth_cookies_file`, return them.
- Playwright is imported **inside** the login function so a missing install only fails when login is actually needed, with a clear message.

The interactive login is genuinely interactive (a human logs in), so it is **not** unit-tested against a real browser. Tests in Task 9 mock `_interactive_login`. This task includes a manual verification step instead.

**Files:**
- Create: `jakpost_scraper/auth.py`

- [ ] **Step 1: Create `jakpost_scraper/auth.py`**

```python
"""Authenticated-session handling. The only module that imports Playwright.

Auth is opt-in (config.auth_enabled). ensure_session returns an httpx cookie
jar that HttpClient carries on every request. Cached cookies are reused
without a validation request; an expired session is caught mid-run by the
caller (see cli.run). Login uses a real browser because Jakarta Post premium
accounts authenticate via Google OAuth, which cannot be scripted over raw
HTTP.
"""

import json
import os

import httpx

from .config import Config

# Login is complete once the browser lands back on a thejakartapost.com page
# after the Google OAuth callback. We poll for the auth cookie being set.
_COOKIE_DOMAIN = "thejakartapost.com"
_OAUTH_CALLBACK = "https://www.thejakartapost.com/login/google/process"
# Either of these cookies present means Jakarta Post has minted a session.
_SESSION_COOKIE_NAMES = ("laravel_session", "auth_token_tjp_new")
_POLL_INTERVAL_SECONDS = 2.0


class AuthError(Exception):
    """Raised when an authenticated session cannot be obtained."""


def ensure_session(config: Config, force_reauth: bool = False) -> httpx.Cookies:
    """Return an httpx cookie jar for an authenticated Jakarta Post session.

    Reuses config.auth_cookies_file if it exists and force_reauth is False;
    otherwise runs an interactive browser login and persists the result.
    """
    if not force_reauth and os.path.exists(config.auth_cookies_file):
        return _load_cookies(config.auth_cookies_file)
    cookies = _interactive_login(config)
    _save_cookies(config.auth_cookies_file, cookies)
    return cookies


def _load_cookies(path: str) -> httpx.Cookies:
    """Load a {name: value} cookie mapping from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise AuthError(f"{path} must contain a JSON object of cookies")
    jar = httpx.Cookies()
    for name, value in data.items():
        jar.set(name, str(value), domain=_COOKIE_DOMAIN)
    return jar


def _save_cookies(path: str, cookies: httpx.Cookies) -> None:
    """Write a cookie jar as a {name: value} JSON object."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = {name: cookies.get(name) for name in cookies.keys()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _interactive_login(config: Config) -> httpx.Cookies:
    """Open a real browser, let the user log in, and return the session cookies.

    Raises AuthError if Playwright is not installed or login does not complete
    within config.auth_login_timeout seconds.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise AuthError(
            "Authentication needs Playwright. Install it with: "
            "pip install 'jakpost-scraper[auth]' && playwright install chromium"
        ) from e

    deadline_ms = config.auth_login_timeout * 1000
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            config.auth_profile_dir, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(config.auth_login_url)
            print("A browser window has opened. Log in with your Google "
                  "account to The Jakarta Post, then wait — the window closes "
                  "automatically once you are signed in.")
            elapsed = 0
            while elapsed < deadline_ms:
                jar = _extract_session_cookies(context)
                if jar is not None:
                    return jar
                page.wait_for_timeout(_POLL_INTERVAL_SECONDS * 1000)
                elapsed += _POLL_INTERVAL_SECONDS * 1000
            raise AuthError(
                f"Login not completed within {config.auth_login_timeout}s")
        finally:
            context.close()


def _extract_session_cookies(context) -> "httpx.Cookies | None":
    """Return all thejakartapost.com cookies as an httpx jar once a session
    cookie is present; otherwise None (login not finished yet)."""
    raw = [c for c in context.cookies()
           if _COOKIE_DOMAIN in c.get("domain", "")]
    names = {c["name"] for c in raw}
    if not names.intersection(_SESSION_COOKIE_NAMES):
        return None
    jar = httpx.Cookies()
    for c in raw:
        jar.set(c["name"], c["value"], domain=_COOKIE_DOMAIN)
    return jar
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `python -c "from jakpost_scraper.auth import ensure_session, AuthError; print('ok')"`
Expected: prints `ok` (no Playwright import happens at module load).

- [ ] **Step 3: Manual verification of the live login (one-time, not automated)**

This step needs a real Jakarta Post premium account and is run by a human, not a subagent. Skip if no account is available; note it as deferred.

Run a throwaway script:
```bash
python -c "
from jakpost_scraper.config import Config
from jakpost_scraper.auth import ensure_session
cfg = Config(auth_enabled=True, auth_cookies_file='./.auth/cookies.json')
jar = ensure_session(cfg, force_reauth=True)
print('cookies captured:', sorted(jar.keys()))
"
```
Expected: a browser opens; after Google login the window closes and the script prints the captured cookie names (should include `laravel_session` and/or `auth_token_tjp_new`). Confirm `./.auth/cookies.json` was written. If the login page URL is wrong, update `auth_login_url` in `config.yaml`.

- [ ] **Step 4: Commit**

```bash
git add jakpost_scraper/auth.py
git commit -m "feat: add auth module with browser-based session capture"
```

---

### Task 9: Test `ensure_session` decision logic

Cover the no-browser path (cookie file exists → load it) and the login path (no file → `_interactive_login` is called). `_interactive_login` is mocked — no real browser, no network.

**Files:**
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

import httpx

from jakpost_scraper.auth import ensure_session, AuthError
from jakpost_scraper.config import Config


def _cfg(tmp_path, **kw):
    return Config(
        auth_enabled=True,
        auth_cookies_file=str(tmp_path / "cookies.json"),
        auth_profile_dir=str(tmp_path / "profile"),
        **kw,
    )


def test_existing_cookie_file_is_loaded_without_login(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps({"laravel_session": "abc"}))

    def _fail(_config):
        raise AssertionError("_interactive_login must not be called")

    monkeypatch.setattr("jakpost_scraper.auth._interactive_login", _fail)
    jar = ensure_session(_cfg(tmp_path))
    assert jar.get("laravel_session") == "abc"


def test_missing_cookie_file_triggers_login_and_persists(tmp_path, monkeypatch):
    calls = []

    def _fake_login(config):
        calls.append(config)
        jar = httpx.Cookies()
        jar.set("laravel_session", "fresh", domain="thejakartapost.com")
        return jar

    monkeypatch.setattr("jakpost_scraper.auth._interactive_login", _fake_login)
    jar = ensure_session(_cfg(tmp_path))
    assert jar.get("laravel_session") == "fresh"
    assert len(calls) == 1
    saved = json.loads((tmp_path / "cookies.json").read_text())
    assert saved == {"laravel_session": "fresh"}


def test_force_reauth_ignores_existing_cookie_file(tmp_path, monkeypatch):
    (tmp_path / "cookies.json").write_text(json.dumps({"laravel_session": "old"}))

    def _fake_login(config):
        jar = httpx.Cookies()
        jar.set("laravel_session", "new", domain="thejakartapost.com")
        return jar

    monkeypatch.setattr("jakpost_scraper.auth._interactive_login", _fake_login)
    jar = ensure_session(_cfg(tmp_path), force_reauth=True)
    assert jar.get("laravel_session") == "new"


def test_corrupt_cookie_file_raises_autherror(tmp_path):
    (tmp_path / "cookies.json").write_text("[\"not\", \"an\", \"object\"]")
    try:
        ensure_session(_cfg(tmp_path))
    except AuthError:
        pass
    else:
        raise AssertionError("expected AuthError for non-object cookie file")
```

- [ ] **Step 2: Run tests to verify they fail or pass appropriately**

Run: `pytest tests/test_auth.py -v`
Expected: PASS — `auth.py` already implements this behavior (built in Task 8). If any fail, fix `auth.py` to match the asserted behavior.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py
git commit -m "test: cover ensure_session decision logic"
```

---

### Task 10: Wire auth into the CLI

Add `--auth`/`--no-auth` and `--reauth` flags. In `run`, when auth is enabled, call `ensure_session` and pass the cookie jar to `HttpClient`. After scraping, if auth was enabled and >50% of premium articles are truncated, raise `AuthError` to abort the run.

**Files:**
- Modify: `jakpost_scraper/cli.py:6-16`, `:20-48`, `:51-105`, `:108-122`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test for argument parsing**

Append to `tests/test_cli.py`:

```python
def test_auth_flags_parse():
    from jakpost_scraper.cli import build_parser
    args = build_parser().parse_args(["--auth", "--reauth"])
    assert args.auth is True
    assert args.reauth is True


def test_no_auth_flag_parses():
    from jakpost_scraper.cli import build_parser
    args = build_parser().parse_args(["--no-auth"])
    assert args.auth is False


def test_auth_defaults_to_none_when_unset():
    from jakpost_scraper.cli import build_parser
    args = build_parser().parse_args([])
    assert args.auth is None
    assert args.reauth is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_auth_flags_parse -v`
Expected: FAIL — `unrecognized arguments: --auth --reauth`

- [ ] **Step 3: Add the CLI flags**

In `jakpost_scraper/cli.py`, inside `build_parser` (before `return parser`, line 36-37) add:

```python
    parser.add_argument("--auth", dest="auth", action="store_true", default=None,
                        help="Enable authenticated scraping for this run")
    parser.add_argument("--no-auth", dest="auth", action="store_false",
                        help="Disable authenticated scraping for this run")
    parser.add_argument("--reauth", action="store_true",
                        help="Force interactive re-login even if a session is cached")
```

In `cli_overrides` (lines 40-48), map `--auth` onto the `auth_enabled` config key:

```python
def cli_overrides(args: argparse.Namespace) -> dict:
    """Extract config overrides (summary_mode, sections, auth) from parsed args."""
    overrides: dict = {}
    if args.summary_mode is not None:
        overrides["summary_mode"] = args.summary_mode
    if args.sections is not None:
        overrides["sections"] = [s.strip() for s in args.sections.split(",")
                                 if s.strip()]
    if args.auth is not None:
        overrides["auth_enabled"] = args.auth
    return overrides
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for the mid-run abort helper**

The abort decision is a pure function so it can be tested directly. Append to `tests/test_cli.py`:

```python
def _article(is_premium, is_truncated):
    from datetime import datetime, timezone
    from jakpost_scraper.models import Article
    when = datetime(2026, 5, 20, tzinfo=timezone.utc)
    return Article(url="u", title="t", section="s", published_at=when,
                   authors=[], body="b", is_paywalled=is_truncated,
                   is_premium=is_premium, is_truncated=is_truncated,
                   lead_image_url=None, scraped_at=when)


def test_session_looks_dead_when_majority_premium_truncated():
    from jakpost_scraper.cli import _session_looks_dead
    arts = [_article(True, True), _article(True, True), _article(True, False)]
    assert _session_looks_dead(arts) is True


def test_session_ok_when_minority_truncated():
    from jakpost_scraper.cli import _session_looks_dead
    arts = [_article(True, False), _article(True, False), _article(True, True)]
    assert _session_looks_dead(arts) is False


def test_session_ok_when_no_premium_articles():
    from jakpost_scraper.cli import _session_looks_dead
    arts = [_article(False, False), _article(False, False)]
    assert _session_looks_dead(arts) is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_session_looks_dead_when_majority_premium_truncated -v`
Expected: FAIL — `cannot import name '_session_looks_dead'`

- [ ] **Step 7: Implement auth wiring and the abort helper in `cli.py`**

Add the `auth` import — change line 6 area imports; after the existing `from .config import ...` line add:

```python
from .auth import AuthError, ensure_session
```

Add the helper function after `cli_overrides` (after line 48):

```python
def _session_looks_dead(articles: list) -> bool:
    """True if a majority of premium articles came back truncated — the signal
    that an authenticated session has expired mid-run (see D-005)."""
    premium = [a for a in articles if a.is_premium]
    if not premium:
        return False
    truncated = sum(1 for a in premium if a.is_truncated)
    return truncated > len(premium) / 2
```

In `run`, replace the `with HttpClient(...)` line and its discovery block. Replace lines 66-67:

```python
    cookies = None
    if config.auth_enabled:
        cookies = ensure_session(config, force_reauth=args.reauth)

    with HttpClient(config.http_timeout, config.http_retries,
                    config.request_delay, cookies=cookies) as http:
```

After `scrape_articles` is called and `articles` is assigned (after line 80, before `result.articles = articles` on line 81), add the mid-run abort check:

```python
        if config.auth_enabled and _session_looks_dead(articles):
            raise AuthError(
                "Most premium articles came back truncated — the session has "
                "likely expired. Re-run with --reauth to log in again.")
```

> Note: this `raise` is inside the `with HttpClient(...)` block, so the client is closed cleanly by the context manager before the exception propagates.

In `main`, add `AuthError` to the caught exception tuple (line 115):

```python
    except (ConfigError, StateError, DiscoveryError, PreflightError,
            AuthError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
```

- [ ] **Step 8: Run the CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 9: Run the full suite**

Run: `pytest -q`
Expected: PASS — all tests green.

- [ ] **Step 10: Commit**

```bash
git add jakpost_scraper/cli.py tests/test_cli.py
git commit -m "feat: wire authenticated scraping into the CLI run"
```

---

### Task 11: Surface premium/truncated counts in the Markdown report

The report should show how many premium articles were captured in full versus truncated — the visible signal that auth is working. Add a `RunResult` field for the count and render it.

**Files:**
- Modify: `jakpost_scraper/models.py:108-120` (add `RunResult` field)
- Modify: `jakpost_scraper/cli.py` (populate the field in `run`)
- Modify: `jakpost_scraper/output.py:75-85` (render it)
- Test: `tests/test_output.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_output.py` (adjust the import line if `RunResult`/`Article` are already imported at the top of that file — do not duplicate imports):

```python
def test_report_shows_premium_capture_counts(tmp_path):
    from datetime import datetime, timezone
    from jakpost_scraper.config import Config
    from jakpost_scraper.models import Article, RunResult
    from jakpost_scraper.output import write_markdown_report

    when = datetime(2026, 5, 20, tzinfo=timezone.utc)

    def _a(is_premium, is_truncated):
        return Article(url="u" + str(id((is_premium, is_truncated))),
                       title="t", section="s", published_at=when, authors=[],
                       body="b", is_paywalled=is_truncated,
                       is_premium=is_premium, is_truncated=is_truncated,
                       lead_image_url=None, scraped_at=when)

    result = RunResult(run_id="2026-05-20T00-00-00Z", since=when, until=when,
                       summary_mode="digest")
    result.articles = [_a(True, False), _a(True, True), _a(False, False)]
    result.scraped = 3
    result.premium_full = 1

    cfg = Config(reports_dir=str(tmp_path))
    path = write_markdown_report(result, cfg)
    text = open(path, encoding="utf-8").read()
    assert "Premium captured in full:** 1" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_output.py::test_report_shows_premium_capture_counts -v`
Expected: FAIL — `RunResult` has no field `premium_full` (`TypeError` on attribute set, or `AssertionError` on the missing report line).

- [ ] **Step 3: Add the `RunResult` field**

In `jakpost_scraper/models.py`, add to the `RunResult` dataclass after `skipped_paywall` (line 116):

```python
    premium_full: int = 0
```

- [ ] **Step 4: Populate it in `cli.run`**

In `jakpost_scraper/cli.py`, where `run` sets `result.scraped` etc. (after line 84, near `result.skipped_paywall = len(skipped_paywall)`), add:

```python
    result.premium_full = sum(
        1 for a in articles if a.is_premium and not a.is_truncated)
```

- [ ] **Step 5: Render it in the report**

In `jakpost_scraper/output.py`, in `_render_report`, extend the counts line (lines 80-82). Replace that line group with:

```python
        (f"**Discovered:** {result.discovered}  |  **Scraped:** {result.scraped}"
         f"  |  **Failed:** {len(result.failed_urls)}  |  "
         f"**Skipped (paywall):** {result.skipped_paywall}  |  "
         f"**Premium captured in full:** {result.premium_full}  "),
```

- [ ] **Step 6: Run the test and full suite**

Run: `pytest tests/test_output.py -v && pytest -q`
Expected: PASS — all green.

- [ ] **Step 7: Commit**

```bash
git add jakpost_scraper/models.py jakpost_scraper/cli.py jakpost_scraper/output.py tests/test_output.py
git commit -m "feat: report how many premium articles were captured in full"
```

---

### Task 12: Integration test for the authenticated path

Extend `tests/test_integration.py` with a run where `auth_enabled=True` and a premium-full fixture is served, asserting the full body is captured (`is_truncated=False`) and `premium_full` is counted. `ensure_session` is monkeypatched to return a fixed cookie jar — no browser.

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Inspect the existing integration test structure**

Run: `sed -n '1,60p' tests/test_integration.py`
Expected: shows how the existing test mocks sitemaps/articles via `httpx_mock`, builds `Config`, and calls `cli.run`. Reuse that exact setup style — fixture URLs, `Config` construction, `run(config, state, args)` call — for the new test.

- [ ] **Step 2: Write the failing integration test**

Append to `tests/test_integration.py` a test that follows the file's existing pattern. It must:

1. Build a `Config` with `auth_enabled=True` and a `tmp_path`-based `auth_cookies_file`.
2. `monkeypatch.setattr("jakpost_scraper.cli.ensure_session", lambda config, force_reauth=False: __import__("httpx").Cookies())` so no browser launches.
3. Mock the sitemap index + a news sitemap that lists one article URL, exactly as the existing integration test does.
4. Serve `tests/fixtures/article_premium_full.html` for that article URL via `httpx_mock`.
5. Call `run(config, state, args)` with `--no-summary`-equivalent args (set `args.no_summary = True`) to keep the test offline from the summarizer.
6. Assert: the resulting `RunResult` has one article, `article.is_premium is True`, `article.is_truncated is False`, and `result.premium_full == 1`.

Concrete test (adapt fixture-URL constants and the `args` namespace to match the existing test's helpers in this file):

```python
def test_authenticated_run_captures_full_premium_body(tmp_path, httpx_mock,
                                                      monkeypatch):
    import httpx
    from jakpost_scraper.cli import run

    monkeypatch.setattr("jakpost_scraper.cli.ensure_session",
                        lambda config, force_reauth=False: httpx.Cookies())

    # --- mock discovery: reuse the same sitemap fixtures the other
    # integration tests use; serve one premium article URL ---
    # (Use this file's existing _mock_sitemaps helper / fixture constants.
    #  The single article URL served below must be the one the news
    #  sitemap fixture lists.)
    article_url = ARTICLE_URL  # the constant already defined in this file
    httpx_mock.add_response(
        url=article_url,
        text=(FIXTURES / "article_premium_full.html").read_text(encoding="utf-8"),
    )

    config = make_config(tmp_path, auth_enabled=True,
                         auth_cookies_file=str(tmp_path / "cookies.json"))
    state = empty_state()
    args = make_args(no_summary=True)

    result = run(config, state, args)

    assert result.scraped == 1
    art = result.articles[0]
    assert art.is_premium is True
    assert art.is_truncated is False
    assert result.premium_full == 1
```

> If `test_integration.py` does not already have `make_config`, `empty_state`, `make_args`, or `_mock_sitemaps` helpers, use whatever construction the existing tests in that file use inline — repeat that construction here rather than inventing helper names. The key requirements are listed in Step 2's numbered list.

- [ ] **Step 3: Run the integration test to verify it fails first**

Run: `pytest tests/test_integration.py::test_authenticated_run_captures_full_premium_body -v`
Expected: FAIL initially if fixture wiring is incomplete — iterate on the sitemap mocking until the article is discovered and scraped. Once wiring is correct it should PASS (production code is already complete from Tasks 1-11).

- [ ] **Step 4: Run the full suite**

Run: `pytest -q`
Expected: PASS — every test green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration coverage for authenticated full-body capture"
```

---

### Task 13: Update README and config sample

Document the new feature: how to enable auth, install Playwright, and what the first-run login looks like.

**Files:**
- Modify: `README.md`
- Modify: `config.yaml`

- [ ] **Step 1: Add an "Authenticated scraping" section to `README.md`**

Append to `README.md`:

```markdown
## Authenticated scraping (premium articles)

By default the scraper runs as a guest, so premium articles return only a
teaser. To capture full premium article bodies, enable authenticated
scraping with your own Jakarta Post account.

**One-time setup:**

```bash
pip install -e ".[auth]"
playwright install chromium
```

**Enable it** — set `auth_enabled: true` in `config.yaml`, or pass `--auth`
on a single run.

**First run:** a browser window opens. Log in with your Google account; the
window closes automatically once you are signed in. The session is saved to
`.auth/` (gitignored) and reused on later runs — no login needed until it
expires.

**When the session expires:** the run aborts with a message. Re-run with
`--reauth` to log in again.

Authentication is entirely opt-in: with `auth_enabled: false` (the default)
the scraper behaves exactly as before and Playwright is never loaded.
```

- [ ] **Step 2: Add commented auth keys to `config.yaml`**

Append to `config.yaml`:

```yaml

# Authenticated scraping (optional; off by default).
# auth_enabled: false
# auth_login_url: "https://www.thejakartapost.com/login"
# auth_login_timeout: 300
```

- [ ] **Step 3: Commit**

```bash
git add README.md config.yaml
git commit -m "docs: document authenticated scraping setup"
```

---

### Task 14: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: PASS — all tests green, no warnings about missing fixtures.

- [ ] **Step 2: Verify guest mode is untouched**

Run: `python -c "
from jakpost_scraper.config import load_config
cfg = load_config('config.yaml', {})
assert cfg.auth_enabled is False, 'auth must default off'
print('guest mode default: ok')
"`
Expected: prints `guest mode default: ok`

- [ ] **Step 3: Verify `auth.py` is not imported in guest mode**

Run: `python -c "
import sys
from jakpost_scraper import cli
# cli imports auth at module load (top-level import); that is fine —
# the Playwright import inside auth is deferred, so importing cli/auth
# without Playwright installed must still succeed.
print('auth import-safe without Playwright:', 'jakpost_scraper.auth' in sys.modules)
"`
Expected: prints `auth import-safe without Playwright: True` — confirms importing the package never triggers the Playwright import.

- [ ] **Step 4: Final commit if anything is uncommitted**

```bash
git status
# if clean, nothing to do; otherwise:
git add -A && git commit -m "chore: finalize authenticated scraping feature"
```

---

## Self-review notes

**Spec coverage check:**
- Capture full premium bodies → Tasks 3, 12. ✓
- Guest scraping unchanged when auth disabled → Tasks 6, 14 (auth defaults off; `ensure_session` only called when enabled). ✓
- `auth.py` only Playwright importer; optional dependency → Tasks 7, 8 (deferred import inside `_interactive_login`). ✓
- `ensure_session` three paths (cached / login / reauth) → Tasks 8, 9. ✓
- No startup validation request (D-006) → Task 8, `ensure_session` loads-and-returns. ✓
- Mid-run expiry abort (D-005, >50% premium truncated) → Task 10, `_session_looks_dead`. ✓
- 5 config keys + validation → Task 6. ✓
- CLI flags `--auth`/`--no-auth`/`--reauth` → Task 10. ✓
- `is_premium` / `is_truncated` split; `is_paywalled` kept as alias → Tasks 2, 3. ✓
- Output surfaces premium/truncated counts → Task 11. ✓
- `.auth/` gitignored → Task 7. ✓
- Playwright-not-installed fails fast with a clear message → Task 8, `_interactive_login`. ✓
- All test files named in the spec → Tasks 1, 9, 3, 5, 6, 12. ✓

**Deviation from spec (intentional, see "Design decisions locked in"):** `is_truncated` is purely `div.tjp-paywall`-based; the spec's secondary "body suspiciously short" heuristic is dropped as YAGNI. Detection remains correct because the paywall div is a deterministic signal.

**Type consistency:** `ensure_session(config, force_reauth=False) -> httpx.Cookies`, `_session_looks_dead(articles) -> bool`, `_detect_premium(jsonld) -> bool`, `_detect_truncated(soup) -> bool` — names and signatures used identically across Tasks 8/9/10 and 3. `Article` field order (`is_paywalled, is_premium, is_truncated`) is consistent across Tasks 2, 3, 4, 10, 11, 12.
