"""Shared fakes for the Algo Signals / GTT tests (not a test file).

SpyKite is a pretend Kite client. Its READ methods return whatever a test put on the class.
Every method that could create, change or cancel an order or GTT is defined too, but it
records the call and then FAILS the test: so a test passes only if nothing like that ran.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

MUTATORS = [
    "place_gtt", "modify_gtt", "delete_gtt",
    "place_order", "modify_order", "cancel_order", "exit_order", "convert_position",
    "place_mf_order", "cancel_mf_order", "place_mf_sip", "modify_mf_sip", "cancel_mf_sip",
]


class SpyKite:
    mutating_calls = []  # names of forbidden methods that were called
    read_calls = []  # names of read methods that were called

    gtts = []
    day_orders = []
    net_positions = []
    holding_rows = []
    state_error = None  # an exception to raise from get_gtts
    allow_place_gtt = False  # live-mode tests switch this on; every OTHER mutator stays forbidden
    placed_gtts = []  # the calls place_gtt received while allowed
    place_gtt_errors = []  # exceptions to raise on successive place_gtt calls (None = succeed)
    next_trigger_id = 100000
    GTT_TYPE_SINGLE = "single"
    instrument_rows = []  # NSE equity rows
    ohlc_data = {}
    candles = {}  # symbol -> list of candle dicts for historical_data

    def __init__(self, api_key=None, timeout=None):
        pass

    def set_access_token(self, token):
        pass

    @classmethod
    def reset(cls):
        cls.mutating_calls = []
        cls.read_calls = []
        cls.gtts, cls.day_orders, cls.net_positions, cls.holding_rows = [], [], [], []
        cls.state_error = None
        cls.allow_place_gtt = False
        cls.placed_gtts = []
        cls.place_gtt_errors = []
        cls.next_trigger_id = 100000
        cls.instrument_rows = []
        cls.ohlc_data = {}
        cls.candles = {}

    # ---- reads
    def get_gtts(self):
        SpyKite.read_calls.append("get_gtts")
        if SpyKite.state_error:
            raise SpyKite.state_error
        return list(SpyKite.gtts)

    def orders(self):
        SpyKite.read_calls.append("orders")
        return list(SpyKite.day_orders)

    def positions(self):
        SpyKite.read_calls.append("positions")
        return {"net": list(SpyKite.net_positions), "day": []}

    def holdings(self):
        SpyKite.read_calls.append("holdings")
        return list(SpyKite.holding_rows)

    def instruments(self, exchange=None):
        SpyKite.read_calls.append("instruments")
        return list(SpyKite.instrument_rows)

    def ohlc(self, instruments):
        SpyKite.read_calls.append("ohlc")
        return {k: v for k, v in SpyKite.ohlc_data.items() if k in instruments}

    def profile(self):
        SpyKite.read_calls.append("profile")
        return {"user_id": "AB1234", "user_name": "Test User", "products": [], "exchanges": []}

    def historical_data(self, token, from_dt, to_dt, interval):
        SpyKite.read_calls.append("historical_data")
        return SpyKite.candles.get(token, [])


def _forbidden(name):
    def method(self, *args, **kwargs):
        SpyKite.mutating_calls.append(name)
        raise AssertionError(f"FORBIDDEN broker method called: {name}")

    return method


for _name in MUTATORS:
    setattr(SpyKite, _name, _forbidden(_name))


def instrument(symbol, token, tick_size=0.05):
    return {"tradingsymbol": symbol, "instrument_token": token, "name": symbol, "segment": "NSE", "instrument_type": "EQ", "tick_size": tick_size}


def gtt(gtt_id, symbol, side="BUY", status="active", trigger=100.0, exchange="NSE"):
    return {
        "id": gtt_id,
        "type": "single",
        "status": status,
        "condition": {"exchange": exchange, "tradingsymbol": symbol, "trigger_values": [trigger], "last_price": trigger + 5},
        "orders": [{"exchange": exchange, "tradingsymbol": symbol, "transaction_type": side, "quantity": 1, "price": trigger, "order_type": "LIMIT", "product": "CNC"}],
    }


def day_order(order_id, symbol, status="OPEN", side="BUY", product="CNC", exchange="NSE", when=None):
    return {
        "order_id": order_id,
        "tradingsymbol": symbol,
        "exchange": exchange,
        "transaction_type": side,
        "product": product,
        "status": status,
        "order_timestamp": when or datetime(2026, 11, 26, 9, 16, 1),  # IST wall-clock, like Kite; the tests pretend today is 2026-11-26
    }


def position(symbol, qty, exchange="NSE"):
    return {"tradingsymbol": symbol, "exchange": exchange, "quantity": qty, "product": "CNC"}


def holding(symbol, qty, t1=0, exchange="NSE"):
    return {"tradingsymbol": symbol, "exchange": exchange, "quantity": qty, "t1_quantity": t1}


def _place_gtt(self, trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders):
    """Refused (and the test fails) unless a live-mode test has explicitly allowed it."""
    if not SpyKite.allow_place_gtt:
        SpyKite.mutating_calls.append("place_gtt")
        raise AssertionError("FORBIDDEN broker method called: place_gtt")
    errors = SpyKite.place_gtt_errors
    call = {"trigger_type": trigger_type, "tradingsymbol": tradingsymbol, "exchange": exchange, "trigger_values": trigger_values, "last_price": last_price, "orders": orders}
    SpyKite.placed_gtts.append(call)
    if errors:
        err = errors.pop(0)
        if err is not None:
            raise err
    SpyKite.next_trigger_id += 1
    return {"trigger_id": SpyKite.next_trigger_id}


SpyKite.place_gtt = _place_gtt
