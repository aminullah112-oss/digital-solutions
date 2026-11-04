"""Rate-limited HTTP fetcher that records every redirect hop."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests

log = logging.getLogger(__name__)

REDIRECT_CODES = {301, 302, 303, 307, 308}
RETRY_STATUSES = {429, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)  # (url, status) per hop
    error: str | None = None
    elapsed_ms: int = 0
    truncated: bool = False

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml")


class Fetcher:
    """Sequential fetcher. One request in flight; ``delay_seconds`` between requests."""

    def __init__(
        self,
        user_agent: str,
        delay_seconds: float = 1.0,
        timeout_seconds: float = 20,
        max_redirects: int = 10,
        retries: int = 2,
        max_body_bytes: int = 5_000_000,
        session: requests.Session | None = None,
    ):
        self.delay = delay_seconds
        self.timeout = timeout_seconds
        self.max_redirects = max_redirects
        self.retries = retries
        self.max_body_bytes = max_body_bytes
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5"})
        self._last_request = 0.0
        self.request_count = 0

    @classmethod
    def from_config(cls, crawler_cfg: dict) -> "Fetcher":
        return cls(
            user_agent=crawler_cfg.get("user_agent", "OhmetrySEOEngine/0.1"),
            delay_seconds=float(crawler_cfg.get("delay_seconds", 1.0)),
            timeout_seconds=float(crawler_cfg.get("timeout_seconds", 20)),
            max_redirects=int(crawler_cfg.get("max_redirects", 10)),
            retries=int(crawler_cfg.get("retries", 2)),
            max_body_bytes=int(crawler_cfg.get("max_body_bytes", 5_000_000)),
        )

    def _throttle(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _request_once(self, url: str) -> requests.Response:
        attempt = 0
        while True:
            self._throttle()
            self.request_count += 1
            try:
                resp = self.session.get(url, allow_redirects=False, timeout=self.timeout, stream=True)
            except requests.RequestException:
                if attempt >= self.retries:
                    raise
                attempt += 1
                time.sleep(min(2 ** attempt, 16))
                continue
            if resp.status_code in RETRY_STATUSES and attempt < self.retries:
                retry_after = resp.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1)
                resp.close()
                attempt += 1
                log.warning("HTTP %s from %s, retrying in %.0fs", resp.status_code, url, min(delay, 60))
                time.sleep(min(delay, 60))
                continue
            return resp

    def get(self, url: str, read_body: bool = True) -> FetchResult:
        chain: list[tuple[str, int]] = []
        seen: set[str] = set()
        current = url
        started = time.monotonic()
        while True:
            if current in seen:
                return FetchResult(url, current, chain[-1][1] if chain else None, redirect_chain=chain,
                                   error="redirect loop", elapsed_ms=_ms(started))
            seen.add(current)
            try:
                resp = self._request_once(current)
            except requests.RequestException as exc:
                return FetchResult(url, current, None, redirect_chain=chain,
                                   error=f"{type(exc).__name__}: {exc}", elapsed_ms=_ms(started))
            headers = {k.lower(): v for k, v in resp.headers.items()}
            if resp.status_code in REDIRECT_CODES and "location" in headers:
                chain.append((current, resp.status_code))
                resp.close()
                if len(chain) > self.max_redirects:
                    return FetchResult(url, current, resp.status_code, headers, redirect_chain=chain,
                                       error=f"more than {self.max_redirects} redirects", elapsed_ms=_ms(started))
                current = urljoin(current, headers["location"])
                continue
            body, truncated = (None, False)
            if read_body:
                body, truncated = self._read_body(resp)
            resp.close()
            return FetchResult(url, current, resp.status_code, headers, body, chain,
                               elapsed_ms=_ms(started), truncated=truncated)

    def _read_body(self, resp: requests.Response) -> tuple[bytes, bool]:
        chunks, size = [], 0
        for chunk in resp.iter_content(65536):
            chunks.append(chunk)
            size += len(chunk)
            if size >= self.max_body_bytes:
                return b"".join(chunks)[: self.max_body_bytes], True
        return b"".join(chunks), False


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
