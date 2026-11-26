"""LIVE GTT placement: this is the ONLY module that can place a real order, and only one kind.

What it can do
  * place a single-leg BUY GTT: NSE, product CNC, order type LIMIT, quantity 1,
    trigger price == limit price == the breakout candle's low (rounded to the tick size).
That is all. There is no code anywhere in this app to modify, cancel or delete a GTT or an
order, to place a SELL, or to place a stoploss. A stoploss stays "planned after buy".

Why it is hard to trigger by accident
  * It is OFF unless you start the backend with ALGO_LIVE_ORDERS=1 (a button click can't turn it on).
  * Placing needs a one-time preview token. The preview lists exactly what would be placed;
    the placement only goes through for those same symbols at those same prices.
  * Hard limits (all enforced on the server): quantity 1; at most ALGO_LIVE_MAX_ORDERS per run
    (default 5, never above 20); at most ALGO_LIVE_MAX_ORDER_VALUE rupees per order
    (default 25000); at most ALGO_LIVE_MAX_ORDERS_PER_DAY per day (default 10, never above 50).
  * Every rule of the simulation still applies: an existing buy GTT, a day BUY order, a position
    or a holding blocks the order. A GTT placed a moment ago also blocks (Kite's list can lag).
  * Placements are serialised under one lock, with a fresh read of Kite's state inside it.
  * After an unclear error (timeout, network) it STOPS and tells you to check Kite, instead of
    guessing and risking a duplicate.
Everything it does is written to backend/.data/live_gtt_audit.jsonl.
"""

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from kiteconnect import exceptions as kite_exc

import gtt_sim

ENV_ENABLE = "ALGO_LIVE_ORDERS"
ENV_MAX_ORDERS = "ALGO_LIVE_MAX_ORDERS"
ENV_MAX_VALUE = "ALGO_LIVE_MAX_ORDER_VALUE"
ENV_MAX_DAY = "ALGO_LIVE_MAX_ORDERS_PER_DAY"
DEFAULT_MAX_ORDERS, CAP_MAX_ORDERS = 5, 20
DEFAULT_MAX_VALUE = 25_000
DEFAULT_MAX_DAY, CAP_MAX_DAY = 10, 50
TOKEN_TTL_SECONDS = 300
RECENT_WINDOW_SECONDS = 600  # a GTT placed this recently blocks a repeat even if Kite's list hasn't caught up
GTT_TYPE_SINGLE = "single"
DATA_DIR = Path(__file__).resolve().parent / ".data"

LIVE_CREATED = "Live buy GTT placed on Kite. Stoploss planned after buy execution."
TOKEN_MESSAGES = {
    "missing": "A preview is required before placing live orders. Click Run Live again.",
    "unknown": "That preview is no longer valid (it was already used, or the backend restarted). Click Run Live again.",
    "expired": "The preview expired after 5 minutes. Click Run Live again.",
    "changed": "The orders changed since the preview. Click Run Live again.",
}


class LiveStoreError(Exception):
    """The live log is unreadable, so we refuse to place anything (it is our duplicate guard)."""


class PreviewRejected(Exception):
    """The confirmation does not match a valid preview."""

    def __init__(self, reason: str):
        super().__init__(TOKEN_MESSAGES[reason])
        self.reason = reason


def live_enabled() -> bool:
    """True only when ALGO_LIVE_ORDERS is explicitly set to 1, true, yes or on."""
    return os.environ.get(ENV_ENABLE, "").strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, cap: Optional[int] = None) -> int:
    try:
        value = int(os.environ.get(name, "").strip())
    except ValueError:
        return default
    if value < 1:
        return default
    return min(value, cap) if cap else value


@dataclass(frozen=True)
class Limits:
    max_orders: int
    max_order_value: int
    max_per_day: int

    def as_dict(self) -> dict:
        return {"max_orders_per_run": self.max_orders, "max_order_value": self.max_order_value, "max_orders_per_day": self.max_per_day, "quantity": gtt_sim.QUANTITY}


def limits() -> Limits:
    return Limits(
        max_orders=_int_env(ENV_MAX_ORDERS, DEFAULT_MAX_ORDERS, CAP_MAX_ORDERS),
        max_order_value=_int_env(ENV_MAX_VALUE, DEFAULT_MAX_VALUE),
        max_per_day=_int_env(ENV_MAX_DAY, DEFAULT_MAX_DAY, CAP_MAX_DAY),
    )


# ------------------------------------------------------------------ writer ---
class GttWriter:
    """The only object in the app that can place an order, and it can place only one kind."""

    def __init__(self, kite):
        self._kite = kite

    def place_buy_gtt(self, symbol: str, trigger_price: Decimal, last_price: Decimal) -> str:
        """Place a single-leg BUY GTT (NSE, CNC, LIMIT, quantity 1). Returns Kite's trigger id."""
        if not symbol or not symbol.isascii() or len(symbol) > 20:
            raise ValueError("invalid symbol")
        if trigger_price <= 0 or last_price <= 0:
            raise ValueError("invalid price")
        price = float(trigger_price)
        response = self._kite.place_gtt(
            trigger_type=GTT_TYPE_SINGLE,
            tradingsymbol=symbol,
            exchange="NSE",
            trigger_values=[price],
            last_price=float(last_price),
            orders=[{"transaction_type": "BUY", "quantity": gtt_sim.QUANTITY, "order_type": "LIMIT", "product": "CNC", "price": price}],
        )
        return str(response["trigger_id"])


# --------------------------------------------------------------------- log ---
def _log_path() -> Path:
    return Path(os.environ.get("LIVE_GTT_FILE") or DATA_DIR / "live_gtts.json")


def _audit_path() -> Path:
    return Path(os.environ.get("LIVE_GTT_AUDIT_FILE") or DATA_DIR / "live_gtt_audit.jsonl")


def _read_log() -> dict:
    try:
        text = _log_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"placed": []}
    except OSError as exc:
        raise LiveStoreError(f"cannot read the live log: {exc}") from exc
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get("placed"), list):
            raise ValueError("unexpected structure")
    except ValueError as exc:
        raise LiveStoreError(f"the live log is corrupt ({exc}); fix or delete {_log_path().name}") from exc
    return data


def _write_log(data: dict) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _audit(entry: dict) -> None:
    """Append-only record of every attempt. Best effort: it must never stop an order that already went out."""
    try:
        path = _audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now(gtt_sim.IST).isoformat(timespec="seconds"), **entry}) + "\n")
    except OSError:
        pass


def recent_and_today(now: datetime):
    """(GTTs placed within the recent window, number placed today). Raises LiveStoreError if the log is unreadable."""
    placed = _read_log()["placed"]
    cutoff = now - timedelta(seconds=RECENT_WINDOW_SECONDS)
    recent = [p for p in placed if _parse(p.get("placed_at")) and _parse(p["placed_at"]) >= cutoff]
    today = sum(1 for p in placed if p.get("day") == now.date().isoformat())
    return recent, today


def _parse(text) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ tokens ---
class PreviewTokens:
    """One-time confirmation tokens, kept in memory only (a restart invalidates them)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: Dict[str, dict] = {}

    def issue(self, orders: Dict[str, str]) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            now = time.time()
            self._items = {t: v for t, v in self._items.items() if v["expires"] > now}
            self._items[token] = {"orders": dict(orders), "expires": now + TOKEN_TTL_SECONDS}
        return token

    def consume(self, token: Optional[str]) -> Dict[str, str]:
        """Use the token up (single use). Returns the {symbol: buy price} that was previewed."""
        if not token:
            raise PreviewRejected("missing")
        with self._lock:
            item = self._items.pop(token, None)
        if item is None:
            raise PreviewRejected("unknown")
        if item["expires"] <= time.time():
            raise PreviewRejected("expired")
        return item["orders"]


tokens = PreviewTokens()
_place_lock = threading.Lock()  # one live placement at a time


# ------------------------------------------------------------------ limits ---
def _block(row: dict, message: str) -> None:
    row.update(account_state="blocked", buy_status="blocked", stoploss_status="not_placed", message=message)


def apply_limits(rows: List[dict], lim: Limits, placed_today: int) -> List[dict]:
    """Turn rows that are 'ready' but over a limit into blocked rows. First come, first served, in input order."""
    budget = min(lim.max_orders, max(0, lim.max_per_day - placed_today))
    for row in rows:
        if row["buy_status"] != "ready":
            continue
        value = Decimal(str(row["buy_price"])) * row["quantity"]
        if value > lim.max_order_value:
            _block(row, f"Skipped: order value {value} is above the live limit {lim.max_order_value}.")
        elif budget <= 0:
            _block(row, f"Skipped: live order limit reached ({lim.max_orders} per run, {lim.max_per_day} per day).")
        else:
            budget -= 1
    return rows


def check_orders(orders: List[dict], state: gtt_sim.KiteState, tick_sizes: dict, today: date, now: datetime) -> List[dict]:
    """Read-only evaluation for live mode: Kite's state and recent live placements (dummy records are ignored)."""
    recent, placed_today = recent_and_today(now)
    rows = [gtt_sim.evaluate(o, state, tick_sizes.get(str(o.get("symbol") or "").upper()), [], today, live_recent=recent) for o in orders]
    return apply_limits(rows, limits(), placed_today)


def preview(orders: List[dict], state: gtt_sim.KiteState, tick_sizes: dict, today: date, now: datetime) -> dict:
    """What would be placed right now. Places nothing. Returns a one-time token for exactly those rows."""
    rows = check_orders(orders, state, tick_sizes, today, now)
    would = [r for r in rows if r["buy_status"] == "ready"]
    token = tokens.issue({r["symbol"]: str(r["buy_price"]) for r in would}) if would else None
    return {"token": token, "expires_in": TOKEN_TTL_SECONDS if token else 0, "would_place": would, "results": rows, "limits": limits().as_dict()}


# ------------------------------------------------------------------- place ---
def place(orders: List[dict], token: Optional[str], read_state, tick_sizes_for, writer: GttWriter, today: date, now: datetime) -> List[dict]:
    """Place the previewed orders for real. Needs a valid one-time token.

    read_state() -> KiteState and tick_sizes_for(symbols) -> {symbol: tick} are called INSIDE the lock,
    so the state the checks use is fresh at the moment of placing.
    """
    previewed = tokens.consume(token)  # single use: a replayed confirmation is refused
    with _place_lock:
        state = read_state()
        recent, placed_today = recent_and_today(now)
        ticks = tick_sizes_for({str(o.get("symbol") or "").upper() for o in orders})
        rows = [gtt_sim.evaluate(o, state, ticks.get(str(o.get("symbol") or "").upper()), [], today, live_recent=recent) for o in orders]
        apply_limits(rows, limits(), placed_today)

        # What is placed must be exactly what was previewed.
        for row in rows:
            if row["buy_status"] == "ready" and previewed.get(row["symbol"]) != str(row["buy_price"]):
                raise PreviewRejected("changed")

        stopped = False
        placed_ids: Dict[str, str] = {}  # symbol -> id, so the same symbol twice in one request is placed once
        for order, row in zip(orders, rows):
            if row["buy_status"] != "ready":
                continue
            if row["symbol"] in placed_ids:
                row.update(
                    account_state="already_active", buy_status="already_active", stoploss_status="planned_after_buy",
                    active_buy_trigger_id=placed_ids[row["symbol"]], message=gtt_sim.GTT_ACTIVE,
                )
                continue
            if stopped:
                row.update(buy_status="not_placed", stoploss_status="not_placed", message="Stopped after an unclear error. Check Kite's GTT list before trying again.")
                continue
            symbol, price = row["symbol"], Decimal(str(row["buy_price"]))
            try:
                trigger_id = writer.place_buy_gtt(symbol, price, Decimal(str(row["last_price"])))
            except kite_exc.TokenException:
                stopped = True
                row.update(buy_status="failed", stoploss_status="not_placed", message="Unable to place buy GTT: your Kite login expired. Log in again.")
                _audit({"symbol": symbol, "price": str(price), "result": "failed", "reason": "login expired"})
            except (kite_exc.InputException, kite_exc.OrderException, kite_exc.PermissionException, kite_exc.GeneralException, kite_exc.DataException) as exc:
                # Kite answered and said no: nothing was created, so it is safe to carry on with the others.
                row.update(buy_status="failed", stoploss_status="not_placed", message=f"Unable to place buy GTT: {exc}")
                _audit({"symbol": symbol, "price": str(price), "result": "rejected", "reason": str(exc)})
            except Exception as exc:  # a timeout or network error: the GTT may or may not exist. Do not guess.
                stopped = True
                row.update(
                    buy_status="failed",
                    stoploss_status="not_placed",
                    message=f"Unable to place buy GTT: {exc}. It may have been created: check Kite's GTT list before trying again.",
                )
                _audit({"symbol": symbol, "price": str(price), "result": "unclear", "reason": str(exc)})
            else:
                placed_ids[symbol] = trigger_id
                row.update(buy_status="success", buy_trigger_id=trigger_id, message=LIVE_CREATED, stoploss_status="planned_after_buy")
                _audit({"symbol": symbol, "price": str(price), "result": "placed", "trigger_id": trigger_id})
                try:  # remember it, so a double-submit within minutes can't place it twice
                    data = _read_log()
                    data["placed"].append({"trigger_id": trigger_id, "symbol": symbol, "trigger_price": float(price), "placed_at": now.isoformat(timespec="seconds"), "day": today.isoformat()})
                    _write_log(data)
                except (LiveStoreError, OSError):
                    pass  # the order is already placed and in the audit trail; Kite's own list will show it
        return rows
