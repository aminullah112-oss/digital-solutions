"""Broker interface and a paper broker.

Sides are transaction sides: +1 buy, -1 sell. A protective stop for a long is a
sell stop (side -1).

Order lifecycle contract (what the engine relies on):
  * The ENGINE chooses every order's tag (unique, <= 20 chars) and passes it in,
    so an order whose request timed out can be found later with find_by_tag().
  * An ambiguous request raises OrderUnknown. The order may or may not exist,
    and may appear later. The engine records it and resolves it by tag.
  * cancel() reports the order's state after trying, as an OrderState. Only
    CANCELLED/REJECTED mean "it will not fill"; COMPLETE means it filled (maybe
    partly: check .filled); OPEN or UNKNOWN mean it may still fill.
"""
from __future__ import annotations

import itertools
import logging
from abc import ABC, abstractmethod
from typing import NamedTuple

import pandas as pd


log = logging.getLogger("tradebot.paper")

TERMINAL = ("COMPLETE", "CANCELLED", "REJECTED")


class BrokerError(RuntimeError):
    pass


class TokenExpired(Exception):
    """Broker session is missing, expired or rejected. Deliberately NOT a
    BrokerError: it must stop the whole cycle, not be retried per symbol."""


class OrderUnknown(BrokerError):
    """An order request timed out and its outcome is unknown. The order may exist
    now or appear later; the engine resolves it by tag."""


class Fill(NamedTuple):
    price: float
    qty: int      # may be less than requested (partial fill); never more


class OrderState(NamedTuple):
    status: str                 # OPEN | COMPLETE | CANCELLED | REJECTED | UNKNOWN
    filled: int = 0             # quantity filled so far (a CANCELLED order can be partly filled)
    avg: float | None = None

    @property
    def final(self) -> bool:
        """True when the order can no longer fill any further."""
        return self.status in TERMINAL


class Broker(ABC):
    @abstractmethod
    def bars(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame: ...

    @abstractmethod
    def ltp(self, symbol: str) -> float: ...

    @abstractmethod
    def market(self, symbol: str, side: int, qty: int, tag: str) -> Fill:
        """Place a market order and block until it is terminal. Returns what actually
        filled, including a partial fill. Raises BrokerError if nothing filled, or
        OrderUnknown if the outcome can't be determined."""

    @abstractmethod
    def place_stop(self, symbol: str, side: int, qty: int, trigger: float, tag: str) -> str:
        """Protective stop. Brokers should use an order that survives overnight
        where the product allows it (Kite: GTT for CNC)."""

    @abstractmethod
    def modify_stop(self, order_id: str, trigger: float) -> None: ...

    @abstractmethod
    def cancel(self, order_id: str) -> OrderState:
        """Request cancellation and report the state that follows. Never assume
        the order is dead unless the result is final."""

    @abstractmethod
    def order_status(self, order_id: str) -> OrderState: ...

    @abstractmethod
    def find_by_tag(self, tag: str, hint: dict | None = None) -> tuple[str, OrderState] | None:
        """Locate an order the engine placed with this tag, or None if not visible.
        `hint` is the engine's pending record (symbol, side, qty, trigger), for
        order types that can't carry a tag (Kite GTT)."""

    @abstractmethod
    def net_positions(self) -> dict[str, int]: ...

    def auth_status(self, now=None) -> tuple[bool, str]:
        """(ok, detail). Brokers with expiring sessions override this."""
        return True, ""

    def history(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        """Bars for analysis only (e.g. daily closes for correlations). Unlike
        bars(), must not affect order simulation."""
        return self.bars(symbol, interval, lookback_days)

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


FAULT_KINDS = ("reject", "partial", "timeout", "late", "stop_reject", "stop_cancel",
               "cancel_unconfirmed")


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
    Stops never expire on their own (like GTT); `stop_cancel` simulates expiry.

    Optional fault injection, so paper runs exercise the engine's recovery code
    (there's no Kite sandbox to do this against). Probabilities per call:
      reject              market order rejected, nothing fills
      partial             market order fills 30-90% of the requested quantity
      timeout             the order IS placed/filled, but the call raises OrderUnknown
      late                like timeout, and the order stays invisible to find_by_tag
                          for the next 3 lookups (delayed order-book visibility)
      stop_reject         stop order rejected
      stop_cancel         an open stop is found cancelled (expiry, broker-side cancel)
      cancel_unconfirmed  a cancel request goes unanswered; the order stays OPEN
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

    def auth_status(self, now=None):
        # Paper on Kite data still needs a live Kite session for the data.
        return self.feed.auth_status(now) if hasattr(self.feed, "auth_status") else (True, "")

    def bars(self, symbol, interval, lookback_days):
        df = self.feed.bars(symbol, interval, lookback_days)
        self._last_bars[symbol] = df
        self._check_stops(symbol)
        return df

    def history(self, symbol, interval, lookback_days):
        return self.feed.bars(symbol, interval, lookback_days)

    def ltp(self, symbol):
        if hasattr(self.feed, "ltp"):
            return float(self.feed.ltp(symbol))
        return float(self._last_bars[symbol]["close"].iloc[-1])

    def _new(self, **o) -> str:
        oid = f"P{next(self._ids)}"
        o.setdefault("placed", str(pd.Timestamp.now(tz="UTC")))
        o.setdefault("hidden", 0)
        self.orders[oid] = o
        return oid

    def _ambiguous(self, symbol: str, oid: str, what: str):
        if self._fault("late", symbol):
            self.orders[oid]["hidden"] = 3
            raise OrderUnknown(f"simulated timeout ({what}, {symbol}); order {oid} appears late")
        if self._fault("timeout", symbol):
            raise OrderUnknown(f"simulated timeout ({what}, {symbol}); order {oid} exists")

    def _apply(self, symbol: str, delta: int):
        self.pos[symbol] = self.pos.get(symbol, 0) + delta
        if self.pos[symbol] == 0:
            del self.pos[symbol]

    def market(self, symbol, side, qty, tag=""):
        if self._fault("reject", symbol):
            self._new(symbol=symbol, side=side, qty=qty, kind="market", tag=tag, status="REJECTED",
                      filled=0, avg_price=None)
            raise BrokerError(f"simulated rejection of {tag or 'market'} order for {symbol}")
        filled = qty
        if qty > 1 and self._fault("partial", symbol):
            filled = max(1, int(qty * self._rng.uniform(0.3, 0.9)))
        px = self.ltp(symbol) * (1 + side * self.slip)
        self._apply(symbol, side * filled)
        oid = self._new(symbol=symbol, side=side, qty=qty, kind="market", tag=tag,
                        status="COMPLETE" if filled == qty else "CANCELLED", filled=filled, avg_price=px)
        self._ambiguous(symbol, oid, tag or "market")
        return Fill(px, filled)

    def place_stop(self, symbol, side, qty, trigger, tag=""):
        if self._fault("stop_reject", symbol):
            self._new(symbol=symbol, side=side, qty=qty, kind="stop", tag=tag, trigger=trigger,
                      status="REJECTED", filled=0, avg_price=None)
            raise BrokerError(f"simulated stop rejection for {symbol}")
        oid = self._new(symbol=symbol, side=side, qty=qty, kind="stop", tag=tag, trigger=trigger,
                        status="OPEN", filled=0, avg_price=None)
        self._ambiguous(symbol, oid, "stop")
        return oid

    def modify_stop(self, order_id, trigger):
        o = self.orders[order_id]
        if o["status"] != "OPEN":
            raise BrokerError(f"cannot modify {order_id}: {o['status']}")
        o["trigger"] = trigger

    @staticmethod
    def _state(o) -> OrderState:
        return OrderState(o["status"], o.get("filled", 0), o.get("avg_price"))

    def cancel(self, order_id):
        o = self.orders.get(order_id)
        if o is None:
            return OrderState("UNKNOWN")
        self._check_stops(o["symbol"])
        if o["status"] != "OPEN":
            return self._state(o)
        if self._fault("cancel_unconfirmed", o["symbol"]):
            return OrderState("UNKNOWN")         # request lost; order is still live
        o["status"] = "CANCELLED"
        return self._state(o)

    def order_status(self, order_id):
        o = self.orders.get(order_id)
        if o is None:
            return OrderState("UNKNOWN")
        if o["status"] == "OPEN":
            self._check_stops(o["symbol"])
        if o["status"] == "OPEN" and o["kind"] == "stop" and self._fault("stop_cancel", o["symbol"]):
            o["status"] = "CANCELLED"
        return self._state(o)

    def find_by_tag(self, tag, hint=None):
        hits = [(k, o) for k, o in self.orders.items() if o.get("tag") == tag]
        if not hits:
            return None
        k, o = hits[-1]
        if o.get("hidden", 0) > 0:
            o["hidden"] -= 1
            return None
        if o["status"] == "OPEN":
            self._check_stops(o["symbol"])
        return k, self._state(o)

    def net_positions(self):
        return dict(self.pos)

    def _check_stops(self, symbol):
        open_orders = [o for o in self.orders.values()
                       if o["symbol"] == symbol and o["status"] == "OPEN" and o.get("kind") == "stop"]
        if not open_orders:
            return
        df = self._last_bars.get(symbol)
        for o in open_orders:
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
                o["filled"] = o["qty"]
                o["avg_price"] = o["trigger"] * (1 + o["side"] * self.slip)
                self._apply(symbol, o["side"] * o["qty"])

    def to_dict(self):
        return {"pos": self.pos, "orders": self.orders}
