"""Backtest engine. Pure functions: no network, no Kite.

One simulation core, two strategies that plug into it:

  * SMA crossover: bullish crossover buys, bearish crossover sells.
  * Momentum rotation: once a month, hold the top-ranked stocks by past return.

Both can be gated by a regime filter ("only trade while the Nifty 100 is above
its N-day average"). Rules shared by every strategy (agreed in the design review):

  * Long-only.
  * A decision is made at the CLOSE of a day and executed at the OPEN of the
    stock's next trading day. Never at the close that produced the signal.
  * Each position gets starting_capital / max_positions rupees, fixed for the
    whole test (no compounding). Shares plus buy charges are sized to fit that
    amount. When every slot is full a new buy is skipped and counted.
  * An optional stop-loss sits below the fill price. If a day's low touches it
    the position sells at the stop price, or at the open if the stock gapped
    below it. When a stop and a strategy exit fall on the same day, the stop wins.
  * Slippage makes every fill slightly worse. Zerodha delivery charges are
    deducted on each leg (charges.py).
  * Positions still open on the last day are sold at that day's close.
  * Optional hold-out: the last N% of the period is reported separately, so
    you can judge a strategy on days it was not tuned on.
"""

import math
from bisect import bisect_right
from datetime import date
from typing import Dict, List, Optional, Sequence

import charges
import signals


class NoDataError(Exception):
    """No candles fall inside the test period."""


# --------------------------------------------------------------------- maths
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


def _trade_stats(trades: List[dict]) -> dict:
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else None,
        "avg_loss_pct": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "avg_holding_days": round(sum(t["days_held"] for t in trades) / len(trades), 1) if trades else None,
    }


# -------------------------------------------------------------------- regime
class Regime:
    """Is the index above its N-day simple moving average?

    Asked with the date of the signal day's close, so it only uses what was
    known at that moment. Unknown (not enough index history yet) counts as OFF.
    """

    def __init__(self, index_rows: Sequence[tuple], sma_period: int):
        self.period = sma_period
        self.dates = [r[0] for r in index_rows]
        self.closes = [r[4] for r in index_rows]
        self.sma = signals.sma(self.closes, sma_period)

    def is_on(self, day: Optional[str]) -> bool:
        if day is None:
            return False
        k = bisect_right(self.dates, day) - 1
        if k < 0 or self.sma[k] is None:
            return False
        return self.closes[k] > self.sma[k]


# ---------------------------------------------------------------- strategies
class CrossoverStrategy:
    """Buy the day after a bullish SMA crossover, sell the day after a bearish one."""

    name = "sma_crossover"

    def __init__(self, short_sma: int, long_sma: int, regime: Optional[Regime] = None):
        self.short_sma, self.long_sma, self.regime = short_sma, long_sma, regime
        self.regime_blocked = 0

    def prepare(self, data: Dict[str, dict]) -> None:
        for d in data.values():
            closes = [r[4] for r in d["rows"]]
            d["signals"] = {i: kind for i, kind, _, _ in signals.crossovers(closes, self.short_sma, self.long_sma)}

    def begin_day(self, day: str, prev_day: Optional[str], data: Dict[str, dict]) -> None:
        pass

    def exit_reason(self, sym: str, i: int, data: Dict[str, dict], day: str) -> Optional[str]:
        return "bearish crossover" if i > 0 and data[sym]["signals"].get(i - 1) == "bearish" else None

    def entry_candidates(self, day: str, prev_day: Optional[str], data: Dict[str, dict]) -> List[str]:
        out = []
        for sym in sorted(data):  # ticker order = who gets a free slot first
            i = data[sym]["pos"].get(day)
            if i is not None and i > 0 and data[sym]["signals"].get(i - 1) == "bullish":
                out.append(sym)
        if out and self.regime is not None and not self.regime.is_on(prev_day):
            self.regime_blocked += len(out)
            return []
        return out


class MomentumStrategy:
    """Hold the best performers, reshuffled once a month.

    Score = the stock's return from `lookback_days` trading days ago to
    `skip_days` ago (the latest month is skipped on purpose, because very recent
    winners tend to bounce back). On the first trading day of each month, and on
    the first day of the test, the stocks are ranked using the previous close:

      * a held stock is kept while it stays inside the top `keep_rank`
        (a buffer that avoids selling a stock for dropping from 10th to 11th)
      * free slots are filled from the top `top_n`, best first
      * if the regime filter says OFF, everything is sold and nothing is bought
    """

    name = "momentum"

    def __init__(self, lookback_days: int, skip_days: int, top_n: int, keep_rank: Optional[int] = None, regime: Optional[Regime] = None):
        self.lookback_days, self.skip_days, self.top_n = lookback_days, skip_days, top_n
        self.keep_rank = keep_rank or top_n * 2
        self.regime = regime
        self.regime_blocked = 0
        self.rebalances = 0
        self._started = False
        self._target: List[str] = []
        self._keep: Optional[set] = None
        self._reason = "rank dropped"

    def prepare(self, data: Dict[str, dict]) -> None:
        pass

    def _ranking(self, prev_day: str, data: Dict[str, dict]) -> List[str]:
        scored = []
        for sym, d in data.items():
            p = bisect_right(d["dates"], prev_day) - 1
            if p - self.lookback_days < 0:
                continue  # not enough history to score this stock yet
            if (date.fromisoformat(prev_day) - date.fromisoformat(d["dates"][p])).days > 7:
                continue  # no recent prices (halted or delisted)
            past = d["rows"][p - self.lookback_days][4]
            recent = d["rows"][p - self.skip_days][4]
            scored.append((-(recent / past - 1), sym))
        scored.sort()
        return [sym for _, sym in scored]

    def begin_day(self, day: str, prev_day: Optional[str], data: Dict[str, dict]) -> None:
        rebalance = prev_day is not None and (not self._started or day[:7] != prev_day[:7])
        self._started = True
        self._target, self._keep = [], None
        if not rebalance:
            return
        self.rebalances += 1
        if self.regime is not None and not self.regime.is_on(prev_day):
            self.regime_blocked += 1
            self._keep, self._reason = set(), "regime off"
            return
        ranked = self._ranking(prev_day, data)
        self._target = ranked[: self.top_n]
        self._keep = set(ranked[: self.keep_rank])
        self._reason = "rank dropped"

    def exit_reason(self, sym: str, i: int, data: Dict[str, dict], day: str) -> Optional[str]:
        if self._keep is not None and sym not in self._keep:
            return self._reason
        return None

    def entry_candidates(self, day: str, prev_day: Optional[str], data: Dict[str, dict]) -> List[str]:
        return list(self._target)


# ----------------------------------------------------------------- hold-out
def _segment(points: List[dict], base: dict, trades: List[dict]) -> dict:
    out = {
        "period": {"start": points[0]["date"], "end": points[-1]["date"], "trading_days": len(points)},
        "trades": _trade_stats(trades),
    }
    for key in ("strategy", "nifty100", "same_stocks"):
        values = [p[key] for p in points]
        if base[key] is None or any(v is None for v in values):
            out[key] = None
            continue
        out[key] = {
            "total_return_pct": round((values[-1] / base[key] - 1) * 100, 2),
            "cagr_pct": _cagr_pct(base[key], values[-1], base["date"], points[-1]["date"]),
            "max_drawdown_pct": max_drawdown_pct([base[key]] + values),
        }
    return out


def _segments(curve: List[dict], trades: List[dict], holdout_pct: float) -> Optional[dict]:
    """Report the first part and the held-out last part of the period separately."""
    n = len(curve)
    if not holdout_pct or n < 40:
        return None
    split = max(2, min(n - 2, round(n * (1 - holdout_pct / 100))))
    boundary = curve[split - 1]  # last day of the in-sample part; the base of the out-of-sample returns
    return {
        "holdout_pct": holdout_pct,
        "split_date": curve[split]["date"],
        "in_sample": _segment(curve[:split], curve[0], [t for t in trades if t["exit_date"] <= boundary["date"]]),
        "out_of_sample": _segment(curve[split:], boundary, [t for t in trades if t["exit_date"] > boundary["date"]]),
    }


# ---------------------------------------------------------------- simulation
def simulate(
    stocks: Dict[str, dict],
    strategy,
    *,
    starting_capital: float,
    max_positions: int,
    stop_loss_pct: Optional[float],
    slippage_pct: float,
    include_charges: bool,
    start_date: str,
    index_rows: Optional[list] = None,
    holdout_pct: float = 0,
) -> dict:
    """Replay a strategy.

    stocks: {symbol: {"company": str, "rows": [(date, open, high, low, close), ...]}}, oldest first.
            Rows before `start_date` are used only to warm up indicators and rankings.
    index_rows: same row format for the benchmark index, or None.
    """
    slip = slippage_pct / 100.0
    position_size = starting_capital / max_positions

    data: Dict[str, dict] = {}
    for sym in sorted(stocks):
        rows = stocks[sym]["rows"]
        data[sym] = {
            "company": stocks[sym].get("company", ""),
            "rows": rows,
            "dates": [r[0] for r in rows],
            "pos": {r[0]: i for i, r in enumerate(rows)},
        }
    strategy.prepare(data)

    all_dates = sorted({r[0] for d in data.values() for r in d["rows"]})
    first_index = bisect_right(all_dates, start_date)
    if first_index > 0 and all_dates[first_index - 1] == start_date:
        first_index -= 1
    dates = all_dates[first_index:]
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

    for k, day in enumerate(dates):
        prev_day = all_dates[first_index + k - 1] if first_index + k > 0 else None
        strategy.begin_day(day, prev_day, data)

        # 1. Exits for stocks we hold. The stop is checked first (see module docstring).
        for sym in sorted(held):
            i = data[sym]["pos"].get(day)
            if i is None:
                continue
            _, o, _, low, _ = data[sym]["rows"][i]
            stop = held[sym]["stop"]
            if stop is not None and low <= stop:
                sell(sym, day, o if o <= stop else stop, "stop-loss")
                continue
            reason = strategy.exit_reason(sym, i, data, day)
            if reason:
                sell(sym, day, o, reason)

        # 2. Entries the strategy wants today, best candidate first.
        for sym in strategy.entry_candidates(day, prev_day, data):
            i = data[sym]["pos"].get(day)
            if sym in held or i is None or i == 0:
                continue
            if len(held) >= max_positions:
                skipped["no_free_slot"] += 1
                continue
            _, o, _, low, _ = data[sym]["rows"][i]
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
    summary.update(_trade_stats(trades))
    if hasattr(strategy, "rebalances"):
        summary["rebalances"] = strategy.rebalances

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

    segments = _segments(curve, trades, holdout_pct)

    # Newest first, like the Signals table; ties by ticker.
    trades.sort(key=lambda t: t["symbol"])
    trades.sort(key=lambda t: t["entry_date"], reverse=True)

    skipped["regime_off"] = strategy.regime_blocked
    return {
        "strategy": strategy.name,
        "period": {"start": first_day, "end": last_day, "trading_days": len(dates)},
        "summary": summary,
        "benchmarks": benchmarks,
        "equity_curve": curve,
        "trades": trades,
        "signals_skipped": skipped,
        "segments": segments,
        "costs": {
            "charges": round(totals["charges"], 2),
            "slippage": round(totals["slippage"], 2),
            "total": round(totals["charges"] + totals["slippage"], 2),
        },
    }


# ------------------------------------------------- entry points per strategy
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
    regime_sma: Optional[int] = None,
    holdout_pct: float = 0,
) -> dict:
    """SMA crossover backtest. `regime_sma` turns on the regime filter (needs index_rows)."""
    regime = Regime(index_rows, regime_sma) if regime_sma and index_rows else None
    return simulate(
        stocks,
        CrossoverStrategy(short_sma, long_sma, regime),
        starting_capital=starting_capital,
        max_positions=max_positions,
        stop_loss_pct=stop_loss_pct,
        slippage_pct=slippage_pct,
        include_charges=include_charges,
        start_date=start_date,
        index_rows=index_rows,
        holdout_pct=holdout_pct,
    )


def run_momentum(
    stocks: Dict[str, dict],
    *,
    lookback_days: int,
    skip_days: int,
    top_n: int,
    keep_rank: Optional[int],
    starting_capital: float,
    stop_loss_pct: Optional[float],
    slippage_pct: float,
    include_charges: bool,
    start_date: str,
    index_rows: Optional[list] = None,
    regime_sma: Optional[int] = None,
    holdout_pct: float = 0,
) -> dict:
    """Momentum rotation backtest: `top_n` slots, one per held stock."""
    regime = Regime(index_rows, regime_sma) if regime_sma and index_rows else None
    return simulate(
        stocks,
        MomentumStrategy(lookback_days, skip_days, top_n, keep_rank, regime),
        starting_capital=starting_capital,
        max_positions=top_n,
        stop_loss_pct=stop_loss_pct,
        slippage_pct=slippage_pct,
        include_charges=include_charges,
        start_date=start_date,
        index_rows=index_rows,
        holdout_pct=holdout_pct,
    )
