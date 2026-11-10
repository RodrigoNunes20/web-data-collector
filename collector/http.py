"""A small, polite HTTP client: timeouts, retries with backoff, and a delay between requests."""
from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "web-data-collector/1.0 (portfolio project; polite crawler)"


class FetchError(Exception):
    """Raised when a page or API call cannot be retrieved."""


def build_session(retries: int = 3, headers: Optional[Mapping[str, str]] = None) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, **(headers or {})})
    return session


class Fetcher:
    """Wraps a requests session. Waits `delay` seconds between requests so servers are not hammered."""

    def __init__(
        self,
        delay: float = 1.0,
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.session = session or build_session()
        self._clock = clock
        self._sleep = sleep
        self._last_request: Optional[float] = None

    def _wait_turn(self) -> None:
        if self._last_request is not None and self.delay:
            remaining = self.delay - (self._clock() - self._last_request)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request = self._clock()

    def _get(self, url: str, params: Optional[Mapping[str, Any]] = None) -> requests.Response:
        self._wait_turn()
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise FetchError(f"Could not reach {url}: {exc}") from exc
        if response.status_code >= 400:
            hint = ""
            if response.status_code in (403, 429):
                hint = " (rate limited or blocked; wait a while and try again, or use a token if the API supports it)"
            raise FetchError(f"HTTP {response.status_code} for {url}{hint}")
        return response

    def get_text(self, url: str) -> str:
        response = self._get(url)
        try:  # many sites omit the charset header, which makes requests guess Latin-1 and garble symbols
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            return response.content.decode(response.encoding or "latin-1", errors="replace")

    def get_json(self, url: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        response = self._get(url, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise FetchError(f"Response from {url} is not valid JSON") from exc
