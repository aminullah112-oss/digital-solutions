"""Nifty 100 SMA-crossover scanner.

Steps for one scan:
  1. Load Nifty 100 symbols (nifty100.py).
  2. Map each symbol to its Kite NSE instrument token (kite.instruments).
  3. Fetch daily candles for each stock (kite.historical_data), at most
     3 requests per second because that is Kite's limit for this API.
  4. Look for the latest SMA crossover (signals.py).
  5. Rank: most recent crossover date first.
"""

import math
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple

from kiteconnect import exceptions as kite_exc

import nifty100
import signals

IST = timezone(timedelta(hours=5, minutes=30))

THROTTLE_SECONDS = 0.4  # Kite allows 3 historical-data requests/second
INSTRUMENTS_TTL_SECONDS = 6 * 60 * 60
CANDLES_TTL_SECONDS = 10 * 60  # short: today's candle keeps changing while the market is open
TRADING_DAYS_PER_CALENDAR_DAY = 0.65  # conservative (weekends + holidays)

# Module-level hooks so tests can replace the clock and sleep.
_now = time.monotonic
_sleep = time.sleep
_wall_clock = lambda: datetime.now(IST)  # noqa: E731

_scan_lock = threading.Lock()
_instruments: Dict[str, object] = {"at": 0.0, "map": None, "indices": {}}
_candle_cache: Dict[int, dict] = {}
_last_call = [0.0]


class ScanBusy(Exception):
    """Another scan is already running."""


class HistoricalAccessDenied(Exception):
    """The Kite app is not allowed to download historical candles."""


def reset_caches() -> None:
    """Forget cached instruments and candles (used by tests)."""
    _instruments.update(at=0.0, map=None, indices={})
    _candle_cache.clear()
    _last_call[0] = 0.0


# ------------------------------------------------------------------ Kite ----
def get_instruments(kite) -> Dict[str, dict]:
    """{tradingsymbol: {token, name}} for NSE equities. Cached for 6 hours."""
    cached = _instruments["map"]
    if cached and _now() - float(_instruments["at"]) < INSTRUMENTS_TTL_SECONDS:
        return cached  # type: ignore[return-value]
    rows = kite.instruments("NSE")
    mapping = {
        row["tradingsymbol"]: {"token": row["instrument_token"], "name": row.get("name")}
        for row in rows
        if row.get("segment") == "NSE" and row.get("instrument_type") == "EQ"
    }
    indices = {row["tradingsymbol"]: row["instrument_token"] for row in rows if row.get("segment") == "INDICES"}
    _instruments.update(at=_now(), map=mapping, indices=indices)
    return mapping


def get_index_token(kite, name: str):
    """Instrument token of an NSE index such as "NIFTY 100", or None if Kite doesn't list it."""
    get_instruments(kite)
    return _instruments["indices"].get(name)  # type: ignore[union-attr]


def now_ist() -> datetime:
    return _wall_clock()


def throttled(call):
    """Run `call()` while respecting Kite's 3-requests-per-second limit."""
    wait = THROTTLE_SECONDS - (_now() - _last_call[0])
    if wait > 0:
        _sleep(wait)
    _last_call[0] = _now()
    try:
        return call()
    except kite_exc.KiteException as exc:
        if "too many requests" not in str(exc).lower():
            raise
        _sleep(1.0)  # we were still too fast: back off once and retry
        _last_call[0] = _now()
        return call()


def _get_candles(kite, token: int, from_date: date, to_date: date) -> List[Tuple[str, float]]:
    """Daily (date, close) pairs, oldest first. Reuses a recent download if it covers the range."""
    hit = _candle_cache.get(token)
    if hit and hit["from"] <= from_date and hit["to"] == to_date and _now() - hit["at"] < CANDLES_TTL_SECONDS:
        return hit["rows"]

    raw = throttled(
        lambda: kite.historical_data(
            token,
            datetime.combine(from_date, datetime.min.time()),
            datetime.combine(to_date, datetime.max.time().replace(microsecond=0)),
            "day",
        )
    )
    rows = [(c["date"].date().isoformat(), float(c["close"])) for c in raw]
    _candle_cache[token] = {"from": from_date, "to": to_date, "at": _now(), "rows": rows}
    return rows


# ------------------------------------------------------------------ scan ----
def _market_is_open(now: datetime) -> bool:
    """Rough check: weekday, 09:15-15:30 IST. (Does not know exchange holidays.)"""
    minutes = now.hour * 60 + now.minute
    return now.weekday() < 5 and 9 * 60 + 15 <= minutes <= 15 * 60 + 30


@contextmanager
def exclusive():
    """Only one scan or backtest at a time: Kite's rate limit is shared by all of them."""
    if not _scan_lock.acquire(blocking=False):
        raise ScanBusy()
    try:
        yield
    finally:
        _scan_lock.release()


def run_scan(kite, short_sma: int, long_sma: int, lookback_days: int, max_stocks: int) -> dict:
    with exclusive():
        return _scan(kite, short_sma, long_sma, lookback_days, max_stocks)


def _scan(kite, short_sma: int, long_sma: int, lookback_days: int, max_stocks: int) -> dict:
    constituents, meta = nifty100.load_constituents()
    selected = constituents[:max_stocks]
    instruments = get_instruments(kite)

    now = _wall_clock()
    today = now.date()
    # Enough calendar days to cover long_sma + lookback trading days, plus a buffer.
    candles_needed = long_sma + lookback_days + 1
    from_date = today - timedelta(days=math.ceil(candles_needed / TRADING_DAYS_PER_CALENDAR_DAY) + 10)

    results: List[dict] = []
    skipped: List[dict] = []
    data_as_of = ""

    for row in selected:
        symbol = row["symbol"]
        inst = instruments.get(symbol)
        if not inst:
            skipped.append({"symbol": symbol, "reason": "Not found in Kite's NSE instrument list"})
            continue

        try:
            candles = _get_candles(kite, inst["token"], from_date, today)
        except kite_exc.TokenException:
            raise  # the login expired: stop and let the API layer ask for a new login
        except kite_exc.PermissionException as exc:
            raise HistoricalAccessDenied(str(exc)) from exc
        except kite_exc.KiteException as exc:
            skipped.append({"symbol": symbol, "reason": f"Kite error: {exc}"})
            continue
        except Exception:
            skipped.append({"symbol": symbol, "reason": "Could not download price data"})
            continue

        if len(candles) < long_sma + 1:
            skipped.append({"symbol": symbol, "reason": f"Only {len(candles)} days of price history"})
            continue

        dates = [d for d, _ in candles]
        closes = [c for _, c in candles]
        data_as_of = max(data_as_of, dates[-1])

        hit = signals.latest_crossover(dates, closes, short_sma, long_sma, lookback_days)
        if hit:
            results.append(
                {
                    "symbol": symbol,
                    "company": row["company"],
                    "crossover_type": hit["type"],
                    "crossover_date": hit["date"],
                    "close": round(hit["close"], 2),
                    "sma_short": round(hit["sma_short"], 2),
                    "sma_long": round(hit["sma_long"], 2),
                }
            )

    # Most recent crossover first; ties broken alphabetically so the order is stable.
    results.sort(key=lambda r: r["symbol"])
    results.sort(key=lambda r: r["crossover_date"], reverse=True)
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank

    return {
        "params": {
            "short_sma": short_sma,
            "long_sma": long_sma,
            "lookback_days": lookback_days,
            "max_stocks": max_stocks,
        },
        "generated_at": now.isoformat(timespec="seconds"),
        "market_open": _market_is_open(now),
        "data_as_of": data_as_of or None,
        "universe": {
            "name": "Nifty 100",
            "requested": len(selected),
            "scanned": len(selected) - len(skipped),
            "source": meta["source"],
            "stale": meta["stale"],
        },
        "results": results,
        "skipped": skipped,
    }
