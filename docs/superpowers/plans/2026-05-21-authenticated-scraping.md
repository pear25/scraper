# Authenticated Scraping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `jakpost_scraper` read the full body of premium Jakarta Post articles by logging in with a Jakarta Post account over plain HTTP, while leaving guest scraping unchanged.

**Architecture:** A new `auth.py` module logs in via Jakarta Post's native email/password form — `GET` the login page to obtain the CSRF `_token` and session cookies, then `POST` credentials — and returns an `httpx` cookie jar. That jar is handed to the existing `HttpClient`; all article fetching stays on `httpx`. No browser, no new dependency. Paywall detection is split into two `Article` signals: `is_premium` (the article is gated) and `is_truncated` (this fetch did not get the full body). Auth is opt-in via a config flag and fully skipped when disabled.

**Tech Stack:** Python 3.11+, `httpx`, `BeautifulSoup`/`lxml`, `pytest` + `pytest-httpx`, dataclass-based config. All already project dependencies — nothing new to install.

---

## Design decisions locked in by this plan

Read these before starting — they resolve ambiguities in the spec:

1. **No browser, no Playwright.** Login is a plain Laravel HTML form POST (verified: form has `_token`, `email`, `password`; no captcha; no Cloudflare challenge). See DECISIONS.md D-007.

2. **Credentials come from environment variables** `JAKPOST_EMAIL` and `JAKPOST_PASSWORD`. Never stored in the repo or config files.

3. **`is_truncated` is purely DOM-based.** `True` when the parsed page contains `div.tjp-paywall`, else `False`. The spec mentioned a secondary "body suspiciously short" heuristic; it is **dropped as YAGNI** — the paywall div is a reliable deterministic signal.

4. **`is_premium`** is `True` when JSON-LD `isAccessibleForFree` is falsey (`"false"`, `"0"`, `"no"`).

5. **`is_paywalled` stays on `Article`** as a stored field equal to `is_truncated`, for backward compatibility. Set by `parse_article`, not a computed property.

6. **`ensure_session(config, force_reauth=False) -> httpx.Cookies`.** Cached cookie file present and not `force_reauth` → load and return it. Otherwise → HTTP login. No startup validation request (D-006).

7. **The login GET and POST happen inside one `httpx.Client`** so the `XSRF-TOKEN` cookie and the scraped `_token` are mutually consistent. That client is closed right after; its cookie jar is copied out.

8. **The mid-run expiry abort (D-005)** is a check in `cli.run` after `scrape_articles`, not inside the scraper, keeping the scraper a pure function.

## File structure

| File | Status | Responsibility |
|------|--------|----------------|
| `jakpost_scraper/auth.py` | Create | `ensure_session`, `AuthError`. Native form login over `httpx`. |
| `jakpost_scraper/config.py` | Modify | Add 3 auth fields. |
| `jakpost_scraper/http_client.py` | Modify | Accept optional `cookies` param. |
| `jakpost_scraper/models.py` | Modify | Add `is_premium`, `is_truncated` to `Article`; `premium_full` to `RunResult`. |
| `jakpost_scraper/scraper.py` | Modify | Split paywall detection into the two signals. |
| `jakpost_scraper/cli.py` | Modify | Auth CLI flags; call `ensure_session`; mid-run abort. |
| `jakpost_scraper/output.py` | Modify | Surface premium-captured count in the report. |
| `.gitignore` | Modify | Ignore `.auth/`. |
| `tests/test_auth.py` | Create | `ensure_session` decision + login-flow logic (`pytest-httpx` mocked). |
| `tests/fixtures/login_page.html` | Create | Minimal login page with the `_token` hidden field. |
| `tests/fixtures/article_premium_full.html` | Create | Premium article, full body, no paywall div. |
| `tests/test_scraper.py` | Modify | Cases for `is_premium`/`is_truncated`. |
| `tests/test_http_client.py` | Modify | Cookies are sent on requests. |
| `tests/test_config.py` | Modify | New auth keys load and validate. |
| `tests/test_output.py` | Modify | `Article` constructions; premium-captured count rendered. |
| `tests/test_scrape_articles.py` | Modify | `Article` constructions; skip keyed on truncation. |
| `tests/test_integration.py` | Modify | `auth_enabled` path captures full premium body. |

Tasks are ordered so each leaves the test suite green. Run the full suite with `pytest -q` at any checkpoint.

---

### Task 1: Add the premium-full HTML fixture

A premium article that — viewed authenticated — has the full body and **no** `div.tjp-paywall`. Mirrors `article_paywalled.html` but with real body paragraphs instead of the paywall block.

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

### Task 2: Add the login-page fixture

A minimal Jakarta Post login page carrying the CSRF `_token` hidden field, used by the auth tests to exercise token extraction.

**Files:**
- Create: `tests/fixtures/login_page.html`

- [ ] **Step 1: Create the fixture file**

```html
<!DOCTYPE html>
<html lang="en">
<head><meta name="csrf-token" content="META-TOKEN-VALUE"></head>
<body>
  <form class="auth-box__content-form" role="form" method="POST"
        action="https://www.thejakartapost.com/user/account/login">
    <input type="hidden" name="_token" value="FORM-TOKEN-VALUE-12345">
    <input type="email" name="email" id="email">
    <input type="password" name="password" id="password">
    <input type="submit" value="Log in">
  </form>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/login_page.html
git commit -m "test: add login-page fixture with CSRF token"
```

---

### Task 3: Add `is_premium` and `is_truncated` to the `Article` model

`Article` gains two fields. `is_paywalled` is kept (now redundant with `is_truncated` but preserved for compatibility). `to_dict`/`from_dict` are extended.

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

In `jakpost_scraper/models.py`, replace the `Article` dataclass field list (lines 38-47) so it reads:

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

In `from_dict` (lines 62-74), read the two new keys with `.get()` defaulting to the old `is_paywalled` value, so historical JSON files still load:

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
Expected: FAIL in `test_scraper.py`, `test_output.py`, `test_integration.py`, `test_scrape_articles.py` — any test that constructs `Article` directly or via `parse_article`. Expected; Tasks 4-5 fix production code, and the broken test files are fixed in their own tasks.

- [ ] **Step 6: Commit**

```bash
git add jakpost_scraper/models.py tests/test_models.py
git commit -m "feat: add is_premium and is_truncated to Article model"
```

---

### Task 4: Split paywall detection in the scraper

Replace `_detect_paywall` with two functions and update `parse_article` to set all three flags.

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
Expected: FAIL — `parse_article` does not yet pass `is_premium`/`is_truncated` to `Article`, raising `TypeError`.

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
Expected: PASS — including the existing `test_parse_paywalled_article_detected`.

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/scraper.py tests/test_scraper.py
git commit -m "feat: split paywall detection into is_premium and is_truncated"
```

---

### Task 5: Fix remaining `Article` constructions in tests

Repair tests broken by Task 3 that construct `Article` literally, and add a paywall-skip regression test keyed on `is_truncated`.

**Files:**
- Modify: `tests/test_output.py`, `tests/test_scrape_articles.py`

- [ ] **Step 1: Run the suite to list every remaining failure**

Run: `pytest -q`
Expected: FAIL in tests that build `Article(...)` directly (most likely `tests/test_output.py`). Note each failing file and line.

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

### Task 6: Add `cookies` support to `HttpClient`

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

### Task 7: Add auth config fields

Three new `Config` fields with defaults. Existing config files keep working because every new field has a default. No new validation rule is needed (the fields are a bool and two strings).

**Files:**
- Modify: `jakpost_scraper/config.py:16-31`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_auth_defaults_off(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"), {})
    assert cfg.auth_enabled is False
    assert cfg.auth_cookies_file == "./.auth/cookies.json"
    assert cfg.auth_login_url.endswith("/user/account/login")


def test_auth_keys_load_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("auth_enabled: true\n")
    cfg = load_config(str(path), {})
    assert cfg.auth_enabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_auth_defaults_off -v`
Expected: FAIL — `'Config' object has no attribute 'auth_enabled'`

- [ ] **Step 3: Add the fields**

In `jakpost_scraper/config.py`, add these fields at the end of the `Config` dataclass (after `state_file`, line 30):

```python
    auth_enabled: bool = False
    auth_login_url: str = "https://www.thejakartapost.com/user/account/login"
    auth_cookies_file: str = "./.auth/cookies.json"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add jakpost_scraper/config.py tests/test_config.py
git commit -m "feat: add auth configuration fields"
```

---

### Task 8: Ignore the `.auth/` secrets directory

The cached cookie jar is a session secret. Add `.auth/` to `.gitignore`.

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append to `.gitignore`**

Add this line to `.gitignore`:

```
.auth/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore the .auth session directory"
```

---

### Task 9: Create the `auth` module

`auth.py` exposes `AuthError` and `ensure_session(config, force_reauth=False) -> httpx.Cookies`. Logic:

- If `force_reauth` is `False` **and** `config.auth_cookies_file` exists → load JSON, return `httpx.Cookies`.
- Otherwise → read `JAKPOST_EMAIL`/`JAKPOST_PASSWORD`, run the HTTP login (GET form → extract `_token` → POST credentials), persist all `thejakartapost.com` cookies, return the jar.

The login GET and POST run inside one `httpx.Client` so the `_token` and `XSRF-TOKEN` cookie are consistent. A successful login is detected by a session cookie (`laravel_session` refreshed, or `auth_token_tjp_new` present) appearing after the POST.

**Files:**
- Create: `jakpost_scraper/auth.py`

- [ ] **Step 1: Create `jakpost_scraper/auth.py`**

```python
"""Authenticated-session handling.

Auth is opt-in (config.auth_enabled). ensure_session returns an httpx cookie
jar that HttpClient carries on every request. Login uses Jakarta Post's
native email/password form over plain HTTP — no browser. Credentials are
read from the JAKPOST_EMAIL / JAKPOST_PASSWORD environment variables and are
never stored in the repo. Cached cookies are reused without a validation
request; an expired session is caught mid-run by the caller (see cli.run).
"""

import json
import os

import httpx
from bs4 import BeautifulSoup

from .config import Config

# Domain whose cookies authorize premium access.
_COOKIE_DOMAIN = "thejakartapost.com"
# Either cookie present after the POST means a session was minted.
_SESSION_COOKIE_NAMES = ("laravel_session", "auth_token_tjp_new")
_USER_AGENT = "jakpost-scraper/0.1 (news summarizer bot)"
_LOGIN_TIMEOUT_SECONDS = 30


class AuthError(Exception):
    """Raised when an authenticated session cannot be obtained."""


def ensure_session(config: Config, force_reauth: bool = False) -> httpx.Cookies:
    """Return an httpx cookie jar for an authenticated Jakarta Post session.

    Reuses config.auth_cookies_file if it exists and force_reauth is False;
    otherwise logs in over HTTP and persists the result.
    """
    if not force_reauth and os.path.exists(config.auth_cookies_file):
        return _load_cookies(config.auth_cookies_file)
    cookies = _http_login(config)
    _save_cookies(config.auth_cookies_file, cookies)
    return cookies


def _load_cookies(path: str) -> httpx.Cookies:
    """Load a {name: value} cookie mapping from a JSON file."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise AuthError(f"Could not read cached cookies at {path}: {e}") from e
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


def _credentials() -> tuple[str, str]:
    """Read login credentials from the environment, or raise AuthError."""
    email = os.environ.get("JAKPOST_EMAIL", "").strip()
    password = os.environ.get("JAKPOST_PASSWORD", "")
    if not email:
        raise AuthError("JAKPOST_EMAIL environment variable is not set")
    if not password:
        raise AuthError("JAKPOST_PASSWORD environment variable is not set")
    return email, password


def _extract_csrf_token(html: str) -> str:
    """Pull the hidden _token value out of the login form."""
    soup = BeautifulSoup(html, "lxml")
    field = soup.select_one('form input[name="_token"]')
    if field is None or not field.get("value"):
        raise AuthError("Login page did not contain a CSRF _token field")
    return str(field["value"])


def _http_login(config: Config) -> httpx.Cookies:
    """Log in via the native email/password form and return session cookies.

    GET the login page (sets XSRF-TOKEN + laravel_session cookies, carries the
    _token), then POST credentials. Both requests share one httpx.Client so
    the token and cookie are consistent. Raises AuthError on any failure.
    """
    email, password = _credentials()
    with httpx.Client(timeout=_LOGIN_TIMEOUT_SECONDS,
                      headers={"User-Agent": _USER_AGENT},
                      follow_redirects=True) as client:
        try:
            page = client.get(config.auth_login_url)
            page.raise_for_status()
            token = _extract_csrf_token(page.text)
            client.post(config.auth_login_url, data={
                "_token": token,
                "email": email,
                "password": password,
            })
        except httpx.HTTPError as e:
            raise AuthError(f"Login request failed: {e}") from e

        names = set(client.cookies.keys())
        if not names.intersection(_SESSION_COOKIE_NAMES):
            raise AuthError(
                "Login did not produce a session cookie — check "
                "JAKPOST_EMAIL / JAKPOST_PASSWORD")
        jar = httpx.Cookies()
        for name in client.cookies.keys():
            jar.set(name, client.cookies.get(name), domain=_COOKIE_DOMAIN)
        return jar
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `python -c "from jakpost_scraper.auth import ensure_session, AuthError; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add jakpost_scraper/auth.py
git commit -m "feat: add auth module with native HTTP form login"
```

---

### Task 10: Test the `auth` module

Cover: cached cookie file → no login; missing file → GET-then-POST login; `--reauth` ignores the cache; missing env vars → `AuthError`; login that mints no session cookie → `AuthError`; corrupt cookie file → `AuthError`. The login GET/POST are mocked with `pytest-httpx`; no network.

**Files:**
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

import httpx
import pytest

from jakpost_scraper.auth import ensure_session, AuthError
from jakpost_scraper.config import Config

FIXTURES = Path(__file__).parent / "fixtures"
LOGIN_URL = "https://www.thejakartapost.com/user/account/login"


def _login_html():
    return (FIXTURES / "login_page.html").read_text(encoding="utf-8")


def _cfg(tmp_path, **kw):
    return Config(
        auth_enabled=True,
        auth_login_url=LOGIN_URL,
        auth_cookies_file=str(tmp_path / "cookies.json"),
        **kw,
    )


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("JAKPOST_EMAIL", "user@example.com")
    monkeypatch.setenv("JAKPOST_PASSWORD", "secret")


def test_existing_cookie_file_is_loaded_without_login(tmp_path, monkeypatch):
    (tmp_path / "cookies.json").write_text(json.dumps({"laravel_session": "abc"}))
    # No httpx_mock fixture used: any network call would error out.
    jar = ensure_session(_cfg(tmp_path))
    assert jar.get("laravel_session") == "abc"


def test_missing_cookie_file_triggers_login_and_persists(tmp_path, creds,
                                                         httpx_mock):
    httpx_mock.add_response(url=LOGIN_URL, text=_login_html())  # GET
    httpx_mock.add_response(  # POST
        url=LOGIN_URL, status_code=302,
        headers={"set-cookie": "laravel_session=authed; Path=/"})
    jar = ensure_session(_cfg(tmp_path))
    assert jar.get("laravel_session") == "authed"
    saved = json.loads((tmp_path / "cookies.json").read_text())
    assert saved.get("laravel_session") == "authed"
    # The POST body carried the scraped _token + credentials.
    post = httpx_mock.get_requests()[-1]
    assert b"_token=FORM-TOKEN-VALUE-12345" in post.content
    assert b"email=user%40example.com" in post.content


def test_force_reauth_ignores_existing_cookie_file(tmp_path, creds, httpx_mock):
    (tmp_path / "cookies.json").write_text(json.dumps({"laravel_session": "old"}))
    httpx_mock.add_response(url=LOGIN_URL, text=_login_html())
    httpx_mock.add_response(
        url=LOGIN_URL, status_code=302,
        headers={"set-cookie": "laravel_session=new; Path=/"})
    jar = ensure_session(_cfg(tmp_path), force_reauth=True)
    assert jar.get("laravel_session") == "new"


def test_missing_email_env_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("JAKPOST_EMAIL", raising=False)
    monkeypatch.setenv("JAKPOST_PASSWORD", "secret")
    with pytest.raises(AuthError, match="JAKPOST_EMAIL"):
        ensure_session(_cfg(tmp_path))


def test_missing_password_env_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("JAKPOST_EMAIL", "user@example.com")
    monkeypatch.delenv("JAKPOST_PASSWORD", raising=False)
    with pytest.raises(AuthError, match="JAKPOST_PASSWORD"):
        ensure_session(_cfg(tmp_path))


def test_login_without_session_cookie_raises(tmp_path, creds, httpx_mock):
    httpx_mock.add_response(url=LOGIN_URL, text=_login_html())  # GET
    httpx_mock.add_response(url=LOGIN_URL, text=_login_html())  # POST: re-renders form, no cookie
    with pytest.raises(AuthError, match="session cookie"):
        ensure_session(_cfg(tmp_path))


def test_corrupt_cookie_file_raises(tmp_path):
    (tmp_path / "cookies.json").write_text("not json at all")
    with pytest.raises(AuthError):
        ensure_session(_cfg(tmp_path))


def test_login_page_without_token_raises(tmp_path, creds, httpx_mock):
    httpx_mock.add_response(url=LOGIN_URL,
                            text="<html><form></form></html>")
    with pytest.raises(AuthError, match="CSRF"):
        ensure_session(_cfg(tmp_path))
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_auth.py -v`
Expected: PASS — `auth.py` (Task 9) implements all this behavior. If any test fails, fix `auth.py` to match the asserted behavior.

> Note on `pytest-httpx`: by default it asserts every mocked response is used. `test_existing_cookie_file_is_loaded_without_login` registers no responses and makes no requests — that is fine. If `pytest-httpx` complains about an unused response in any test, it means an expected request was not made — treat that as a real failure to investigate.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py
git commit -m "test: cover auth module login and session-reuse logic"
```

---

### Task 11: Wire auth into the CLI

Add `--auth`/`--no-auth` and `--reauth` flags. In `run`, when auth is enabled, call `ensure_session` and pass the cookie jar to `HttpClient`. After scraping, if auth was enabled and >50% of premium articles are truncated, raise `AuthError` to abort.

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

In `jakpost_scraper/cli.py`, inside `build_parser` (before `return parser`, lines 36-37) add:

```python
    parser.add_argument("--auth", dest="auth", action="store_true", default=None,
                        help="Enable authenticated scraping for this run")
    parser.add_argument("--no-auth", dest="auth", action="store_false",
                        help="Disable authenticated scraping for this run")
    parser.add_argument("--reauth", action="store_true",
                        help="Force a fresh login even if a session is cached")
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

After the existing `from .config import ...` line (line 6 area), add:

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

In `run`, replace the `with HttpClient(...)` line (lines 66-67):

```python
    cookies = None
    if config.auth_enabled:
        cookies = ensure_session(config, force_reauth=args.reauth)

    with HttpClient(config.http_timeout, config.http_retries,
                    config.request_delay, cookies=cookies) as http:
```

After `scrape_articles` is called and `articles` is assigned (after line 80, before `result.articles = articles` on line 81), add the mid-run abort check — still inside the `with HttpClient(...)` block, so the client closes cleanly before the exception propagates:

```python
        if config.auth_enabled and _session_looks_dead(articles):
            raise AuthError(
                "Most premium articles came back truncated — the session has "
                "likely expired. Re-run with --reauth to log in again.")
```

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
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add jakpost_scraper/cli.py tests/test_cli.py
git commit -m "feat: wire authenticated scraping into the CLI run"
```

---

### Task 12: Surface premium-captured count in the Markdown report

The report should show how many premium articles were captured in full — the visible signal that auth is working. Add a `RunResult` field and render it.

**Files:**
- Modify: `jakpost_scraper/models.py:108-120` (add `RunResult` field)
- Modify: `jakpost_scraper/cli.py` (populate the field in `run`)
- Modify: `jakpost_scraper/output.py:75-85` (render it)
- Test: `tests/test_output.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_output.py` (do not duplicate imports already at the top of the file):

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
Expected: FAIL — `RunResult` has no field `premium_full`.

- [ ] **Step 3: Add the `RunResult` field**

In `jakpost_scraper/models.py`, add to the `RunResult` dataclass after `skipped_paywall` (line 116):

```python
    premium_full: int = 0
```

- [ ] **Step 4: Populate it in `cli.run`**

In `jakpost_scraper/cli.py`, where `run` sets `result.skipped_paywall` (after line 84), add:

```python
    result.premium_full = sum(
        1 for a in articles if a.is_premium and not a.is_truncated)
```

- [ ] **Step 5: Render it in the report**

In `jakpost_scraper/output.py`, `_render_report`, replace the counts line group (lines 80-82) with:

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

### Task 13: Integration test for the authenticated path

Extend `tests/test_integration.py` with a run where `auth_enabled=True`, the login GET/POST are mocked, and a premium-full fixture is served — asserting the full body is captured and `premium_full` is counted.

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Inspect the existing integration test structure**

Run: `sed -n '1,70p' tests/test_integration.py`
Expected: shows how the existing test mocks the sitemap index + news sitemaps + article pages via `httpx_mock`, builds `Config`, and calls `cli.run`. Reuse that exact setup style for the new test.

- [ ] **Step 2: Write the failing integration test**

Append a test to `tests/test_integration.py` that follows the file's existing pattern. It must:

1. Set `JAKPOST_EMAIL` / `JAKPOST_PASSWORD` via `monkeypatch.setenv`.
2. Build a `Config` with `auth_enabled=True`, `auth_login_url` set to a test URL, and a `tmp_path`-based `auth_cookies_file`.
3. Mock the login GET (returns `tests/fixtures/login_page.html`) and the login POST (status 302, `set-cookie: laravel_session=authed; Path=/`).
4. Mock the sitemap index + a news sitemap listing one article URL, exactly as the existing integration tests do.
5. Serve `tests/fixtures/article_premium_full.html` for that article URL.
6. Call `run(config, state, args)` with `args.no_summary = True` to stay offline from the summarizer.
7. Assert: `result.scraped == 1`, `result.articles[0].is_premium is True`, `result.articles[0].is_truncated is False`, `result.premium_full == 1`.

Concrete test (adapt the sitemap-mocking helpers and `Config`/`args` construction to match this file's existing helpers — repeat that construction inline rather than inventing helper names):

```python
def test_authenticated_run_captures_full_premium_body(tmp_path, httpx_mock,
                                                      monkeypatch):
    from jakpost_scraper.cli import run

    monkeypatch.setenv("JAKPOST_EMAIL", "user@example.com")
    monkeypatch.setenv("JAKPOST_PASSWORD", "secret")

    login_url = "https://www.thejakartapost.com/user/account/login"
    httpx_mock.add_response(
        url=login_url,
        text=(FIXTURES / "login_page.html").read_text(encoding="utf-8"))
    httpx_mock.add_response(
        url=login_url, status_code=302,
        headers={"set-cookie": "laravel_session=authed; Path=/"})

    # --- mock discovery exactly as the other integration tests do, then
    #     serve one premium article URL ---
    article_url = ARTICLE_URL  # constant already defined in this file
    httpx_mock.add_response(
        url=article_url,
        text=(FIXTURES / "article_premium_full.html").read_text(encoding="utf-8"))

    config = make_config(tmp_path, auth_enabled=True,
                         auth_login_url=login_url,
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

> If `test_integration.py` lacks `make_config`/`empty_state`/`make_args`/sitemap-mock helpers, use whatever construction its existing tests use inline. The numbered requirements in Step 2 are what matters.

- [ ] **Step 3: Run the integration test**

Run: `pytest tests/test_integration.py::test_authenticated_run_captures_full_premium_body -v`
Expected: iterate on the sitemap mocking until the article is discovered, scraped, and the assertions pass. Production code is already complete from Tasks 1-12.

- [ ] **Step 4: Run the full suite**

Run: `pytest -q`
Expected: PASS — every test green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration coverage for authenticated full-body capture"
```

---

### Task 14: Update README and config sample

Document the feature: enabling auth, setting the credential env vars, and `--reauth`.

**Files:**
- Modify: `README.md`
- Modify: `config.yaml`

- [ ] **Step 1: Add an "Authenticated scraping" section to `README.md`**

Append to `README.md`:

```markdown
## Authenticated scraping (premium articles)

By default the scraper runs as a guest, so premium articles return only a
teaser. To capture full premium article bodies, log in with your own Jakarta
Post account.

**Set your credentials** as environment variables (they are never written to
the repo):

```bash
export JAKPOST_EMAIL="you@example.com"
export JAKPOST_PASSWORD="your-password"
```

**Enable it** — set `auth_enabled: true` in `config.yaml`, or pass `--auth`
on a single run.

The scraper logs in over HTTP on the first run and caches the session to
`.auth/` (gitignored), reusing it on later runs. When the session expires,
the run aborts with a message — re-run with `--reauth` to log in again.

Authentication is entirely opt-in: with `auth_enabled: false` (the default)
the scraper behaves exactly as before.
```

- [ ] **Step 2: Add commented auth keys to `config.yaml`**

Append to `config.yaml`:

```yaml

# Authenticated scraping (optional; off by default).
# Set JAKPOST_EMAIL and JAKPOST_PASSWORD environment variables to use it.
# auth_enabled: false
# auth_login_url: "https://www.thejakartapost.com/user/account/login"
```

- [ ] **Step 3: Commit**

```bash
git add README.md config.yaml
git commit -m "docs: document authenticated scraping setup"
```

---

### Task 15: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: PASS — all tests green.

- [ ] **Step 2: Verify guest mode is untouched**

Run: `python -c "
from jakpost_scraper.config import load_config
cfg = load_config('config.yaml', {})
assert cfg.auth_enabled is False, 'auth must default off'
print('guest mode default: ok')
"`
Expected: prints `guest mode default: ok`

- [ ] **Step 3: Verify a missing-credentials error is clear**

Run: `python -c "
import os
for v in ('JAKPOST_EMAIL', 'JAKPOST_PASSWORD'):
    os.environ.pop(v, None)
from jakpost_scraper.auth import ensure_session, AuthError
from jakpost_scraper.config import Config
cfg = Config(auth_enabled=True, auth_cookies_file='/tmp/does-not-exist-xyz.json')
try:
    ensure_session(cfg)
    print('ERROR: expected AuthError')
except AuthError as e:
    print('missing-credentials error ok:', e)
"`
Expected: prints `missing-credentials error ok: JAKPOST_EMAIL environment variable is not set`

- [ ] **Step 4: Final commit if anything is uncommitted**

```bash
git status
# if clean, nothing to do; otherwise:
git add -A && git commit -m "chore: finalize authenticated scraping feature"
```

---

## Self-review notes

**Spec coverage check:**
- Capture full premium bodies → Tasks 4, 13. ✓
- Guest scraping unchanged when auth disabled → Tasks 7, 15 (auth defaults off; `ensure_session` only called when enabled). ✓
- Native HTTP form login, no browser/dependency → Task 9 (`httpx` + `BeautifulSoup`, both existing deps). ✓
- Credentials from `JAKPOST_EMAIL`/`JAKPOST_PASSWORD` env vars → Task 9 `_credentials`, Task 10 tests. ✓
- GET-then-POST in one client; `_token` + `XSRF-TOKEN` consistent → Task 9 `_http_login`. ✓
- `ensure_session` paths (cached / login / `--reauth`) → Tasks 9, 10. ✓
- No startup validation request (D-006) → Task 9 `ensure_session` loads-and-returns. ✓
- Mid-run expiry abort (D-005, >50% premium truncated) → Task 11 `_session_looks_dead`. ✓
- 3 config keys → Task 7. ✓
- CLI flags `--auth`/`--no-auth`/`--reauth` → Task 11. ✓
- `is_premium` / `is_truncated` split; `is_paywalled` kept as alias → Tasks 3, 4. ✓
- Output surfaces premium-captured count → Task 12. ✓
- `.auth/` gitignored → Task 8. ✓
- Login rejected / missing creds / corrupt cookie file → `AuthError` → Task 9, Task 10 tests. ✓
- All test files/fixtures named in the spec (`test_auth.py`, `login_page.html`, `article_premium_full.html`) → Tasks 1, 2, 10. ✓

**Deviation from spec (intentional, see "Design decisions locked in"):** `is_truncated` is purely `div.tjp-paywall`-based; the spec's secondary "body suspiciously short" heuristic is dropped as YAGNI.

**Type consistency:** `ensure_session(config, force_reauth=False) -> httpx.Cookies`, `_session_looks_dead(articles) -> bool`, `_detect_premium(jsonld) -> bool`, `_detect_truncated(soup) -> bool`, `_http_login(config) -> httpx.Cookies`, `_credentials() -> tuple[str, str]`, `_extract_csrf_token(html) -> str` — names and signatures used identically across Tasks 4, 9, 10, 11. `Article` field order (`is_paywalled, is_premium, is_truncated`) is consistent across Tasks 3, 4, 5, 11, 12, 13.
