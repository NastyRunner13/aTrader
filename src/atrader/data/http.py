"""A polite, allowlisted HTTP client for data retrieval.

* Only hosts in `ALLOWED_HOSTS` can be fetched; retrieved text cannot steer retrieval
  to new destinations (docs/06, "Data boundaries and security").
* Requests to one host are spaced by a minimum interval and retried only on 429/5xx.
* Immutable archive files are cached forever by URL; API responses for a short TTL.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = frozenset({
    "www.nseindia.com",
    "nsearchives.nseindia.com",
    "api.gdeltproject.org",
})

# GDELT asks for at most one request every five seconds.
_HOST_MIN_INTERVAL = {"api.gdeltproject.org": 5.5}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 aTrader-personal-research"
)
_MAX_BYTES = 25 * 1024 * 1024


class FetchError(RuntimeError):
    """The source could not be reached or refused the request."""

    def __init__(self, url: str, reason: str, status: int | None = None) -> None:
        super().__init__(f"{reason} ({url})")
        self.url = url
        self.reason = reason
        self.status = status


class NotFoundError(FetchError):
    """The source answered 404: for date-named archives this usually means a holiday."""


@dataclass(frozen=True)
class Fetched:
    url: str
    content: bytes
    retrieved_at: datetime
    from_cache: bool

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


class PoliteClient:
    def __init__(
        self,
        cache_dir: Path,
        min_interval_s: float = 1.0,
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cache_dir = cache_dir / "http"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._min_interval = min_interval_s
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()
        self._client = httpx.Client(
            timeout=timeout_s,
            follow_redirects=False,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json, text/csv, application/xml, */*",
                "Accept-Language": "en-IN,en;q=0.9",
                "Referer": "https://www.nseindia.com/",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, url: str, *, max_age_s: float | None = None) -> Fetched:
        """Fetch `url`. `max_age_s=None` caches forever; 0 disables the cache."""
        host = _checked_host(url)
        cache_file = self._cache_dir / hashlib.sha256(url.encode()).hexdigest()
        cached = self._read_cache(cache_file, max_age_s)
        if cached is not None:
            return Fetched(url, cached[0], cached[1], from_cache=True)

        response = self._request_with_retry(url, host)
        content = response.content
        retrieved_at = datetime.now(UTC)
        if max_age_s != 0:
            cache_file.write_bytes(content)
        return Fetched(url, content, retrieved_at, from_cache=False)

    def _request_with_retry(self, url: str, host: str) -> httpx.Response:
        last_error: FetchError | None = None
        for attempt in range(3):
            self._pace(host)
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = FetchError(url, f"network error: {exc.__class__.__name__}")
                time.sleep(2**attempt)
                continue
            if response.status_code == 404:
                raise NotFoundError(url, "not found", 404)
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = FetchError(url, f"HTTP {response.status_code}", response.status_code)
                time.sleep(3 * (attempt + 1))
                continue
            if response.status_code >= 300:
                raise FetchError(url, f"HTTP {response.status_code}", response.status_code)
            if len(response.content) > _MAX_BYTES:
                raise FetchError(url, "response exceeds size limit")
            return response
        assert last_error is not None
        raise last_error

    def _pace(self, host: str) -> None:
        interval = max(self._min_interval, _HOST_MIN_INTERVAL.get(host, 0.0))
        with self._lock:
            wait = self._last_request.get(host, 0.0) + interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request[host] = time.monotonic()

    @staticmethod
    def _read_cache(path: Path, max_age_s: float | None) -> tuple[bytes, datetime] | None:
        if max_age_s == 0 or not path.exists():
            return None
        modified = path.stat().st_mtime
        if max_age_s is not None and time.time() - modified > max_age_s:
            return None
        return path.read_bytes(), datetime.fromtimestamp(modified, UTC)


def _checked_host(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise FetchError(url, "host is not on the retrieval allowlist")
    return parts.hostname
