"""SMA-crossover backtest engine. Pure functions: no network, no Kite.

The rules (these are the decisions agreed in the design doc):

  * Long-only. A bullish crossover opens a position, a bearish one closes it.
  * A crossover is only known at the close of day t, so the trade happens at
    the OPEN of the stock's next trading day. Never at the signal's own close.
  * Each position gets starting_capital / max_positions rupees, fixed for the
    whole test (no compounding). Shares plus buy charges are sized to fit that
    amount. When every slot is full a new signal is skipped and counted.
    Same-day signals are served in ticker order.
  * An optional stop-loss sits below the fill price. If a day's low touches it
    the position sells at the stop price, or at the open if the stock gapped
    below it. When a stop and a bearish exit fall on the same day, the stop wins.
  * Slippage makes every fill slightly worse. Zerodha delivery charges are
    deducted on each leg (charges.py).
  * Positions still open on the last day are sold at that day's close.
"""

import math
from bisect import bisect_right
from datetime import date
from typing import Dict, List, Optional, Sequence

import charges
import signals


class NoDataError(Exception):
    """No candles fall inside the test period."""


def max_drawdown_pct(values: Sequence[float]) -> float:
    """Worst peak-to-trough fall, as a negative percentage (0.0 if it never fell)."""
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return round(worst * 100, 2)


def _cagr_pct(start_value: float, end_value: float, first: str, last: str) -> Optional[float]:
    days = (date.fromisoformat(last) - date.fromisoformat(first)).days
    if days < 30 or start_value <= 0 or end_value <= 0:
        return None  # too short to annualise sensibly
    return round(((end_value / start_value) ** (365 / days) - 1) * 100, 2)


def _series_stats(values: List[float], first: str, last: str, start_value: float) -> dict:
    return {
        "final_value": round(values[-1], 2),
        "total_return_pct": round((values[-1] / start_value - 1) * 100, 2),
        "cagr_pct": _cagr_pct(start_value, values[-1], first, last),
        "max_drawdown_pct": max_drawdown_pct(values),
    }


def run(
    stocks: Dict[str, dict],
    *,
    short_sma: int,
    long_sma: int,
    starting_capital: float,
    max_positions: int,
    stop_loss_pct: Optional[float],
    slippage_pct: float,
    include_charges: bool,
    start_date: str,
    index_rows: Optional[list] = None,
) -> dict:
    """Replay the strategy.

    stocks: {symbol: {"company": str, "rows": [(date, open, high, low, close), ...]}}, oldest first.
            Rows before `start_date` are used only to warm up the moving averages.
    index_rows: same row format for the benchmark index, or None.
    """
    slip = slippage_pct / 100.0
    position_size = starting_capital / max_positions

    data: Dict[str, dict] = {}
    for sym in sorted(stocks):  # ticker order = who gets a free slot first
        rows = stocks[sym]["rows"]
        data[sym] = {
            "company": stocks[sym].get("company", ""),
            "rows": rows,
            "dates": [r[0] for r in rows],
            "pos": {r[0]: i for i, r in enumerate(rows)},
            "signals": {i: kind for i, kind, _, _ in signals.crossovers([r[4] for r in rows], short_sma, long_sma)},
        }

    dates = sorted({r[0] for d in data.values() for r in d["rows"] if r[0] >= start_date})
    if not dates:
        raise NoDataError("No price data falls inside the test period.")
    first_day, last_day = dates[0], dates[-1]

    # Last known close of every stock, as of the first test day.
    last_close: Dict[str, float] = {}
    for sym, d in data.items():
        k = bisect_right(d["dates"], first_day) - 1
        if k >= 0:
            last_close[sym] = d["rows"][k][4]

    # Benchmark 2: the same stocks held equal-weight from day one, no costs.
    members = sorted(last_close)
    held_shares = {sym: (starting_capital / len(members)) / last_close[sym] for sym in members} if members else {}

    # Benchmark 1: the index, forward-filled over the stock calendar.
    index_close = {r[0]: r[4] for r in index_rows} if index_rows else {}
    index_dates = sorted(index_close)
    k = bisect_right(index_dates, first_day) - 1
    index_last = index_close[index_dates[k]] if k >= 0 else None
    index_base: Optional[float] = None

    cash = starting_capital
    held: Dict[str, dict] = {}
    trades: List[dict] = []
    curve: List[dict] = []
    skipped = {"no_free_slot": 0, "not_enough_cash": 0}
    totals = {"charges": 0.0, "slippage": 0.0}

    def sell(sym: str, day: str, raw_price: float, reason: str) -> None:
        nonlocal cash
        pos = held.pop(sym)
        price = raw_price * (1 - slip)
        proceeds = pos["shares"] * price
        sell_fee = charges.sell_charges(proceeds) if include_charges else 0.0
        cash += proceeds - sell_fee
        invested = pos["shares"] * pos["entry_price"] + pos["buy_fee"]
        pnl = proceeds - sell_fee - invested
        totals["charges"] += pos["buy_fee"] + sell_fee
        totals["slippage"] += pos["shares"] * (pos["entry_price"] - pos["entry_raw"]) + pos["shares"] * (raw_price - price)
        trades.append(
            {
                "symbol": sym,
                "company": data[sym]["company"],
                "entry_date": pos["entry_date"],
                "entry_price": round(pos["entry_price"], 2),
                "exit_date": day,
                "exit_price": round(price, 2),
                "shares": pos["shares"],
                "days_held": (date.fromisoformat(day) - date.fromisoformat(pos["entry_date"])).days,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl / invested * 100, 2),
                "charges": round(pos["buy_fee"] + sell_fee, 2),
                "exit_reason": reason,
            }
        )

    for day in dates:
        # 1. Exits for stocks we hold. The stop is checked first (see module docstring).
        for sym in sorted(held):
            i = data[sym]["pos"].get(day)
            if i is None:
                continue
            _, o, _, low, _ = data[sym]["rows"][i]
            stop = held[sym]["stop"]
            if stop is not None and low <= stop:
                sell(sym, day, o if o <= stop else stop, "stop-loss")
            elif i > 0 and data[sym]["signals"].get(i - 1) == "bearish":
                sell(sym, day, o, "bearish crossover")

        # 2. Entries from yesterday's bullish crossovers, in ticker order.
        for sym, d in data.items():
            i = d["pos"].get(day)
            if sym in held or i is None or i == 0 or d["signals"].get(i - 1) != "bullish":
                continue
            if len(held) >= max_positions:
                skipped["no_free_slot"] += 1
                continue
            _, o, _, low, _ = d["rows"][i]
            entry_price = o * (1 + slip)
            # Size the position so that shares + charges fit inside one slot (and inside our cash).
            budget = min(position_size, cash)
            shares = int(budget // entry_price)
            while shares >= 1:
                cost = shares * entry_price
                buy_fee = charges.buy_charges(cost) if include_charges else 0.0
                over = cost + buy_fee - budget
                if over <= 0:
                    break
                shares -= max(1, math.ceil(over / entry_price))
            if shares < 1:
                skipped["not_enough_cash"] += 1
                continue
            cash -= cost + buy_fee
            stop = entry_price * (1 - stop_loss_pct / 100) if stop_loss_pct else None
            held[sym] = {
                "shares": shares,
                "entry_date": day,
                "entry_raw": o,
                "entry_price": entry_price,
                "buy_fee": buy_fee,
                "stop": stop,
            }
            if stop is not None and low <= stop:  # stopped out on the day we bought
                sell(sym, day, stop, "stop-loss")

        # 3. Mark everything to market at today's close.
        for sym, d in data.items():
            i = d["pos"].get(day)
            if i is not None:
                last_close[sym] = d["rows"][i][4]
        if day in index_close:
            index_last = index_close[day]
        if index_last is not None and index_base is None:
            index_base = index_last

        curve.append(
            {
                "date": day,
                "strategy": cash + sum(p["shares"] * last_close[s] for s, p in held.items()),
                "nifty100": starting_capital * index_last / index_base if index_last is not None and index_base else None,
                "same_stocks": sum(sh * last_close.get(s, 0.0) for s, sh in held_shares.items()) if held_shares else None,
            }
        )

    # Sell whatever is still open at the last close.
    for sym in sorted(held):
        sell(sym, last_day, last_close[sym], "end of test")
    curve[-1]["strategy"] = cash

    # ---------------------------------------------------------------- results
    strategy_values = [c["strategy"] for c in curve]
    summary = _series_stats(strategy_values, first_day, last_day, starting_capital)
    summary["net_profit"] = round(cash - starting_capital, 2)

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    summary.update(
        trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=round(len(wins) / len(trades) * 100, 1) if trades else None,
        avg_win_pct=round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else None,
        avg_loss_pct=round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else None,
        profit_factor=round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        avg_holding_days=round(sum(t["days_held"] for t in trades) / len(trades), 1) if trades else None,
    )

    benchmarks: Dict[str, Optional[dict]] = {"nifty100": None, "same_stocks": None}
    idx_values = [c["nifty100"] for c in curve if c["nifty100"] is not None]
    if idx_values:
        benchmarks["nifty100"] = _series_stats(idx_values, first_day, last_day, starting_capital)
    if held_shares:
        same = [c["same_stocks"] for c in curve]
        benchmarks["same_stocks"] = {**_series_stats(same, first_day, last_day, starting_capital), "stocks": len(held_shares)}

    for c in curve:
        for key in ("strategy", "nifty100", "same_stocks"):
            if c[key] is not None:
                c[key] = round(c[key], 2)

    # Newest first, like the Signals table; ties by ticker.
    trades.sort(key=lambda t: t["symbol"])
    trades.sort(key=lambda t: t["entry_date"], reverse=True)

    return {
        "period": {"start": first_day, "end": last_day, "trading_days": len(dates)},
        "summary": summary,
        "benchmarks": benchmarks,
        "equity_curve": curve,
        "trades": trades,
        "signals_skipped": skipped,
        "costs": {
            "charges": round(totals["charges"], 2),
            "slippage": round(totals["slippage"], 2),
            "total": round(totals["charges"] + totals["slippage"], 2),
        },
    }
