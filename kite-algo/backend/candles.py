"""Daily OHLC candles with a disk cache.

The backtest needs 5 years of open/high/low/close for ~100 stocks. Downloading
that takes ~40 seconds (Kite allows 3 history requests per second), so each
stock's candles are saved to backend/.data/candles/<token>.json and later runs
only download what is missing:

  * no saved file                                      -> download everything
  * saved file starts later than you now need          -> download only the missing earlier days
  * saved file is up to date                           -> no request at all
  * saved file ends before today                       -> download the last few days and merge

"Up to date" means the newest candle is final: today's daily candle is still
changing while NSE is open, so data fetched before 15:45 IST is trusted for
only 10 minutes. Data fetched after the close is trusted until the next
trading day.
"""

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import scanner

Row = Tuple[str, float, float, float, float, float]  # (date, open, high, low, close, volume)
CACHE_VERSION = 2  # version 1 files had no volume; they are ignored and downloaded again

DEFAULT_DIR = Path(__file__).resolve().parent / ".data" / "candles"
MAX_DAYS_PER_REQUEST = 1995  # Kite returns at most 2000 days of daily candles per request
PARTIAL_TTL_SECONDS = 10 * 60
FINAL_AFTER = time(15, 45)  # IST: after this, the day's candle will not change
REFRESH_OVERLAP_DAYS = 7

_memory: Dict[int, dict] = {}


def _dir() -> Path:
    return Path(os.environ.get("CANDLES_DIR") or DEFAULT_DIR)


def reset_memory() -> None:
    """Forget the in-memory copies (the files on disk stay). Used by tests."""
    _memory.clear()


def _last_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _load(token: int) -> Optional[dict]:
    if token in _memory:
        return _memory[token]
    try:
        data = json.loads((_dir() / f"{token}.json").read_text(encoding="utf-8"))
        if data.get("v") != CACHE_VERSION:
            return None
        entry = {
            "from": data["from"],
            "to": data["to"],
            "fetched_at": data["fetched_at"],
            "rows": [tuple(r) for r in data["rows"]],
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None
    _memory[token] = entry
    return entry


def _save(token: int, entry: dict) -> None:
    entry = {**entry, "v": CACHE_VERSION}
    _memory[token] = entry
    try:
        directory = _dir()
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / f"{token}.tmp"
        tmp.write_text(json.dumps(entry), encoding="utf-8")
        os.replace(tmp, directory / f"{token}.json")
    except OSError:
        pass  # caching is best-effort


def _fetch(kite, token: int, start: date, end: date) -> List[Row]:
    """Download candles from Kite, splitting long ranges into several requests."""
    rows: Dict[str, Row] = {}
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(end, chunk_start + timedelta(days=MAX_DAYS_PER_REQUEST - 1))
        raw = scanner.throttled(
            lambda a=chunk_start, b=chunk_end: kite.historical_data(
                token,
                datetime.combine(a, datetime.min.time()),
                datetime.combine(b, datetime.max.time().replace(microsecond=0)),
                "day",
            )
        )
        for c in raw:
            day = c["date"].date().isoformat()
            rows[day] = (day, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c.get("volume") or 0))
        chunk_start = chunk_end + timedelta(days=1)
    return [rows[k] for k in sorted(rows)]


def _is_fresh(entry: dict, end: date, now: datetime) -> bool:
    cached_to = date.fromisoformat(entry["to"])
    if cached_to < end:
        return False
    fetched = datetime.fromisoformat(entry["fetched_at"])
    if fetched >= datetime.combine(cached_to, FINAL_AFTER, tzinfo=scanner.IST):
        return True  # downloaded after the close: that candle is final
    return (now - fetched).total_seconds() < PARTIAL_TTL_SECONDS


def get_ohlc(kite, token: int, from_date: date, to_date: date, force: bool = False) -> List[Row]:
    """Daily candles from `from_date` up to `to_date`, oldest first. Uses and updates the disk cache.

    force=True always re-downloads the recent tail, even when the saved data looks fresh.
    """
    now = scanner.now_ist()
    end = _last_weekday(min(to_date, now.date()))
    from_iso = from_date.isoformat()
    stamp = now.isoformat(timespec="seconds")
    cached = _load(token)

    if not cached:
        rows = _fetch(kite, token, from_date, end)
        _save(token, {"from": from_iso, "to": end.isoformat(), "fetched_at": stamp, "rows": rows})
        return [r for r in rows if r[0] >= from_iso]

    merged = {r[0]: r for r in cached["rows"]}
    saved_from, saved_to, fetched_at = cached["from"], cached["to"], cached["fetched_at"]
    changed = False

    # Need older history than we saved (e.g. you raised the Long SMA)? Download only the missing head.
    if from_iso < saved_from:
        merged.update({r[0]: r for r in _fetch(kite, token, from_date, date.fromisoformat(saved_from))})
        saved_from, changed = from_iso, True

    # Newest candle missing or still changing? Download only the recent tail.
    if force or not _is_fresh(cached, end, now):
        since = max(date.fromisoformat(saved_from), date.fromisoformat(saved_to) - timedelta(days=REFRESH_OVERLAP_DAYS))
        merged.update({r[0]: r for r in _fetch(kite, token, since, end)})
        saved_to, fetched_at, changed = end.isoformat(), stamp, True

    rows = [merged[k] for k in sorted(merged)]
    if changed:
        _save(token, {"from": saved_from, "to": saved_to, "fetched_at": fetched_at, "rows": rows})
    return [r for r in rows if r[0] >= from_iso]


def suspect_moves(rows: List[Row], threshold: float = 0.35) -> List[dict]:
    """Days where the close jumps by more than `threshold` (35%) from the day before.

    In a large-cap stock that is almost always a split or bonus the data was
    not adjusted for, and it would create fake crossovers and fake losses.
    """
    found = []
    for prev, cur in zip(rows, rows[1:]):
        if prev[4] > 0:
            change = cur[4] / prev[4] - 1
            if abs(change) > threshold:
                found.append({"date": cur[0], "change_pct": round(change * 100, 1)})
    return found
