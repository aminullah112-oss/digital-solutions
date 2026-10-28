"""Portfolio-level risk. The strategy proposes; this module decides whether and how much.

Order of defence:
  1. Per-trade: fixed fractional sizing off the stop distance (incl. costs), so a
     stopped-out trade costs ~risk_per_trade_pct of equity, not more.
  2. Per-position and gross exposure caps, max concurrent positions.
  3. Trade quality gates: stop width, reward:risk, price, liquidity.
  4. Loss streak: halve size after N losses in a row, stop for the day after M.
  5. Daily loss limit: no new entries for the rest of the day (intraday: flatten).
  6. Max drawdown from peak: flatten everything and halt until a human resets it.
  7. Entry block: broker state disagrees with the bot's. No new entries, no
     automatic exits (acting on uncertain state can double-exit); a human checks
     the account and runs `reset`.

All of this state is persisted by the live engine, so a restart does not clear it.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

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
             avg_turnover: float | None = None, bar_volume: float | None = None) -> tuple[int, str]:
        """Return (qty, "") to trade, or (0, reason) to reject."""
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

        c = self.cfg.costs
        round_trip = 2 * px * (c.cost_pct + c.slippage_pct)
        risk_ps = sig.risk_per_share + round_trip
        if sig.target is not None:
            reward = abs(sig.target - px) - round_trip
            if reward / risk_ps < r.min_reward_risk:
                return 0, f"reward:risk {reward / risk_ps:.2f} after costs < {r.min_reward_risk}"

        risk_amt = equity * r.risk_per_trade_pct / 100 * self.risk_multiplier()
        qty = math.floor(risk_amt / risk_ps)
        qty = min(qty, math.floor(equity * r.max_position_pct / 100 / px))
        gross = sum(p.notional for p in positions.values())
        room = equity * r.max_gross_exposure_pct / 100 - gross
        qty = min(qty, math.floor(max(room, 0) / px))
        if bar_volume is not None and r.max_volume_pct:
            qty = min(qty, math.floor(bar_volume * r.max_volume_pct / 100))
        budget = equity * r.max_open_risk_pct / 100 - self.open_risk(positions)
        qty = min(qty, math.floor(max(budget, 0) / risk_ps))
        if qty < 1:
            return 0, "size rounds to zero (caps, open-risk budget or volume limit)"
        return qty, ""

    def to_dict(self) -> dict:
        return asdict(self.state)
