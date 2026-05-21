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
