"""LIVE GTT placement, tested against a fake Kite. No real order is placed by these tests.

SpyKite records every place_gtt call. Its other order/GTT-changing methods (modify, delete, cancel, place_order,
and so on) fail the test if they are ever called, and the autouse fixture double-checks that none were.
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
import live_gtt  # noqa: E402
import main  # noqa: E402
import scanner  # noqa: E402
import token_store  # noqa: E402
from fakes_algo import SpyKite, day_order, gtt, holding, instrument, position  # noqa: E402

NOW = datetime(2026, 11, 26, 11, 0, tzinfo=scanner.IST)
RESPONSE_FIELDS = {
    "symbol", "quantity", "buy_price", "stoploss", "tick_size", "last_price", "account_state",
    "position_quantity", "active_buy_trigger_id", "active_stoploss_trigger_id", "day_buy_order_id",
    "day_buy_order_status", "buy_status", "buy_trigger_id", "stoploss_status", "stoploss_trigger_id", "message",
}
SPEC = {"symbol": "SIEMENS", "quantity": 1, "buy_price": 3903.3, "stoploss": 3708.1, "last_price": 4043}
TCS = {"symbol": "TCS", "quantity": 1, "buy_price": 100, "stoploss": 95, "last_price": 105}
INFY = {"symbol": "INFY", "quantity": 1, "buy_price": 200, "stoploss": 190, "last_price": 210}
PENNY = {"symbol": "PENNY", "quantity": 1, "buy_price": 10, "stoploss": 9.5, "last_price": 11}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("KITE_SESSION_FILE", str(tmp_path / "session.json"))
    monkeypatch.setenv("DUMMY_GTT_FILE", str(tmp_path / "dummy_gtts.json"))
    monkeypatch.setenv("LIVE_GTT_FILE", str(tmp_path / "live_gtts.json"))
    monkeypatch.setenv("LIVE_GTT_AUDIT_FILE", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("ALGO_LIVE_ORDERS", "1")
    for var in (live_gtt.ENV_MAX_ORDERS, live_gtt.ENV_MAX_VALUE, live_gtt.ENV_MAX_DAY):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(main, "KiteConnect", SpyKite)
    clock = {"now": NOW}
    monkeypatch.setattr(scanner, "_wall_clock", lambda: clock["now"])
    monkeypatch.setattr(live_gtt, "tokens", live_gtt.PreviewTokens())
    scanner.reset_caches()
    SpyKite.reset()
    SpyKite.allow_place_gtt = True
    SpyKite.instrument_rows = [instrument("SIEMENS", 1, 0.1), instrument("TCS", 2, 0.05), instrument("PENNY", 3, 0.01), instrument("INFY", 4, 0.05)]
    token_store.save_session("key123", "secret-token", "AB1234")
    yield clock
    assert SpyKite.mutating_calls == [], f"a forbidden broker method was called: {SpyKite.mutating_calls}"
    assert not (live_gtt.DATA_DIR / "live_gtts.json").exists() and not (live_gtt.DATA_DIR / "live_gtt_audit.jsonl").exists(), "a test wrote to the real .data folder"
    scanner.reset_caches()


@pytest.fixture
def client():
    return TestClient(main.app)


def preview(client, orders):
    return client.post("/api/algo-orders/live-gtt/preview", json={"orders": orders})


def place(client, orders, token, **extra):
    return client.post("/api/algo-orders/live-gtt", json={"confirm_live": True, "orders": orders, "preview_token": token, **extra})


def go(client, orders):
    """Preview, then place exactly what was previewed."""
    pv = preview(client, orders).json()
    return pv, place(client, orders, pv["token"])


def log():
    return json.loads(Path(live_gtt._log_path()).read_text())["placed"]


def audit():
    return [json.loads(line) for line in Path(live_gtt._audit_path()).read_text().splitlines()]


# ======================================================== switching it on ====
@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_explicit_truthy_values_enable_live(monkeypatch, value):
    monkeypatch.setenv("ALGO_LIVE_ORDERS", value)
    assert live_gtt.live_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "", "no", "maybe", "2", "enabled", "off"])
def test_anything_else_keeps_it_off(monkeypatch, value):
    monkeypatch.setenv("ALGO_LIVE_ORDERS", value)
    assert live_gtt.live_enabled() is False


def test_unset_means_off(monkeypatch):
    monkeypatch.delenv("ALGO_LIVE_ORDERS")
    assert live_gtt.live_enabled() is False


def test_mode_endpoint_reports_live_and_its_limits(client):
    body = client.get("/api/algo-orders/mode").json()
    assert body == {"mode": "live", "live_enabled": True, "limits": {"max_orders_per_run": 5, "max_order_value": 25000, "max_orders_per_day": 10, "quantity": 1}}


def test_mode_endpoint_reports_simulation_by_default(client, monkeypatch):
    monkeypatch.delenv("ALGO_LIVE_ORDERS")
    assert client.get("/api/algo-orders/mode").json() == {"mode": "simulation", "live_enabled": False, "limits": None}


def test_the_limits_can_be_lowered_and_are_capped(monkeypatch):
    monkeypatch.setenv(live_gtt.ENV_MAX_ORDERS, "2")
    monkeypatch.setenv(live_gtt.ENV_MAX_VALUE, "5000")
    monkeypatch.setenv(live_gtt.ENV_MAX_DAY, "4")
    assert live_gtt.limits() == live_gtt.Limits(2, 5000, 4)
    monkeypatch.setenv(live_gtt.ENV_MAX_ORDERS, "100")
    monkeypatch.setenv(live_gtt.ENV_MAX_DAY, "500")
    assert (live_gtt.limits().max_orders, live_gtt.limits().max_per_day) == (20, 50)  # the environment can't raise them past the hard caps


@pytest.mark.parametrize("bad", ["abc", "0", "-3", "", "1.5"])
def test_invalid_limit_settings_fall_back_to_the_defaults(monkeypatch, bad):
    for var in (live_gtt.ENV_MAX_ORDERS, live_gtt.ENV_MAX_VALUE, live_gtt.ENV_MAX_DAY):
        monkeypatch.setenv(var, bad)
    assert live_gtt.limits() == live_gtt.Limits(5, 25000, 10)


# ================================================== simulation is the default ====
def test_without_the_setting_nothing_real_can_happen(client, monkeypatch):
    monkeypatch.delenv("ALGO_LIVE_ORDERS")
    SpyKite.allow_place_gtt = False  # if the code called place_gtt even once, the test would fail
    assert preview(client, [SPEC]).status_code == 409
    res = client.post("/api/algo-orders/live-gtt", json={"confirm_live": True, "orders": [SPEC]})
    row = res.json()["results"][0]
    assert res.json()["mode"] == "simulation" and res.json()["dummy"] is True
    assert row["buy_trigger_id"].startswith("DUMMY-") and SpyKite.placed_gtts == []


def test_a_token_is_ignored_in_simulation(client, monkeypatch):
    monkeypatch.delenv("ALGO_LIVE_ORDERS")
    SpyKite.allow_place_gtt = False
    res = client.post("/api/algo-orders/live-gtt", json={"confirm_live": True, "orders": [SPEC], "preview_token": "whatever"})
    assert res.json()["results"][0]["buy_status"] == "success" and SpyKite.placed_gtts == []


# ================================================================== preview ====
def test_preview_lists_what_would_be_placed_and_places_nothing(client):
    res = preview(client, [SPEC, TCS])
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "live" and body["token"] and body["expires_in"] == 300
    assert [r["symbol"] for r in body["would_place"]] == ["SIEMENS", "TCS"]
    assert all(set(r) == RESPONSE_FIELDS for r in body["results"])
    assert all(r["buy_status"] == "ready" for r in body["would_place"])
    assert body["limits"]["max_orders_per_run"] == 5
    assert SpyKite.placed_gtts == [] and not Path(live_gtt._log_path()).exists()


def test_preview_only_lists_rows_that_are_clear(client):
    SpyKite.net_positions = [position("TCS", 3)]
    SpyKite.day_orders = [day_order("9", "INFY")]
    SpyKite.gtts = [gtt(5, "PENNY")]
    body = preview(client, [SPEC, TCS, INFY, PENNY, {**SPEC, "symbol": "NOSUCH"}]).json()
    assert [r["symbol"] for r in body["would_place"]] == ["SIEMENS"]
    by = {r["symbol"]: r["message"] for r in body["results"]}
    assert by["TCS"].startswith("Skipped: existing position") and by["INFY"] == "Skipped: day BUY order already exists." and by["PENNY"] == "Skipped: buy GTT already active."


def test_preview_with_nothing_to_place_issues_no_token(client):
    SpyKite.net_positions = [position("SIEMENS", 1)]
    body = preview(client, [SPEC]).json()
    assert body["token"] is None and body["would_place"] == [] and body["expires_in"] == 0


def test_state_endpoint_in_live_mode_ignores_dummy_records_and_reports_live_mode(client):
    gtt_sim.DummyGttStore.path().write_text(json.dumps({"counter": 1, "records": [{"trigger_id": "DUMMY-SIEMENS-000001", "symbol": "SIEMENS", "status": "active", "transaction_type": "BUY"}]}))
    body = client.post("/api/algo-orders/gtt-state", json={"orders": [SPEC]}).json()
    assert body["mode"] == "live" and body["dummy"] is False
    assert body["results"][0]["buy_status"] == "ready"  # a fake record must not block a real order
    assert SpyKite.placed_gtts == []


# ================================================================== placing ====
def test_placing_sends_exactly_one_single_leg_cnc_limit_buy_of_one_share(client):
    pv, res = go(client, [SPEC])
    assert res.status_code == 200
    assert SpyKite.placed_gtts == [
        {
            "trigger_type": "single",
            "tradingsymbol": "SIEMENS",
            "exchange": "NSE",
            "trigger_values": [3903.3],
            "last_price": 4043.0,
            "orders": [{"transaction_type": "BUY", "quantity": 1, "order_type": "LIMIT", "product": "CNC", "price": 3903.3}],
        }
    ]
    body = res.json()
    assert body["mode"] == "live" and body["dummy"] is False and "LIVE" in body["message"]
    row = body["results"][0]
    assert set(row) == RESPONSE_FIELDS
    assert (row["buy_status"], row["buy_trigger_id"], row["stoploss_status"], row["stoploss_trigger_id"]) == ("success", "100001", "planned_after_buy", None)
    assert row["message"] == "Live buy GTT placed on Kite. Stoploss planned after buy execution."
    assert (row["buy_price"], row["stoploss"], row["tick_size"]) == (3903.3, 3708.1, 0.1)


def test_no_stoploss_and_no_sell_is_ever_placed(client):
    go(client, [SPEC, TCS, INFY])
    assert len(SpyKite.placed_gtts) == 3
    for call in SpyKite.placed_gtts:
        assert call["trigger_type"] == "single" and len(call["orders"]) == 1 and call["orders"][0]["transaction_type"] == "BUY"


def test_the_price_sent_is_the_breakout_low_rounded_to_tick_never_the_ltp(client):
    go(client, [{"symbol": "TCS", "quantity": 1, "buy_price": 3903.325, "stoploss": 1, "last_price": 4999}])
    call = SpyKite.placed_gtts[0]
    assert call["trigger_values"] == [3903.35] and call["orders"][0]["price"] == 3903.35 and call["last_price"] == 4999.0


def test_only_the_previewed_ready_rows_are_placed(client):
    SpyKite.net_positions = [position("TCS", 3)]
    pv, res = go(client, [SPEC, TCS, {**INFY, "last_price": None}])
    by = {r["symbol"]: r for r in res.json()["results"]}
    assert [c["tradingsymbol"] for c in SpyKite.placed_gtts] == ["SIEMENS"]
    assert by["SIEMENS"]["buy_status"] == "success" and by["TCS"]["buy_status"] == "blocked" and by["INFY"]["buy_status"] == "waiting_for_ltp"


def test_a_log_and_an_audit_trail_are_written(client):
    go(client, [SPEC])
    assert [(p["symbol"], p["trigger_id"], p["trigger_price"], p["day"]) for p in log()] == [("SIEMENS", "100001", 3903.3, "2026-11-26")]
    assert [(a["symbol"], a["result"], a["trigger_id"]) for a in audit()] == [("SIEMENS", "placed", "100001")]


def test_real_state_still_blocks_in_live_mode(client):
    SpyKite.net_positions = [position("SIEMENS", 2)]
    SpyKite.holding_rows = [holding("TCS", 1)]
    SpyKite.day_orders = [day_order("7", "INFY", status="OPEN")]
    SpyKite.gtts = [gtt(55, "PENNY", trigger=10)]
    orders = [SPEC, TCS, INFY, PENNY]
    pv = preview(client, orders).json()
    assert pv["token"] is None
    assert SpyKite.placed_gtts == []
    assert {r["symbol"]: r["buy_status"] for r in pv["results"]} == {"SIEMENS": "blocked", "TCS": "blocked", "INFY": "blocked", "PENNY": "already_active"}


# ================================================ confirmation and the token ====
def test_confirm_live_must_still_be_true(client):
    pv = preview(client, [SPEC]).json()
    for body in ({"orders": [SPEC], "preview_token": pv["token"]}, {"confirm_live": False, "orders": [SPEC], "preview_token": pv["token"]}):
        res = client.post("/api/algo-orders/live-gtt", json=body)
        assert res.status_code == 400 and res.json()["detail"] == "confirm_live must be true."
    assert client.post("/api/algo-orders/live-gtt", json={"confirm_live": "yes", "orders": [SPEC], "preview_token": pv["token"]}).status_code == 422
    assert SpyKite.placed_gtts == []
    assert place(client, [SPEC], pv["token"]).status_code == 200  # the token survived the refused attempts


def test_placing_without_a_preview_is_refused(client):
    for token in (None, "", "not-a-real-token"):
        res = place(client, [SPEC], token)
        assert res.status_code == 409, token
    assert "preview is required" in place(client, [SPEC], None).json()["detail"]
    assert SpyKite.placed_gtts == []


def test_a_token_works_once(client):
    pv = preview(client, [SPEC]).json()
    assert place(client, [SPEC], pv["token"]).status_code == 200
    again = place(client, [SPEC], pv["token"])
    assert again.status_code == 409 and "no longer valid" in again.json()["detail"]
    assert len(SpyKite.placed_gtts) == 1


def test_a_token_expires_after_five_minutes(client, monkeypatch):
    pv = preview(client, [SPEC]).json()
    real = live_gtt.time.time()
    monkeypatch.setattr(live_gtt.time, "time", lambda: real + 301)
    res = place(client, [SPEC], pv["token"])
    assert res.status_code == 409 and "expired" in res.json()["detail"]
    assert SpyKite.placed_gtts == []


def test_a_changed_price_is_refused_and_the_token_is_burnt(client):
    pv = preview(client, [SPEC]).json()
    res = place(client, [{**SPEC, "buy_price": 3800}], pv["token"])
    assert res.status_code == 409 and "changed" in res.json()["detail"] and SpyKite.placed_gtts == []
    assert place(client, [SPEC], pv["token"]).status_code == 409  # you have to preview again


def test_an_order_that_was_not_in_the_preview_is_refused(client):
    pv = preview(client, [SPEC]).json()
    res = place(client, [SPEC, TCS], pv["token"])  # TCS is clear too, but you never saw it
    assert res.status_code == 409 and SpyKite.placed_gtts == []


def test_a_token_is_not_valid_across_a_backend_restart(client, monkeypatch):
    pv = preview(client, [SPEC]).json()
    monkeypatch.setattr(live_gtt, "tokens", live_gtt.PreviewTokens())  # a restart forgets every token
    assert place(client, [SPEC], pv["token"]).status_code == 409


def test_login_is_required(client):
    token_store.clear_session()
    assert preview(client, [SPEC]).status_code == 401
    assert place(client, [SPEC], "x").status_code == 401
    assert SpyKite.placed_gtts == []


# =============================================================== duplicates ====
def test_a_second_run_places_nothing_even_if_kite_does_not_list_the_gtt_yet(client):
    go(client, [SPEC])
    pv = preview(client, [SPEC]).json()
    row = pv["results"][0]
    assert pv["token"] is None and (row["buy_status"], row["active_buy_trigger_id"], row["message"]) == ("already_active", "100001", "Skipped: buy GTT already active.")
    assert len(SpyKite.placed_gtts) == 1


def test_once_kite_lists_the_gtt_its_own_state_blocks_it(client, isolated):
    go(client, [SPEC])
    SpyKite.gtts = [gtt(100001, "SIEMENS", trigger=3903.3)]
    isolated["now"] = NOW + timedelta(hours=2)  # long after the recent-placement window
    assert preview(client, [SPEC]).json()["results"][0]["buy_status"] == "already_active"


def test_after_the_window_the_decision_rests_on_kites_state_alone(client, isolated):
    go(client, [SPEC])
    isolated["now"] = NOW + timedelta(seconds=live_gtt.RECENT_WINDOW_SECONDS - 1)
    assert preview(client, [SPEC]).json()["token"] is None  # still inside the window
    isolated["now"] = NOW + timedelta(seconds=live_gtt.RECENT_WINDOW_SECONDS + 1)
    assert preview(client, [SPEC]).json()["results"][0]["buy_status"] == "ready"  # Kite shows nothing, so it is clear again


def test_a_stale_confirmation_cannot_place_a_stock_that_was_just_placed(client):
    stale = live_gtt.tokens.issue({"SIEMENS": "3903.3"})  # as if an old preview were still open
    go(client, [SPEC])
    res = place(client, [SPEC], stale)
    assert res.json()["results"][0]["buy_status"] == "already_active" and len(SpyKite.placed_gtts) == 1


def test_the_same_symbol_twice_in_one_request_is_placed_once(client):
    pv = preview(client, [SPEC, SPEC]).json()
    rows = place(client, [SPEC, SPEC], pv["token"]).json()["results"]
    assert [r["buy_status"] for r in rows] == ["success", "already_active"] and len(SpyKite.placed_gtts) == 1
    assert rows[1]["active_buy_trigger_id"] == rows[0]["buy_trigger_id"]


def test_dummy_records_never_block_or_count_in_live_mode(client):
    gtt_sim.DummyGttStore.path().write_text(json.dumps({"counter": 1, "records": [{"trigger_id": "DUMMY-SIEMENS-000001", "symbol": "SIEMENS", "status": "active", "transaction_type": "BUY"}]}))
    assert go(client, [SPEC])[1].json()["results"][0]["buy_status"] == "success"


def test_concurrent_previews_for_the_same_stock_place_it_once(client):
    tokens = [live_gtt.tokens.issue({"SIEMENS": "3903.3"}) for _ in range(8)]
    barrier = threading.Barrier(8)

    def attempt(token):
        barrier.wait()
        return live_gtt.place([{**SPEC, "buy_price": Decimal("3903.3"), "last_price": Decimal("4043")}], token, lambda: gtt_sim.KiteState([], [], [], []), lambda syms: {"SIEMENS": 0.1}, live_gtt.GttWriter(SpyKite()), date(2026, 11, 26), NOW)[0]["buy_status"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(attempt, tokens))
    assert statuses.count("success") == 1 and statuses.count("already_active") == 7
    assert len(SpyKite.placed_gtts) == 1 and len(log()) == 1


def test_one_token_confirmed_by_many_requests_at_once_works_once():
    token = live_gtt.tokens.issue({"SIEMENS": "3903.3"})
    barrier = threading.Barrier(8)

    def attempt(_):
        barrier.wait()
        try:
            live_gtt.place([{**SPEC, "buy_price": Decimal("3903.3"), "last_price": Decimal("4043")}], token, lambda: gtt_sim.KiteState([], [], [], []), lambda syms: {"SIEMENS": 0.1}, live_gtt.GttWriter(SpyKite()), date(2026, 11, 26), NOW)
            return "placed"
        except live_gtt.PreviewRejected:
            return "refused"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count("placed") == 1 and results.count("refused") == 7 and len(SpyKite.placed_gtts) == 1


# ================================================================== limits ====
def test_at_most_n_orders_per_run(client, monkeypatch):
    monkeypatch.setenv(live_gtt.ENV_MAX_ORDERS, "2")
    pv, res = go(client, [SPEC, TCS, INFY, PENNY])
    statuses = [r["buy_status"] for r in res.json()["results"]]
    assert statuses == ["success", "success", "blocked", "blocked"] and len(SpyKite.placed_gtts) == 2
    assert res.json()["results"][2]["message"] == "Skipped: live order limit reached (2 per run, 10 per day)."
    assert [r["symbol"] for r in pv["would_place"]] == ["SIEMENS", "TCS"]  # the preview already showed this


def test_an_order_above_the_value_limit_is_not_placed(client, monkeypatch):
    monkeypatch.setenv(live_gtt.ENV_MAX_VALUE, "150")
    pv, res = go(client, [SPEC, TCS, INFY])
    by = {r["symbol"]: r for r in res.json()["results"]}
    assert by["SIEMENS"]["buy_status"] == "blocked" and by["SIEMENS"]["message"] == "Skipped: order value 3903.3 is above the live limit 150."
    assert by["INFY"]["buy_status"] == "blocked" and by["TCS"]["buy_status"] == "success"
    assert [c["tradingsymbol"] for c in SpyKite.placed_gtts] == ["TCS"]


def test_the_daily_limit_counts_what_was_already_placed_today(client, monkeypatch):
    monkeypatch.setenv(live_gtt.ENV_MAX_DAY, "10")
    Path(live_gtt._log_path()).write_text(json.dumps({"placed": [{"trigger_id": str(i), "symbol": f"OLD{i}", "trigger_price": 1.0, "placed_at": "2026-11-26T09:20:00+05:30", "day": "2026-11-26"} for i in range(9)]}))
    pv, res = go(client, [SPEC, TCS])
    assert [r["buy_status"] for r in res.json()["results"]] == ["success", "blocked"]
    assert "10 per day" in res.json()["results"][1]["message"]
    assert preview(client, [INFY]).json()["token"] is None  # today's budget is used up


def test_yesterdays_placements_do_not_count_against_today(client, monkeypatch):
    monkeypatch.setenv(live_gtt.ENV_MAX_DAY, "1")
    Path(live_gtt._log_path()).write_text(json.dumps({"placed": [{"trigger_id": "1", "symbol": "OLD", "trigger_price": 1.0, "placed_at": "2026-11-25T09:20:00+05:30", "day": "2026-11-25"}]}))
    assert go(client, [SPEC])[1].json()["results"][0]["buy_status"] == "success"


def test_quantity_other_than_one_is_never_placed(client):
    pv = preview(client, [{**SPEC, "quantity": 5}]).json()
    assert pv["token"] is None and pv["results"][0]["message"] == "Quantity must be 1."


# ================================================================== failures ====
def test_kite_rejecting_one_order_does_not_stop_the_others(client):
    SpyKite.place_gtt_errors = [None, kite_exc.InputException("Trigger price too close to the last price"), None]
    pv, res = go(client, [SPEC, TCS, INFY])
    rows = {r["symbol"]: r for r in res.json()["results"]}
    assert rows["SIEMENS"]["buy_status"] == "success" and rows["INFY"]["buy_status"] == "success"
    assert rows["TCS"]["buy_status"] == "failed" and rows["TCS"]["message"] == "Unable to place buy GTT: Trigger price too close to the last price"
    assert rows["TCS"]["buy_trigger_id"] is None
    assert len(SpyKite.placed_gtts) == 3
    assert sorted(p["symbol"] for p in log()) == ["INFY", "SIEMENS"]  # a rejected order is not remembered as placed
    assert [a["result"] for a in audit()] == ["placed", "rejected", "placed"]


@pytest.mark.parametrize("error", [kite_exc.NetworkException("timed out", code=504), RuntimeError("boom"), ConnectionError("reset")])
def test_an_unclear_error_stops_the_run_instead_of_guessing(client, error):
    SpyKite.place_gtt_errors = [None, error, None]
    pv, res = go(client, [SPEC, TCS, INFY])
    rows = {r["symbol"]: r for r in res.json()["results"]}
    assert rows["SIEMENS"]["buy_status"] == "success"
    assert rows["TCS"]["buy_status"] == "failed" and "It may have been created: check Kite's GTT list" in rows["TCS"]["message"]
    assert rows["INFY"]["buy_status"] == "not_placed" and rows["INFY"]["message"] == "Stopped after an unclear error. Check Kite's GTT list before trying again."
    assert len(SpyKite.placed_gtts) == 2  # INFY was never attempted
    assert [p["symbol"] for p in log()] == ["SIEMENS"]
    assert [a["result"] for a in audit()] == ["placed", "unclear"]


def test_an_expired_login_stops_the_run(client):
    SpyKite.place_gtt_errors = [kite_exc.TokenException("Incorrect `api_key` or `access_token`.")]
    pv, res = go(client, [SPEC, TCS])
    rows = res.json()["results"]
    assert res.status_code == 200 and rows[0]["buy_status"] == "failed" and "login expired" in rows[0]["message"]
    assert rows[1]["buy_status"] == "not_placed" and len(SpyKite.placed_gtts) == 1


def test_if_kite_state_cannot_be_read_nothing_is_placed(client):
    pv = preview(client, [SPEC]).json()
    SpyKite.state_error = kite_exc.NetworkException("gateway timeout", code=504)
    res = place(client, [SPEC], pv["token"])
    assert res.status_code == 502 and SpyKite.placed_gtts == []


def test_an_unreadable_live_log_refuses_to_place(client):
    pv = preview(client, [SPEC]).json()
    Path(live_gtt._log_path()).write_text("{not json")
    res = place(client, [SPEC], pv["token"])
    assert res.status_code == 500 and "Live GTT log problem" in res.json()["detail"]
    assert SpyKite.placed_gtts == [] and Path(live_gtt._log_path()).read_text() == "{not json"
    assert preview(client, [SPEC]).status_code == 500


def test_a_failure_to_write_the_log_does_not_hide_an_order_that_went_out(client, monkeypatch):
    pv = preview(client, [SPEC]).json()
    monkeypatch.setattr(live_gtt, "_write_log", lambda data: (_ for _ in ()).throw(OSError("disk full")))
    res = place(client, [SPEC], pv["token"])
    assert res.json()["results"][0]["buy_status"] == "success" and len(SpyKite.placed_gtts) == 1  # the order is reported, not lost
    assert [a["result"] for a in audit()] == ["placed"]


# ================================================================ the writer ====
def test_the_writer_sends_the_exact_payload_and_returns_the_trigger_id():
    writer = live_gtt.GttWriter(SpyKite())
    assert writer.place_buy_gtt("SIEMENS", Decimal("3903.3"), Decimal("4043")) == "100001"
    assert SpyKite.placed_gtts[0]["trigger_values"] == [3903.3] and SpyKite.placed_gtts[0]["orders"][0]["price"] == 3903.3


@pytest.mark.parametrize("symbol, trigger, last", [("", Decimal(1), Decimal(1)), ("X" * 21, Decimal(1), Decimal(1)), ("RELIANCE", Decimal(0), Decimal(1)), ("RELIANCE", Decimal(-1), Decimal(1)), ("RELIANCE", Decimal(1), Decimal(0))])
def test_the_writer_refuses_nonsense(symbol, trigger, last):
    with pytest.raises(ValueError):
        live_gtt.GttWriter(SpyKite()).place_buy_gtt(symbol, trigger, last)
    assert SpyKite.placed_gtts == []


def test_the_read_only_wrapper_still_refuses_place_gtt():
    from broker_guard import ForbiddenBrokerCall, ReadOnlyKite

    with pytest.raises(ForbiddenBrokerCall):
        ReadOnlyKite(SpyKite()).place_gtt
    assert SpyKite.placed_gtts == []
