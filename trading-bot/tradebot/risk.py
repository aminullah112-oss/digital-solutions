"""Portfolio-level risk. The strategy proposes; this module decides whether and how much.

Order of defence:
  1. Per-trade: fixed fractional sizing off the stop distance (incl. costs), so a
     stopped-out trade costs ~risk_per_trade_pct of equity, not more.
  2. Per-position and gross exposure caps, max concurrent positions.
  3. Trade quality gates: stop width, reward:risk, price, liquidity.
  4. Loss streak: halve size after N losses in a row, stop for the day after M.
  5. Daily loss limit: no new entries for the rest of the day (intraday: flatten).
  6. Max drawdown from peak: flatten everything and halt until a human resets it.
  7. Concentration: at most N positions and X% open risk per sector, and a
     correlated-risk budget so five banks don't count as five independent bets.
  8. Entry block: broker state disagrees with the bot's. No new entries, no
     automatic exits (acting on uncertain state can double-exit); a human checks
     the account and runs `reset`.

All of this state is persisted by the live engine, so a restart does not clear it.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Callable

import pandas as pd

from .config import Config
from .models import Position, Signal, Trade


@dataclass
class RiskState:
    peak_equity: float
    day: str = ""
    day_start_equity: float = 0.0
    loss_streak: int = 0
    day_halted: str = ""        # reason, cleared on a new day
    hard_halted: str = ""       # reason, cleared only by reset()
    entry_block: str = ""       # reason, cleared only by reset(); blocks entries, never flattens


class Correlations:
    """Correlation of daily close-to-close returns between symbols, using only
    days strictly before `asof` so a backtest can't peek at the signal day."""

    def __init__(self, closes: dict[str, pd.Series], lookback: int = 60, min_obs: int = 30):
        df = pd.DataFrame(closes).sort_index()
        self.rets = df.pct_change(fill_method=None)
        self.lookback, self.min_obs = lookback, min_obs
        self._memo: dict = {}

    @staticmethod
    def daily_closes(df: pd.DataFrame) -> pd.Series:
        s = df["close"].groupby(df.index.date).last()
        s.index = pd.to_datetime(s.index)
        return s

    @classmethod
    def from_frames(cls, frames: dict[str, pd.DataFrame], lookback: int = 60) -> "Correlations":
        return cls({s: cls.daily_closes(df) for s, df in frames.items()}, lookback)

    def corr(self, a: str, b: str, asof) -> float | None:
        if a == b:
            return 1.0
        if a not in self.rets or b not in self.rets:
            return None
        day = pd.Timestamp(pd.Timestamp(asof).date())
        key = (min(a, b), max(a, b), day)
        if key not in self._memo:
            i = self.rets.index.searchsorted(day, side="left")
            w = self.rets[[a, b]].iloc[max(0, i - self.lookback):i].dropna()
            rho = w[a].corr(w[b]) if len(w) >= self.min_obs else float("nan")
            self._memo[key] = None if pd.isna(rho) else float(rho)
        return self._memo[key]


class RiskManager:
    def __init__(self, cfg: Config, state: dict | None = None):
        self.cfg = cfg
        self.r = cfg.risk
        self.state = RiskState(**state) if state else RiskState(peak_equity=cfg.initial_capital)

    # ------------------------------------------------------------ state updates
    def on_new_day(self, day: str, equity: float) -> None:
        if day == self.state.day:
            return
        self.state.day = day
        self.state.day_start_equity = equity
        self.state.day_halted = ""
        # A loss streak that triggered a day halt shouldn't also cut size forever:
        # reset to the reduce threshold so the next loss still keeps size halved.
        if self.state.loss_streak >= self.r.loss_streak_halt:
            self.state.loss_streak = self.r.loss_streak_reduce

    def on_equity(self, equity: float) -> None:
        s = self.state
        s.peak_equity = max(s.peak_equity, equity)
        dd = 100 * (1 - equity / s.peak_equity)
        if dd >= self.r.max_drawdown_pct and not s.hard_halted:
            s.hard_halted = f"max drawdown {dd:.1f}% >= {self.r.max_drawdown_pct}%"
        if s.day_start_equity:
            day_pnl = 100 * (equity / s.day_start_equity - 1)
            if day_pnl <= -self.r.daily_loss_limit_pct and not s.day_halted:
                s.day_halted = f"daily loss {day_pnl:.2f}% hit limit {self.r.daily_loss_limit_pct}%"

    def on_trade_closed(self, t: Trade) -> None:
        s = self.state
        s.loss_streak = s.loss_streak + 1 if t.pnl < 0 else 0
        if s.loss_streak >= self.r.loss_streak_halt and not s.day_halted:
            s.day_halted = f"{s.loss_streak} losses in a row"

    def block_entries(self, why: str) -> None:
        if not self.state.entry_block:
            self.state.entry_block = why

    def reset(self, equity: float) -> None:
        """Manual reset after a hard halt. Re-bases the peak at current equity."""
        self.state.hard_halted = ""
        self.state.entry_block = ""
        self.state.day_halted = ""
        self.state.loss_streak = 0
        self.state.peak_equity = equity

    # ---------------------------------------------------------------- queries
    def halted(self) -> str:
        return self.state.hard_halted or self.state.entry_block or self.state.day_halted

    def must_flatten(self) -> str:
        """Reasons that require closing open positions right now."""
        if self.state.hard_halted:
            return self.state.hard_halted
        if self.cfg.mode == "intraday" and self.state.day_halted:
            return self.state.day_halted
        return ""

    def risk_multiplier(self) -> float:
        return 0.5 if self.state.loss_streak >= self.r.loss_streak_reduce else 1.0

    @staticmethod
    def open_risk(positions: dict[str, Position]) -> float:
        """Money lost if every open position hit its current stop (0 once a stop is
        at or past breakeven). Gaps can make the real loss larger."""
        return sum(p.qty * max(0.0, p.side * (p.entry - p.stop)) for p in positions.values())

    def size(self, sig: Signal, equity: float, positions: dict[str, Position],
             avg_turnover: float | None = None, bar_volume: float | None = None,
             corr: Callable[[str, str], float | None] | None = None) -> tuple[int, str]:
        """Return (qty, "") to trade, or (0, reason) to reject. `corr(a, b)` gives
        the correlation of two symbols' daily returns, or None if unknown."""
        r = self.r
        if why := self.halted():
            return 0, f"halted: {why}"
        if sig.symbol in positions:
            return 0, "already in position"
        if len(positions) >= r.max_open_positions:
            return 0, "max open positions"
        px = sig.ref_price
        if px < r.min_price:
            return 0, f"price {px:.2f} < min {r.min_price}"
        if avg_turnover is not None and avg_turnover < r.min_avg_turnover:
            return 0, f"illiquid: avg turnover {avg_turnover:,.0f}"
        if sig.side * (px - sig.stop) <= 0:
            return 0, "stop on wrong side of price"
        stop_pct = 100 * sig.risk_per_share / px
        if stop_pct > r.max_stop_pct:
            return 0, f"stop {stop_pct:.1f}% wider than {r.max_stop_pct}%"
        sectors = self.cfg.sectors
        sector = sectors.get(sig.symbol) if sectors else None
        same_sector = {s: p for s, p in positions.items() if sector and sectors.get(s) == sector}
        if sector and len(same_sector) >= r.max_sector_positions:
            return 0, f"sector {sector}: {len(same_sector)} positions already (max {r.max_sector_positions})"

        c = self.cfg.costs
        round_trip = 2 * px * (c.cost_pct + c.slippage_pct)
        risk_ps = sig.risk_per_share + round_trip
        if sig.target is not None:
            reward = abs(sig.target - px) - round_trip
            if reward / risk_ps < r.min_reward_risk:
                return 0, f"reward:risk {reward / risk_ps:.2f} after costs < {r.min_reward_risk}"

        def by_risk(budget: float) -> int:
            return math.floor(max(budget, 0) / risk_ps)

        pct = equity / 100
        gross = sum(p.notional for p in positions.values())
        limits = [
            ("risk per trade", by_risk(pct * r.risk_per_trade_pct * self.risk_multiplier())),
            ("position size cap", math.floor(pct * r.max_position_pct / px)),
            ("gross exposure cap", math.floor(max(pct * r.max_gross_exposure_pct - gross, 0) / px)),
            ("open-risk budget", by_risk(pct * r.max_open_risk_pct - self.open_risk(positions))),
        ]
        if bar_volume is not None and r.max_volume_pct:
            limits.append(("volume participation", math.floor(bar_volume * r.max_volume_pct / 100)))
        if sector:
            limits.append((f"sector {sector} risk budget",
                           by_risk(pct * r.max_sector_risk_pct - self.open_risk(same_sector))))
        if corr is not None and r.max_correlated_risk_pct:
            load = self.correlated_load(sig, positions, corr)
            limits.append(("correlated-risk budget", by_risk(pct * r.max_correlated_risk_pct - load)))
        name, qty = min(limits, key=lambda x: x[1])
        if qty < 1:
            return 0, f"size zero: {name} exhausted"
        return qty, ""

    def correlated_load(self, sig: Signal, positions: dict[str, Position],
                        corr: Callable[[str, str], float | None]) -> float:
        """Open risk that would move with the candidate: each same-direction
        position's risk to its stop, weighted by max(0, correlation). Opposite-side
        positions get no hedge credit (correlations break down in sell-offs)."""
        load = 0.0
        for s, p in positions.items():
            if p.side != sig.side:
                continue
            rho = corr(sig.symbol, s)
            rho = self.r.corr_unknown if rho is None else rho
            load += max(0.0, rho) * p.qty * max(0.0, p.side * (p.entry - p.stop))
        return load

    def to_dict(self) -> dict:
        return asdict(self.state)
