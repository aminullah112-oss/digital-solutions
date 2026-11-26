"""Runs one backtest: load the Nifty 100 list, get candles (disk cache first), call the engine.

Shares the scan lock and the 3-requests-per-second throttle with the Signals
scanner, because Kite's rate limit is per account, not per feature.
"""

import math
from datetime import timedelta
from typing import Optional

from kiteconnect import exceptions as kite_exc

import backtest
import candles
import nifty100
import scanner

INDEX_NAME = "NIFTY 100"


class NoUsableData(Exception):
    """Every stock was skipped or excluded, so there is nothing to test."""


def run_backtest(
    kite,
    *,
    short_sma: int,
    long_sma: int,
    years: int,
    max_stocks: int,
    starting_capital: float,
    max_positions: int,
    stop_loss_pct: Optional[float],
    slippage_pct: float,
    include_charges: bool,
) -> dict:
    with scanner.exclusive():
        constituents, meta = nifty100.load_constituents()
        selected = constituents[:max_stocks]
        instruments = scanner.get_instruments(kite)

        now = scanner.now_ist()
        today = now.date()
        start = today - timedelta(days=round(years * 365))
        # Extra days before the start so the long SMA already has data on day one.
        fetch_from = start - timedelta(days=math.ceil(long_sma * 1.6) + 10)

        stocks, skipped, excluded, notes = {}, [], [], []
        for row in selected:
            symbol = row["symbol"]
            inst = instruments.get(symbol)
            if not inst:
                skipped.append({"symbol": symbol, "reason": "Not found in Kite's NSE instrument list"})
                continue
            try:
                rows = candles.get_ohlc(kite, inst["token"], fetch_from, today)
            except kite_exc.TokenException:
                raise  # login expired: stop and let the API layer ask for a new login
            except kite_exc.PermissionException as exc:
                raise scanner.HistoricalAccessDenied(str(exc)) from exc
            except kite_exc.KiteException as exc:
                skipped.append({"symbol": symbol, "reason": f"Kite error: {exc}"})
                continue
            except Exception:
                skipped.append({"symbol": symbol, "reason": "Could not download price data"})
                continue

            if len(rows) < long_sma + 2:
                skipped.append({"symbol": symbol, "reason": f"Only {len(rows)} days of price history"})
                continue
            moves = candles.suspect_moves(rows)
            if moves:
                worst = max(moves, key=lambda m: abs(m["change_pct"]))
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": f"Possible unadjusted split or bonus: {worst['change_pct']:+.0f}% in one day on {worst['date']}",
                    }
                )
                continue
            stocks[symbol] = {"company": row["company"], "rows": rows}

        if not stocks:
            raise NoUsableData("No stock had usable price data, so there is nothing to test.")

        index_rows = None
        token = scanner.get_index_token(kite, INDEX_NAME)
        if token is None:
            notes.append("The Nifty 100 index was not found in Kite's instrument list, so that benchmark is left out.")
        else:
            try:
                index_rows = candles.get_ohlc(kite, token, fetch_from, today)
            except kite_exc.TokenException:
                raise
            except kite_exc.PermissionException as exc:
                raise scanner.HistoricalAccessDenied(str(exc)) from exc
            except Exception:
                notes.append("The Nifty 100 index prices could not be downloaded, so that benchmark is left out.")

        result = backtest.run(
            stocks,
            short_sma=short_sma,
            long_sma=long_sma,
            starting_capital=starting_capital,
            max_positions=max_positions,
            stop_loss_pct=stop_loss_pct,
            slippage_pct=slippage_pct,
            include_charges=include_charges,
            start_date=start.isoformat(),
            index_rows=index_rows,
        )

        return {
            "params": {
                "short_sma": short_sma,
                "long_sma": long_sma,
                "years": years,
                "max_stocks": max_stocks,
                "starting_capital": starting_capital,
                "max_positions": max_positions,
                "stop_loss_pct": stop_loss_pct,
                "slippage_pct": slippage_pct,
                "include_charges": include_charges,
            },
            "generated_at": now.isoformat(timespec="seconds"),
            "market_open": scanner._market_is_open(now),
            "universe": {
                "name": "Nifty 100",
                "requested": len(selected),
                "used": len(stocks),
                "source": meta["source"],
                "stale": meta["stale"],
            },
            "excluded": excluded,
            "skipped": skipped,
            "notes": notes,
            **result,
        }
