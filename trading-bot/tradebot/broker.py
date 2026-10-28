"""Broker interface and a paper broker.

Sides are transaction sides: +1 buy, -1 sell. A protective stop for a long is a
sell stop (side -1)."""
from __future__ import annotations

import itertools
import logging
from abc import ABC, abstractmethod
from typing import NamedTuple

import pandas as pd


log = logging.getLogger("tradebot.paper")


class BrokerError(RuntimeError):
    pass


class OrderUnknown(BrokerError):
    """An order request timed out and the order can't be found in the order book.
    It may still exist. The engine blocks new entries until a human checks."""


class Fill(NamedTuple):
    price: float
    qty: int      # may be less than requested (partial fill); never more


class Broker(ABC):
    @abstractmethod
    def bars(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame: ...

    @abstractmethod
    def ltp(self, symbol: str) -> float: ...

    @abstractmethod
    def market(self, symbol: str, side: int, qty: int, tag: str = "") -> Fill:
        """Place a market order and block until it is terminal. Returns what actually
        filled, including a partial fill. Raises only if nothing filled."""

    @abstractmethod
    def place_stop(self, symbol: str, side: int, qty: int, trigger: float, tag: str = "") -> str: ...

    @abstractmethod
    def modify_stop(self, order_id: str, trigger: float) -> None: ...

    @abstractmethod
    def cancel(self, order_id: str) -> bool:
        """True if cancelled; False if it had already filled or was gone."""

    @abstractmethod
    def order_status(self, order_id: str) -> tuple[str, float | None]:
        """(status, avg_price). status in OPEN, COMPLETE, CANCELLED, REJECTED."""

    @abstractmethod
    def net_positions(self) -> dict[str, int]: ...

    def to_dict(self) -> dict:
        return {}


class YFinanceFeed:
    """Delayed public data for paper trading. Not suitable for live execution."""

    def __init__(self, tz: str, suffix: str = ".NS"):
        self.tz, self.suffix = tz, suffix

    def bars(self, symbol, interval, lookback_days):
        from .data import download_yfinance
        return download_yfinance(symbol + self.suffix, interval, f"{max(lookback_days, 1)}d", self.tz)

    def ltp(self, symbol):
        return float(self.bars(symbol, "minute", 1)["close"].iloc[-1])


FAULT_KINDS = ("reject", "partial", "timeout", "stop_reject", "stop_cancel")


def parse_faults(spec: str | None) -> dict[str, float]:
    """'reject=0.05,partial=0.1' -> {'reject': 0.05, 'partial': 0.1}"""
    out: dict[str, float] = {}
    for part in filter(None, (spec or "").split(",")):
        k, _, v = part.partition("=")
        k = k.strip()
        if k not in FAULT_KINDS:
            raise ValueError(f"unknown fault {k!r}; choose from {FAULT_KINDS}")
        p = float(v)
        if not 0 <= p <= 1:
            raise ValueError(f"fault {k} probability must be in [0, 1]")
        out[k] = p
    return out


class PaperBroker(Broker):
    """Simulated execution on top of any data feed (yfinance, or a real broker's
    data). Market orders fill at last price +/- slippage; stops are checked
    against each new price and against bar lows/highs printed since placement.

    Optional fault injection, so paper runs exercise the engine's recovery code
    (there's no Kite sandbox to do this against). Probabilities per call:
      reject       market order rejected, nothing fills
      partial      market order fills 30-90% of the requested quantity
      timeout      the order IS placed/filled, but the call raises OrderUnknown
      stop_reject  stop order rejected
      stop_cancel  an open stop is found cancelled (expiry, broker-side cancel)
    """

    def __init__(self, feed, slippage_pct: float = 0.0005, state: dict | None = None,
                 faults: dict[str, float] | None = None, seed: int | None = None):
        import random
        self.feed = feed
        self.slip = slippage_pct
        state = state or {}
        self.pos: dict[str, int] = state.get("pos", {})
        self.orders: dict[str, dict] = state.get("orders", {})
        self._ids = itertools.count(len(self.orders) + 1)
        self._last_bars: dict[str, pd.DataFrame] = {}
        self.faults = faults or {}
        self._rng = random.Random(seed)
        self.injected: list[tuple[str, str]] = []

    def _fault(self, kind: str, symbol: str) -> bool:
        p = self.faults.get(kind, 0)
        if p and self._rng.random() < p:
            self.injected.append((kind, symbol))
            log.warning("[fault injected] %s on %s", kind, symbol)
            return True
        return False

    def bars(self, symbol, interval, lookback_days):
        df = self.feed.bars(symbol, interval, lookback_days)
        self._last_bars[symbol] = df
        self._check_stops(symbol)
        return df

    def ltp(self, symbol):
        if hasattr(self.feed, "ltp"):
            return float(self.feed.ltp(symbol))
        return float(self._last_bars[symbol]["close"].iloc[-1])

    def market(self, symbol, side, qty, tag=""):
        if self._fault("reject", symbol):
            raise BrokerError(f"simulated rejection of {tag or 'market'} order for {symbol}")
        if qty > 1 and self._fault("partial", symbol):
            qty = max(1, int(qty * self._rng.uniform(0.3, 0.9)))
        px = self.ltp(symbol) * (1 + side * self.slip)
        self.pos[symbol] = self.pos.get(symbol, 0) + side * qty
        if self.pos[symbol] == 0:
            del self.pos[symbol]
        if self._fault("timeout", symbol):
            raise OrderUnknown(f"simulated timeout: {tag or 'market'} order for {symbol} (it did fill)")
        return Fill(px, qty)

    def place_stop(self, symbol, side, qty, trigger, tag=""):
        if self._fault("stop_reject", symbol):
            raise BrokerError(f"simulated stop rejection for {symbol}")
        oid = f"P{next(self._ids)}"
        self.orders[oid] = dict(symbol=symbol, side=side, qty=qty, trigger=trigger,
                                status="OPEN", avg_price=None,
                                placed=str(pd.Timestamp.now(tz="UTC")))
        if self._fault("timeout", symbol):
            raise OrderUnknown(f"simulated timeout placing stop for {symbol} (order {oid} exists)")
        return oid

    def modify_stop(self, order_id, trigger):
        o = self.orders[order_id]
        if o["status"] != "OPEN":
            raise BrokerError(f"cannot modify {order_id}: {o['status']}")
        o["trigger"] = trigger

    def cancel(self, order_id):
        o = self.orders.get(order_id)
        if o is None or o["status"] != "OPEN":
            return False
        self._check_stops(o["symbol"])
        if o["status"] != "OPEN":
            return False
        o["status"] = "CANCELLED"
        return True

    def order_status(self, order_id):
        o = self.orders[order_id]
        if o["status"] == "OPEN":
            self._check_stops(o["symbol"])
        if o["status"] == "OPEN" and self._fault("stop_cancel", o["symbol"]):
            o["status"] = "CANCELLED"
        return o["status"], o["avg_price"]

    def net_positions(self):
        return dict(self.pos)

    def _check_stops(self, symbol):
        open_orders = [(k, o) for k, o in self.orders.items() if o["symbol"] == symbol and o["status"] == "OPEN"]
        if not open_orders:
            return
        df = self._last_bars.get(symbol)
        for _, o in open_orders:
            placed = pd.Timestamp(o["placed"])
            extreme = None
            if df is not None:
                recent = df[df.index.tz_convert("UTC") >= placed.floor("min")]
                if len(recent):
                    extreme = recent["low"].min() if o["side"] < 0 else recent["high"].max()
            try:
                px = self.ltp(symbol)
            except Exception:
                px = None
            probes = [x for x in (extreme, px) if x is not None]
            if not probes:
                continue
            worst = min(probes) if o["side"] < 0 else max(probes)
            if (o["side"] < 0 and worst <= o["trigger"]) or (o["side"] > 0 and worst >= o["trigger"]):
                o["status"] = "COMPLETE"
                o["avg_price"] = o["trigger"] * (1 + o["side"] * self.slip)
                self.pos[symbol] = self.pos.get(symbol, 0) + o["side"] * o["qty"]
                if self.pos[symbol] == 0:
                    del self.pos[symbol]

    def to_dict(self):
        return {"pos": self.pos, "orders": self.orders}
