"""URL normalisation, internal/external classification and crawl-trap filters."""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

DEFAULT_PORTS = {"http": 80, "https": 443}


def normalise(url: str, base: str | None = None, strip_params: set[str] | None = None) -> str | None:
    """Return a canonical form of ``url`` for de-duplication, or None if not http(s).

    - resolves relative URLs against ``base``
    - lowercases scheme and host, drops default ports and fragments
    - collapses repeated slashes in the path
    - drops tracking parameters and sorts the rest
    Trailing slashes are preserved: /a and /a/ can be different resources and
    the audit needs to see both if the site links to both.
    """
    if url is None:
        return None
    url = url.strip()
    if not url or url.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
        return None
    if base:
        url = urljoin(base, url)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        return None
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return None
    netloc = host if port in (None, DEFAULT_PORTS[scheme]) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    strip = {p.lower() for p in (strip_params or set())}
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in strip]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_internal(url: str, allowed_hosts: set[str]) -> bool:
    return host_of(url) in allowed_hosts


def has_skipped_extension(url: str, skip_extensions: set[str]) -> bool:
    path = unquote(urlsplit(url).path).lower()
    return any(path.endswith(ext) for ext in skip_extensions)


def trap_reason(url: str, crawler_cfg: dict) -> str | None:
    """Return why a URL should not be fetched, or None if it is crawlable."""
    parts = urlsplit(url)
    max_params = int(crawler_cfg.get("max_query_params", 2))
    if parts.query and len(parse_qsl(parts.query, keep_blank_values=True)) > max_params:
        return f"more than {max_params} query parameters"
    segments = [s for s in parts.path.split("/") if s]
    if segments:
        most_common = Counter(segments).most_common(1)[0][1]
        if most_common > int(crawler_cfg.get("max_repeated_segments", 3)):
            return "repeated path segments (possible crawl trap)"
    if len(url) > 2000:
        return "URL longer than 2000 characters"
    for pattern in crawler_cfg.get("exclude_patterns", []) or []:
        if re.search(pattern, url):
            return f"matches exclude pattern {pattern!r}"
    return None
