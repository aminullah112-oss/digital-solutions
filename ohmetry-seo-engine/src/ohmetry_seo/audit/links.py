"""Internal link graph: inbound/outbound counts, orphans, broken and redirecting links."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..crawler import CrawlResult


@dataclass
class LinkStats:
    inbound_pages: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    outbound_internal: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    outbound_external: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    anchors: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    broken: list[tuple[str, str, int | None, str]] = field(default_factory=list)  # source, target, status, anchor
    to_redirect: list[tuple[str, str, str]] = field(default_factory=list)  # source, target, final
    generic_anchor_links: list[tuple[str, str, str]] = field(default_factory=list)
    external_links: list[tuple[str, str]] = field(default_factory=list)

    def inbound_count(self, url: str) -> int:
        return len(self.inbound_pages.get(url, ()))


def build_link_stats(crawl: CrawlResult, generic_anchors: set[str]) -> LinkStats:
    stats = LinkStats()
    pages = crawl.pages
    seen_edges: set[tuple[str, str]] = set()
    for e in crawl.edges:
        if not e.internal:
            stats.outbound_external[e.source] += 1
            stats.external_links.append((e.source, e.target))
            continue
        if e.source == e.target:
            continue
        stats.outbound_internal[e.source] += 1
        stats.anchors[e.target].append(e.anchor)
        stats.inbound_pages[e.target].add(e.source)
        if e.anchor.strip().lower() in generic_anchors:
            stats.generic_anchor_links.append((e.source, e.target, e.anchor))
        if (e.source, e.target) in seen_edges:
            continue
        seen_edges.add((e.source, e.target))
        target = pages.get(e.target)
        if target is None or not target.fetched:
            continue
        if target.fetch_error and not target.is_redirect:
            stats.broken.append((e.source, e.target, None, e.anchor))
        elif target.is_redirect:
            if target.status and target.status >= 400:
                stats.broken.append((e.source, e.target, target.status, e.anchor))
            else:
                stats.to_redirect.append((e.source, e.target, target.final_url or ""))
        elif target.status and target.status >= 400:
            stats.broken.append((e.source, e.target, target.status, e.anchor))
    return stats
