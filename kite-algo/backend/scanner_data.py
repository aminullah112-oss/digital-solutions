"""Data for the Algo Signals tab.

GET /api/scanner-data returns the Nifty 100 with daily candles (including
volume), in one response, so the browser can run the breakout scanner on it.

  {
    "metadata": {generated_at, interval, universe, days, candles_from, candles_to,
                 stock_count, skipped, excluded, cached, ...},
    "stocks":   [{symbol, company_name, instrument_token,
                  nifty_flags: {nifty50, nifty100},
                  candles: [{date, open, high, low, close, volume}, ...]}, ...]
  }

The built response is kept in memory for 5 minutes (the "scanner cache").
POST /api/scanner-data/refresh rebuilds it and re-downloads the latest candles.
Candles themselves are saved on disk by candles.py, so a restart is cheap.
"""

import re
import time
from datetime import timedelta
from typing import Dict, List

from kiteconnect import exceptions as kite_exc

import candles
import nifty100
import scanner

DEFAULT_DAYS = 120  # calendar days of candles, about 80 trading days (the scanner needs 41)
MIN_DAYS = 60
MAX_DAYS = 365
CACHE_TTL_SECONDS = 5 * 60
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9&\-]{1,20}$")
MAX_SNAPSHOT_SYMBOLS = 200

_cache: Dict[str, object] = {"days": None, "at": 0.0, "payload": None}


def reset_cache() -> None:
    _cache.update(days=None, at=0.0, payload=None)


def get_scanner_data(kite, days: int = DEFAULT_DAYS, force: bool = False) -> dict:
    """Return the scanner response. force=True rebuilds it and re-downloads the newest candles."""
    if not force and _cache["payload"] is not None and _cache["days"] == days and time.monotonic() - float(_cache["at"]) < CACHE_TTL_SECONDS:
        payload = _cache["payload"]
        return {"metadata": {**payload["metadata"], "cached": True}, "stocks": payload["stocks"]}  # type: ignore[index]

    with scanner.exclusive():
        constituents, meta = nifty100.load_constituents()
        nifty50 = nifty100.load_index_symbols("nifty50")
        instruments = scanner.get_instruments(kite)
        now = scanner.now_ist()
        today = now.date()
        from_date = today - timedelta(days=days)

        stocks: List[dict] = []
        skipped: List[dict] = []
        excluded: List[dict] = []
        for row in constituents:
            symbol = row["symbol"]
            inst = instruments.get(symbol)
            if not inst:
                skipped.append({"symbol": symbol, "reason": "Not found in Kite's NSE instrument list"})
                continue
            try:
                rows = candles.get_ohlc(kite, inst["token"], from_date, today, force=force)
            except kite_exc.TokenException:
                raise
            except kite_exc.PermissionException as exc:
                raise scanner.HistoricalAccessDenied(str(exc)) from exc
            except kite_exc.KiteException as exc:
                skipped.append({"symbol": symbol, "reason": f"Kite error: {exc}"})
                continue
            except Exception:
                skipped.append({"symbol": symbol, "reason": "Could not download price data"})
                continue
            moves = candles.suspect_moves(rows)
            if moves:
                worst = max(moves, key=lambda m: abs(m["change_pct"]))
                excluded.append({"symbol": symbol, "reason": f"Possible unadjusted split or bonus: {worst['change_pct']:+.0f}% on {worst['date']}"})
                continue
            stocks.append(
                {
                    "symbol": symbol,
                    "company_name": row["company"],
                    "instrument_token": inst["token"],
                    "nifty_flags": {"nifty100": True, "nifty50": (symbol in nifty50) if nifty50 is not None else None},
                    "candles": [{"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in rows],
                }
            )

        last_dates = [s["candles"][-1]["date"] for s in stocks if s["candles"]]
        payload = {
            "metadata": {
                "generated_at": now.isoformat(timespec="seconds"),
                "interval": "day",
                "universe": "Nifty 100",
                "days": days,
                "candles_from": from_date.isoformat(),
                "candles_to": max(last_dates) if last_dates else None,
                "stock_count": len(stocks),
                "skipped": skipped,
                "excluded": excluded,
                "list_source": meta["source"],
                "list_stale": meta["stale"],
                "market_open": scanner._market_is_open(now),
                "cached": False,
            },
            "stocks": stocks,
        }
        _cache.update(days=days, at=time.monotonic(), payload=payload)
        return payload


def ohlc_snapshot(kite, symbols: List[str]) -> dict:
    """Latest price snapshot for NSE symbols: {SYMBOL: {last_price, instrument_token, ohlc}}.

    Symbols Kite doesn't return are left out. Read-only.
    """
    clean = []
    for s in symbols:
        s = s.strip().upper()
        if s and SYMBOL_PATTERN.match(s) and s not in clean:
            clean.append(s)
    if not clean:
        raise ValueError("No valid symbols given.")
    if len(clean) > MAX_SNAPSHOT_SYMBOLS:
        raise ValueError(f"At most {MAX_SNAPSHOT_SYMBOLS} symbols at a time.")
    raw = kite.ohlc([f"NSE:{s}" for s in clean])
    out = {}
    for s in clean:
        item = raw.get(f"NSE:{s}")
        if item and item.get("last_price") is not None:
            out[s] = {"last_price": item["last_price"], "instrument_token": item.get("instrument_token"), "ohlc": item.get("ohlc")}
    return out
