"""XML sitemap and sitemap-index parsing (gzip supported, XXE-safe)."""

from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass, field

from lxml import etree

from .fetcher import Fetcher

log = logging.getLogger(__name__)

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, recover=False)


@dataclass
class SitemapEntry:
    loc: str
    lastmod: str | None
    sitemap: str


@dataclass
class SitemapResult:
    entries: list[SitemapEntry] = field(default_factory=list)
    fetched: list[dict] = field(default_factory=list)  # {url, status, kind, count, error}


def parse_sitemap_xml(content: bytes) -> tuple[str, list[tuple[str, str | None]]]:
    """Return (kind, [(loc, lastmod)]) where kind is 'urlset' or 'sitemapindex'."""
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    root = etree.fromstring(content, parser=_PARSER)
    tag = etree.QName(root).localname
    if tag not in ("urlset", "sitemapindex"):
        raise ValueError(f"not a sitemap (root element <{tag}>)")
    child = "url" if tag == "urlset" else "sitemap"
    items = []
    for node in root.iter(f"{NS}{child}", child):
        loc = node.findtext(f"{NS}loc") or node.findtext("loc")
        lastmod = node.findtext(f"{NS}lastmod") or node.findtext("lastmod")
        if loc and loc.strip():
            items.append((loc.strip(), lastmod.strip() if lastmod else None))
    return tag, items


def collect_sitemaps(fetcher: Fetcher, sitemap_urls: list[str], max_sitemaps: int = 100, max_depth: int = 3) -> SitemapResult:
    result = SitemapResult()
    queue = [(u, 0) for u in dict.fromkeys(sitemap_urls)]
    seen: set[str] = set()
    while queue and len(seen) < max_sitemaps:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        res = fetcher.get(url)
        record = {"url": url, "status": res.status, "kind": None, "count": 0, "error": res.error}
        result.fetched.append(record)
        if res.error or res.status != 200 or not res.body:
            record["error"] = record["error"] or f"HTTP {res.status}"
            continue
        try:
            kind, items = parse_sitemap_xml(res.body)
        except (etree.XMLSyntaxError, ValueError, OSError) as exc:
            record["error"] = f"parse error: {exc}"
            continue
        record["kind"], record["count"] = kind, len(items)
        if kind == "sitemapindex":
            if depth < max_depth:
                queue.extend((loc, depth + 1) for loc, _ in items)
        else:
            result.entries.extend(SitemapEntry(loc, lastmod, url) for loc, lastmod in items)
    return result
