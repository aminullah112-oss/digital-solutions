"""PageSpeed Insights API v5: CrUX field data + Lighthouse lab metrics."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import requests

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Core Web Vitals thresholds (web.dev/articles/vitals), evaluated at p75.
THRESHOLDS = {
    "LCP_ms": (2500, 4000),
    "INP_ms": (200, 500),
    "CLS": (0.1, 0.25),
}

FIELD_KEYS = {
    "LARGEST_CONTENTFUL_PAINT_MS": "LCP_ms",
    "INTERACTION_TO_NEXT_PAINT": "INP_ms",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": "CLS",
}
LAB_AUDITS = {
    "largest-contentful-paint": "lab_LCP_ms",
    "cumulative-layout-shift": "lab_CLS",
    "total-blocking-time": "lab_TBT_ms",
    "first-contentful-paint": "lab_FCP_ms",
    "speed-index": "lab_SpeedIndex_ms",
}
OPPORTUNITY_AUDITS = ("render-blocking-resources", "unused-javascript", "unused-css-rules", "uses-optimized-images",
                      "modern-image-formats", "uses-responsive-images", "offscreen-images", "uses-text-compression",
                      "uses-long-cache-ttl", "font-display", "unminified-javascript", "unminified-css")


def rate(metric: str, value: float | None) -> str:
    if value is None or metric not in THRESHOLDS:
        return "unknown"
    good, poor = THRESHOLDS[metric]
    return "good" if value <= good else ("poor" if value > poor else "needs improvement")


def parse_psi(payload: dict, url: str, strategy: str) -> dict:
    row: dict = {"url": url, "strategy": strategy,
                 "tested_at": payload.get("analysisUTCTimestamp") or datetime.now(timezone.utc).isoformat()}
    le = payload.get("loadingExperience") or {}
    metrics = le.get("metrics") or {}
    # CrUX returns URL-level data only when the URL has enough traffic; otherwise
    # PSI falls back to origin-level data (id = origin). Record which one we got.
    row["field_data_scope"] = "none" if not metrics else ("origin" if le.get("origin_fallback") else "url")
    for key, name in FIELD_KEYS.items():
        p = (metrics.get(key) or {}).get("percentile")
        if p is not None and name == "CLS":
            p = p / 100  # CrUX reports CLS ×100
        row[f"field_{name}"] = p
        row[f"field_{name}_rating"] = rate(name, p)
    lh = payload.get("lighthouseResult") or {}
    perf = ((lh.get("categories") or {}).get("performance") or {}).get("score")
    row["lab_performance_score"] = round(perf * 100) if perf is not None else None
    audits = lh.get("audits") or {}
    for audit_id, name in LAB_AUDITS.items():
        row[name] = (audits.get(audit_id) or {}).get("numericValue")
    opps = []
    for audit_id in OPPORTUNITY_AUDITS:
        a = audits.get(audit_id) or {}
        score = a.get("score")
        if score is None or score >= 0.9:
            continue
        savings = (a.get("details") or {}).get("overallSavingsMs")
        opps.append(f"{audit_id} (~{int(savings)} ms)" if savings else audit_id)
    row["lab_opportunities"] = "; ".join(opps)
    row["lighthouse_version"] = lh.get("lighthouseVersion")
    return row


def run_pagespeed(urls: list[str], api_key: str | None = None, strategies=("mobile", "desktop"),
                  pause_s: float = 1.0, session: requests.Session | None = None) -> list[dict]:
    api_key = api_key or os.environ.get("PAGESPEED_API_KEY")
    if not api_key:
        raise RuntimeError("PAGESPEED_API_KEY not set; PageSpeed integration is unconfigured")
    s = session or requests.Session()
    rows = []
    for url in urls:
        for strategy in strategies:
            params = {"url": url, "strategy": strategy, "category": "performance", "key": api_key}
            row = None
            for attempt in range(3):
                try:
                    resp = s.get(API, params=params, timeout=120)
                    if resp.status_code == 429 or resp.status_code >= 500:
                        time.sleep(2 ** (attempt + 2))
                        continue
                    resp.raise_for_status()
                    row = parse_psi(resp.json(), url, strategy)
                    break
                except requests.RequestException as exc:
                    row = {"url": url, "strategy": strategy, "error": str(exc)[:200]}
                    time.sleep(2 ** (attempt + 1))
            rows.append(row or {"url": url, "strategy": strategy, "error": "retries exhausted"})
            time.sleep(pause_s)
    return rows
