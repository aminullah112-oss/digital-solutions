"""Loads the Nifty 100 constituent list from the official NSE Indices CSV.

The CSV (ind_nifty100list.csv) has columns:
    Company Name, Industry, Symbol, Series, ISIN Code

Sources, tried in order:
  1. niftyindices.com  (NSE Indices' own website)
  2. nsearchives.nseindia.com  (NSE's mirror of the same file)

The list only changes a few times a year (index rebalances), so it is cached
for 24 hours, in memory and in backend/.data/nifty100.csv. If every download
fails but an older copy exists, the old copy is used and flagged as stale.
"""

import csv
import io
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import requests

SOURCES = (
    "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
    "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv",
)
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent / ".data" / "nifty100.csv"
CACHE_TTL_SECONDS = 24 * 60 * 60
MIN_EXPECTED_ROWS = 50  # guards against saving an error page as the list
REQUEST_TIMEOUT_SECONDS = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; kite-algo)"}


class ConstituentsError(Exception):
    """The Nifty 100 list could not be loaded."""


_lock = threading.Lock()
_memory: Dict[str, object] = {"rows": None, "at": 0.0, "source": None}


def _cache_path() -> Path:
    return Path(os.environ.get("NIFTY100_CACHE_FILE") or DEFAULT_CACHE_PATH)


def parse_csv(text: str, min_rows: int = MIN_EXPECTED_ROWS) -> List[dict]:
    """Turn the CSV text into [{symbol, company, industry}, ...]."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    fields = {(f or "").strip() for f in (reader.fieldnames or [])}
    if not {"Company Name", "Symbol"} <= fields:
        raise ConstituentsError("The file is not in the expected Nifty CSV format.")

    rows, seen = [], set()
    for raw in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        symbol = row.get("Symbol", "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        rows.append(
            {"symbol": symbol, "company": row.get("Company Name", ""), "industry": row.get("Industry", "")}
        )
    if len(rows) < min_rows:
        raise ConstituentsError(f"Only {len(rows)} rows found; expected at least {min_rows}.")
    return rows


def _download(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig")


def load_constituents() -> Tuple[List[dict], dict]:
    """Return (rows, meta). meta = {"source": url-or-"cache", "stale": bool}."""
    with _lock:
        now = time.time()
        if _memory["rows"] and now - float(_memory["at"]) < CACHE_TTL_SECONDS:
            return _memory["rows"], {"source": _memory["source"], "stale": False}  # type: ignore[return-value]

        path = _cache_path()
        try:
            if path.exists() and now - path.stat().st_mtime < CACHE_TTL_SECONDS:
                rows = parse_csv(path.read_text(encoding="utf-8"))
                _memory.update(rows=rows, at=now, source="cache")
                return rows, {"source": "cache", "stale": False}
        except (ConstituentsError, OSError):
            pass  # unreadable cache: fall through to a fresh download

        problems = []
        for url in SOURCES:
            try:
                text = _download(url)
                rows = parse_csv(text)
            except Exception as exc:  # network error, bad status, bad format
                problems.append(f"{urlparse(url).hostname}: {type(exc).__name__}")
                continue
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            except OSError:
                pass  # caching is best-effort
            _memory.update(rows=rows, at=now, source=url)
            return rows, {"source": url, "stale": False}

        # Every download failed: an old copy is better than nothing.
        try:
            if path.exists():
                rows = parse_csv(path.read_text(encoding="utf-8"))
                return rows, {"source": "cache", "stale": True}
        except (ConstituentsError, OSError):
            pass
        raise ConstituentsError(
            "Could not download the Nifty 100 list (" + "; ".join(problems) + "). Check your internet connection."
        )


# ----------------------------------------------------- other index lists ----
_OTHER_URLS = {
    "nifty50": (
        "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
        "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
    ),
}
_other_memory: Dict[str, dict] = {}


def load_index_symbols(index: str, min_rows: int = 40):
    """Symbols in another NSE index (for example "nifty50"), or None if the list can't be loaded.

    Only used to flag stocks, so a failure is not an error. Cached for 24 hours.
    """
    with _lock:
        hit = _other_memory.get(index)
        if hit and time.time() - hit["at"] < CACHE_TTL_SECONDS:
            return hit["symbols"]
        for url in _OTHER_URLS.get(index, ()):
            try:
                rows = parse_csv(_download(url), min_rows=min_rows)
            except Exception:
                continue
            symbols = {r["symbol"] for r in rows}
            _other_memory[index] = {"at": time.time(), "symbols": symbols}
            return symbols
        return hit["symbols"] if hit else None
