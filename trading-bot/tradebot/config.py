"""Configuration. Every number that changes behaviour lives here, loaded from JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import time
from pathlib import Path


@dataclass
class Session:
    timezone: str = "Asia/Kolkata"
    open: str = "09:15"
    close: str = "15:30"
    # Intraday: no new entries after this, and everything is flat by flatten_at.
    last_entry: str = "14:45"
    flatten_at: str = "15:15"
    # Weekdays from this time until the close, the bot checks the broker session
    # and alerts if a login is needed.
    login_reminder: str = "08:45"

    def t(self, name: str) -> time:
        h, m = getattr(self, name).split(":")
        return time(int(h), int(m))


@dataclass
class Costs:
    # Per side, as a fraction of notional. NSE equity intraday all-in (brokerage,
    # STT, exchange, GST, stamp) is roughly 0.03-0.05% per side; delivery is
    # higher because STT applies on both sides at 0.1%.
    cost_pct: float = 0.0005
    # Adverse fill vs. the reference price, per side.
    slippage_pct: float = 0.0005


@dataclass
class Risk:
    risk_per_trade_pct: float = 0.5        # % of equity lost if the stop is hit
    max_position_pct: float = 20.0         # notional cap per position, % of equity
    max_gross_exposure_pct: float = 100.0  # sum of open notionals; 100 = no leverage
    max_open_positions: int = 5
    max_open_risk_pct: float = 3.0         # sum of (entry - stop) * qty over open positions
    max_volume_pct: float = 1.0            # qty <= this % of the signal bar's volume
    daily_loss_limit_pct: float = 2.0      # stop trading for the day past this
    max_drawdown_pct: float = 15.0         # hard halt from equity peak; manual reset
    loss_streak_reduce: int = 3            # halve risk after this many losses in a row
    loss_streak_halt: int = 5              # stop for the day after this many
    max_stop_pct: float = 8.0              # reject trades whose stop is wider than this
    min_reward_risk: float = 1.5           # only enforced when a strategy sets a target
    min_price: float = 20.0
    min_avg_turnover: float = 5e7          # 20-bar average close*volume (₹5 crore)
    max_gap_slip_r: float = 0.5            # cancel entry if the fill adds > this much R


@dataclass
class Config:
    mode: str = "intraday"                 # "intraday" or "swing"
    strategy: str = "orb"
    strategy_params: dict = field(default_factory=dict)
    symbols: list = field(default_factory=list)
    interval: str = "5minute"
    allow_short: bool = False
    # Hard cap on bars held, applied on top of any strategy's own time stop.
    # For swing with daily bars, 10 = ten trading days (about two calendar weeks).
    max_hold_bars: int | None = None
    initial_capital: float = 500_000.0
    session: Session = field(default_factory=Session)
    costs: Costs = field(default_factory=Costs)
    risk: Risk = field(default_factory=Risk)
    state_file: str = "state/bot_state.json"
    kill_switch_file: str = "STOP"

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        raw = json.loads(Path(path).read_text())
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "Config":
        nested = {"session": Session, "costs": Costs, "risk": Risk}
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        kwargs = {}
        for k, v in raw.items():
            if k in nested:
                sub_known = {f.name for f in fields(nested[k])}
                bad = set(v) - sub_known
                if bad:
                    raise ValueError(f"unknown {k} keys: {sorted(bad)}")
                kwargs[k] = nested[k](**v)
            else:
                kwargs[k] = v
        cfg = cls(**kwargs)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.mode not in ("intraday", "swing"):
            raise ValueError("mode must be 'intraday' or 'swing'")
        if self.max_hold_bars is not None and self.max_hold_bars < 1:
            raise ValueError("max_hold_bars must be >= 1")
        r = self.risk
        if not 0 < r.risk_per_trade_pct <= 2:
            raise ValueError("risk_per_trade_pct must be in (0, 2]; above 2% per trade is gambling")
        if r.max_open_risk_pct < r.risk_per_trade_pct:
            raise ValueError("max_open_risk_pct must be >= risk_per_trade_pct")
        if r.daily_loss_limit_pct < r.risk_per_trade_pct:
            raise ValueError("daily_loss_limit_pct must be >= risk_per_trade_pct")
        if r.max_gross_exposure_pct > 100 and self.mode == "swing":
            raise ValueError("leverage on swing positions is not allowed by this bot")

    def hold_limit(self, strategy_max: int | None) -> int | None:
        caps = [b for b in (strategy_max, self.max_hold_bars) if b]
        return min(caps) if caps else None

    def to_dict(self) -> dict:
        return asdict(self)
