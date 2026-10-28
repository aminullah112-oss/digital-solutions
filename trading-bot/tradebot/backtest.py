"""Event-driven, bar-by-bar backtester using the same Strategy and RiskManager as live.

Fill rules are deliberately pessimistic:
  * Signals are computed on bar i's close and filled at bar i+1's open + slippage.
  * An entry is cancelled if the open gaps through the stop or adds more than
    max_gap_slip_r of extra risk.
  * If a bar touches both stop and target, the stop is assumed to fill first.
  * A stop that gaps fills at the (worse) open, not at the stop price.
  * Costs and slippage are charged on both sides.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from .models import Position, Signal, Trade
from .risk import RiskManager
from .strategies import Strategy


def add_turnover(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Average daily traded value over prior days, for the liquidity gate."""
    df = df.copy()
    value = df["close"] * df["volume"]
    if mode == "swing":
        df["turnover"] = value.rolling(20, min_periods=10).mean().shift(1)
    else:
        daily = value.groupby(df.index.date).sum()
        avg = daily.rolling(10, min_periods=3).mean().shift(1)
        df["turnover"] = pd.Series(df.index.date, index=df.index).map(avg).astype(float)
    return df


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity: pd.Series
    rejections: Counter = field(default_factory=Counter)
    halts: list[tuple] = field(default_factory=list)
    config: Config | None = None


class Backtester:
    def __init__(self, cfg: Config, strategy: Strategy):
        if strategy.mode != cfg.mode:
            raise ValueError(f"strategy {strategy.name} is {strategy.mode}, config mode is {cfg.mode}")
        self.cfg = cfg
        self.strat = strategy

    def run(self, data: dict[str, pd.DataFrame], start=None, end=None) -> BacktestResult:
        """Trade only within [start, end). Indicators still see the full history
        before start, so an out-of-sample window doesn't lose its warmup."""
        cfg, strat = self.cfg, self.strat
        risk = RiskManager(cfg)
        slip, cost = cfg.costs.slippage_pct, cfg.costs.cost_pct
        intraday = cfg.mode == "intraday"
        last_entry, flatten_at = cfg.session.t("last_entry"), cfg.session.t("flatten_at")

        frames = {s: add_turnover(strat.prepare(df), cfg.mode) for s, df in data.items()}
        # Precompute "last bar of its day" so intraday positions never carry overnight.
        last_of_day = {}
        for s, df in frames.items():
            d = pd.Series(df.index.date, index=df.index)
            last_of_day[s] = (d != d.shift(-1)).to_numpy()
        timeline = sorted(set().union(*(df.index for df in frames.values())))
        if start is not None:
            timeline = [t for t in timeline if t >= start]
        if end is not None:
            timeline = [t for t in timeline if t < end]
        pos_of = {s: {ts: i for i, ts in enumerate(df.index)} for s, df in frames.items()}

        cash = cfg.initial_capital
        positions: dict[str, Position] = {}
        pending: dict[str, tuple[Signal, int, object]] = {}
        last_px: dict[str, float] = {}
        trades: list[Trade] = []
        rejections: Counter = Counter()
        halts: list[tuple] = []
        eq_t, eq_v = [], []

        def close(sym, px, ts, why):
            nonlocal cash
            p = positions.pop(sym)
            exit_cost = p.qty * px * cost
            cash += p.side * p.qty * px - exit_cost
            pnl = p.side * p.qty * (px - p.entry) - p.entry_cost - exit_cost
            t = Trade(sym, p.side, p.qty, p.entry_time, ts, p.entry, px, pnl,
                      pnl / (p.qty * p.r_per_share) if p.r_per_share else 0.0,
                      why, p.reason, p.bars_held)
            trades.append(t)
            risk.on_trade_closed(t)

        def equity():
            return cash + sum(p.side * p.qty * last_px[s] for s, p in positions.items())

        prev_day = None
        for ts in timeline:
            day = ts.date()
            if day != prev_day:
                risk.on_new_day(str(day), equity())
                prev_day = day

            for sym, df in frames.items():
                i = pos_of[sym].get(ts)
                if i is None:
                    continue
                o, h, l, c = (df[k].iat[i] for k in ("open", "high", "low", "close"))
                just_entered = False

                # 1. fill pending entry at this bar's open
                if sym in pending:
                    sig, qty, sig_ts = pending.pop(sym)
                    fill = o * (1 + sig.side * slip)
                    R = sig.risk_per_share
                    if intraday and sig_ts.date() != day:
                        rejections["entry cancelled: new session"] += 1
                    elif sig.side * (fill - sig.stop) <= 0:
                        rejections["entry cancelled: gapped through stop"] += 1
                    elif sig.target is not None and sig.side * (sig.target - fill) <= 0:
                        rejections["entry cancelled: gapped through target"] += 1
                    elif sig.side * (fill - sig.ref_price) > cfg.risk.max_gap_slip_r * R:
                        rejections["entry cancelled: adverse gap"] += 1
                    else:
                        ec = qty * fill * cost
                        cash -= sig.side * qty * fill + ec
                        positions[sym] = Position(sym, sig.side, qty, fill, sig.stop, sig.stop,
                                                  sig.target, ts, sig.max_bars, sig.reason,
                                                  entry_cost=ec)
                        just_entered = True

                # 2. exits on this bar
                p = positions.get(sym)
                if p is not None:
                    s = p.side
                    exit_px = why = None
                    if not just_entered and s * (o - p.stop) <= 0:
                        exit_px, why = o * (1 - s * slip), "stop (gap)"
                    elif not just_entered and p.target is not None and s * (o - p.target) >= 0:
                        exit_px, why = o, "target (gap)"
                    else:
                        hit_stop = (l <= p.stop) if s > 0 else (h >= p.stop)
                        hit_tgt = p.target is not None and ((h >= p.target) if s > 0 else (l <= p.target))
                        if hit_stop:
                            exit_px = p.stop * (1 - s * slip)
                            why = "trailing stop" if p.stop != p.initial_stop else "stop"
                        elif hit_tgt:
                            exit_px, why = p.target, "target"
                    if exit_px is None:
                        p.bars_held += 1
                        p.best_price = max(p.best_price, h) if s > 0 else min(p.best_price, l)
                        if intraday and (ts.time() >= flatten_at or last_of_day[sym][i]):
                            exit_px, why = c * (1 - s * slip), "end of day"
                        elif p.max_bars and p.bars_held >= p.max_bars:
                            exit_px, why = c * (1 - s * slip), "time stop"
                        else:
                            p.stop = strat.update_stop(p, df, i)
                    if exit_px is not None:
                        close(sym, exit_px, ts, why)
                last_px[sym] = c

            eq = equity()
            risk.on_equity(eq)
            if flat_why := risk.must_flatten():
                if positions or pending:
                    halts.append((ts, flat_why))
                for sym in list(positions):
                    p = positions[sym]
                    close(sym, last_px[sym] * (1 - p.side * slip), ts, f"risk flatten: {flat_why}")
                pending.clear()
                eq = equity()

            # 3. new signals on this bar's close
            if not risk.halted():
                for sym, df in frames.items():
                    i = pos_of[sym].get(ts)
                    if i is None or i < strat.warmup or sym in positions or sym in pending:
                        continue
                    if intraday and (ts.time() >= last_entry or last_of_day[sym][i]):
                        continue
                    sig = strat.signal(sym, df, i, cfg.allow_short)
                    if sig is None:
                        continue
                    committed = dict(positions)
                    for ps, (psig, pq, _) in pending.items():
                        committed[ps] = Position(ps, psig.side, pq, psig.ref_price, psig.stop,
                                                 psig.stop, None, ts)
                    turnover = df["turnover"].iat[i]
                    qty, why = risk.size(sig, eq, committed,
                                         None if np.isnan(turnover) else float(turnover),
                                         float(df["volume"].iat[i]))
                    if qty:
                        pending[sym] = (sig, qty, ts)
                    else:
                        rejections[re.sub(r"-?[\d][\d.,]*", "#", why)] += 1
            else:
                pending.clear()

            eq_t.append(ts)
            eq_v.append(eq)

        for sym in list(positions):
            p = positions[sym]
            close(sym, last_px[sym] * (1 - p.side * slip), eq_t[-1], "end of data")
        if eq_v:
            eq_v[-1] = cash

        return BacktestResult(trades, pd.Series(eq_v, index=pd.DatetimeIndex(eq_t)),
                              rejections, halts, cfg)
