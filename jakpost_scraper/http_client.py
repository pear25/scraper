"""Shared HTTP client with retries and a politeness delay."""

import time

import httpx

USER_AGENT = "jakpost-scraper/0.1 (news summarizer bot)"
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
