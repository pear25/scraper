import httpx
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


def test_get_honors_retry_after_header(httpx_mock, monkeypatch):
    sleeps = []
    monkeypatch.setattr("jakpost_scraper.http_client.time.sleep",
                        lambda s: sleeps.append(s))
    httpx_mock.add_response(url="https://example.com/p", status_code=503,
                            headers={"Retry-After": "30"})
    httpx_mock.add_response(url="https://example.com/p", text="ok")
    with _client() as client:
        assert client.get("https://example.com/p").text == "ok"
    assert sleeps == [30.0]


def test_get_retries_on_network_error(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("boom"),
                             url="https://example.com/p")
    httpx_mock.add_response(url="https://example.com/p", text="recovered")
    with _client() as client:
        assert client.get("https://example.com/p").text == "recovered"
