# Decisions

Master log of architectural and product decisions for `jakpost_scraper`.
Each row records a decision, why it was made, and what was deliberately deferred.

| ID | Date | Topic | Decision | Rationale | Status | Backlog / Follow-up |
|----|------|-------|----------|-----------|--------|---------------------|
| D-001 | 2026-05-21 | Authenticated scraping — login method | Authenticate via a real browser (Playwright) rather than scripting login with raw HTTP. | Jakarta Post premium accounts use Google SSO (OAuth). Google's login runs JavaScript, captcha, and 2FA, which an `httpx`-only client cannot complete. | Accepted | — |
| D-002 | 2026-05-21 | Session handling | Use a **persistent browser profile** (option A): first run opens a browser for one interactive Google login; later runs reuse the saved profile silently. Article fetching stays on the existing `httpx.Client`; Playwright is used only to obtain the session. | Minimizes recurring friction for non-technical users — login is a familiar one-time action, and most runs need zero interaction. Keeps the per-article scrape loop unchanged (no performance regression). | Accepted | — |
| D-003 | 2026-05-21 | Performance impact of Playwright | Accept Playwright as a dependency. Browser launches **only** when no valid cached session exists; valid sessions load cookies straight into `httpx` with zero browser overhead. | Per-run cost is a one-time ~150 MB install plus ~2–5 s conditional startup. Per-article fetching is unaffected. Memory spike (~300–500 MB Chromium) is brief and released after auth. | Accepted | — |
| D-004 | 2026-05-21 | Silent re-authentication | **Not pursued now.** Silent *reuse* of a valid session is supported; silent *re-auth* of an expired session is impossible with Google SSO (requires human 2FA). Re-auth, when needed, is automatic-to-trigger but interactive. | The scraper runs primarily as a manually triggered cron job. Sessions are evaluated at cold start and last days to weeks, so re-auth is rare. Not worth engineering further now. | Deferred | Revisit if session expiry becomes frequent: explore long-lived token storage to stretch session lifetime (cannot eliminate the occasional Google login). |
| D-005 | 2026-05-21 | Mid-run session expiry | If the session dies during a run, abort cleanly and re-prompt on the next run rather than silently shipping teaser text as full articles. | Startup auth check makes mid-run expiry rare; failing loud prevents incomplete data being treated as complete. | Accepted | — |

## Notes

- "Status" values: **Accepted** (decided and in scope), **Deferred** (consciously parked, see follow-up), **Superseded** (replaced by a later decision — link the new ID).
- When a decision is revisited, add a new row rather than editing the old one, and mark the old row **Superseded**.
