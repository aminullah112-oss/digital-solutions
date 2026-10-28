"""Zerodha Kite Connect v3 adapter (REST, stdlib only).

Needs KITE_API_KEY and KITE_ACCESS_TOKEN in the environment. The access token
expires daily; generate it each morning through Kite's login flow. Historical
candles require the Kite Connect historical-data subscription.

This adapter has NOT been exercised against a live account by its author. Run it
with --paper (Kite data, simulated fills) until you have verified every order
path against Kite's sandbox or with 1-share orders.
"""
from __future__ import annotations

import csv
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

import pandas as pd

from .broker import Broker, BrokerError
from .data import normalize

ROOT = "https://api.kite.trade"
TERMINAL = {"COMPLETE", "CANCELLED", "REJECTED"}


class KiteBroker(Broker):
    def __init__(self, tz: str, product: str, exchange: str = "NSE",
                 stop_order_type: str = "SL-M", stop_limit_buffer_pct: float = 0.5,
                 api_key: str | None = None, access_token: str | None = None):
        self.api_key = api_key or os.environ.get("KITE_API_KEY")
        self.token = access_token or os.environ.get("KITE_ACCESS_TOKEN")
        if not self.api_key or not self.token:
            raise BrokerError("set KITE_API_KEY and KITE_ACCESS_TOKEN")
        if product not in ("MIS", "CNC"):
            raise BrokerError("product must be MIS (intraday) or CNC (delivery)")
        self.tz, self.product, self.exchange = tz, product, exchange
        self.stop_type, self.stop_buf = stop_order_type, stop_limit_buffer_pct / 100
        self._tokens: dict[str, int] | None = None

    # ------------------------------------------------------------------ http
    def _req(self, method: str, path: str, params: dict | None = None, raw: bool = False):
        url = ROOT + path
        body = None
        if params and method == "GET":
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        elif params:
            body = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=body, method=method, headers={
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.token}",
        })
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = r.read()
                break
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")
                if e.code == 429 and attempt < 2:
                    time.sleep(1 + attempt)
                    continue
                raise BrokerError(f"{method} {path} -> {e.code}: {msg}") from e
            except urllib.error.URLError as e:
                if attempt < 2:
                    time.sleep(1 + attempt)
                    continue
                raise BrokerError(f"{method} {path}: {e}") from e
        if raw:
            return data.decode()
        payload = json.loads(data)
        if payload.get("status") != "success":
            raise BrokerError(f"{method} {path}: {payload}")
        return payload["data"]

    # ------------------------------------------------------------------ data
    def _token(self, symbol: str) -> int:
        if self._tokens is None:
            text = self._req("GET", f"/instruments/{self.exchange}", raw=True)
            self._tokens = {row["tradingsymbol"]: int(row["instrument_token"])
                            for row in csv.DictReader(io.StringIO(text))}
        if symbol not in self._tokens:
            raise BrokerError(f"unknown symbol {self.exchange}:{symbol}")
        return self._tokens[symbol]

    def bars(self, symbol, interval, lookback_days):
        to = pd.Timestamp.now(tz=self.tz)
        frm = to - timedelta(days=lookback_days)
        # Kite caps the range per request (e.g. ~100 days for 5minute, 2000 for day).
        chunk = {"day": 1900}.get(interval, 90)
        frames = []
        start = frm
        while start < to:
            end = min(start + timedelta(days=chunk), to)
            data = self._req("GET", f"/instruments/historical/{self._token(symbol)}/{interval}", {
                "from": start.strftime("%Y-%m-%d %H:%M:%S"), "to": end.strftime("%Y-%m-%d %H:%M:%S"),
            })
            if data["candles"]:
                frames.append(pd.DataFrame(data["candles"],
                                           columns=["date", "open", "high", "low", "close", "volume"]))
            start = end
        if not frames:
            raise BrokerError(f"no candles for {symbol}")
        return normalize(pd.concat(frames), self.tz)

    def ltp(self, symbol):
        key = f"{self.exchange}:{symbol}"
        return float(self._req("GET", "/quote/ltp", {"i": key})[key]["last_price"])

    # ---------------------------------------------------------------- orders
    def _place(self, **p) -> str:
        p.update(exchange=self.exchange, product=self.product, validity="DAY")
        return self._req("POST", "/orders/regular", p)["order_id"]

    def _history(self, order_id):
        return self._req("GET", f"/orders/{order_id}")[-1]

    def market(self, symbol, side, qty, tag=""):
        oid = self._place(tradingsymbol=symbol, transaction_type="BUY" if side > 0 else "SELL",
                          order_type="MARKET", quantity=qty, tag=tag[:20])
        deadline = time.time() + 30
        while time.time() < deadline:
            h = self._history(oid)
            if h["status"] == "COMPLETE":
                return float(h["average_price"])
            if h["status"] in ("REJECTED", "CANCELLED"):
                raise BrokerError(f"market order {oid} {h['status']}: {h.get('status_message')}")
            time.sleep(0.5)
        raise BrokerError(f"market order {oid} not filled within 30s; check the order book manually")

    def _stop_params(self, side, trigger):
        trigger = round(trigger, 1) if trigger >= 1 else round(trigger, 2)
        p = dict(order_type=self.stop_type, trigger_price=trigger)
        if self.stop_type == "SL":
            # Stop-limit with a generous buffer; a pure limit could be skipped in a fast market.
            p["price"] = round(trigger * (1 + side * self.stop_buf), 1)
        return p

    def place_stop(self, symbol, side, qty, trigger, tag=""):
        return self._place(tradingsymbol=symbol, transaction_type="BUY" if side > 0 else "SELL",
                           quantity=qty, tag=tag[:20], **self._stop_params(side, trigger))

    def modify_stop(self, order_id, trigger):
        side = 1 if self._history(order_id)["transaction_type"] == "BUY" else -1
        self._req("PUT", f"/orders/regular/{order_id}", self._stop_params(side, trigger))

    def cancel(self, order_id):
        h = self._history(order_id)
        if h["status"] in TERMINAL:
            return False
        try:
            self._req("DELETE", f"/orders/regular/{order_id}")
        except BrokerError:
            return self._history(order_id)["status"] == "CANCELLED"
        return True

    def order_status(self, order_id):
        h = self._history(order_id)
        st = h["status"]
        st = st if st in TERMINAL else "OPEN"
        return st, float(h["average_price"]) if h.get("average_price") else None

    def net_positions(self):
        """Advisory: the engine uses this only to warn about mismatches. The stop
        order's status is the source of truth for whether a position closed."""
        out: dict[str, int] = {}
        if self.product == "CNC":
            # Delivery buys from earlier sessions live in holdings, not positions.
            for h in self._req("GET", "/portfolio/holdings"):
                if h["exchange"] == self.exchange:
                    q = int(h.get("quantity", 0)) + int(h.get("t1_quantity", 0))
                    if q:
                        out[h["tradingsymbol"]] = q
        for p in self._req("GET", "/portfolio/positions")["day"]:
            if p["product"] == self.product and p["exchange"] == self.exchange:
                out[p["tradingsymbol"]] = out.get(p["tradingsymbol"], 0) + int(p["quantity"])
        return {k: v for k, v in out.items() if v}
