# Authenticated Scraping — Design

**Date:** 2026-05-21
**Status:** Approved (design); pending implementation plan
**Related:** [DECISIONS.md](../../../DECISIONS.md) — D-005, D-006, D-007 (D-007
supersedes D-001/D-002/D-003/D-004)

> **Revision note:** an earlier version of this design used Google SSO +
> Playwright. Inspection of the live login page on 2026-05-21 showed Jakarta
> Post offers a native email/password login — a plain Laravel HTML form, no
> captcha, no bot challenge. The design below uses a pure `httpx` HTTP login
> and **no browser**. See D-007.

## Problem

The scraper currently fetches Jakarta Post articles as a guest. Premium
("paywalled") articles return only a teaser body, so summaries of those
articles are based on incomplete text. The goal is to let the scraper read
premium articles in full by logging in with a Jakarta Post account.

## Key facts about the login (verified 2026-05-21)

The login page `https://www.thejakartapost.com/user/account/login` contains:

```html
<form method="POST" action="https://www.thejakartapost.com/user/account/login">
  <input type="hidden" name="_token" value="...">
  <input type="email"    name="email">
  <input type="password" name="password">
  <input type="submit">
</form>
```

- It is a **plain HTML form POST** (`application/x-www-form-urlencoded`) —
  not a JavaScript/XHR login.
- CSRF uses Laravel's double-submit pattern: the `GET` response sets an
  `XSRF-TOKEN` cookie **and** the page embeds a matching `_token` hidden
  field. The POST must send the `_token` value scraped from the *same* page
  load that set the cookie.
- The `GET` already sets `laravel_session` and `XSRF-TOKEN` cookies. A
  successful `POST` refreshes `laravel_session` to an authenticated session
  (and the site additionally uses `auth_token_tjp_new`).
- **No captcha** (no reCAPTCHA / hCaptcha / Turnstile on the page).
- **No Cloudflare bot challenge.** The site is fronted by CloudFront (a
  plain CDN), which does not gate logins.

Because nothing on the login path requires JavaScript execution, the entire
flow runs on `httpx`. No browser is needed.

## Goals

- Capture the full body of premium articles when authenticated.
- Keep guest scraping working unchanged when authentication is disabled.
- Fully non-interactive login — suitable for an unattended cron job.
- No per-article performance regression.
- Never store credentials in the repository.

## Non-goals

- Browser automation. The native form login does not need it (D-007).
- A startup session-validation request (deferred — D-006).
- Solving captchas or bot challenges — none exist on this login.

## Architecture

A new `auth` module owns the login flow and produces an `httpx` cookie jar.
The rest of the codebase is unchanged; article fetching stays on the
existing `HttpClient`.

```
cli.py
  └─ load_config()                         (config.py — extended)
  └─ auth.ensure_session(config)  ──►  returns an httpx cookie jar
        ├─ if cached cookies file present  → load & return
        └─ else → HTTP login (GET form → POST creds) → persist → return
  └─ HttpClient(..., cookies=jar)           (http_client.py — extended)
  └─ discover() / scrape_articles()         (unchanged)
```

### Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `jakpost_scraper/auth.py` (new) | Obtain a session. Public surface: `ensure_session(config, force_reauth=False) -> httpx.Cookies`, `AuthError`. Reads credentials from env vars; performs the GET-form/POST-credentials login. | `httpx`, `BeautifulSoup` (both already project deps) |
| `http_client.py` (extended) | Gains an optional `cookies` parameter passed to `httpx.Client(cookies=...)`. No other change. | `httpx` |
| `config.py` (extended) | New auth config keys with safe defaults. | — |
| `cli.py` (extended) | New auth CLI flags; calls `ensure_session` when auth is enabled; mid-run expiry abort. | `auth.py`, `config.py` |
| `scraper.py` (modified) | Paywall-detection split (see below). Fetch loop unchanged. | `http_client.py` |
| `models.py` (modified) | New `is_premium` / `is_truncated` fields. | — |
| `output.py` (modified) | Report premium-captured-in-full count. | — |
| `discovery.py` | Unchanged — already routes through `HttpClient`. | — |

**No new dependency.** `httpx` and `beautifulsoup4` are already in
`pyproject.toml`. There is no optional `[auth]` extra and no install step.
When `auth_enabled` is false, `auth.py` is never imported.

## Credentials

Credentials are read from **environment variables**, never stored in the
repo:

- `JAKPOST_EMAIL` — the account email.
- `JAKPOST_PASSWORD` — the account password.

If `auth_enabled` is true and either variable is missing or empty,
`ensure_session` raises `AuthError` with a message naming the missing
variable. `config.yaml` holds only non-secret settings.

## Authentication flow & session lifecycle

`ensure_session(config, force_reauth=False)` runs at startup, before
discovery. Two paths:

### 1. Cached session present (common case)

- Extracted cookies live at `auth_cookies_file` (default
  `./.auth/cookies.json`).
- If the file exists and `force_reauth` is false, load it into an
  `httpx.Cookies` jar and return it. There is **no startup validation
  request** (D-006): an expired session is detected mid-run by the
  truncated-rate signal below.

### 2. No cached session (first run), or `--reauth` forced

The HTTP login, performed inside one short-lived `httpx.Client` so cookies
carry across the two requests:

1. Read `JAKPOST_EMAIL` / `JAKPOST_PASSWORD` from the environment; raise
   `AuthError` if missing.
2. `GET auth_login_url`. This sets the `XSRF-TOKEN` and `laravel_session`
   cookies on the client.
3. Parse the response HTML; extract the hidden `_token` input's value. The
   `_token` and the cookies **must come from this same response** —
   CloudFront may cache the page, but a fresh GET-then-POST in one client is
   internally consistent.
4. `POST auth_login_url` with form body `{_token, email, password}`.
5. On success, the client's cookie jar now holds the authenticated
   `laravel_session` (and `auth_token_tjp_new`). Persist **all**
   `thejakartapost.com` cookies to `auth_cookies_file` and return the jar.
6. On failure (the response indicates login was rejected — see Error
   handling), raise `AuthError`.

### 3. Mid-run expiry (D-005)

If, during a run, premium articles come back truncated at a rate exceeding
50% of premium articles in the run, the run aborts cleanly with a re-auth
message rather than shipping teaser text as full articles. Since there is no
startup validation request (D-006), this mid-run signal is the primary
mechanism for detecting an expired session.

### Lifecycle notes

- The login `httpx.Client` is closed immediately after the cookie jar is
  extracted. Article scraping uses a separate `HttpClient` carrying that jar.
- `.auth/` is added to `.gitignore`; it holds the session cookie jar.
- When `auth_enabled` is false, the entire flow is skipped (guest scraping).

## Configuration & CLI

New `Config` keys, all with defaults so existing `config.yaml` files keep
working unchanged:

| Key | Default | Purpose |
|-----|---------|---------|
| `auth_enabled` | `false` | Master switch. `false` → guest scraping, as today. |
| `auth_login_url` | `https://www.thejakartapost.com/user/account/login` | The login form URL (used for both the GET and the POST). |
| `auth_cookies_file` | `./.auth/cookies.json` | Cached `thejakartapost.com` cookie jar. |

CLI flags (`cli.py`) for ad-hoc overrides without editing `config.yaml`:

- `--auth` / `--no-auth` — override `auth_enabled` for one run.
- `--reauth` — force a fresh HTTP login even if a cached session exists.

`load_config()` continues to reject unknown keys; the new keys are added to
the accepted set.

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
| `is_premium` | Article is gated content. | JSON-LD `isAccessibleForFree` is falsey. |
| `is_truncated` | The full body was **not** captured for this fetch. | `div.tjp-paywall` is present in the page. |

Outcomes:

- **Guest run:** `is_premium=true` articles come back `is_truncated=true` —
  same observable behavior as today.
- **Authenticated run:** `is_premium=true`, `is_truncated=false` — full body
  captured. This is the feature win.

The existing `paywall_mode` (`keep-teaser` / `skip`) now keys off
`is_truncated`, so partial articles are handled by logic that already
exists.

**Backward compatibility:** `is_paywalled` remains on the model as a stored
field equal to `is_truncated`, so existing output consumers and tests do not
break. Output JSON and the Markdown report gain `is_premium` and
`is_truncated`; the report additionally reports how many premium articles
were captured in full — a visible signal the feature is working.

## Error handling

| Situation | Behavior |
|-----------|----------|
| `auth_enabled=false` | Auth flow skipped entirely; guest scraping as today. |
| `JAKPOST_EMAIL` / `JAKPOST_PASSWORD` missing while `auth_enabled=true` | Raise `AuthError` naming the missing variable; run aborts. |
| Cached session file present | Load cookies; no login request. |
| Cached session file missing, or `--reauth` | Run the HTTP login. |
| Login rejected (bad credentials / CSRF failure) | Raise `AuthError` with a clear message; run aborts. |
| Network failure during login | Raise `AuthError` wrapping the underlying error; run aborts. |
| Corrupt `auth_cookies_file` | Raise `AuthError`; the user can delete the file or pass `--reauth`. |
| Mid-run session expiry (>50% premium truncated) | Abort cleanly with a re-auth message; next run re-logs-in. |
| Single premium article truncated below threshold | Fall back to existing `paywall_mode` (keep-teaser / skip) per article. |

## Testing

Follows the existing fixture-based, no-live-network pattern. No test hits the
network — `pytest-httpx` mocks the login GET and POST.

- **`test_auth.py` (new)** — `ensure_session` decision logic: cached cookies
  → no login request; missing cookies → GET-then-POST login; `--reauth`
  ignores the cache; missing env vars → `AuthError`; rejected login →
  `AuthError`. The login GET/POST are mocked with `pytest-httpx`.
- **New fixture** `tests/fixtures/login_page.html` — a minimal login page
  with the `_token` hidden field, for the login-flow test to parse.
- **New HTML fixture** `article_premium_full.html` — premium article, full
  body, no paywall div — for the `is_premium`/`is_truncated` tests.
- **`test_scraper.py` (extended)** — cases for the `is_premium` /
  `is_truncated` split across guest and authenticated fixtures.
- **`test_http_client.py` (extended)** — cookies passed to `HttpClient` are
  sent on outgoing requests.
- **`test_config.py` (extended)** — new auth keys load, default off, unknown
  keys still rejected.
- **`test_integration.py` (extended)** — an `auth_enabled` path with the
  login GET/POST mocked and a premium fixture asserting the full body is
  captured; the existing guest path is untouched.

## Open items for implementation

- **Login-success detection.** A successful Laravel form login typically
  responds with a `302` redirect away from the login page; a failed one
  re-renders the login page (often `200` with an error message). The
  implementation will treat "the response is still the login form / contains
  a login-error indication" as failure and anything else as success, and
  must verify a session cookie (`laravel_session` or `auth_token_tjp_new`)
  is present after the POST. The exact success heuristic is finalized during
  implementation against a real login response.
- **Cookie scope:** persist **all** `thejakartapost.com` cookies, not a
  hardcoded subset (D-006 / D-007) — `laravel_session`, `auth_token_tjp_new`,
  `XSRF-TOKEN`, etc.
- **Startup session validation:** deferred (D-006).
