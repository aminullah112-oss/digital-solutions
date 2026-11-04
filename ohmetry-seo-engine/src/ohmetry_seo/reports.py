"""Write the Phase 1 baseline report set (CSV + JSON + Markdown)."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .audit.catalog import CATALOG
from .audit.checks import AuditResult
from .crawler import CrawlResult, PageRecord
from .gsc import POSITION_CAVEAT, GscDataset, page_metrics, segment_pages
from .scoring import SEVERITY_ORDER, Recommendation


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def page_type(url: str) -> str:
    """Rough template guess from the URL path. Refine once the real URL patterns are known."""
    path = urlsplit(url).path.lower().strip("/")
    if not path:
        return "home"
    first = path.split("/")[0]
    if "calculator" in path or first in ("calculators", "calculator", "tools", "tool"):
        return "calculator"
    if first in ("guides", "guide", "blog", "articles", "learn", "resources", "reference"):
        return "guide"
    if first in ("about", "contact", "privacy", "privacy-policy", "terms", "disclaimer"):
        return "info"
    if first in ("category", "categories", "topics", "tag"):
        return "category"
    return "other"


def _issue_summary(audit: AuditResult, url: str) -> str:
    return "; ".join(sorted({i.code for i in audit.for_url(url)}))


def _priority_for(audit: AuditResult, url: str) -> str:
    codes = {i.code for i in audit.for_url(url)}
    if not codes:
        return ""
    return min((CATALOG[c].pclass for c in codes), key=lambda p: int(p[1]))


def write_reports(out_dir: Path, crawl: CrawlResult, audit: AuditResult, recs: list[Recommendation],
                  gsc: list[GscDataset] | None = None, psi_rows: list[dict] | None = None,
                  psi_status: str = "unconfigured", gsc_status: str = "unconfigured") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    pages = sorted(crawl.pages.values(), key=lambda p: (p.depth, p.url))
    crawled = [p for p in pages if p.fetched or not p.robots_allowed]
    links = audit.links
    gsc_pages = page_metrics(gsc or [])

    # url-inventory.csv ------------------------------------------------------
    header = ["url", "http_status", "final_url", "redirect_hops", "indexable", "indexability_reason", "canonical",
              "meta_robots", "x_robots_tag", "page_type", "title", "title_chars", "meta_description", "meta_description_chars",
              "h1", "h2_headings", "word_count_diagnostic", "structured_data_types", "internal_inbound_pages",
              "internal_outbound_links", "external_outbound_links", "images", "images_missing_alt", "in_sitemap",
              "sitemap_lastmod", "last_modified_header", "depth", "discovered_via", "response_ms",
              "gsc_clicks", "gsc_impressions", "gsc_ctr", "gsc_avg_position", "issues", "priority"]
    rows = []
    for p in crawled:
        d = p.data
        g = gsc_pages.get(p.url, {})
        rows.append([
            p.url, p.status, p.final_url if p.is_redirect else "", len(p.redirect_chain), p.indexable,
            p.indexability_reason(), p.canonical or "", ",".join(d.meta_robots) if d else "", ",".join(p.x_robots_tag),
            page_type(p.url), d.title if d else "", len(d.title or "") if d else "", d.meta_description if d else "",
            len(d.meta_description or "") if d else "", " | ".join(d.h1) if d else "", " | ".join(d.h2[:15]) if d else "",
            d.word_count if d else "", ",".join(d.structured_data_types) if d else "",
            links.inbound_count(p.url) if links else "", links.outbound_internal.get(p.url, 0) if links else "",
            links.outbound_external.get(p.url, 0) if links else "", len(d.images) if d else "",
            sum(1 for i in d.images if i.alt is None) if d else "", p.in_sitemap, p.sitemap_lastmod or "",
            p.last_modified_header or "", p.depth, p.discovered_via, p.elapsed_ms,
            g.get("clicks", ""), g.get("impressions", ""), g.get("ctr", ""), g.get("position", ""),
            _issue_summary(audit, p.url), _priority_for(audit, p.url),
        ])
    _write_csv(out_dir / "url-inventory.csv", header, rows)
    written.append(out_dir / "url-inventory.csv")

    # technical-audit.csv (issue register) -----------------------------------
    sev_rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    issue_rows = sorted(audit.issues, key=lambda i: (sev_rank[i.severity], i.code, i.url))
    _write_csv(out_dir / "technical-audit.csv",
               ["severity", "priority_class", "code", "category", "title", "url", "evidence", "recommended_remediation"],
               [[i.severity, CATALOG[i.code].pclass, i.code, i.category, CATALOG[i.code].title, i.url, i.evidence,
                 CATALOG[i.code].action] for i in issue_rows])
    written.append(out_dir / "technical-audit.csv")
    (out_dir / "technical-audit.json").write_text(json.dumps([asdict(i) for i in issue_rows], indent=2), encoding="utf-8")
    written.append(out_dir / "technical-audit.json")

    # indexability-report.csv -------------------------------------------------
    _write_csv(out_dir / "indexability-report.csv",
               ["url", "http_status", "robots_txt_allowed", "meta_robots", "x_robots_tag", "canonical",
                "canonical_is_self", "in_sitemap", "indexable", "reason"],
               [[p.url, p.status, p.robots_allowed, ",".join(p.data.meta_robots) if p.data else "",
                 ",".join(p.x_robots_tag), p.canonical or "", (p.canonical in (None, p.url)) if p.data else "",
                 p.in_sitemap, p.indexable, p.indexability_reason()] for p in crawled])
    written.append(out_dir / "indexability-report.csv")

    # metadata-report.csv ------------------------------------------------------
    html_pages = [p for p in crawled if p.is_html_200]
    _write_csv(out_dir / "metadata-report.csv",
               ["url", "indexable", "title", "title_chars", "title_count", "meta_description", "meta_description_chars",
                "h1_count", "h1", "lang", "viewport", "hreflang_count"],
               [[p.url, p.indexable, p.data.title or "", len(p.data.title or ""), len(p.data.titles),
                 p.data.meta_description or "", len(p.data.meta_description or ""), len(p.data.h1),
                 " | ".join(p.data.h1), p.data.lang or "", bool(p.data.viewport), len(p.data.hreflang)] for p in html_pages])
    written.append(out_dir / "metadata-report.csv")

    # internal-link-report.csv -------------------------------------------------
    link_rows = []
    if links:
        for p in html_pages:
            anchors = Counter(a for a in links.anchors.get(p.url, []) if a)
            link_rows.append([p.url, p.indexable, links.inbound_count(p.url), links.outbound_internal.get(p.url, 0),
                              links.outbound_external.get(p.url, 0), p.depth,
                              "; ".join(f"{a} ({n})" for a, n in anchors.most_common(5))])
    _write_csv(out_dir / "internal-link-report.csv",
               ["url", "indexable", "inbound_internal_pages", "outbound_internal_links", "outbound_external_links",
                "click_depth_from_seed", "top_inbound_anchors"], link_rows)
    written.append(out_dir / "internal-link-report.csv")
    if links and links.broken:
        _write_csv(out_dir / "broken-internal-links.csv", ["source", "target", "status", "anchor"],
                   [list(b) for b in links.broken])
        written.append(out_dir / "broken-internal-links.csv")

    # structured-data-report.csv -----------------------------------------------
    sd_rows = []
    for p in html_pages:
        errs = [b.error for b in p.data.jsonld if b.error]
        f = audit.structured_data.get(p.url, [])
        sd_rows.append([p.url, len(p.data.jsonld), ",".join(p.data.structured_data_types), p.data.has_microdata,
                        "; ".join(errs),
                        "; ".join(f"{x['type']}.{x['detail']}" for x in f if x["kind"] == "missing_required"),
                        "; ".join(f"{x['type']}.{x['detail']}" for x in f if x["kind"] == "missing_recommended"),
                        "; ".join(f"{x['type']}" for x in f if x["kind"] == "restricted")])
    _write_csv(out_dir / "structured-data-report.csv",
               ["url", "jsonld_blocks", "types", "has_microdata", "json_errors", "missing_required",
                "missing_recommended", "restricted_types"], sd_rows)
    written.append(out_dir / "structured-data-report.csv")

    # performance-baseline.csv -------------------------------------------------
    psi_header = ["url", "strategy", "tested_at", "field_data_scope", "field_LCP_ms", "field_LCP_ms_rating",
                  "field_INP_ms", "field_INP_ms_rating", "field_CLS", "field_CLS_rating", "lab_performance_score",
                  "lab_LCP_ms", "lab_CLS", "lab_TBT_ms", "lab_FCP_ms", "lab_SpeedIndex_ms", "lab_opportunities",
                  "lighthouse_version", "error"]
    _write_csv(out_dir / "performance-baseline.csv", psi_header,
               [[r.get(h, "") for h in psi_header] for r in (psi_rows or [])])
    written.append(out_dir / "performance-baseline.csv")

    # priority-action-plan.md ---------------------------------------------------
    (out_dir / "priority-action-plan.md").write_text(_action_plan_md(crawl, recs), encoding="utf-8")
    written.append(out_dir / "priority-action-plan.md")

    # baseline-summary.md --------------------------------------------------------
    (out_dir / "baseline-summary.md").write_text(
        _summary_md(crawl, audit, recs, gsc or [], gsc_pages, psi_rows or [], psi_status, gsc_status), encoding="utf-8")
    written.append(out_dir / "baseline-summary.md")
    return written


def _action_plan_md(crawl: CrawlResult, recs: list[Recommendation]) -> str:
    lines = [f"# Priority action plan — {urlsplit(crawl.start_url).netloc}", "",
             f"Generated from the crawl finished {crawl.finished_at}. Recommendations are grouped by issue type and "
             "sorted by priority class, then score.", "",
             "**Score** is an internal triage number (see `config/scoring.yaml`), not a Google ranking factor. "
             "Every component is shown so a high score can't hide weak evidence. Expected outcomes are hypotheses "
             "to be checked against Search Console after the change, not promises.", "",
             "Nothing here has been applied to the website. Every production change needs owner approval.", ""]
    if not recs:
        lines.append("_No issues detected._")
    lines += ["| # | Class | Score | Issue | URLs | Effort | Risk | Confidence |", "|---|---|---|---|---|---|---|---|"]
    for n, r in enumerate(recs[:20], 1):
        c = r.components
        lines.append(f"| {n} | {r.pclass} | {r.score} | {r.title} (`{r.code}`) | {len(r.affected_urls)} | "
                     f"{c['effort']}/5 | {c['risk']}/5 | {c['confidence']}/5 |")
    lines.append("")
    for n, r in enumerate(recs, 1):
        c = r.components
        lines += [f"## {n}. [{r.pclass}] {r.title}", "",
                  f"- **Code:** `{r.code}` · **Severity:** {r.severity} · **Affected URLs:** {len(r.affected_urls)}",
                  f"- **Score:** {r.score} = impact {c['impact']}, relevance {c['relevance']}, confidence {c['confidence']}, "
                  f"reach {c['reach']}, effort {c['effort']} (inverse), risk {c['risk']} (inverse)",
                  f"- **Why it matters:** {r.why}",
                  f"- **Proposed action:** {r.action}",
                  f"- **Expected outcome:** {r.hypothesis}",
                  f"- **Validation:** {r.validation}",
                  f"- **Rollback:** {r.rollback}"]
        if r.traffic_note:
            lines.append(f"- **Search Console:** {r.traffic_note}")
        lines += ["- **Evidence (sample):**"] + [f"  - `{e[:300]}`" for e in r.evidence_samples]
        lines += ["- **Affected URLs (first 15):**"] + [f"  - {u}" for u in r.affected_urls[:15]]
        if len(r.affected_urls) > 15:
            lines.append(f"  - … {len(r.affected_urls) - 15} more in technical-audit.csv")
        lines.append("")
    return "\n".join(lines)


def _summary_md(crawl, audit, recs, gsc, gsc_pages, psi_rows, psi_status, gsc_status) -> str:
    pages: list[PageRecord] = list(crawl.pages.values())
    fetched = [p for p in pages if p.fetched]
    status = Counter(str(p.status) if p.status else "error" for p in fetched)
    indexable = [p for p in fetched if p.indexable]
    reasons = Counter(p.indexability_category() for p in fetched)
    sev = Counter(i.severity for i in audit.issues)
    sd_types = Counter(t for p in fetched if p.data for t in p.data.structured_data_types)
    ptypes = Counter(page_type(p.url) for p in indexable)
    sm = crawl.sitemaps
    sm_urls = sum(1 for p in pages if p.in_sitemap)
    skipped = Counter(p.skipped_reason for p in pages if p.skipped_reason and p.skipped_reason != "external host")
    L = [f"# SEO baseline summary — {urlsplit(crawl.start_url).netloc}", "",
         f"_ohmetry-seo-engine {__version__}. All figures below come from this run's own crawl unless a source is named._", "",
         "## Crawl", "",
         f"- Start URL: {crawl.start_url}",
         f"- Started / finished (UTC): {crawl.started_at} / {crawl.finished_at}",
         f"- User agent: `{crawl.user_agent}`",
         f"- Limits: {crawl.limits}; HTTP requests made: {crawl.request_count}",
         f"- Page limit reached: {'**yes — inventory is incomplete**' if crawl.hit_page_limit else 'no'}",
         f"- robots.txt: {crawl.robots.url if crawl.robots else '-'} → HTTP {crawl.robots.status if crawl.robots else '-'}, "
         f"mode `{crawl.robots.mode if crawl.robots else '-'}`",
         f"- Sitemaps read: " + (", ".join(f"{f['url']} ({f['kind'] or 'error'}, {f['count']} entries{', ' + f['error'] if f['error'] else ''})"
                                           for f in sm.fetched) if sm else "none"),
         f"- URLs listed in sitemaps: {sm_urls}",
         "",
         "Raw HTML only: the crawler does not execute JavaScript. Pages flagged `JS_DEPENDENT_CONTENT` need checking "
         "in GSC URL Inspection to see what Google renders.", "",
         "## Inventory", "",
         f"- URLs fetched: **{len(fetched)}**; indexable: **{len(indexable)}**",
         "- HTTP status: " + ", ".join(f"{k}: {v}" for k, v in sorted(status.items())),
         "- Indexability: " + ", ".join(f"{k}: {v}" for k, v in reasons.most_common()),
         "- Indexable pages by URL-pattern type (heuristic): " + ", ".join(f"{k}: {v}" for k, v in ptypes.most_common()),
         ]
    if skipped:
        L.append("- Not fetched: " + ", ".join(f"{k}: {v}" for k, v in skipped.most_common()))
    L.append("- Host/protocol variants: " + ("; ".join(
        f"{v['url']} → {v['final_url']} hops={v['hops']} {'OK' if v['ok'] else 'PROBLEM'}" for v in crawl.host_variants)
        or "none checked (start URL is not https and no www/apex alternative is in allowed_hosts)"))
    L += ["", "## Technical issues", "",
          "- By severity: " + ", ".join(f"{s}: {sev.get(s, 0)}" for s in SEVERITY_ORDER),
          f"- Distinct issue types: {len(recs)} (see priority-action-plan.md)",
          f"- Exact-duplicate groups: {len(audit.exact_duplicates)}; near-duplicate pairs: {len(audit.near_duplicates)}",
          f"- Broken internal link instances: {len(audit.links.broken) if audit.links else 0}",
          "- Structured data types found: " + (", ".join(f"{k} ({v})" for k, v in sd_types.most_common()) or "none"),
          "", "### Top 10 actions", ""]
    for n, r in enumerate(recs[:10], 1):
        L.append(f"{n}. **[{r.pclass}] {r.title}** — {len(r.affected_urls)} URL(s), score {r.score}")
    L += ["", "## Search Console", ""]
    if gsc:
        L += [f"- Status: {gsc_status}"]
        for ds in gsc:
            dr = f"{ds.date_range[0]} → {ds.date_range[1]}" if ds.date_range[0] else "date range not supplied"
            tot_c = sum(r.get("clicks") or 0 for r in ds.rows)
            tot_i = sum(r.get("impressions") or 0 for r in ds.rows)
            L.append(f"- `{ds.source}` ({ds.dimension}, {len(ds.rows)} rows, {dr}): {tot_c:,.0f} clicks, "
                     f"{tot_i:,.0f} impressions (row totals; GSC anonymises some queries so query totals undercount)")
        if gsc_pages:
            bands = segment_pages(gsc_pages)
            crawled_set = {p.url for p in fetched}
            missing = [u for u in gsc_pages if u not in crawled_set]
            L += ["", "Prioritisation bands (from the brief; bands, not ranking predictions):", ""]
            L += [f"- {k}: {len(v)}" for k, v in bands.items()]
            if missing:
                L.append(f"- GSC pages not found by the crawl: {len(missing)} (e.g. {missing[:3]}) — check for orphaned or removed URLs")
        L += ["", f"> {POSITION_CAVEAT}"]
    else:
        L.append(f"- Status: **{gsc_status}**. No clicks, impressions, CTR or positions are reported. "
                 "Import an export with `--gsc` or configure the API (see README).")
    L += ["", "## Analytics (GA4)", "", "- Status: **unconfigured** (Phase 3). No session or conversion data reported.",
          "", "## Page experience (PageSpeed Insights)", ""]
    ok_rows = [r for r in psi_rows if not r.get("error")]
    if ok_rows:
        L.append(f"- Status: {psi_status}; {len(ok_rows)} tests ({len(psi_rows) - len(ok_rows)} errors)")
        for metric in ("LCP_ms", "INP_ms", "CLS"):
            ratings = Counter(r.get(f"field_{metric}_rating") for r in ok_rows)
            L.append(f"- Field {metric} ratings: " + ", ".join(f"{k}: {v}" for k, v in ratings.items()))
        L.append("- Field data is CrUX p75 over 28 days; `field_data_scope=origin` means the URL lacked its own data.")
    else:
        L.append(f"- Status: **{psi_status}**. No Core Web Vitals reported.")
    L += ["", "## Known limitations of this baseline", "",
          "- Word counts are diagnostics, never a quality verdict.",
          "- Title/description length checks use characters as a proxy for pixel width.",
          "- Structured-data checks are a subset of Google's rules; confirm with the Rich Results Test.",
          "- Page type is guessed from URL patterns.", ""]
    return "\n".join(L)


def save_snapshot(path: Path, crawl: CrawlResult) -> None:
    """Persist the crawl so later runs can diff against it."""
    data = {
        "start_url": crawl.start_url, "started_at": crawl.started_at, "finished_at": crawl.finished_at,
        "user_agent": crawl.user_agent, "limits": crawl.limits, "host_variants": crawl.host_variants,
        "robots": {"url": crawl.robots.url, "status": crawl.robots.status, "mode": crawl.robots.mode,
                   "sitemaps": crawl.robots.sitemaps} if crawl.robots else None,
        "sitemaps": crawl.sitemaps.fetched if crawl.sitemaps else [],
        "pages": [{**{k: v for k, v in asdict(p).items() if k != "data"},
                   "indexable": p.indexable, "data": p.data.to_dict() if p.data else None}
                  for p in crawl.pages.values() if p.fetched or not p.robots_allowed],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
