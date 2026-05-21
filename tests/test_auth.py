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
