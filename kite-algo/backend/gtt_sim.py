"""GTT placement SIMULATION. Nothing in this module can send anything to Kite.

What it does
  * Reads the account state from Kite (read-only): GTTs, today's orders, positions, holdings.
  * Decides, per stock, whether a buy GTT *would* be placed.
  * Writes a DUMMY record to a local file (backend/.data/dummy_gtts.json) instead of placing it.

Safety, by construction
  * The Kite client given to these functions is a broker_guard.ReadOnlyKite: any
    method outside its read-only allow-list (place_gtt, place_order, modify_*,
    cancel_*, delete_*) raises instead of running.
  * Dummy records never become fills, positions, holdings or stoploss orders, and
    never touch the real account. A stoploss is only ever "planned_after_buy".
  * The duplicate check and the record creation happen under one lock, on a fresh
    read of the file, so repeated or concurrent requests cannot create two records.
    (One backend process is assumed, as in the README's run command.)

Prices are exact decimals (Decimal), rounded to the instrument's tick size with
ROUND_HALF_UP: no floating-point rounding is involved.
"""

import json
import os
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
QUANTITY = 1
STOPLOSS_FACTOR = Decimal("0.95")  # stoploss = buy price x 0.95, no ATR
DELIVERY_PRODUCTS = frozenset({"CNC", "MTF"})
EXCLUDED_ORDER_STATUSES = frozenset({"CANCELLED", "REJECTED"})
DEFAULT_PATH = Path(__file__).resolve().parent / ".data" / "dummy_gtts.json"

# Messages (the wording is part of the agreed spec).
READY = "Ready for buy GTT placement."
CREATED = "Dummy buy GTT created. No order sent to Kite. Stoploss planned after buy execution."
GTT_ACTIVE = "Skipped: buy GTT already active."
DUMMY_ACTIVE = "Skipped: dummy buy GTT already active."
DAY_ORDER = "Skipped: day BUY order already exists."
WAITING = "Waiting for LTP."
NO_BUY_PRICE = "Buy price is not available for this row."
BAD_TICK = "Trigger price should be a multiple of tick size."
NO_TICK = "Tick size is not available for this symbol."
BAD_QUANTITY = "Quantity must be 1."
BAD_STOPLOSS = "Stoploss must be below the buy price."


def position_message(quantity) -> str:
    return f"Skipped: existing position/holding quantity is {quantity}."


def failed_message(reason: str) -> str:
    return f"Unable to create dummy GTT record: {reason}"


class DummyStoreError(Exception):
    """The dummy record file exists but can't be read. We refuse to guess and risk duplicates."""


# ------------------------------------------------------------------ numbers ---
def to_decimal(value) -> Optional[Decimal]:
    """Exact Decimal from a Decimal, int, or the shortest text of a float. None if not a usable number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        out = value
    else:
        try:
            out = Decimal(str(value))  # str(float) is the shortest text that round-trips: 0.1 -> '0.1'
        except InvalidOperation:
            return None
    return out if out.is_finite() else None


def round_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Nearest multiple of `tick` (halves round up), exactly."""
    steps = (value / tick).to_integral_value(rounding=ROUND_HALF_UP)
    return steps * tick


def is_multiple(value: Decimal, tick: Decimal) -> bool:
    return value % tick == 0


def _num(value):
    """Decimal/number -> a plain JSON number (int when whole)."""
    if value is None:
        return None
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return int(d) if d == d.to_integral_value() else float(d)


# -------------------------------------------------------------- kite state ---
@dataclass
class KiteState:
    gtts: list
    orders: list
    net_positions: list
    holdings: list

    @classmethod
    def read(cls, kite) -> "KiteState":
        """Four read-only calls. `kite` must be a ReadOnlyKite."""
        gtts = kite.get_gtts() or []
        orders = kite.orders() or []
        positions = kite.positions() or {}
        holdings = kite.holdings() or []
        return cls(list(gtts), list(orders), list(positions.get("net") or []), list(holdings))


def _symbol_of(item: dict) -> str:
    return str(item.get("tradingsymbol") or "").upper()


def _is_nse(item: dict) -> bool:
    return str(item.get("exchange") or "NSE").upper() == "NSE"


def existing_quantity(state: KiteState, symbol: str):
    """Net position quantity plus holding quantity (settled and T+1) for the NSE symbol."""
    total = Decimal(0)
    for p in state.net_positions:
        if _symbol_of(p) == symbol and _is_nse(p):
            total += max(Decimal(0), to_decimal(p.get("quantity")) or Decimal(0))
    for h in state.holdings:
        if _symbol_of(h) == symbol and _is_nse(h):
            total += max(Decimal(0), to_decimal(h.get("quantity")) or Decimal(0))
            total += max(Decimal(0), to_decimal(h.get("t1_quantity")) or Decimal(0))
    return _num(total)


def _gtt_symbol(g: dict) -> str:
    cond = g.get("condition") or {}
    sym = cond.get("tradingsymbol")
    if not sym and g.get("orders"):
        sym = g["orders"][0].get("tradingsymbol")
    return str(sym or "").upper()


def _gtt_exchange(g: dict) -> str:
    cond = g.get("condition") or {}
    return str(cond.get("exchange") or (g.get("orders") or [{}])[0].get("exchange") or "NSE").upper()


def active_gtts(state: KiteState, symbol: str) -> List[dict]:
    return [
        g
        for g in state.gtts
        if str(g.get("status") or "").lower() == "active" and _gtt_symbol(g) == symbol and _gtt_exchange(g) == "NSE"
    ]


def _has_side(g: dict, side: str) -> bool:
    return any(str(o.get("transaction_type") or "").upper() == side for o in g.get("orders") or [])


def _order_date(order: dict) -> Optional[date]:
    """The calendar day (IST) an order was placed, or None if the timestamp can't be read.

    Kite reports order times as IST wall-clock time without a time zone, so a naive datetime is taken as IST.
    A time-zone-aware one is converted to IST first.
    """
    ts = order.get("order_timestamp")
    if isinstance(ts, datetime):
        return (ts.astimezone(IST) if ts.tzinfo else ts).date()
    if isinstance(ts, date):
        return ts
    if isinstance(ts, str) and len(ts) >= 10:
        try:
            return date.fromisoformat(ts[:10])
        except ValueError:
            return None
    return None


def day_buy_order(state: KiteState, symbol: str, today: date) -> Optional[dict]:
    """The latest of today's NSE delivery BUY orders for the symbol that is not cancelled or rejected."""
    found = None
    for o in state.orders:
        if _symbol_of(o) != symbol or not _is_nse(o):
            continue
        if str(o.get("transaction_type") or "").upper() != "BUY":
            continue
        if str(o.get("product") or "").upper() not in DELIVERY_PRODUCTS:
            continue
        if str(o.get("status") or "").upper() in EXCLUDED_ORDER_STATUSES:
            continue
        d = _order_date(o)
        if d is not None and d != today:
            continue  # not a current-day order
        found = o  # keep the last one in the list: Kite lists orders oldest first
    return found


# ------------------------------------------------------------------ result ---
def _result(symbol: str, **fields) -> dict:
    out = {
        "symbol": symbol,
        "quantity": QUANTITY,
        "buy_price": None,
        "stoploss": None,
        "tick_size": None,
        "last_price": None,
        "account_state": "clear",
        "position_quantity": 0,
        "active_buy_trigger_id": None,
        "active_stoploss_trigger_id": None,
        "day_buy_order_id": None,
        "day_buy_order_status": None,
        "buy_status": "not_placed",
        "buy_trigger_id": None,
        "stoploss_status": "not_placed",
        "stoploss_trigger_id": None,
        "message": "",
    }
    out.update(fields)
    return out


def evaluate(order: dict, state: KiteState, tick_size, dummies: List[dict], today: date, live_recent: Optional[List[dict]] = None) -> dict:
    """Decide what would happen to one candidate. Pure: reads inputs, writes nothing.

    order: {symbol, quantity, buy_price, last_price}  (a stoploss sent by the client is ignored;
           the server computes it from the buy price so it can't be tampered with)
    dummies: active DUMMY records (simulation mode). live_recent: GTTs the live mode placed a moment ago,
           which Kite's own list may not show yet (live mode only).
    Returns the response row (the 17 fields of the API).
    """
    symbol = str(order.get("symbol") or "").upper()
    last_price = to_decimal(order.get("last_price"))
    pos_qty = existing_quantity(state, symbol)
    own_gtts = active_gtts(state, symbol)
    sl_gtt = next((g for g in own_gtts if _has_side(g, "SELL")), None) if pos_qty > 0 else None
    day = day_buy_order(state, symbol, today)

    row = _result(
        symbol,
        last_price=_num(last_price) if last_price is not None and last_price > 0 else None,
        position_quantity=pos_qty,
        active_stoploss_trigger_id=str(sl_gtt["id"]) if sl_gtt else None,
        stoploss_trigger_id=str(sl_gtt["id"]) if sl_gtt else None,
        stoploss_status="already_active" if sl_gtt else "not_placed",
        day_buy_order_id=str(day.get("order_id")) if day else None,
        day_buy_order_status=str(day.get("status")) if day else None,
    )

    def unavailable(message: str) -> dict:
        row.update(account_state="invalid", buy_status="not_available", stoploss_status="not_available", message=message)
        return row

    # ---- is the candidate itself valid?
    if order.get("quantity") != QUANTITY:
        return unavailable(BAD_QUANTITY)
    buy = to_decimal(order.get("buy_price"))
    if buy is None or buy <= 0:
        return unavailable(NO_BUY_PRICE)
    tick = to_decimal(tick_size)
    if tick is None or tick <= 0:
        return unavailable(NO_TICK)
    buy = round_to_tick(buy, tick)
    stoploss = round_to_tick(buy * STOPLOSS_FACTOR, tick)
    if buy <= 0:
        return unavailable(NO_BUY_PRICE)
    if stoploss <= 0 or stoploss >= buy:
        return unavailable(BAD_STOPLOSS)
    if not is_multiple(buy, tick) or not is_multiple(stoploss, tick):
        return unavailable(BAD_TICK)
    row.update(buy_price=_num(buy), stoploss=_num(stoploss), tick_size=_num(tick))

    # ---- does something already cover this stock? (first match wins)
    def already_active(**fields) -> dict:
        row.update(account_state="already_active", buy_status="already_active", stoploss_status="planned_after_buy")
        row.update(fields)
        return row

    real_buy = next((g for g in own_gtts if _has_side(g, "BUY")), None)
    if real_buy:
        return already_active(active_buy_trigger_id=str(real_buy["id"]), message=GTT_ACTIVE)
    same_trigger = next((g for g in own_gtts if any(to_decimal(v) == buy for v in (g.get("condition") or {}).get("trigger_values") or [])), None)
    if same_trigger:
        return already_active(active_buy_trigger_id=str(same_trigger["id"]), message=GTT_ACTIVE)
    just_placed = next((d for d in (live_recent or []) if d.get("symbol") == symbol), None)
    if just_placed:
        return already_active(active_buy_trigger_id=str(just_placed["trigger_id"]), message=GTT_ACTIVE)
    dummy = next((d for d in dummies if d.get("symbol") == symbol and d.get("status") == "active" and d.get("transaction_type") == "BUY"), None)
    if dummy:
        return already_active(buy_trigger_id=dummy["trigger_id"], message=DUMMY_ACTIVE)

    if day:
        row.update(account_state="blocked", buy_status="blocked", stoploss_status="not_placed", message=DAY_ORDER)
        return row
    if pos_qty > 0:
        row.update(account_state="blocked", buy_status="blocked", message=position_message(pos_qty))
        return row

    # ---- clear. Do we have a price to compare against?
    if last_price is None or last_price <= 0:
        row.update(account_state="waiting", buy_status="waiting_for_ltp", stoploss_status="waiting_for_ltp", message=WAITING)
        return row

    row.update(account_state="clear", buy_status="ready", stoploss_status="planned_after_buy", message=READY)
    return row


# ------------------------------------------------------------------- store ---
class DummyGttStore:
    """Dummy GTT records in a local JSON file. Never sent to Kite."""

    def __init__(self):
        self._lock = threading.RLock()

    @staticmethod
    def path() -> Path:
        return Path(os.environ.get("DUMMY_GTT_FILE") or DEFAULT_PATH)

    def _read(self) -> dict:
        try:
            text = self.path().read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"counter": 0, "records": []}
        except OSError as exc:
            raise DummyStoreError(f"cannot read {self.path().name}: {exc}") from exc
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("records"), list) or not isinstance(data.get("counter"), int):
                raise ValueError("unexpected structure")
        except ValueError as exc:
            raise DummyStoreError(f"{self.path().name} is corrupt ({exc}); fix or delete it") from exc
        return data

    def _write(self, data: dict) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # a crash can never leave half a file

    def records(self) -> List[dict]:
        with self._lock:
            return list(self._read()["records"])

    def check_and_create(self, order: dict, state: KiteState, tick_size, today: date) -> dict:
        """The atomic step: re-read the file, check every rule, and only then create the record."""
        with self._lock:
            try:
                data = self._read()
            except DummyStoreError as exc:
                return _failed_row(order, str(exc))
            row = evaluate(order, state, tick_size, data["records"], today)
            if row["buy_status"] != "ready":
                return row
            counter = data["counter"] + 1
            trigger_id = f"DUMMY-{row['symbol']}-{counter:06d}"
            record = {
                "trigger_id": trigger_id,
                "symbol": row["symbol"],
                "exchange": "NSE",
                "product": "CNC",
                "transaction_type": "BUY",
                "order_type": "LIMIT",
                "quantity": QUANTITY,
                "trigger_price": row["buy_price"],
                "order_price": row["buy_price"],
                "stoploss_planned": row["stoploss"],
                "status": "active",
                "dummy": True,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            try:
                self._write({"counter": counter, "records": data["records"] + [record]})
            except OSError as exc:
                row.update(buy_status="failed", message=failed_message(str(exc)))
                return row
            row.update(buy_status="success", buy_trigger_id=trigger_id, message=CREATED)
            return row


def _failed_row(order: dict, reason: str) -> dict:
    symbol = str(order.get("symbol") or "").upper()
    return _result(symbol, buy_status="failed", stoploss_status="not_placed", account_state="invalid", message=failed_message(reason))


store = DummyGttStore()


# ------------------------------------------------------------ entry points ---
def check_orders(orders: List[dict], state: KiteState, tick_sizes: Dict[str, object], today: date, dummy_store: Optional[DummyGttStore] = None) -> List[dict]:
    """Read-only: what would happen to each candidate? Creates nothing."""
    dummy_store = dummy_store or store
    dummies = dummy_store.records()  # raises DummyStoreError if unreadable
    return [evaluate(o, state, tick_sizes.get(str(o.get("symbol") or "").upper()), dummies, today) for o in orders]


def create_dummy_orders(orders: List[dict], state: KiteState, tick_sizes: Dict[str, object], today: date, dummy_store: Optional[DummyGttStore] = None) -> List[dict]:
    """Create dummy records for the rows that pass every check. Nothing is sent to Kite."""
    dummy_store = dummy_store or store
    out = []
    for o in orders:
        try:
            out.append(dummy_store.check_and_create(o, state, tick_sizes.get(str(o.get("symbol") or "").upper()), today))
        except Exception as exc:  # whatever went wrong, report it on the row and never fall back to anything else
            out.append(_failed_row(o, str(exc)))
    return out
