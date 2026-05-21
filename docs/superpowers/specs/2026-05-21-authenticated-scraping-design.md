# Authenticated Scraping — Design

**Date:** 2026-05-21
**Status:** Approved (design); pending implementation plan
**Related:** [DECISIONS.md](../../../DECISIONS.md) rows D-001 through D-006

## Problem

The scraper currently fetches Jakarta Post articles as a guest. Premium
("paywalled") articles return only a teaser body, so summaries of those
articles are based on incomplete text. The goal is to let the scraper read
premium articles in full by reusing an authenticated Jakarta Post session.

## Key constraint

Jakarta Post premium accounts log in via **Google SSO (OAuth)**. Google's
login flow runs JavaScript, may present a captcha, and requires 2FA — it
cannot be completed by an `httpx`-only HTTP client. Authentication therefore
requires a real browser. Article *scraping*, however, does not: once a
session exists, its `thejakartapost.com` cookies authorize plain HTTP
requests.

This splits the feature into two concerns:

- **Authentication** — needs a real browser (Playwright), runs rarely.
- **Scraping** — stays on the existing `httpx` client, runs every article.

## Goals

- Capture the full body of premium articles when an authenticated session
  is available.
- Keep guest scraping working unchanged when authentication is disabled.
- Minimize recurring friction for non-technical users: most runs need zero
  interaction; interactive login happens only on first run or after the
  session genuinely expires.
- No per-article performance regression.

## Non-goals

- Silent re-authentication of an expired session — impossible with Google
  SSO, which requires human 2FA (see D-004, deferred).
- Storing Jakarta Post credentials in the project. Only the resulting
  session cookies are persisted.
- Scripting Google's login page with raw HTTP.

## Architecture

A new `auth` module owns everything session-related and is the only module
that imports Playwright. The rest of the codebase is unchanged.

```
cli.py
  └─ load_config()                         (config.py — extended)
  └─ auth.ensure_session(config)  ──►  returns an httpx cookie jar
        ├─ if cached cookies file present  → load & return  (no browser)
        └─ else → launch Playwright, interactive login,
                  persist profile, extract cookies, return them
  └─ HttpClient(..., cookies=jar)           (http_client.py — extended)
  └─ discover() / scrape_articles()         (unchanged)
```

### Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `jakpost_scraper/auth.py` (new) | Obtain a valid session. Public surface: `ensure_session(config) -> httpx.Cookies`. All browser/profile/login internals are hidden behind it. | Playwright (optional), `httpx` |
| `http_client.py` (extended) | Gains an optional `cookies` parameter passed to `httpx.Client(cookies=...)`. No other change. | `httpx` |
| `config.py` (extended) | New auth config keys with safe defaults. | — |
| `cli.py` (extended) | New auth CLI flags; calls `ensure_session` when auth is enabled. | `auth.py`, `config.py` |
| `scraper.py` (modified) | Paywall-detection split (see below). Fetch loop unchanged. | `http_client.py` |
| `models.py` (modified) | New `is_premium` / `is_truncated` fields. | — |
| `discovery.py` | Unchanged — already routes through `HttpClient`. | — |

Playwright is an **optional dependency** installed via
`pip install jakpost_scraper[auth]`. When `auth_enabled` is false, `auth.py`
is never imported and the tool behaves exactly as today.

## Authentication flow & session lifecycle

`ensure_session(config)` runs at startup, before discovery. Three paths:

### 1. Cached session present (common case — no browser)

- A persistent Playwright profile lives at `auth_profile_dir`
  (default `./.auth/profile`).
- Extracted `thejakartapost.com` cookies live at `auth_cookies_file`
  (default `./.auth/cookies.json`).
- If `auth_cookies_file` exists, `ensure_session` loads it and returns the
  cookie jar without launching Playwright. There is **no startup validation
  request** (see D-006): an expired session is detected mid-run by the
  truncated-rate signal below, not pre-flight.

### 2. No cached session (first run), or `--reauth` forced

- Launch Playwright via `launch_persistent_context(auth_profile_dir,
  headless=False)`.
- Navigate to `auth_login_url`. The user clicks "Sign in with Google" and
  completes login including 2FA. Login is a standard Google OAuth 2.0
  Authorization Code flow. The script polls for success: the OAuth callback
  `https://www.thejakartapost.com/login/google/process` completes and the
  browser lands back on a `thejakartapost.com` page with session cookies
  set. Timeout is `auth_login_timeout` seconds (default 300).
- On success: extract **all** `thejakartapost.com` cookies, write
  `auth_cookies_file`, close the browser, return the jar.
- On timeout or the user closing the window: raise `AuthError`; the run
  aborts with a clear message.

### 3. Mid-run expiry (D-005)

If, during a run, premium articles come back truncated at a rate crossing a
threshold (>50% of premium articles in the run), the run aborts cleanly with
a re-auth message rather than shipping teaser text as full articles. Since
there is no startup validation request (D-006), this mid-run signal is the
primary mechanism for detecting an expired session.

### Lifecycle notes

- The browser is always closed immediately after authentication — never held
  open during scraping.
- `.auth/` is added to `.gitignore`; it holds session secrets.
- When `auth_enabled` is false, the entire flow is skipped (guest scraping).

## Configuration & CLI

New `Config` keys, all with defaults so existing `config.yaml` files keep
working unchanged:

| Key | Default | Purpose |
|-----|---------|---------|
| `auth_enabled` | `false` | Master switch. `false` → guest scraping, as today. |
| `auth_profile_dir` | `./.auth/profile` | Persistent Playwright browser profile. |
| `auth_cookies_file` | `./.auth/cookies.json` | Extracted `thejakartapost.com` cookie jar. |
| `auth_login_url` | Jakarta Post login page (exact path confirmed during implementation) | Page opened for interactive login. |
| `auth_login_timeout` | `300` | Seconds to wait for the interactive Google login. |

CLI flags (`cli.py`) for ad-hoc overrides without editing `config.yaml`:

- `--auth` / `--no-auth` — override `auth_enabled` for one run.
- `--reauth` — force the login flow even if a cached session exists (stale
  session, or switching accounts).

`load_config()` continues to reject unknown keys; the new keys are added to
the accepted set.

**Credential security:** no username or password is ever stored in the
project. The only persisted secret is the session cookie jar in `.auth/`
(gitignored). The user authenticates in a real Google window; the scraper
keeps only the resulting session.

## Paywall detection & output semantics

Today's `_detect_paywall()` conflates two things that diverge once
authenticated:

- **Is this article premium?** — a property of the *article*. JSON-LD
  `isAccessibleForFree == false`. Remains `false` even when the current user
  can read it.
- **Did we get the full text?** — a property of *this fetch*. With a valid
  session, a premium article returns the complete body.

These are split into two `Article` fields:

| Field | Meaning | Derivation |
|-------|---------|------------|
| `is_premium` | Article is gated content. | JSON-LD `isAccessibleForFree == false`. |
| `is_truncated` | The full body was **not** captured for this fetch. | `div.tjp-paywall` present, **or** body suspiciously short despite `is_premium`. |

Outcomes:

- **Guest run:** `is_premium=true` articles come back `is_truncated=true` —
  same observable behavior as today.
- **Authenticated run:** `is_premium=true`, `is_truncated=false` — full body
  captured. This is the feature win.

The existing `paywall_mode` (`keep-teaser` / `skip`) now keys off
`is_truncated`, so partial articles are handled by logic that already
exists.

**Backward compatibility:** `is_paywalled` remains on the model as a derived
alias of `is_truncated`, so existing output consumers and tests do not
break. Output JSON and the Markdown report gain `is_premium` and
`is_truncated`; the Markdown report additionally reports how many premium
articles were captured in full versus truncated — a visible signal the
feature is working.

**Mid-run expiry signal:** when `auth_enabled` is true and the truncated
rate across a run exceeds 50% of premium articles, the run aborts with a
re-auth message, distinguishing a dead session from a single odd article.

## Error handling

| Situation | Behavior |
|-----------|----------|
| `auth_enabled=false` | Auth flow skipped entirely; guest scraping as today. |
| Cached session file present | Load cookies; no browser launch, no validation request. |
| Cached session file missing, or `--reauth` | Launch interactive login. |
| Interactive login times out / window closed | Raise `AuthError`; run aborts with a clear message. |
| Playwright not installed but `auth_enabled=true` | Fail fast with a message pointing to `pip install jakpost_scraper[auth]`. |
| Mid-run session expiry (>50% premium truncated) | Abort cleanly with a re-auth message; next run re-prompts login. |
| Single premium article truncated below threshold | Fall back to existing `paywall_mode` (keep-teaser / skip) per article. |

## Testing

Follows the existing fixture-based, no-live-network pattern. No test launches
a real browser or hits the network.

- **`test_auth.py` (new)** — `ensure_session` decision logic: valid cached
  cookies → no browser; missing/invalid cookies → login path triggered.
  Playwright is mocked; the test covers the decision logic, not the browser.
- **New HTML fixtures** — `article_premium_full.html` (premium, full body,
  as seen authenticated) alongside the existing `article_paywalled.html`.
- **`test_scraper.py` (extended)** — cases for the `is_premium` /
  `is_truncated` split across guest and authenticated fixtures.
- **`test_http_client.py` (extended)** — cookies passed to `HttpClient` are
  sent on outgoing requests.
- **`test_config.py` (extended)** — new auth keys load, default off, unknown
  keys still rejected.
- **`test_integration.py` (extended)** — an `auth_enabled` path with mocked
  cookies and a premium fixture asserting the full body is captured; the
  existing guest path is untouched.

## Open items for implementation

- **Login URL:** Jakarta Post's own login page (the page hosting the
  "Sign in with Google" button — exact path to confirm).
- **Login-success signal:** the OAuth callback
  `https://www.thejakartapost.com/login/google/process` completes and the
  browser lands back on a `thejakartapost.com` page with session cookies
  set. (Confirmed: standard Google OAuth 2.0 Authorization Code flow —
  `state` is a server-issued CSRF token, which is why interactive browser
  login is required and raw-HTTP login is not.)
- **Cookie scope:** persist **all** `thejakartapost.com` cookies, not a
  hardcoded subset. Authorization is known to span at least
  `laravel_session` and `auth_token_tjp_new` (Laravel backend); the `_new`
  suffix and a possible `XSRF-TOKEN` mean a fixed list is brittle. Saving
  the whole domain jar is robust and harmless.
- **Startup session validation:** deferred (D-006). `ensure_session`
  returns cached cookies without a pre-flight validation request; an
  expired session is caught mid-run by the >50% truncated-rate signal
  (D-005). A startup validation check (and the known-premium URL it would
  need) can be added when revisited.
