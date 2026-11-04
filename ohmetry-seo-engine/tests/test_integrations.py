"""GSC and PageSpeed parsing. Fixtures here are synthetic test data, not Ohmetry data."""

import io
import zipfile

import pytest

from ohmetry_seo.gsc import load_gsc_exports, page_metrics, parse_api_rows, parse_gsc_csv, segment_pages
from ohmetry_seo.pagespeed import parse_psi, rate

GSC_PAGES_CSV = """﻿Top pages,Clicks,Impressions,CTR,Position
https://ohmetry.com/calculators/x,12,"1,200",1%,8.4
https://ohmetry.com/guides/y,0,40,0%,35.2
https://ohmetry.com/,300,5000,6%,3.1
"""


def test_parse_gsc_ui_export():
    ds = parse_gsc_csv(GSC_PAGES_CSV, "csv:Pages.csv", "2026-08-01", "2026-10-31")
    assert ds.dimension == "page" and len(ds.rows) == 3
    r = ds.rows[0]
    assert r == {"key": "https://ohmetry.com/calculators/x", "clicks": 12.0, "impressions": 1200.0,
                 "ctr": pytest.approx(0.01), "position": 8.4}
    assert ds.date_range == ("2026-08-01", "2026-10-31")


def test_gsc_missing_date_range_is_flagged():
    assert "Date range not supplied" in parse_gsc_csv(GSC_PAGES_CSV, "csv:x").note


def test_gsc_rejects_unknown_csv():
    with pytest.raises(ValueError):
        parse_gsc_csv("Date,Foo\n2026-01-01,1\n", "csv:Chart.csv")


def test_gsc_zip_import(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Pages.csv", GSC_PAGES_CSV)
        z.writestr("Queries.csv", "Top queries,Clicks,Impressions,CTR,Position\nohms law calculator,5,100,5%,6\n")
        z.writestr("Filters.csv", "Filter,Value\nSearch type,Web\n")
    path = tmp_path / "export.zip"
    path.write_bytes(buf.getvalue())
    sets = load_gsc_exports(path)
    assert sorted(d.dimension for d in sets) == ["page", "query"]
    assert "https://ohmetry.com/" in page_metrics(sets)


def test_gsc_api_rows():
    rows = parse_api_rows([{"keys": ["https://ohmetry.com/a", "mobile"], "clicks": 1, "impressions": 10,
                            "ctr": 0.1, "position": 4.2}], ["page", "device"])
    assert rows[0]["page"] == "https://ohmetry.com/a" and rows[0]["device"] == "mobile" and rows[0]["key"] == rows[0]["page"]


def test_segment_pages():
    m = page_metrics([parse_gsc_csv(GSC_PAGES_CSV, "csv:x")])
    bands = segment_pages(m, min_impressions=100)
    assert "https://ohmetry.com/calculators/x" in bands["striking_distance_4_20"]
    assert "https://ohmetry.com/calculators/x" in bands["high_impr_low_ctr"]
    assert "https://ohmetry.com/guides/y" in bands["no_meaningful_impressions"]
    assert "https://ohmetry.com/" in bands["earning_clicks"]


PSI = {
    "analysisUTCTimestamp": "2026-11-01T00:00:00Z",
    "loadingExperience": {"id": "https://ohmetry.com/", "metrics": {
        "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 3100},
        "INTERACTION_TO_NEXT_PAINT": {"percentile": 150},
        "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 30}}},
    "lighthouseResult": {"lighthouseVersion": "12.0.0",
                         "categories": {"performance": {"score": 0.72}},
                         "audits": {"largest-contentful-paint": {"numericValue": 3500.5},
                                    "total-blocking-time": {"numericValue": 210},
                                    "render-blocking-resources": {"score": 0.3, "details": {"overallSavingsMs": 640}},
                                    "uses-text-compression": {"score": 1}}},
}


def test_parse_psi():
    r = parse_psi(PSI, "https://ohmetry.com/", "mobile")
    assert r["field_data_scope"] == "url"
    assert r["field_LCP_ms"] == 3100 and r["field_LCP_ms_rating"] == "needs improvement"
    assert r["field_INP_ms_rating"] == "good"
    assert r["field_CLS"] == pytest.approx(0.30) and r["field_CLS_rating"] == "poor"
    assert r["lab_performance_score"] == 72
    assert r["lab_opportunities"] == "render-blocking-resources (~640 ms)"


def test_psi_without_field_data():
    r = parse_psi({"loadingExperience": {}, "lighthouseResult": {}}, "u", "desktop")
    assert r["field_data_scope"] == "none" and r["field_LCP_ms_rating"] == "unknown"


def test_rate_thresholds():
    assert rate("LCP_ms", 2500) == "good" and rate("LCP_ms", 4001) == "poor"
    assert rate("CLS", 0.1) == "good" and rate("INP_ms", 300) == "needs improvement"
