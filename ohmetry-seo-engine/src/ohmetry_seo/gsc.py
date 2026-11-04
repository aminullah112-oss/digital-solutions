"""Google Search Console data: CSV export import (always available) and API pull (optional).

Average position in GSC is an impression-weighted average across every
query, country and device the URL appeared for. It isn't a fixed rank, and
reports must say so.
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .urls import normalise

PAGE_COLS = {"top pages", "pages", "page", "landing page", "url"}
QUERY_COLS = {"top queries", "queries", "query"}
COUNTRY_COLS = {"country", "countries"}
DEVICE_COLS = {"device", "devices"}
METRIC_COLS = {"clicks": "clicks", "impressions": "impressions", "ctr": "ctr",
               "position": "position", "average position": "position"}

POSITION_CAVEAT = ("GSC average position is impression-weighted across all queries, countries and devices "
                   "in the date range. It is not the rank any single user saw.")


@dataclass
class GscDataset:
    source: str  # "csv:<file>" or "api"
    date_range: tuple[str | None, str | None]
    dimension: str  # page | query | country | device
    rows: list[dict] = field(default_factory=list)
    note: str = ""


def _num(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    v = value.strip().replace(",", "")
    if not v or v in ("-", "—"):
        return None
    if v.endswith("%"):
        return float(v[:-1]) / 100
    return float(v)


def parse_gsc_csv(text: str, source: str, start: str | None = None, end: str | None = None) -> GscDataset:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames:
        raise ValueError(f"{source}: empty CSV")
    cols = {c: c.strip().lower() for c in reader.fieldnames}
    dim_col, dimension = None, None
    for orig, low in cols.items():
        for names, dim in ((PAGE_COLS, "page"), (QUERY_COLS, "query"), (COUNTRY_COLS, "country"), (DEVICE_COLS, "device")):
            if low in names:
                dim_col, dimension = orig, dim
                break
        if dim_col:
            break
    if not dim_col:
        raise ValueError(f"{source}: no page/query/country/device column in {list(cols.values())}")
    metric_cols = {orig: METRIC_COLS[low] for orig, low in cols.items() if low in METRIC_COLS}
    if not metric_cols:
        raise ValueError(f"{source}: no Clicks/Impressions/CTR/Position columns")
    rows = []
    for raw in reader:
        key = (raw.get(dim_col) or "").strip()
        if not key:
            continue
        row = {"key": normalise(key) if dimension == "page" else key}
        for orig, metric in metric_cols.items():
            row[metric] = _num(raw.get(orig))
        if row.get("ctr") is not None and row["ctr"] > 1:  # some exports give 3.2 meaning 3.2%
            row["ctr"] = row["ctr"] / 100
        rows.append(row)
    return GscDataset(source, (start, end), dimension, rows,
                      note="" if start else "Date range not supplied with the CSV; GSC UI exports don't include it.")


def load_gsc_exports(path: str | Path, start: str | None = None, end: str | None = None) -> list[GscDataset]:
    """Load a GSC UI export: a single CSV, a directory of CSVs, or the .zip GSC downloads."""
    path = Path(path)
    out: list[GscDataset] = []
    if path.is_dir():
        files = sorted(path.glob("*.csv"))
        for f in files:
            try:
                out.append(parse_gsc_csv(f.read_text(encoding="utf-8-sig"), f"csv:{f.name}", start, end))
            except ValueError:
                continue  # e.g. Filters.csv, Chart.csv
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for name in sorted(z.namelist()):
                if name.lower().endswith(".csv"):
                    try:
                        out.append(parse_gsc_csv(z.read(name).decode("utf-8-sig"), f"csv:{path.name}/{name}", start, end))
                    except ValueError:
                        continue
    else:
        out.append(parse_gsc_csv(path.read_text(encoding="utf-8-sig"), f"csv:{path.name}", start, end))
    return out


def page_metrics(datasets: list[GscDataset]) -> dict[str, dict]:
    for ds in datasets:
        if ds.dimension == "page":
            return {r["key"]: r for r in ds.rows if r["key"]}
    return {}


# --- API ------------------------------------------------------------------

def fetch_search_analytics(site_url: str, start: str, end: str, dimensions: list[str],
                           credentials_path: str | None = None, row_limit: int = 25000,
                           max_rows: int = 250000) -> GscDataset:
    """Pull searchanalytics.query with pagination. Requires `pip install ".[google]"`."""
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError('Search Console API needs google-auth: pip install ".[google]"') from exc
    credentials_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set; Search Console API is unconfigured")
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    session = AuthorizedSession(creds)
    from urllib.parse import quote
    endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/searchAnalytics/query"
    rows, start_row = [], 0
    while start_row < max_rows:
        body = {"startDate": start, "endDate": end, "dimensions": dimensions,
                "rowLimit": row_limit, "startRow": start_row, "dataState": "final"}
        resp = session.post(endpoint, json=body, timeout=60)
        resp.raise_for_status()
        batch = resp.json().get("rows", [])
        rows.extend(parse_api_rows(batch, dimensions))
        if len(batch) < row_limit:
            break
        start_row += row_limit
    return GscDataset("api", (start, end), dimensions[0] if len(dimensions) == 1 else "+".join(dimensions), rows,
                      note=f"searchanalytics.query dimensions={dimensions} dataState=final")


def parse_api_rows(batch: list[dict], dimensions: list[str]) -> list[dict]:
    out = []
    for r in batch:
        keys = r.get("keys", [])
        row = {dim: (normalise(k) if dim == "page" else k) for dim, k in zip(dimensions, keys)}
        row["key"] = row.get(dimensions[0])
        for m in ("clicks", "impressions", "ctr", "position"):
            row[m] = r.get(m)
        out.append(row)
    return out


def segment_pages(metrics: dict[str, dict], min_impressions: int = 100) -> dict[str, list[str]]:
    """Prioritisation bands from the master brief §7A. Bands, not predictions."""
    bands: dict[str, list[str]] = {"striking_distance_4_20": [], "page_two_three_11_30": [],
                                   "high_impr_low_ctr": [], "earning_clicks": [], "no_meaningful_impressions": []}
    for url, r in metrics.items():
        impr, pos, ctr, clicks = r.get("impressions") or 0, r.get("position"), r.get("ctr"), r.get("clicks") or 0
        if impr < min_impressions:
            bands["no_meaningful_impressions"].append(url)
            continue
        if pos is not None and 4 <= pos <= 20:
            bands["striking_distance_4_20"].append(url)
        if pos is not None and 11 <= pos <= 30:
            bands["page_two_three_11_30"].append(url)
        if ctr is not None and pos is not None and pos <= 10 and ctr < 0.02:
            bands["high_impr_low_ctr"].append(url)
        if clicks > 0:
            bands["earning_clicks"].append(url)
    return bands
