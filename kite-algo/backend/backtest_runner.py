"""Runs one backtest: load the Nifty 100 list, get candles (disk cache first), call the engine.

Shares the scan lock and the 3-requests-per-second throttle with the Signals
scanner, because Kite's rate limit is per account, not per feature.
"""

import math
from datetime import timedelta
from typing import Callable, Optional

from kiteconnect import exceptions as kite_exc

import backtest
import candles
import nifty100
import scanner

INDEX_NAME = "NIFTY 100"


class NoUsableData(Exception):
    """Every stock was skipped or excluded, or a required input could not be loaded."""


def _warmup_days(trading_days: int) -> int:
    """Calendar days to download before the start so an N-day indicator has data on day one."""
    return math.ceil(trading_days * 1.6) + 10


def _load_stocks(kite, selected, instruments, fetch_from, today, min_rows):
    stocks, skipped, excluded = {}, [], []
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

        if len(rows) < min_rows:
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
    return stocks, skipped, excluded


def _load_index(kite, index_from, today, required):
    """Nifty 100 index candles. Returns (rows or None, notes)."""
    token = scanner.get_index_token(kite, INDEX_NAME)
    if token is None:
        if required:
            raise NoUsableData("The regime filter needs Nifty 100 index prices, but the index was not found in Kite's instrument list.")
        return None, ["The Nifty 100 index was not found in Kite's instrument list, so that benchmark is left out."]
    try:
        return candles.get_ohlc(kite, token, index_from, today), []
    except kite_exc.TokenException:
        raise
    except kite_exc.PermissionException as exc:
        raise scanner.HistoricalAccessDenied(str(exc)) from exc
    except Exception:
        if required:
            raise NoUsableData("The regime filter needs Nifty 100 index prices, but they could not be downloaded.")
        return None, ["The Nifty 100 index prices could not be downloaded, so that benchmark is left out."]


def _execute(
    kite,
    *,
    years: int,
    max_stocks: int,
    stock_warmup_days: int,
    min_rows: int,
    regime_filter: bool,
    regime_sma: int,
    params: dict,
    simulate: Callable[..., dict],
) -> dict:
    with scanner.exclusive():
        constituents, meta = nifty100.load_constituents()
        selected = constituents[:max_stocks]
        instruments = scanner.get_instruments(kite)

        now = scanner.now_ist()
        today = now.date()
        start = today - timedelta(days=round(years * 365))
        fetch_from = start - timedelta(days=stock_warmup_days)
        index_from = min(fetch_from, start - timedelta(days=_warmup_days(regime_sma))) if regime_filter else fetch_from

        stocks, skipped, excluded = _load_stocks(kite, selected, instruments, fetch_from, today, min_rows)
        if not stocks:
            raise NoUsableData("No stock had usable price data, so there is nothing to test.")
        index_rows, notes = _load_index(kite, index_from, today, regime_filter)

        result = simulate(stocks, start_date=start.isoformat(), index_rows=index_rows)

        return {
            "params": {**params, "years": years, "max_stocks": max_stocks, "regime_filter": regime_filter, "regime_sma": regime_sma},
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
    regime_filter: bool = False,
    regime_sma: int = 200,
    holdout_pct: int = 40,
) -> dict:
    """SMA crossover backtest."""

    def simulate(stocks, start_date, index_rows):
        return backtest.run(
            stocks,
            short_sma=short_sma,
            long_sma=long_sma,
            starting_capital=starting_capital,
            max_positions=max_positions,
            stop_loss_pct=stop_loss_pct,
            slippage_pct=slippage_pct,
            include_charges=include_charges,
            start_date=start_date,
            index_rows=index_rows,
            regime_sma=regime_sma if regime_filter else None,
            holdout_pct=holdout_pct,
        )

    return _execute(
        kite,
        years=years,
        max_stocks=max_stocks,
        stock_warmup_days=_warmup_days(long_sma),
        min_rows=long_sma + 2,
        regime_filter=regime_filter,
        regime_sma=regime_sma,
        params={
            "short_sma": short_sma,
            "long_sma": long_sma,
            "starting_capital": starting_capital,
            "max_positions": max_positions,
            "stop_loss_pct": stop_loss_pct,
            "slippage_pct": slippage_pct,
            "include_charges": include_charges,
            "holdout_pct": holdout_pct,
        },
        simulate=simulate,
    )


def run_momentum_backtest(
    kite,
    *,
    lookback_days: int,
    skip_days: int,
    top_n: int,
    keep_rank: Optional[int],
    years: int,
    max_stocks: int,
    starting_capital: float,
    stop_loss_pct: Optional[float],
    slippage_pct: float,
    include_charges: bool,
    regime_filter: bool = False,
    regime_sma: int = 200,
    holdout_pct: int = 40,
) -> dict:
    """Momentum rotation backtest (monthly rebalance, `top_n` equal slots)."""

    def simulate(stocks, start_date, index_rows):
        return backtest.run_momentum(
            stocks,
            lookback_days=lookback_days,
            skip_days=skip_days,
            top_n=top_n,
            keep_rank=keep_rank,
            starting_capital=starting_capital,
            stop_loss_pct=stop_loss_pct,
            slippage_pct=slippage_pct,
            include_charges=include_charges,
            start_date=start_date,
            index_rows=index_rows,
            regime_sma=regime_sma if regime_filter else None,
            holdout_pct=holdout_pct,
        )

    return _execute(
        kite,
        years=years,
        max_stocks=max_stocks,
        stock_warmup_days=_warmup_days(lookback_days + 1),
        min_rows=lookback_days + 2,
        regime_filter=regime_filter,
        regime_sma=regime_sma,
        params={
            "lookback_days": lookback_days,
            "skip_days": skip_days,
            "top_n": top_n,
            "keep_rank": keep_rank or top_n * 2,
            "starting_capital": starting_capital,
            "stop_loss_pct": stop_loss_pct,
            "slippage_pct": slippage_pct,
            "include_charges": include_charges,
            "holdout_pct": holdout_pct,
        },
        simulate=simulate,
    )
