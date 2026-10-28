from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Signal:
    """Generated on the close of a bar; filled at the next bar's open."""
    symbol: str
    side: int                  # +1 long, -1 short
    ref_price: float           # close of the signal bar
    stop: float
    target: float | None = None
    max_bars: int | None = None  # time stop
    reason: str = ""

    @property
    def risk_per_share(self) -> float:
        return abs(self.ref_price - self.stop)


@dataclass
class Position:
    symbol: str
    side: int
    qty: int
    entry: float
    stop: float
    initial_stop: float
    target: float | None
    entry_time: pd.Timestamp
    max_bars: int | None = None
    reason: str = ""
    bars_held: int = 0
    best_price: float = 0.0    # highest high (long) / lowest low (short) since entry
    entry_cost: float = 0.0
    broker_stop_id: str | None = None
    stop_qty: int = 0              # quantity the live stop covers; resized when qty changes
    stop_tag: str | None = None    # stop placement whose outcome is being resolved
    exit_tag: str | None = None    # exit order whose outcome is being resolved
    exit_wanted: str = ""          # exit reason, retried until it completes
    through: int = 0               # cycles price has been through an OPEN stop
    stop_uncertain: bool = False   # broker cannot confirm that the stop is active

    def __post_init__(self):
        if not self.best_price:
            self.best_price = self.entry

    @property
    def r_per_share(self) -> float:
        return abs(self.entry - self.initial_stop)

    @property
    def notional(self) -> float:
        return self.qty * self.entry

    def open_r(self, price: float) -> float:
        return self.side * (price - self.entry) / self.r_per_share if self.r_per_share else 0.0


@dataclass
class Trade:
    symbol: str
    side: int
    qty: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    exit: float
    pnl: float                 # net of costs
    r_multiple: float
    exit_reason: str
    reason: str = ""
    bars_held: int = 0


@dataclass
class Order:
    symbol: str
    side: int
    qty: int
    kind: str = "market"       # market | stop
    price: float | None = None
    tag: str = ""
    id: str = ""
    status: str = "open"
    fill_price: float | None = None
    meta: dict = field(default_factory=dict)
