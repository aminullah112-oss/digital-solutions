"""Breadth-first crawler seeded from the start URL and XML sitemaps.

Read-only by construction: it only issues GET requests, never submits forms,
never follows links off the allowed hosts, and checks robots.txt before every
fetch.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from .fetcher import Fetcher, FetchResult
from .parser import PageData, parse_page
from .robots import RobotsInfo, fetch_robots
from .sitemap import SitemapResult, collect_sitemaps
from .urls import has_skipped_extension, is_internal, normalise, trap_reason

log = logging.getLogger(__name__)


@dataclass
class PageRecord:
    url: str
    depth: int
    discovered_via: str  # seed | sitemap | link | redirect
    in_sitemap: bool = False
    sitemap_lastmod: str | None = None
    robots_allowed: bool = True
    skipped_reason: str | None = None
    status: int | None = None
    final_url: str | None = None
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)
    content_type: str | None = None
    x_robots_tag: list[str] = field(default_factory=list)
    last_modified_header: str | None = None
    fetch_error: str | None = None
    elapsed_ms: int = 0
    data: PageData | None = None

    @property
    def fetched(self) -> bool:
        return self.status is not None or self.fetch_error is not None

    @property
    def is_redirect(self) -> bool:
        return bool(self.redirect_chain)

    @property
    def is_html_200(self) -> bool:
        return self.status == 200 and not self.is_redirect and self.data is not None

    @property
    def noindex(self) -> bool:
        return ("noindex" in self.x_robots_tag or "none" in self.x_robots_tag
                or bool(self.data and self.data.noindex))

    @property
    def canonical(self) -> str | None:
        return self.data.canonicals[0] if self.data and self.data.canonicals else None

    @property
    def indexable(self) -> bool:
        """Eligible for indexing as itself: 200 HTML, robots-allowed, no noindex,
        canonical absent or self-referencing."""
        if not (self.is_html_200 and self.robots_allowed) or self.noindex:
            return False
        return self.canonical in (None, self.url)

    def indexability_category(self) -> str:
        """Short bucket label for counting (the full reason carries the URLs)."""
        reason = self.indexability_reason()
        for prefix in ("not crawled", "fetch error", "redirects", "canonicalised", "noindex", "non-HTML"):
            if reason.startswith(prefix):
                return prefix
        return reason

    def indexability_reason(self) -> str:
        if self.skipped_reason:
            return f"not crawled: {self.skipped_reason}"
        if not self.robots_allowed:
            return "blocked by robots.txt"
        if self.fetch_error:
            return f"fetch error: {self.fetch_error}"
        if self.is_redirect:
            return f"redirects to {self.final_url}"
        if self.status != 200:
            return f"HTTP {self.status}"
        if self.data is None:
            return f"non-HTML ({self.content_type})"
        if "noindex" in self.x_robots_tag or "none" in self.x_robots_tag:
            return "noindex (X-Robots-Tag header)"
        if self.data.noindex:
            return "noindex (meta robots)"
        if self.canonical and self.canonical != self.url:
            return f"canonicalised to {self.canonical}"
        return "indexable"


@dataclass
class LinkEdge:
    source: str
    target: str
    anchor: str
    nofollow: bool
    internal: bool


@dataclass
class CrawlResult:
    start_url: str
    started_at: str
    finished_at: str = ""
    user_agent: str = ""
    limits: dict = field(default_factory=dict)
    robots: RobotsInfo | None = None
    sitemaps: SitemapResult | None = None
    pages: dict[str, PageRecord] = field(default_factory=dict)
    edges: list[LinkEdge] = field(default_factory=list)
    host_variants: list[dict] = field(default_factory=list)
    hit_page_limit: bool = False
    request_count: int = 0


class Crawler:
    def __init__(self, cfg: dict, fetcher: Fetcher | None = None):
        self.cfg = cfg
        self.site = cfg["site"]
        self.ccfg = cfg.get("crawler", {})
        self.fetcher = fetcher or Fetcher.from_config(self.ccfg)
        self.allowed_hosts = {h.lower() for h in self.site["allowed_hosts"]}
        self.strip_params = set(self.ccfg.get("strip_query_params", []) or [])
        self.skip_ext = set(self.ccfg.get("skip_extensions", []) or [])
        self.max_pages = int(self.ccfg.get("max_pages", 2000))
        self.max_depth = int(self.ccfg.get("max_depth", 10))
        self.follow_nofollow = bool(self.ccfg.get("follow_nofollow", False))
        self.user_agent = self.ccfg.get("user_agent", "OhmetrySEOEngine/0.1")

    def _norm(self, url: str, base: str | None = None) -> str | None:
        return normalise(url, base, self.strip_params)

    def run(self) -> CrawlResult:
        start = self._norm(self.site["start_url"])
        if not start:
            raise ValueError(f"invalid start_url: {self.site['start_url']}")
        result = CrawlResult(start, _now(), user_agent=self.user_agent,
                             limits={"max_pages": self.max_pages, "max_depth": self.max_depth,
                                     "delay_seconds": self.fetcher.delay})

        log.info("fetching robots.txt")
        result.robots = robots = fetch_robots(self.fetcher, start)

        sitemap_urls = list(self.site.get("sitemaps") or []) + robots.sitemaps
        root = urlunsplit((urlsplit(start).scheme, urlsplit(start).netloc, "/sitemap.xml", "", ""))
        if root not in sitemap_urls:
            sitemap_urls.append(root)
        log.info("reading %d sitemap(s)", len(sitemap_urls))
        result.sitemaps = sm = collect_sitemaps(self.fetcher, sitemap_urls)

        sitemap_index: dict[str, str | None] = {}
        for entry in sm.entries:
            u = self._norm(entry.loc)
            if u:
                sitemap_index.setdefault(u, entry.lastmod)

        queue: deque[tuple[str, int, str]] = deque([(start, 0, "seed")])
        queue.extend((u, 0, "sitemap") for u in sitemap_index)
        pages = result.pages
        fetched_count = 0

        while queue:
            url, depth, via = queue.popleft()
            if url in pages:
                continue
            rec = PageRecord(url, depth, via, url in sitemap_index, sitemap_index.get(url))
            pages[url] = rec

            if not is_internal(url, self.allowed_hosts):
                rec.skipped_reason = "external host"
                continue
            if has_skipped_extension(url, self.skip_ext):
                rec.skipped_reason = "non-page file extension"
                continue
            reason = trap_reason(url, self.ccfg)
            if reason:
                rec.skipped_reason = reason
                continue
            if not robots.can_fetch(self.user_agent, url) or not robots.googlebot_allowed(url):
                rec.robots_allowed = False
                continue
            if fetched_count >= self.max_pages:
                rec.skipped_reason = "max_pages reached"
                result.hit_page_limit = True
                continue

            log.info("[%d] %s", fetched_count + 1, url)
            res = self.fetcher.get(url)
            fetched_count += 1
            self._apply(rec, res)

            if rec.is_redirect and rec.final_url:
                target = self._norm(rec.final_url)
                if target and target not in pages and is_internal(target, self.allowed_hosts):
                    # Reuse this response for the target instead of fetching again.
                    trec = PageRecord(target, depth, "redirect", target in sitemap_index, sitemap_index.get(target))
                    trec.robots_allowed = robots.can_fetch(self.user_agent, target)
                    self._apply(trec, FetchResult(target, target, res.status, res.headers, res.body,
                                                  [], res.error, res.elapsed_ms, res.truncated))
                    pages[target] = trec
                    self._enqueue_links(trec, depth, queue, result)
                continue

            self._enqueue_links(rec, depth, queue, result)

        self._check_host_variants(start, result)
        result.finished_at = _now()
        result.request_count = self.fetcher.request_count
        return result

    def _apply(self, rec: PageRecord, res: FetchResult) -> None:
        rec.status, rec.final_url = res.status, res.final_url
        rec.redirect_chain, rec.fetch_error, rec.elapsed_ms = res.redirect_chain, res.error, res.elapsed_ms
        rec.content_type = res.content_type or None
        rec.last_modified_header = res.headers.get("last-modified")
        xrt = res.headers.get("x-robots-tag", "")
        rec.x_robots_tag = [d.strip().lower() for part in xrt.split(",") for d in [part.split(":")[-1]] if d.strip()]
        if res.status == 200 and not res.redirect_chain and res.is_html and res.body:
            rec.data = parse_page(res.body, rec.url, self.strip_params)

    def _enqueue_links(self, rec: PageRecord, depth: int, queue: deque, result: CrawlResult) -> None:
        if not rec.data:
            return
        for link in rec.data.links:
            internal = is_internal(link.url, self.allowed_hosts)
            result.edges.append(LinkEdge(rec.url, link.url, link.anchor, link.nofollow, internal))
            if not internal or link.url in result.pages:
                continue
            if link.nofollow and not self.follow_nofollow:
                continue
            if depth + 1 > self.max_depth:
                continue
            queue.append((link.url, depth + 1, "link"))

    def _check_host_variants(self, start: str, result: CrawlResult) -> None:
        """Check that http:// and the other www/apex host redirect to the preferred origin."""
        parts = urlsplit(start)
        host = parts.hostname or ""
        alt_host = host[4:] if host.startswith("www.") else f"www.{host}"
        variants: set[str] = set()
        if parts.scheme == "https":
            variants.add(urlunsplit(("http", host, "/", "", "")))
        if alt_host in self.allowed_hosts:
            variants.add(urlunsplit((parts.scheme, alt_host, "/", "", "")))
            if parts.scheme == "https":
                variants.add(urlunsplit(("http", alt_host, "/", "", "")))
        preferred_origin = f"{parts.scheme}://{parts.netloc}"
        for v in sorted(variants):
            res = self.fetcher.get(v, read_body=False)
            final = self._norm(res.final_url) or res.final_url
            result.host_variants.append({
                "url": v, "status": res.status, "final_url": final,
                "hops": [s for _, s in res.redirect_chain], "error": res.error,
                "ok": bool(res.redirect_chain) and final.startswith(preferred_origin)
                      and all(s in (301, 308) for _, s in res.redirect_chain),
            })


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
