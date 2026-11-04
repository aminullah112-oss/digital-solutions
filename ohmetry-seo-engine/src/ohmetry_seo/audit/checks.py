"""Turn a CrawlResult into an evidence-backed issue register."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..crawler import CrawlResult, PageRecord
from ..urls import host_of
from .catalog import CATALOG
from .duplicates import find_exact_duplicates, find_near_duplicates
from .links import LinkStats, build_link_stats
from .structured_data import validate_jsonld


@dataclass
class Issue:
    code: str
    url: str
    evidence: str
    severity: str = ""
    category: str = ""

    def __post_init__(self):
        t = CATALOG[self.code]
        self.severity = self.severity or t.severity
        self.category = t.category


@dataclass
class AuditResult:
    issues: list[Issue] = field(default_factory=list)
    links: LinkStats | None = None
    exact_duplicates: list[list[str]] = field(default_factory=list)
    near_duplicates: list[tuple[str, str, float]] = field(default_factory=list)
    structured_data: dict[str, list[dict]] = field(default_factory=dict)  # url -> findings
    audited_pages: list[str] = field(default_factory=list)  # indexable HTML pages checked on-page

    def by_code(self) -> dict[str, list[Issue]]:
        out: dict[str, list[Issue]] = defaultdict(list)
        for i in self.issues:
            out[i.code].append(i)
        return out

    def for_url(self, url: str) -> list[Issue]:
        return [i for i in self.issues if i.url == url]


def run_audit(crawl: CrawlResult, cfg: dict) -> AuditResult:
    acfg = cfg.get("audit", {})
    res = AuditResult()
    add = lambda code, url, evidence, severity="": res.issues.append(Issue(code, url, evidence, severity))  # noqa: E731
    pages = crawl.pages
    internal = [p for p in pages.values() if p.fetched]
    indexable = [p for p in internal if p.indexable]
    res.audited_pages = [p.url for p in indexable]
    preferred_host = host_of(crawl.start_url)

    # --- site level -------------------------------------------------------
    robots = crawl.robots
    if robots and robots.mode == "disallow_all":
        add("ROBOTS_UNREACHABLE", robots.url, f"status={robots.status} error={robots.error}")
    for v in crawl.host_variants:
        if not v["ok"]:
            add("HOST_VARIANT_NOT_REDIRECTED", v["url"],
                f"status={v['status']} hops={v['hops']} final={v['final_url']} error={v['error']}")
    sm = crawl.sitemaps
    if sm is not None:
        ok = [f for f in sm.fetched if not f["error"]]
        for f in sm.fetched:
            # A missing default /sitemap.xml is only a problem if no other sitemap worked.
            if f["error"] and (ok and f["status"] == 404 and f["url"].endswith("/sitemap.xml")):
                continue
            if f["error"] and ok:
                add("SITEMAP_ERROR", f["url"], f["error"])
        if not ok:
            add("SITEMAP_MISSING", crawl.start_url, "; ".join(f"{f['url']}: {f['error']}" for f in sm.fetched) or "none tried")

    # --- per URL: HTTP / indexability --------------------------------------
    for p in internal:
        chain = p.redirect_chain
        if p.fetch_error == "redirect loop":
            add("REDIRECT_LOOP", p.url, " -> ".join(u for u, _ in chain))
        elif p.fetch_error and not chain:
            add("FETCH_ERROR", p.url, p.fetch_error)
        if len(chain) > 1 and p.fetch_error != "redirect loop":
            add("REDIRECT_CHAIN", p.url, " -> ".join(f"{u} [{s}]" for u, s in chain) + f" -> {p.final_url}")
        if p.status and p.status >= 500:
            add("HTTP_5XX", p.url, f"HTTP {p.status}")
        elif p.status and 400 <= p.status < 500:
            add("HTTP_4XX", p.url, f"HTTP {p.status} (discovered via {p.discovered_via})")
        if p.in_sitemap:
            if p.status != 200 or chain:
                add("SITEMAP_URL_NOT_200", p.url, f"HTTP {p.status}" + (f", redirects to {p.final_url}" if chain else ""))
            elif p.noindex:
                add("NOINDEX_IN_SITEMAP", p.url, p.indexability_reason())
            elif p.canonical and p.canonical != p.url:
                add("SITEMAP_URL_NOT_CANONICAL", p.url, f"canonical={p.canonical}")
        elif p.noindex and p.is_html_200:
            add("NOINDEX", p.url, p.indexability_reason())
        if p.is_html_200 and p.data.soft_404_signal:
            add("SOFT_404", p.url, f"title={p.data.title!r} h1={p.data.h1[:1]}")

    for p in pages.values():
        if not p.robots_allowed and p.in_sitemap:
            add("BLOCKED_BY_ROBOTS_IN_SITEMAP", p.url, "Disallowed for Googlebot or our user agent")

    # --- canonical --------------------------------------------------------
    for p in internal:
        if not p.is_html_200:
            continue
        canons = list(dict.fromkeys(p.data.canonicals))
        if len(canons) > 1:
            add("CANONICAL_MULTIPLE", p.url, " | ".join(canons))
        if not canons:
            if not p.noindex:
                add("CANONICAL_MISSING", p.url, "no <link rel=canonical>")
            continue
        target_url = canons[0]
        if target_url == p.url:
            continue
        if host_of(target_url) != preferred_host and host_of(target_url) not in {h.lower() for h in cfg["site"]["allowed_hosts"]}:
            add("CANONICAL_EXTERNAL_HOST", p.url, f"canonical={target_url}")
            continue
        target = pages.get(target_url)
        if target is not None and target.fetched and (not target.is_html_200 or target.noindex):
            add("CANONICAL_TO_NON_INDEXABLE", p.url, f"canonical={target_url} ({target.indexability_reason()})")
        else:
            add("CANONICAL_CROSS_PAGE", p.url, f"canonical={target_url}")

    # --- sitemap coverage -------------------------------------------------
    if sm is not None and any(not f["error"] for f in sm.fetched):
        for p in indexable:
            if not p.in_sitemap:
                add("NOT_IN_SITEMAP", p.url, f"discovered via {p.discovered_via}")

    # --- on-page (indexable pages only) -------------------------------------
    tmin, tmax = int(acfg.get("title_min_chars", 15)), int(acfg.get("title_max_chars", 60))
    dmin, dmax = int(acfg.get("meta_description_min_chars", 50)), int(acfg.get("meta_description_max_chars", 160))
    titles, descs = defaultdict(list), defaultdict(list)
    for p in indexable:
        d = p.data
        if not d.titles or not d.title:
            add("TITLE_MISSING", p.url, "no <title> or empty title")
        else:
            if len(d.titles) > 1:
                add("TITLE_MULTIPLE", p.url, " | ".join(d.titles))
            titles[d.title.strip().lower()].append(p.url)
            if len(d.title) > tmax:
                add("TITLE_TOO_LONG", p.url, f"{len(d.title)} chars: {d.title!r}")
            elif len(d.title) < tmin:
                add("TITLE_TOO_SHORT", p.url, f"{len(d.title)} chars: {d.title!r}")
        if not d.meta_description:
            add("META_DESC_MISSING", p.url, "no meta description")
        else:
            descs[d.meta_description.strip().lower()].append(p.url)
            n = len(d.meta_description)
            if n < dmin or n > dmax:
                add("META_DESC_LENGTH", p.url, f"{n} chars")
        if not d.h1:
            add("H1_MISSING", p.url, "no <h1>")
        elif len(d.h1) > 1:
            add("H1_MULTIPLE", p.url, " | ".join(d.h1))
        prev = 0
        for level, text in d.headings:
            if prev and level > prev + 1:
                add("HEADING_LEVEL_SKIP", p.url, f"H{prev} -> H{level} at {text[:60]!r}")
                break
            prev = level
        missing_alt = [i.src for i in d.images if i.alt is None]
        if missing_alt:
            add("IMG_ALT_MISSING", p.url, f"{len(missing_alt)} of {len(d.images)} images; e.g. {missing_alt[:3]}")
        no_dims = [i.src for i in d.images if not i.has_dimensions]
        if no_dims:
            add("IMG_NO_DIMENSIONS", p.url, f"{len(no_dims)} of {len(d.images)} images")
        if not d.lang:
            add("LANG_MISSING", p.url, "<html> has no lang attribute")
        if not d.viewport:
            add("VIEWPORT_MISSING", p.url, "no meta viewport")
        if d.likely_js_shell:
            add("JS_DEPENDENT_CONTENT", p.url, f"{d.word_count} words in raw HTML, {d.script_count} scripts")
        elif d.word_count < int(acfg.get("low_word_count", 150)):
            add("LOW_TEXT_CONTENT", p.url, f"{d.word_count} words of main content in raw HTML")

        # structured data
        findings = []
        for block in d.jsonld:
            if block.error:
                add("STRUCTURED_DATA_INVALID_JSON", p.url, block.error)
                continue
            findings.extend(validate_jsonld(block.data))
        res.structured_data[p.url] = findings
        req = [f for f in findings if f["kind"] == "missing_required"]
        rec = [f for f in findings if f["kind"] == "missing_recommended"]
        if req:
            add("STRUCTURED_DATA_MISSING_PROPERTY", p.url, "required: " + ", ".join(f"{f['type']}.{f['detail']}" for f in req))
        elif rec:
            add("STRUCTURED_DATA_MISSING_PROPERTY", p.url,
                "recommended: " + ", ".join(f"{f['type']}.{f['detail']}" for f in rec), severity="low")
        for f in findings:
            if f["kind"] == "restricted":
                add("STRUCTURED_DATA_RESTRICTED_TYPE", p.url, f"{f['type']}: {f['detail']}")
        if not d.jsonld and not d.has_microdata:
            add("STRUCTURED_DATA_NONE", p.url, "no JSON-LD or microdata")

    for _, urls in titles.items():
        if len(urls) > 1:
            for u in urls:
                add("TITLE_DUPLICATE", u, f"same title as {len(urls) - 1} other page(s): {[x for x in urls if x != u][:3]}")
    for _, urls in descs.items():
        if len(urls) > 1:
            for u in urls:
                add("META_DESC_DUPLICATE", u, f"same description as {len(urls) - 1} other page(s): {[x for x in urls if x != u][:3]}")

    # --- duplicates -------------------------------------------------------
    res.exact_duplicates = find_exact_duplicates(indexable)
    for group in res.exact_duplicates:
        for u in group:
            add("EXACT_DUPLICATE_CONTENT", u, f"identical main text to {[x for x in group if x != u][:3]}")
    res.near_duplicates = find_near_duplicates(indexable, float(acfg.get("near_duplicate_threshold", 0.9)), res.exact_duplicates)
    for a, b, score in res.near_duplicates:
        add("NEAR_DUPLICATE_CONTENT", a, f"{score:.0%} shingle overlap with {b}")
        add("NEAR_DUPLICATE_CONTENT", b, f"{score:.0%} shingle overlap with {a}")

    # --- links ------------------------------------------------------------
    generic = {a.lower() for a in acfg.get("generic_anchors", [])}
    res.links = links = build_link_stats(crawl, generic)
    home = crawl.start_url
    for p in indexable:
        if p.url == home:
            continue
        n = links.inbound_count(p.url)
        if n == 0:
            add("ORPHAN_PAGE", p.url, f"0 internal pages link here (found via {p.discovered_via})")
        elif n == 1:
            add("LOW_INBOUND_LINKS", p.url, f"only linked from {next(iter(links.inbound_pages[p.url]))}")
    broken_by_source: dict[str, list[str]] = defaultdict(list)
    for src, tgt, status, anchor in links.broken:
        broken_by_source[src].append(f"{tgt} [{status or 'error'}] anchor={anchor[:40]!r}")
    for src, items in broken_by_source.items():
        add("BROKEN_INTERNAL_LINK", src, f"{len(items)} broken: " + "; ".join(items[:5]))
    redir_by_source: dict[str, list[str]] = defaultdict(list)
    for src, tgt, final in links.to_redirect:
        redir_by_source[src].append(f"{tgt} -> {final}")
    for src, items in redir_by_source.items():
        add("INTERNAL_LINK_TO_REDIRECT", src, f"{len(items)} link(s): " + "; ".join(items[:5]))
    generic_by_source: dict[str, int] = defaultdict(int)
    for src, _, _ in links.generic_anchor_links:
        generic_by_source[src] += 1
    for src, n in generic_by_source.items():
        add("GENERIC_ANCHOR_TEXT", src, f"{n} link(s) with generic anchors")

    return res
