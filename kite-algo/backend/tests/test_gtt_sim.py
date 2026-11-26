"""GTT placement SIMULATION: rules, rounding, the dummy store, and the endpoints.

Everything runs against SpyKite (see fakes_algo.py). Its order/GTT-changing methods fail the test if
they are ever called, and the autouse fixture below double-checks that none were, after every test.
"""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kiteconnect import exceptions as kite_exc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

import gtt_sim  # noqa: E402
import main  # noqa: E402
import scanner  # noqa: E402
import token_store  # noqa: E402
from fakes_algo import SpyKite, day_order, gtt, holding, instrument, position  # noqa: E402

TODAY = date(2026, 11, 26)
EMPTY = gtt_sim.KiteState([], [], [], [])
RESPONSE_FIELDS = {
    "symbol", "quantity", "buy_price", "stoploss", "tick_size", "last_price", "account_state",
    "position_quantity", "active_buy_trigger_id", "active_stoploss_trigger_id", "day_buy_order_id",
    "day_buy_order_status", "buy_status", "buy_trigger_id", "stoploss_status", "stoploss_trigger_id", "message",
}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("KITE_SESSION_FILE", str(tmp_path / "session.json"))
    monkeypatch.setenv("DUMMY_GTT_FILE", str(tmp_path / "dummy_gtts.json"))
    monkeypatch.setattr(main, "KiteConnect", SpyKite)
    monkeypatch.setattr(scanner, "_wall_clock", lambda: datetime(2026, 11, 26, 11, 0, tzinfo=scanner.IST))
    scanner.reset_caches()
    SpyKite.reset()
    SpyKite.instrument_rows = [instrument("SIEMENS", 1, 0.1), instrument("TCS", 2, 0.05), instrument("PENNY", 3, 0.01), instrument("INFY", 4, 0.05)]
    token_store.save_session("key123", "secret-token", "AB1234")
    yield
    assert not gtt_sim.DEFAULT_PATH.exists(), "a test wrote to the real backend/.data/dummy_gtts.json"
    assert SpyKite.mutating_calls == [], f"a broker method that changes orders/GTTs was called: {SpyKite.mutating_calls}"
    scanner.reset_caches()


def order(symbol="SIEMENS", buy="3903.3", last="4043", qty=1, **extra):
    return {"symbol": symbol, "quantity": qty, "buy_price": Decimal(buy) if buy is not None else None, "last_price": Decimal(last) if last is not None else None, **extra}


def ev(o=None, state=EMPTY, tick=0.1, dummies=()):
    return gtt_sim.evaluate(o or order(), state, tick, list(dummies), TODAY)


def state(**kw):
    return gtt_sim.KiteState(kw.get("gtts", []), kw.get("orders", []), kw.get("net", []), kw.get("holdings", []))


# ============================================================ exact numbers ====
def test_the_example_from_the_spec_comes_out_exactly():
    row = ev()
    assert row == {
        "symbol": "SIEMENS", "quantity": 1, "buy_price": 3903.3, "stoploss": 3708.1, "tick_size": 0.1, "last_price": 4043,
        "account_state": "clear", "position_quantity": 0, "active_buy_trigger_id": None, "active_stoploss_trigger_id": None,
        "day_buy_order_id": None, "day_buy_order_status": None, "buy_status": "ready", "buy_trigger_id": None,
        "stoploss_status": "planned_after_buy", "stoploss_trigger_id": None, "message": "Ready for buy GTT placement.",
    }
    assert set(row) == RESPONSE_FIELDS


@pytest.mark.parametrize(
    "value, tick, expected",
    [
        ("3903.3", "0.1", "3903.3"),
        ("3903.325", "0.05", "3903.35"),  # exactly half a tick: rounds up
        ("3903.324", "0.05", "3903.30"),
        ("3708.135", "0.1", "3708.1"),
        ("100.15", "0.05", "100.15"),  # a float would store this as 100.1499999...
        ("0.015", "0.01", "0.02"),
        ("99.97", "0.25", "100.00"),
        ("101", "0.05", "101.00"),
    ],
)
def test_round_to_tick_is_exact(value, tick, expected):
    out = gtt_sim.round_to_tick(Decimal(value), Decimal(tick))
    assert out == Decimal(expected)
    assert gtt_sim.is_multiple(out, Decimal(tick))


def test_stoploss_is_95_percent_of_the_buy_price_rounded_to_tick_without_atr():
    # buy 3903.35 x 0.95 = 3708.1825 -> nearest 0.05 is 3708.20
    row = ev(order("TCS", "3903.325", "4000"), tick=0.05)
    assert (row["buy_price"], row["stoploss"], row["tick_size"]) == (3903.35, 3708.2, 0.05)
    assert Decimal(str(row["stoploss"])) % Decimal("0.05") == 0


def test_float_noise_never_leaks_into_prices():
    row = ev(order("INFY", "100.15", "101"), tick=0.05)
    assert (row["buy_price"], row["stoploss"]) == (100.15, 95.15)  # 100.15 x 0.95 = 95.1425 -> 95.15


def test_every_price_is_a_multiple_of_the_tick_size():
    for tick in (0.01, 0.05, 0.1, 0.25):
        for buy in ("123.456", "7.77", "2999.99", "50.05"):
            row = ev(order("X", buy, "1"), tick=tick)
            t = Decimal(str(tick))
            assert Decimal(str(row["buy_price"])) % t == 0 and Decimal(str(row["stoploss"])) % t == 0


def test_the_clients_stoploss_is_ignored():
    assert ev(order(stoploss="1.0"))["stoploss"] == 3708.1


# ============================================================ invalid rows ====
def test_missing_buy_price_keeps_the_row_but_marks_buy_and_stoploss_unavailable():
    row = ev(order(buy=None))
    assert (row["buy_status"], row["stoploss_status"], row["account_state"]) == ("not_available", "not_available", "invalid")
    assert row["message"] == "Buy price is not available for this row."
    assert row["buy_price"] is None and row["stoploss"] is None


@pytest.mark.parametrize("buy", ["0", "-5"])
def test_zero_or_negative_buy_price_is_unavailable(buy):
    assert ev(order(buy=buy))["buy_status"] == "not_available"


@pytest.mark.parametrize("tick", [None, 0, -0.05])
def test_missing_tick_size_is_invalid_not_guessed(tick):
    row = ev(tick=tick)
    assert (row["buy_status"], row["account_state"]) == ("not_available", "invalid")
    assert row["message"] == "Tick size is not available for this symbol."


def test_quantity_other_than_one_is_invalid():
    row = ev(order(qty=2))
    assert (row["buy_status"], row["message"]) == ("not_available", "Quantity must be 1.")


def test_a_price_too_small_for_a_stoploss_below_it_is_invalid():
    row = ev(order("PENNY", "0.01", "1"), tick=0.01)  # 0.01 x 0.95 rounds back to 0.01
    assert (row["buy_status"], row["message"]) == ("not_available", "Stoploss must be below the buy price.")


# ================================================================== waiting ====
@pytest.mark.parametrize("last", [None, "0", "-1"])
def test_no_live_price_means_waiting_for_ltp(last):
    row = ev(order(last=last))
    assert (row["account_state"], row["buy_status"], row["stoploss_status"]) == ("waiting", "waiting_for_ltp", "waiting_for_ltp")
    assert row["message"] == "Waiting for LTP."
    assert row["buy_price"] == 3903.3  # the prices are still shown


# ================================================================== blocking ====
def test_an_active_buy_gtt_blocks():
    row = ev(state=state(gtts=[gtt(777, "SIEMENS")]))
    assert (row["buy_status"], row["account_state"], row["active_buy_trigger_id"]) == ("already_active", "already_active", "777")
    assert row["message"] == "Skipped: buy GTT already active."
    assert row["stoploss_status"] == "planned_after_buy"


@pytest.mark.parametrize("status", ["cancelled", "triggered", "disabled", "expired", "rejected", "deleted"])
def test_gtts_that_are_not_active_do_not_block(status):
    assert ev(state=state(gtts=[gtt(777, "SIEMENS", status=status)]))["buy_status"] == "ready"


def test_a_gtt_for_another_symbol_or_exchange_does_not_block():
    assert ev(state=state(gtts=[gtt(1, "TCS"), gtt(2, "SIEMENS", exchange="BSE")]))["buy_status"] == "ready"


def test_a_sell_gtt_alone_does_not_block_but_an_active_gtt_with_the_same_buy_trigger_does():
    assert ev(state=state(gtts=[gtt(9, "SIEMENS", side="SELL", trigger=3500.0)]))["buy_status"] == "ready"
    row = ev(state=state(gtts=[gtt(9, "SIEMENS", side="SELL", trigger=3903.3)]))
    assert (row["buy_status"], row["active_buy_trigger_id"]) == ("already_active", "9")


def test_an_active_dummy_gtt_blocks_and_its_id_is_returned():
    dummy = {"trigger_id": "DUMMY-SIEMENS-000004", "symbol": "SIEMENS", "status": "active", "transaction_type": "BUY"}
    row = ev(dummies=[dummy])
    assert (row["buy_status"], row["account_state"], row["buy_trigger_id"]) == ("already_active", "already_active", "DUMMY-SIEMENS-000004")
    assert row["active_buy_trigger_id"] is None
    assert row["message"] == "Skipped: dummy buy GTT already active."


def test_dummies_for_other_symbols_or_inactive_ones_do_not_block():
    others = [
        {"trigger_id": "DUMMY-TCS-000001", "symbol": "TCS", "status": "active", "transaction_type": "BUY"},
        {"trigger_id": "DUMMY-SIEMENS-000002", "symbol": "SIEMENS", "status": "cancelled", "transaction_type": "BUY"},
    ]
    assert ev(dummies=others)["buy_status"] == "ready"


@pytest.mark.parametrize("status", ["OPEN", "COMPLETE", "TRIGGER PENDING", "PUT ORDER REQ RECEIVED", "AMO REQ RECEIVED"])
def test_a_live_delivery_buy_order_today_blocks(status):
    row = ev(state=state(orders=[day_order("2611001", "SIEMENS", status=status)]))
    assert (row["buy_status"], row["account_state"]) == ("blocked", "blocked")
    assert (row["day_buy_order_id"], row["day_buy_order_status"]) == ("2611001", status)
    assert row["message"] == "Skipped: day BUY order already exists."
    assert row["stoploss_status"] == "not_placed"


@pytest.mark.parametrize(
    "o",
    [
        day_order("1", "SIEMENS", status="CANCELLED"),
        day_order("2", "SIEMENS", status="REJECTED"),
        day_order("3", "SIEMENS", status="cancelled"),
        day_order("4", "SIEMENS", side="SELL"),
        day_order("5", "SIEMENS", product="MIS"),
        day_order("6", "SIEMENS", exchange="BSE"),
        day_order("7", "TCS"),
        day_order("8", "SIEMENS", when=datetime(2026, 11, 25, 15, 0)),  # yesterday
    ],
)
def test_orders_that_must_not_block(o):
    row = ev(state=state(orders=[o]))
    assert row["buy_status"] == "ready" and row["day_buy_order_id"] is None


def test_order_times_are_judged_in_ist_naive_means_ist_and_aware_is_converted():
    from datetime import timezone

    aware_utc = lambda h: datetime(2026, 11, 26, h, 0, tzinfo=timezone.utc)
    # 03:00 UTC is 08:30 IST on the 26th: today. 19:00 UTC is 00:30 IST on the 27th: tomorrow, so not today.
    assert ev(state=state(orders=[day_order("1", "SIEMENS", when=aware_utc(3))]))["buy_status"] == "blocked"
    assert ev(state=state(orders=[day_order("2", "SIEMENS", when=aware_utc(19))]))["buy_status"] == "ready"
    assert ev(state=state(orders=[day_order("3", "SIEMENS", when=datetime(2026, 11, 26, 23, 59))]))["buy_status"] == "blocked"  # naive = IST
    assert ev(state=state(orders=[day_order("4", "SIEMENS", when="2026-11-26 09:16:01")]))["buy_status"] == "blocked"  # text form


def test_an_order_without_a_timestamp_counts_as_a_current_day_order():
    o = day_order("9", "SIEMENS")
    o["order_timestamp"] = None
    assert ev(state=state(orders=[o]))["buy_status"] == "blocked"


def test_the_latest_matching_day_order_is_reported():
    row = ev(state=state(orders=[day_order("1", "SIEMENS", status="OPEN"), day_order("2", "SIEMENS", status="COMPLETE")]))
    assert (row["day_buy_order_id"], row["day_buy_order_status"]) == ("2", "COMPLETE")


@pytest.mark.parametrize(
    "st, qty",
    [
        (state(net=[position("SIEMENS", 5)]), 5),
        (state(holdings=[holding("SIEMENS", 3)]), 3),
        (state(holdings=[holding("SIEMENS", 0, t1=2)]), 2),  # bought yesterday, not settled yet
        (state(net=[position("SIEMENS", 4)], holdings=[holding("SIEMENS", 3, t1=1)]), 8),
    ],
)
def test_an_existing_position_or_holding_blocks(st, qty):
    row = ev(state=st)
    assert (row["buy_status"], row["account_state"], row["position_quantity"]) == ("blocked", "blocked", qty)
    assert row["message"] == f"Skipped: existing position/holding quantity is {qty}."


@pytest.mark.parametrize(
    "st",
    [
        state(net=[position("SIEMENS", 0)]),
        state(net=[position("SIEMENS", -3)]),  # a short is not a long position
        state(net=[position("TCS", 9)]),
        state(net=[position("SIEMENS", 9, exchange="BSE")]),
        state(holdings=[holding("SIEMENS", 0)]),
        state(holdings=[holding("SIEMENS", 5, exchange="BSE")]),
    ],
)
def test_positions_and_holdings_that_must_not_block(st):
    row = ev(state=st)
    assert row["buy_status"] == "ready" and row["position_quantity"] == 0


def test_an_active_stoploss_gtt_is_shown_for_a_held_symbol_only():
    sl = gtt(55, "SIEMENS", side="SELL", trigger=3500.0)
    held = ev(state=state(net=[position("SIEMENS", 1)], gtts=[sl]))
    assert (held["active_stoploss_trigger_id"], held["stoploss_trigger_id"], held["stoploss_status"]) == ("55", "55", "already_active")
    not_held = ev(state=state(gtts=[sl]))
    assert not_held["active_stoploss_trigger_id"] is None and not_held["buy_status"] == "ready"


def test_blocking_reasons_are_reported_in_a_fixed_order():
    everything = state(
        gtts=[gtt(1, "SIEMENS")],
        orders=[day_order("9", "SIEMENS")],
        net=[position("SIEMENS", 2)],
    )
    dummy = [{"trigger_id": "DUMMY-SIEMENS-000001", "symbol": "SIEMENS", "status": "active", "transaction_type": "BUY"}]
    assert ev(state=everything, dummies=dummy)["message"] == "Skipped: buy GTT already active."
    no_real = state(orders=[day_order("9", "SIEMENS")], net=[position("SIEMENS", 2)])
    assert ev(state=no_real, dummies=dummy)["message"] == "Skipped: dummy buy GTT already active."
    assert ev(state=no_real)["message"] == "Skipped: day BUY order already exists."
    assert ev(state=state(net=[position("SIEMENS", 2)]))["message"].startswith("Skipped: existing position")


def test_a_blocked_row_is_blocked_even_without_a_live_price():
    assert ev(order(last=None), state=state(net=[position("SIEMENS", 1)]))["buy_status"] == "blocked"


# ================================================================ the store ====
def store():
    return gtt_sim.DummyGttStore()


def create(o=None, st=EMPTY, tick=0.1, dummy_store=None):
    return (dummy_store or gtt_sim.store).check_and_create(o or order(), st, tick, TODAY)


def test_creating_a_dummy_record_matches_the_spec_example():
    row = create()
    assert row["buy_status"] == "success" and row["buy_trigger_id"] == "DUMMY-SIEMENS-000001"
    assert row["stoploss_status"] == "planned_after_buy" and row["stoploss_trigger_id"] is None
    assert row["message"] == "Dummy buy GTT created. No order sent to Kite. Stoploss planned after buy execution."
    assert set(row) == RESPONSE_FIELDS


def test_the_record_stored_on_disk():
    create()
    data = json.loads(gtt_sim.DummyGttStore.path().read_text())
    assert data["counter"] == 1 and len(data["records"]) == 1
    rec = data["records"][0]
    assert {k: rec[k] for k in ("trigger_id", "symbol", "exchange", "product", "transaction_type", "order_type", "quantity", "trigger_price", "order_price", "status", "dummy")} == {
        "trigger_id": "DUMMY-SIEMENS-000001", "symbol": "SIEMENS", "exchange": "NSE", "product": "CNC", "transaction_type": "BUY",
        "order_type": "LIMIT", "quantity": 1, "trigger_price": 3903.3, "order_price": 3903.3, "status": "active", "dummy": True,
    }
    assert rec["stoploss_planned"] == 3708.1


def test_only_a_buy_record_is_ever_stored_never_a_stoploss_sell():
    create()
    assert [r["transaction_type"] for r in gtt_sim.store.records()] == ["BUY"]


def test_the_trigger_and_order_price_use_the_breakout_low_rounded_never_the_ltp():
    row = create(order("TCS", "3903.325", "4999"), tick=0.05)
    rec = gtt_sim.store.records()[0]
    assert rec["trigger_price"] == rec["order_price"] == 3903.35 and rec["trigger_price"] != 4999
    assert row["buy_price"] == 3903.35


def test_ids_count_up_across_symbols():
    assert create(order("SIEMENS"))["buy_trigger_id"] == "DUMMY-SIEMENS-000001"
    assert create(order("TCS", "100", "110"), tick=0.05)["buy_trigger_id"] == "DUMMY-TCS-000002"


def test_creating_the_same_symbol_again_returns_the_existing_id_and_makes_no_second_record():
    first = create()
    again = create()
    assert again["buy_status"] == "already_active" and again["buy_trigger_id"] == first["buy_trigger_id"]
    assert again["message"] == "Skipped: dummy buy GTT already active."
    assert len(gtt_sim.store.records()) == 1


def test_a_different_buy_price_for_an_active_symbol_still_does_not_create_a_second_record():
    create()
    assert create(order(buy="3800"))["buy_status"] == "already_active"
    assert len(gtt_sim.store.records()) == 1


def test_records_survive_a_backend_restart():
    first = create()
    restarted = store()  # a new process: nothing in memory, only the file
    again = create(dummy_store=restarted)
    assert again["buy_status"] == "already_active" and again["buy_trigger_id"] == first["buy_trigger_id"]
    assert [r["trigger_id"] for r in restarted.records()] == ["DUMMY-SIEMENS-000001"]


def test_the_check_endpoint_sees_dummy_records_after_a_restart():
    create()
    rows = gtt_sim.check_orders([order()], EMPTY, {"SIEMENS": 0.1}, TODAY, dummy_store=store())
    assert rows[0]["buy_status"] == "already_active" and rows[0]["buy_trigger_id"] == "DUMMY-SIEMENS-000001"


def test_concurrent_requests_cannot_create_duplicates():
    barrier = threading.Barrier(24)

    def attempt(_):
        barrier.wait()
        return create()["buy_status"]

    with ThreadPoolExecutor(max_workers=24) as pool:
        statuses = list(pool.map(attempt, range(24)))
    assert statuses.count("success") == 1 and statuses.count("already_active") == 23
    assert len(gtt_sim.store.records()) == 1


def test_concurrent_requests_for_different_symbols_get_unique_ids():
    symbols = [("SIEMENS", 0.1), ("TCS", 0.05), ("INFY", 0.05), ("PENNY", 0.01)] * 5
    barrier = threading.Barrier(len(symbols))

    def attempt(item):
        barrier.wait()
        return create(order(item[0], "100", "110"), tick=item[1])

    with ThreadPoolExecutor(max_workers=len(symbols)) as pool:
        rows = list(pool.map(attempt, symbols))
    ids = [r["buy_trigger_id"] for r in rows if r["buy_status"] == "success"]
    assert len(ids) == 4 == len(set(ids))
    assert sorted(r["symbol"] for r in gtt_sim.store.records()) == ["INFY", "PENNY", "SIEMENS", "TCS"]


def test_the_same_symbol_twice_in_one_batch_creates_one_record():
    rows = gtt_sim.create_dummy_orders([order(), order()], EMPTY, {"SIEMENS": 0.1}, TODAY)
    assert [r["buy_status"] for r in rows] == ["success", "already_active"]


@pytest.mark.parametrize("o", [order(buy=None), order(last=None), order(qty=3)])
def test_rows_that_are_not_ready_create_nothing(o):
    row = create(o)
    assert row["buy_status"] in ("not_available", "waiting_for_ltp")
    assert not gtt_sim.DummyGttStore.path().exists()


def test_blocked_rows_create_nothing():
    for st in (state(net=[position("SIEMENS", 1)]), state(orders=[day_order("1", "SIEMENS")]), state(gtts=[gtt(5, "SIEMENS")])):
        assert create(st=st)["buy_status"] in ("blocked", "already_active")
    assert not gtt_sim.DummyGttStore.path().exists()


def test_a_write_failure_is_reported_on_the_row_and_leaves_nothing_behind(monkeypatch):
    s = store()

    def boom(data):
        raise OSError("disk full")

    with monkeypatch.context() as m:  # scoped: a bare monkeypatch.undo() would also undo the fixture's temp-file setup
        m.setattr(s, "_write", boom)
        row = create(dummy_store=s)
    assert row["buy_status"] == "failed" and row["message"] == "Unable to create dummy GTT record: disk full"
    assert row["buy_trigger_id"] is None
    assert not gtt_sim.DummyGttStore.path().exists()
    assert create()["buy_trigger_id"] == "DUMMY-SIEMENS-000001"  # the id was not used up by the failure


def test_a_corrupt_store_is_never_reset_and_no_record_is_created():
    path = gtt_sim.DummyGttStore.path()
    path.write_text("{not json")
    row = create()
    assert row["buy_status"] == "failed" and row["message"].startswith("Unable to create dummy GTT record:")
    assert path.read_text() == "{not json"  # left alone for a person to look at
    with pytest.raises(gtt_sim.DummyStoreError):
        gtt_sim.check_orders([order()], EMPTY, {"SIEMENS": 0.1}, TODAY)


def test_a_store_with_the_wrong_structure_is_refused_too():
    gtt_sim.DummyGttStore.path().write_text(json.dumps({"records": "nope"}))
    with pytest.raises(gtt_sim.DummyStoreError):
        gtt_sim.store.records()


def test_creating_a_dummy_does_not_change_the_state_it_was_given():
    st = state(gtts=[gtt(1, "TCS")], net=[position("INFY", 2)])
    before = json.dumps([st.gtts, st.orders, st.net_positions, st.holdings], default=str)
    create(st=st)
    assert json.dumps([st.gtts, st.orders, st.net_positions, st.holdings], default=str) == before  # no fake fills, positions or holdings


# ============================================================== endpoints ====
@pytest.fixture
def client():
    return TestClient(main.app)


def post_state(client, orders):
    return client.post("/api/algo-orders/gtt-state", json={"orders": orders})


def post_live(client, orders, **extra):
    return client.post("/api/algo-orders/live-gtt", json={"confirm_live": True, "orders": orders, **extra})


SPEC = {"symbol": "SIEMENS", "quantity": 1, "buy_price": 3903.3, "stoploss": 3708.1, "last_price": 4043}


def test_state_endpoint_reports_without_creating_or_sending_anything(client):
    res = post_state(client, [SPEC])
    assert res.status_code == 200
    body = res.json()
    assert body["dummy"] is True and "no order is ever sent to Kite" in body["message"]
    row = body["results"][0]
    assert row["buy_status"] == "ready" and row["account_state"] == "clear" and row["tick_size"] == 0.1
    assert not gtt_sim.DummyGttStore.path().exists()
    assert set(SpyKite.read_calls) >= {"get_gtts", "orders", "positions", "holdings"}


def test_state_endpoint_reads_all_four_kite_sources_and_reflects_each(client):
    SpyKite.gtts = [gtt(41, "TCS")]
    SpyKite.day_orders = [day_order("77", "INFY", status="COMPLETE")]
    SpyKite.net_positions = [position("PENNY", 5)]
    SpyKite.holding_rows = [holding("SIEMENS", 2)]
    orders = [
        {**SPEC, "symbol": "TCS", "buy_price": 100, "last_price": 105},
        {**SPEC, "symbol": "INFY", "buy_price": 100, "last_price": 105},
        {**SPEC, "symbol": "PENNY", "buy_price": 10, "last_price": 11},
        {**SPEC},
    ]
    rows = {r["symbol"]: r for r in post_state(client, orders).json()["results"]}
    assert rows["TCS"]["message"] == "Skipped: buy GTT already active." and rows["TCS"]["active_buy_trigger_id"] == "41"
    assert rows["INFY"]["message"] == "Skipped: day BUY order already exists." and rows["INFY"]["day_buy_order_id"] == "77"
    assert rows["PENNY"]["message"] == "Skipped: existing position/holding quantity is 5."
    assert rows["SIEMENS"]["message"] == "Skipped: existing position/holding quantity is 2."


def test_live_endpoint_rejects_a_missing_or_false_confirm_live_before_touching_kite(client):
    for body in ({"orders": [SPEC]}, {"orders": [SPEC], "confirm_live": False}, {"orders": [SPEC], "confirm_live": None}):
        res = client.post("/api/algo-orders/live-gtt", json=body)
        assert res.status_code in (400, 422), body
    res = client.post("/api/algo-orders/live-gtt", json={"orders": [SPEC]})
    assert res.status_code == 400 and "confirm_live must be true" in res.json()["detail"]
    assert "no order is ever sent to Kite" in res.json()["detail"]
    assert SpyKite.read_calls == [] and not gtt_sim.DummyGttStore.path().exists()


@pytest.mark.parametrize("value", ["true", "yes", 1, "1"])
def test_confirm_live_must_be_the_json_boolean_true(client, value):
    assert client.post("/api/algo-orders/live-gtt", json={"orders": [SPEC], "confirm_live": value}).status_code == 422
    assert not gtt_sim.DummyGttStore.path().exists()


def test_live_endpoint_creates_a_dummy_record_and_sends_nothing(client):
    res = post_live(client, [SPEC])
    assert res.status_code == 200 and res.json()["dummy"] is True
    row = res.json()["results"][0]
    assert row == {
        "symbol": "SIEMENS", "quantity": 1, "buy_price": 3903.3, "stoploss": 3708.1, "tick_size": 0.1, "last_price": 4043,
        "account_state": "clear", "position_quantity": 0, "active_buy_trigger_id": None, "active_stoploss_trigger_id": None,
        "day_buy_order_id": None, "day_buy_order_status": None, "buy_status": "success", "buy_trigger_id": "DUMMY-SIEMENS-000001",
        "stoploss_status": "planned_after_buy", "stoploss_trigger_id": None,
        "message": "Dummy buy GTT created. No order sent to Kite. Stoploss planned after buy execution.",
    }
    assert SpyKite.mutating_calls == []


def test_repeated_live_requests_never_duplicate(client):
    ids = []
    for _ in range(5):
        row = post_live(client, [SPEC]).json()["results"][0]
        ids.append(row["buy_trigger_id"])
    assert set(ids) == {"DUMMY-SIEMENS-000001"}
    assert len(gtt_sim.store.records()) == 1
    assert row["buy_status"] == "already_active" and row["message"] == "Skipped: dummy buy GTT already active."


def test_the_state_endpoint_shows_the_active_dummy_afterwards(client):
    post_live(client, [SPEC])
    row = post_state(client, [SPEC]).json()["results"][0]
    assert (row["buy_status"], row["buy_trigger_id"]) == ("already_active", "DUMMY-SIEMENS-000001")


def test_a_mixed_batch_creates_only_the_clear_rows(client):
    SpyKite.gtts = [gtt(41, "TCS")]
    SpyKite.net_positions = [position("PENNY", 5)]
    orders = [
        {**SPEC},  # clear
        {**SPEC, "symbol": "TCS", "buy_price": 100, "last_price": 101},  # a real buy GTT exists
        {**SPEC, "symbol": "PENNY", "buy_price": 10, "last_price": 11},  # held
        {**SPEC, "symbol": "INFY", "buy_price": None, "stoploss": None, "last_price": 100},  # no buy price
    ]
    by = {r["symbol"]: r for r in post_live(client, orders).json()["results"]}
    assert by["SIEMENS"]["buy_status"] == "success"
    assert by["TCS"]["buy_status"] == "already_active" and by["TCS"]["buy_trigger_id"] is None
    assert by["PENNY"]["buy_status"] == "blocked"
    assert by["INFY"]["buy_status"] == "not_available"
    assert [r["symbol"] for r in gtt_sim.store.records()] == ["SIEMENS"]


def test_waiting_rows_are_not_created_even_if_the_client_sends_them(client):
    row = post_live(client, [{**SPEC, "last_price": None}]).json()["results"][0]
    assert row["buy_status"] == "waiting_for_ltp" and not gtt_sim.DummyGttStore.path().exists()


def test_a_tampered_stoploss_in_the_request_is_ignored(client):
    row = post_live(client, [{**SPEC, "stoploss": 1}]).json()["results"][0]
    assert row["stoploss"] == 3708.1


def test_tick_sizes_come_from_the_instrument_master(client):
    rows = {
        r["symbol"]: r
        for r in post_state(
            client,
            [
                {"symbol": "SIEMENS", "quantity": 1, "buy_price": 3903.27, "last_price": 4000},
                {"symbol": "TCS", "quantity": 1, "buy_price": 3903.27, "last_price": 4000},
                {"symbol": "PENNY", "quantity": 1, "buy_price": 12.345, "last_price": 13},
            ],
        ).json()["results"]
    }
    assert (rows["SIEMENS"]["tick_size"], rows["SIEMENS"]["buy_price"]) == (0.1, 3903.3)
    assert (rows["TCS"]["tick_size"], rows["TCS"]["buy_price"]) == (0.05, 3903.25)
    assert (rows["PENNY"]["tick_size"], rows["PENNY"]["buy_price"]) == (0.01, 12.35)


def test_decimal_prices_survive_the_json_round_trip_exactly(client):
    row = post_state(client, [{"symbol": "INFY", "quantity": 1, "buy_price": 100.15, "last_price": 101}]).json()["results"][0]
    assert (row["buy_price"], row["stoploss"]) == (100.15, 95.15)


def test_an_unknown_instrument_is_invalid_not_guessed(client):
    row = post_state(client, [{**SPEC, "symbol": "NOSUCH"}]).json()["results"][0]
    assert row["buy_status"] == "not_available" and row["message"] == "Tick size is not available for this symbol."


def test_lowercase_symbols_are_accepted(client):
    assert post_state(client, [{**SPEC, "symbol": "siemens"}]).json()["results"][0]["symbol"] == "SIEMENS"


@pytest.mark.parametrize("bad", [{"symbol": "../etc"}, {"symbol": ""}, {"symbol": "X" * 40}, {"symbol": "A B"}, {"quantity": "many"}, {"buy_price": "abc"}])
def test_bad_requests_are_rejected_with_422(client, bad):
    assert post_state(client, [{**SPEC, **bad}]).status_code == 422


def test_too_many_orders_are_rejected(client):
    assert post_state(client, [SPEC] * 101).status_code == 422


def test_an_empty_list_is_fine(client):
    assert post_state(client, []).json()["results"] == []


def test_not_logged_in_gives_401_for_both_endpoints(client):
    token_store.clear_session()
    assert post_state(client, [SPEC]).status_code == 401
    assert post_live(client, [SPEC]).status_code == 401
    assert not gtt_sim.DummyGttStore.path().exists()


def test_if_kite_state_cannot_be_read_nothing_is_created(client):
    SpyKite.state_error = kite_exc.NetworkException("gateway timeout", code=504)
    res = post_live(client, [SPEC])
    assert res.status_code == 502 and "Kite API error" in res.json()["detail"]
    assert not gtt_sim.DummyGttStore.path().exists()
    assert post_state(client, [SPEC]).status_code == 502


def test_an_expired_login_gives_401_and_clears_the_session(client):
    SpyKite.state_error = kite_exc.TokenException("Incorrect `api_key` or `access_token`.")
    assert post_live(client, [SPEC]).status_code == 401
    assert token_store.load_session() is None


def test_an_unreadable_dummy_store_is_a_clear_error_not_a_reset(client):
    gtt_sim.DummyGttStore.path().write_text("garbage")
    res = post_state(client, [SPEC])
    assert res.status_code == 500 and "Dummy GTT store problem" in res.json()["detail"]
    row = post_live(client, [SPEC]).json()["results"][0]
    assert row["buy_status"] == "failed" and row["message"].startswith("Unable to create dummy GTT record:")
    assert gtt_sim.DummyGttStore.path().read_text() == "garbage"


def test_responses_never_contain_the_access_token(client):
    assert "secret-token" not in post_live(client, [SPEC]).text + post_state(client, [SPEC]).text


def test_a_concurrent_flood_of_live_requests_creates_one_record(client):
    barrier = threading.Barrier(12)

    def go(_):
        barrier.wait()
        return TestClient(main.app).post("/api/algo-orders/live-gtt", json={"confirm_live": True, "orders": [SPEC]}).json()["results"][0]["buy_status"]

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(go, range(12)))
    assert statuses.count("success") == 1 and len(gtt_sim.store.records()) == 1
