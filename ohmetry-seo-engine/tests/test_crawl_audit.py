"""End-to-end: crawl the local fixture site and check the audit finds the planted defects."""

import csv

from ohmetry_seo.audit import run_audit
from ohmetry_seo.cli import main
from ohmetry_seo.crawler import Crawler
from ohmetry_seo.fetcher import Fetcher
from ohmetry_seo.reports import write_reports
from ohmetry_seo.scoring import build_recommendations


def _crawl(cfg):
    crawl = Crawler(cfg).run()
    return crawl, run_audit(crawl, cfg)


def codes_for(audit, url):
    return {i.code for i in audit.for_url(url)}


def test_crawl_discovers_and_respects_robots(site, site_cfg):
    base, handler = site
    crawl, _ = _crawl(site_cfg)
    pages = crawl.pages
    assert f"{base}/" in pages and pages[f"{base}/"].indexable
    assert f"{base}/orphan-guide" in pages  # sitemap-only discovery
    secret = pages[f"{base}/private/secret"]
    assert secret.robots_allowed is False and secret.status is None
    assert not any(h.startswith("/private/") for h in handler.hits)  # never requested
    assert pages[f"{base}/calculators/three-phase-power"].in_sitemap
    # utm param stripped: no separate tracked URL
    assert not any("utm_source" in u for u in pages)
    assert "https://external.example/" not in pages  # external links are recorded, never queued
    assert any(e.target == "https://external.example/" and not e.internal for e in crawl.edges)
    assert not any("external.example" in h for h in handler.hits)


def test_redirect_chain_recorded(site, site_cfg):
    base, _ = site
    crawl, audit = _crawl(site_cfg)
    old = crawl.pages[f"{base}/old-page"]
    assert [s for _, s in old.redirect_chain] == [301, 301]
    assert old.final_url == f"{base}/calculators/three-phase-power"
    assert "REDIRECT_CHAIN" in codes_for(audit, f"{base}/old-page")
    assert "SITEMAP_URL_NOT_200" in codes_for(audit, f"{base}/old-page")
    assert "INTERNAL_LINK_TO_REDIRECT" in codes_for(audit, f"{base}/")


def test_audit_finds_planted_defects(site, site_cfg):
    base, _ = site
    _, audit = _crawl(site_cfg)
    assert "HTTP_4XX" in codes_for(audit, f"{base}/gone")
    assert "BROKEN_INTERNAL_LINK" in codes_for(audit, f"{base}/")
    assert "GENERIC_ANCHOR_TEXT" in codes_for(audit, f"{base}/")
    assert "IMG_ALT_MISSING" in codes_for(audit, f"{base}/")
    assert "NOINDEX_IN_SITEMAP" in codes_for(audit, f"{base}/noindexed")
    assert "BLOCKED_BY_ROBOTS_IN_SITEMAP" in codes_for(audit, f"{base}/private/secret")
    assert "ORPHAN_PAGE" in codes_for(audit, f"{base}/orphan-guide")
    assert {"H1_MULTIPLE", "STRUCTURED_DATA_INVALID_JSON"} <= codes_for(audit, f"{base}/guides/voltage-drop")
    assert "HEADING_LEVEL_SKIP" in codes_for(audit, f"{base}/calculators/three-phase-power")
    no_meta = codes_for(audit, f"{base}/no-meta")
    assert {"TITLE_MISSING", "META_DESC_MISSING", "H1_MISSING", "LANG_MISSING", "VIEWPORT_MISSING",
            "CANONICAL_MISSING", "NOT_IN_SITEMAP"} <= no_meta
    assert "JS_DEPENDENT_CONTENT" in codes_for(audit, f"{base}/spa")
    # dup-b canonicalises to dup-a: not indexable itself, flagged in sitemap
    assert "SITEMAP_URL_NOT_CANONICAL" in codes_for(audit, f"{base}/dup-b")
    # breadcrumb on calculator page has a valid structure (last item has no URL; allowed)
    assert "STRUCTURED_DATA_MISSING_PROPERTY" not in codes_for(audit, f"{base}/calculators/three-phase-power")
    # Organization in the home @graph lacks url
    assert "STRUCTURED_DATA_MISSING_PROPERTY" in codes_for(audit, f"{base}/")


def test_no_false_positives_on_clean_page(site, site_cfg):
    base, _ = site
    _, audit = _crawl(site_cfg)
    clean = codes_for(audit, f"{base}/calculators/three-phase-power")
    for code in ("TITLE_MISSING", "H1_MISSING", "CANONICAL_MISSING", "ORPHAN_PAGE", "VIEWPORT_MISSING", "HTTP_4XX"):
        assert code not in clean


def test_max_pages_limit(site, site_cfg):
    site_cfg["crawler"]["max_pages"] = 3
    crawl = Crawler(site_cfg).run()
    fetched_pages = [p for p in crawl.pages.values() if p.fetched and p.discovered_via != "redirect"]
    assert len(fetched_pages) == 3 and crawl.hit_page_limit


def test_rate_limit_is_applied(site, site_cfg):
    import time
    base, _ = site
    f = Fetcher("TestBot", delay_seconds=0.2, retries=0)
    t = time.monotonic()
    for _ in range(3):
        f.get(f"{base}/")
    assert time.monotonic() - t >= 0.4


def test_reports_written_and_scored(site, site_cfg, tmp_path):
    crawl, audit = _crawl(site_cfg)
    recs = build_recommendations(audit, site_cfg)
    assert recs and all(recs[i].pclass <= recs[i + 1].pclass for i in range(len(recs) - 1))
    assert all(set(r.components) == {"impact", "relevance", "confidence", "reach", "effort", "risk"} for r in recs)
    written = write_reports(tmp_path, crawl, audit, recs)
    names = {p.name for p in written}
    for required in ("baseline-summary.md", "url-inventory.csv", "technical-audit.csv", "indexability-report.csv",
                     "metadata-report.csv", "internal-link-report.csv", "structured-data-report.csv",
                     "performance-baseline.csv", "priority-action-plan.md"):
        assert required in names
    summary = (tmp_path / "baseline-summary.md").read_text()
    assert "unconfigured" in summary  # no fake GSC/PSI numbers
    with (tmp_path / "url-inventory.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert all(r["gsc_clicks"] == "" for r in rows)
    with (tmp_path / "performance-baseline.csv").open() as fh:
        assert len(list(csv.reader(fh))) == 1  # header only, nothing invented


def test_cli_end_to_end(site, tmp_path, monkeypatch):
    base, _ = site
    import shutil
    from pathlib import Path
    cfg_dir = tmp_path / "config"
    shutil.copytree(Path(__file__).resolve().parents[1] / "config", cfg_dir)
    (cfg_dir / "site.yaml").write_text(f"site:\n  start_url: {base}/\n  allowed_hosts: ['127.0.0.1']\n")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    assert main(["audit", "--config", str(cfg_dir), "--out", str(out), "--delay", "0"]) == 0
    assert (out / "priority-action-plan.md").exists()
    assert list((tmp_path / "data" / "snapshots").glob("crawl-*.json"))
