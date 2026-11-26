"""POST /api/backtest/sma-crossover with a fake Kite client (no network, no credentials)."""

import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kiteconnect import exceptions as kite_exc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candles  # noqa: E402
import main  # noqa: E402
import nifty100  # noqa: E402
import scanner  # noqa: E402
import token_store  # noqa: E402

CSV_TEXT = (Path(__file__).parent / "fixtures" / "ind_nifty100list.csv").read_text(encoding="utf-8")
SYMBOLS = [r["symbol"] for r in nifty100.parse_csv(CSV_TEXT)]
TOKENS = {s: 1000 + i for i, s in enumerate(SYMBOLS)}
SYMBOL_OF = {t: s for s, t in TOKENS.items()}
INDEX_TOKEN = 9000
TODAY = date(2026, 11, 26)  # a Thursday
ACCESS_TOKEN = "secret-token-xyz"


def business_days_ending(end, n):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def wave(k, n=420):
    """A smooth up-and-down price path, so 6/30 SMAs cross several times."""
    base = 100 + 40 * k
    return [round(base * (1 + 0.10 * math.sin(i / (5 + k % 4)) + 0.0005 * i), 2) for i in range(n)]


class FakeKite:
    missing = set()  # symbols Kite "doesn't list"
    index_listed = True
    closes = {}  # symbol (or "INDEX") -> closes override
    errors = {}  # symbol -> exception
    calls = []  # (token, from, to)

    def __init__(self, api_key, timeout=None):
        pass

    def set_access_token(self, token):
        pass

    def instruments(self, exchange):
        rows = [
            {"tradingsymbol": s, "instrument_token": TOKENS[s], "name": s, "segment": "NSE", "instrument_type": "EQ"}
            for s in SYMBOLS[:30]
            if s not in FakeKite.missing
        ]
        rows.append({"tradingsymbol": "NIFTY 50", "instrument_token": 8999, "name": "x", "segment": "INDICES", "instrument_type": "EQ"})
        if FakeKite.index_listed:
            rows.append({"tradingsymbol": "NIFTY 100", "instrument_token": INDEX_TOKEN, "name": "x", "segment": "INDICES", "instrument_type": "EQ"})
        return rows

    def historical_data(self, token, from_dt, to_dt, interval):
        assert interval == "day"
        sym = SYMBOL_OF.get(token, "INDEX")
        FakeKite.calls.append((token, from_dt.date(), to_dt.date()))
        if sym in FakeKite.errors:
            raise FakeKite.errors[sym]
        k = SYMBOLS.index(sym) if sym != "INDEX" else 99
        closes = FakeKite.closes.get(sym) or wave(k)
        days = business_days_ending(TODAY, len(closes))
        rows, prev = [], closes[0]
        for i, (d, c) in enumerate(zip(days, closes)):
            o = prev * (1 + 0.001 * (-1) ** i)
            rows.append(
                {
                    "date": datetime(d.year, d.month, d.day, tzinfo=scanner.IST),
                    "open": o,
                    "high": max(o, c) * 1.003,
                    "low": min(o, c) * 0.997,
                    "close": c,
                    "volume": 1,
                }
            )
            prev = c
        return rows


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("KITE_SESSION_FILE", str(tmp_path / "session.json"))
    monkeypatch.setenv("NIFTY100_CACHE_FILE", str(tmp_path / "nifty100.csv"))
    monkeypatch.setenv("CANDLES_DIR", str(tmp_path / "candles"))
    monkeypatch.setattr(main, "KiteConnect", FakeKite)
    monkeypatch.setattr(nifty100, "_download", lambda url: CSV_TEXT)
    nifty100._memory.update(rows=None, at=0.0, source=None)
    scanner.reset_caches()
    candles.reset_memory()
    monkeypatch.setattr(scanner, "THROTTLE_SECONDS", 0)
    monkeypatch.setattr(scanner, "_sleep", lambda s: None)
    monkeypatch.setattr(scanner, "_wall_clock", lambda: datetime(2026, 11, 26, 11, 0, tzinfo=scanner.IST))
    FakeKite.missing = set()
    FakeKite.index_listed = True
    FakeKite.closes = {}
    FakeKite.errors = {}
    FakeKite.calls = []
    token_store.save_session("key123", ACCESS_TOKEN, "AB1234")
    yield
    scanner.reset_caches()
    candles.reset_memory()


@pytest.fixture
def client():
    return TestClient(main.app)


def post(client, **overrides):
    body = {
        "short_sma": 6,
        "long_sma": 30,
        "years": 1,
        "max_stocks": 6,
        "starting_capital": 1_000_000,
        "max_positions": 10,
        "stop_loss_pct": None,
        "slippage_pct": 0.05,
        "include_charges": True,
    }
    body.update(overrides)
    return client.post("/api/backtest/sma-crossover", json=body)


# ------------------------------------------------------------ happy path ----
def test_response_shape(client):
    res = post(client)
    assert res.status_code == 200
    data = res.json()
    assert set(data) >= {
        "params", "generated_at", "market_open", "universe", "excluded", "skipped", "notes",
        "period", "summary", "benchmarks", "equity_curve", "trades", "signals_skipped", "costs",
    }
    assert data["params"]["years"] == 1 and data["params"]["max_stocks"] == 6
    assert data["universe"] == {"name": "Nifty 100", "requested": 6, "used": 6, "source": nifty100.SOURCES[0], "stale": False}
    assert data["market_open"] is True
    t = data["trades"][0]
    assert set(t) == {
        "symbol", "company", "entry_date", "entry_price", "exit_date", "exit_price",
        "shares", "days_held", "pnl", "pnl_pct", "charges", "exit_reason",
    }


def test_money_in_equals_money_out(client):
    data = post(client, max_stocks=10).json()
    s = data["summary"]
    assert len(data["trades"]) > 3, "the test data should produce several trades"
    total_pnl = sum(t["pnl"] for t in data["trades"])
    assert s["final_value"] - 1_000_000 == pytest.approx(total_pnl, abs=0.01 * len(data["trades"]) + 0.01)
    assert s["net_profit"] == pytest.approx(total_pnl, abs=0.01 * len(data["trades"]) + 0.01)
    assert data["equity_curve"][-1]["strategy"] == s["final_value"]


def test_never_more_open_positions_than_slots(client):
    data = post(client, max_stocks=12, max_positions=2, starting_capital=200_000).json()
    assert data["trades"], "need trades to test this"
    for point in data["equity_curve"]:
        d = point["date"]
        open_now = [t for t in data["trades"] if t["entry_date"] <= d < t["exit_date"]]
        assert len(open_now) <= 2
    assert data["signals_skipped"]["no_free_slot"] > 0  # with 2 slots and 12 stocks something must be skipped


def test_trades_make_sense(client):
    data = post(client, max_stocks=10, stop_loss_pct=5).json()
    allowed = {"bearish crossover", "stop-loss", "end of test"}
    assert {t["exit_reason"] for t in data["trades"]} <= allowed
    assert "stop-loss" in {t["exit_reason"] for t in data["trades"]}
    for t in data["trades"]:
        assert t["entry_date"] <= t["exit_date"] and t["shares"] >= 1 and t["entry_price"] > 0
        assert t["days_held"] >= 0
        if t["exit_reason"] == "end of test":
            assert t["exit_date"] == data["period"]["end"]
    assert [t["entry_date"] for t in data["trades"]] == sorted((t["entry_date"] for t in data["trades"]), reverse=True)


def test_equity_curve_and_benchmarks(client):
    data = post(client).json()
    curve = data["equity_curve"]
    assert curve[0]["date"] == data["period"]["start"] and curve[-1]["date"] == data["period"]["end"]
    assert curve[0]["nifty100"] == 1_000_000.0 and curve[0]["same_stocks"] == pytest.approx(1_000_000.0, abs=1.0)
    dates = [c["date"] for c in curve]
    assert dates == sorted(set(dates))
    assert data["benchmarks"]["nifty100"]["total_return_pct"] is not None
    assert data["benchmarks"]["same_stocks"]["stocks"] == 6
    # the period is about one year of trading days
    assert 240 <= data["period"]["trading_days"] <= 262


def test_without_costs_the_cost_total_is_zero(client):
    data = post(client, include_charges=False, slippage_pct=0).json()
    assert data["costs"] == {"charges": 0.0, "slippage": 0.0, "total": 0.0}


def test_costs_reduce_profit(client):
    free = post(client, include_charges=False, slippage_pct=0, max_stocks=8).json()["summary"]["final_value"]
    paid = post(client, include_charges=True, slippage_pct=0.05, max_stocks=8).json()["summary"]["final_value"]
    assert paid < free


def test_max_stocks_limits_downloads(client):
    post(client, max_stocks=4)
    tokens = {c[0] for c in FakeKite.calls}
    assert tokens == {TOKENS[s] for s in SYMBOLS[:4]} | {INDEX_TOKEN}


# ------------------------------------------------------------- data issues ----
def test_stock_with_a_suspected_unadjusted_split_is_excluded_and_listed(client):
    closes = wave(1)
    closes = closes[:200] + [c / 2 for c in closes[200:]]  # a 2-for-1 split nobody adjusted for
    FakeKite.closes = {SYMBOLS[1]: closes}
    data = post(client).json()
    assert data["universe"]["used"] == 5
    assert [e["symbol"] for e in data["excluded"]] == [SYMBOLS[1]]
    assert "split" in data["excluded"][0]["reason"] and "-50%" in data["excluded"][0]["reason"]
    assert SYMBOLS[1] not in {t["symbol"] for t in data["trades"]}


def test_symbol_missing_in_kite_is_skipped(client):
    FakeKite.missing = {SYMBOLS[2]}
    data = post(client).json()
    assert data["skipped"] == [{"symbol": SYMBOLS[2], "reason": "Not found in Kite's NSE instrument list"}]
    assert data["universe"]["used"] == 5


def test_a_failing_stock_is_skipped_not_fatal(client):
    FakeKite.errors = {SYMBOLS[0]: kite_exc.DataException("bad data")}
    data = post(client).json()
    assert data["skipped"][0]["symbol"] == SYMBOLS[0] and data["skipped"][0]["reason"].startswith("Kite error")
    assert data["universe"]["used"] == 5


def test_short_history_is_skipped(client):
    FakeKite.closes = {SYMBOLS[0]: wave(0, n=20)}
    data = post(client).json()
    assert data["skipped"] == [{"symbol": SYMBOLS[0], "reason": "Only 20 days of price history"}]


def test_missing_index_still_runs_without_that_benchmark(client):
    FakeKite.index_listed = False
    data = post(client).json()
    assert data["benchmarks"]["nifty100"] is None and data["benchmarks"]["same_stocks"] is not None
    assert any("Nifty 100 index" in n for n in data["notes"])
    assert all(c["nifty100"] is None for c in data["equity_curve"])


def test_index_download_failure_is_a_note_not_an_error(client):
    FakeKite.errors = {"INDEX": kite_exc.DataException("nope")}
    data = post(client).json()
    assert data["benchmarks"]["nifty100"] is None
    assert any("could not be downloaded" in n for n in data["notes"])


def test_nothing_usable_gives_502(client):
    FakeKite.missing = set(SYMBOLS[:6])
    res = post(client)
    assert res.status_code == 502 and "nothing to test" in res.json()["detail"]


# --------------------------------------------------------------- caching ----
def test_second_identical_run_downloads_nothing(client):
    post(client, max_stocks=5)
    first = len(FakeKite.calls)
    assert first == 6  # 5 stocks + the index
    again = post(client, max_stocks=5).json()
    assert len(FakeKite.calls) == first
    assert again["summary"]["trades"] > 0


def test_changing_only_the_rules_downloads_nothing(client):
    post(client, max_stocks=5)
    n = len(FakeKite.calls)
    post(client, max_stocks=5, max_positions=3, stop_loss_pct=8, slippage_pct=0.2)
    assert len(FakeKite.calls) == n


def test_raising_long_sma_downloads_only_earlier_days(client):
    post(client, max_stocks=3, long_sma=30)
    first = list(FakeKite.calls)
    post(client, max_stocks=3, long_sma=60)
    extra = FakeKite.calls[len(first):]
    assert len(extra) == 4  # 3 stocks + index, each a small head request
    saved_from = first[0][1]
    assert all(to <= saved_from for _, _, to in extra)  # they end where the saved data begins


# --------------------------------------------------------------- failures ----
def test_missing_history_permission_gives_403(client):
    FakeKite.errors = {SYMBOLS[0]: kite_exc.PermissionException("Insufficient permission for that call.")}
    res = post(client)
    assert res.status_code == 403 and "Historical Data" in res.json()["detail"]


def test_expired_token_gives_401_and_clears_session(client):
    FakeKite.errors = {SYMBOLS[0]: kite_exc.TokenException("Incorrect `api_key` or `access_token`.")}
    assert post(client).status_code == 401
    assert token_store.load_session() is None


def test_not_logged_in_gives_401(client):
    token_store.clear_session()
    assert post(client).status_code == 401


def test_busy_gives_409_then_works_again(client):
    assert scanner._scan_lock.acquire(blocking=False)
    try:
        res = post(client)
    finally:
        scanner._scan_lock.release()
    assert res.status_code == 409 and "already running" in res.json()["detail"]
    assert post(client, max_stocks=1).status_code == 200


def test_a_signals_scan_and_a_backtest_share_the_same_lock(client):
    with scanner.exclusive():
        assert post(client).status_code == 409
        assert client.post("/api/signals/sma-crossover", json={}).status_code == 409


def test_nifty_list_failure_gives_502(client, monkeypatch):
    def boom(url):
        raise ConnectionError("offline")

    monkeypatch.setattr(nifty100, "_download", boom)
    assert post(client).status_code == 502


def test_response_never_contains_the_access_token(client):
    assert ACCESS_TOKEN not in post(client).text


# ------------------------------------------------------------ validation ----
@pytest.mark.parametrize(
    "overrides",
    [
        {"short_sma": 30, "long_sma": 30},
        {"short_sma": 40, "long_sma": 30},
        {"short_sma": 1},
        {"long_sma": 1000},
        {"years": 0},
        {"years": 6},
        {"max_stocks": 0},
        {"max_stocks": 101},
        {"starting_capital": 100},
        {"max_positions": 0},
        {"stop_loss_pct": 0},
        {"stop_loss_pct": 60},
        {"slippage_pct": -1},
        {"slippage_pct": 5},
    ],
)
def test_invalid_inputs_are_rejected_before_any_download(client, overrides):
    assert post(client, **overrides).status_code == 422
    assert FakeKite.calls == []


def test_short_not_smaller_than_long_message(client):
    assert "Short SMA must be smaller than Long SMA" in str(post(client, short_sma=30, long_sma=6).json()["detail"])


def test_defaults_match_the_design_doc():
    assert main.BacktestRequest().model_dump() == {
        "short_sma": 6,
        "long_sma": 30,
        "years": 5,
        "max_stocks": 100,
        "starting_capital": 1_000_000,
        "max_positions": 10,
        "stop_loss_pct": None,
        "slippage_pct": 0.05,
        "include_charges": True,
        "regime_filter": False,
        "regime_sma": 200,
        "holdout_pct": 40,
    }


def test_momentum_defaults():
    assert main.MomentumRequest().model_dump() == {
        "lookback_days": 252,
        "skip_days": 21,
        "top_n": 10,
        "keep_rank": None,
        "years": 5,
        "max_stocks": 100,
        "starting_capital": 1_000_000,
        "stop_loss_pct": None,
        "slippage_pct": 0.05,
        "include_charges": True,
        "regime_filter": False,
        "regime_sma": 200,
        "holdout_pct": 40,
    }


# =============================================================== momentum ====
def post_m(client, **overrides):
    body = {
        "lookback_days": 120,
        "skip_days": 10,
        "top_n": 4,
        "years": 1,
        "max_stocks": 12,
        "starting_capital": 1_000_000,
        "stop_loss_pct": None,
        "slippage_pct": 0.05,
        "include_charges": True,
    }
    body.update(overrides)
    return client.post("/api/backtest/momentum", json=body)


def month_starts(data):
    """The first trading day of each month inside the test, plus the first test day: the only days momentum trades."""
    days = [c["date"] for c in data["equity_curve"]]
    return {days[0]} | {d for prev, d in zip(days, days[1:]) if d[:7] != prev[:7]}


def test_momentum_response_and_invariants(client):
    res = post_m(client)
    assert res.status_code == 200
    data = res.json()
    assert data["strategy"] == "momentum"
    assert data["params"]["lookback_days"] == 120 and data["params"]["top_n"] == 4 and data["params"]["keep_rank"] == 8
    assert data["universe"]["used"] == 12
    assert data["summary"]["rebalances"] >= 11  # about one a month for a year
    assert data["trades"], "momentum should trade"
    total = sum(t["pnl"] for t in data["trades"])
    assert data["summary"]["final_value"] - 1_000_000 == pytest.approx(total, abs=0.01 * len(data["trades"]) + 0.01)
    for point in data["equity_curve"]:
        assert len([t for t in data["trades"] if t["entry_date"] <= point["date"] < t["exit_date"]]) <= 4
    assert {t["exit_reason"] for t in data["trades"]} <= {"rank dropped", "stop-loss", "end of test"}


def test_momentum_only_trades_on_rebalance_days(client):
    data = post_m(client).json()
    days = month_starts(data)
    assert {t["entry_date"] for t in data["trades"]} <= days
    rotated = [t for t in data["trades"] if t["exit_reason"] == "rank dropped"]
    assert rotated and {t["exit_date"] for t in rotated} <= days


def test_momentum_uses_each_stock_for_a_slot_not_more(client):
    data = post_m(client, top_n=3, starting_capital=300_000).json()
    assert all(t["shares"] * t["entry_price"] <= 100_000 for t in data["trades"])  # capital / top_n per position


def test_momentum_second_run_downloads_nothing(client):
    post_m(client, max_stocks=5)
    n = len(FakeKite.calls)
    assert n == 6  # 5 stocks + the index
    post_m(client, max_stocks=5, top_n=2, keep_rank=3, slippage_pct=0.2)  # rule changes only
    assert len(FakeKite.calls) == n


def test_switching_from_crossover_to_momentum_downloads_only_earlier_days(client):
    post(client, max_stocks=3)
    first = list(FakeKite.calls)
    post_m(client, max_stocks=3)  # momentum needs more warm-up history than a 30-day SMA
    extra = FakeKite.calls[len(first):]
    assert len(extra) == 4  # 3 stocks + the index, each a head request
    assert all(to <= first[0][1] for _, _, to in extra)


@pytest.mark.parametrize(
    "overrides",
    [
        {"skip_days": 120},
        {"skip_days": 300},
        {"lookback_days": 10},
        {"lookback_days": 600},
        {"top_n": 0},
        {"top_n": 51},
        {"keep_rank": 2},  # smaller than top_n=4
        {"regime_sma": 10},
        {"holdout_pct": 81},
        {"holdout_pct": -1},
        {"years": 6},
        {"stop_loss_pct": 0},
    ],
)
def test_momentum_invalid_inputs_rejected(client, overrides):
    assert post_m(client, **overrides).status_code == 422
    assert FakeKite.calls == []


def test_momentum_error_paths(client):
    FakeKite.errors = {SYMBOLS[0]: kite_exc.PermissionException("Insufficient permission for that call.")}
    assert post_m(client).status_code == 403
    FakeKite.errors = {SYMBOLS[0]: kite_exc.TokenException("expired")}
    assert post_m(client).status_code == 401 and token_store.load_session() is None
    assert post_m(client).status_code == 401  # not logged in now
    token_store.save_session("key123", ACCESS_TOKEN, "AB1234")
    FakeKite.errors = {}
    with scanner.exclusive():
        assert post_m(client).status_code == 409


# ================================================================== regime ====
def index_regime(sma_period):
    """Re-derive 'index close above its SMA' per date from the fake index prices (independent of the engine)."""
    closes = wave(99)
    days = [d.isoformat() for d in business_days_ending(TODAY, len(closes))]
    avg = signals_sma(closes, sma_period)
    return {days[i]: (avg[i] is not None and closes[i] > avg[i]) for i in range(len(days))}, days


def signals_sma(values, n):
    return [None if i < n - 1 else sum(values[i - n + 1 : i + 1]) / n for i in range(len(values))]


def previous_day(days, d):
    return days[days.index(d) - 1]


def test_crossover_regime_filter_only_enters_when_the_index_was_above_its_average(client):
    on, days = index_regime(100)
    data = post(client, max_stocks=10, regime_filter=True, regime_sma=100).json()
    assert data["trades"]
    assert all(on[previous_day(days, t["entry_date"])] for t in data["trades"])  # the signal day's close was ON
    assert data["signals_skipped"]["regime_off"] > 0 and data["params"]["regime_filter"] is True


def test_the_regime_filter_really_changes_the_trades(client):
    on, days = index_regime(100)
    plain = post(client, max_stocks=10).json()
    blocked = [t for t in plain["trades"] if not on[previous_day(days, t["entry_date"])]]
    assert blocked, "negative control: without the filter some entries happen while the regime is OFF"
    filtered = post(client, max_stocks=10, regime_filter=True, regime_sma=100).json()
    assert len(filtered["trades"]) < len(plain["trades"])
    assert plain["signals_skipped"]["regime_off"] == 0


def test_momentum_regime_filter_sells_everything_when_the_index_turns_off(client):
    on, days = index_regime(100)
    data = post_m(client, regime_filter=True, regime_sma=100).json()
    off_exits = [t for t in data["trades"] if t["exit_reason"] == "regime off"]
    assert off_exits, "the fake index drops below its average during the year"
    assert all(not on[previous_day(days, t["exit_date"])] for t in off_exits)
    assert all(on[previous_day(days, t["entry_date"])] for t in data["trades"])  # never buys while OFF
    assert data["signals_skipped"]["regime_off"] > 0


def test_regime_filter_downloads_extra_index_history_only(client):
    post(client, max_stocks=2, regime_filter=True, regime_sma=300)
    stock_from = min(f for t, f, _ in FakeKite.calls if t != INDEX_TOKEN)
    index_from = next(f for t, f, _ in FakeKite.calls if t == INDEX_TOKEN)
    assert (stock_from - index_from).days > 300  # the index needs ~490 days of warm-up, stocks only ~58


@pytest.mark.parametrize("call", ["crossover", "momentum"])
def test_regime_filter_without_the_index_is_a_clear_error(client, call):
    FakeKite.index_listed = False
    res = post(client, regime_filter=True) if call == "crossover" else post_m(client, regime_filter=True)
    assert res.status_code == 502 and "regime filter needs" in res.json()["detail"]


def test_regime_filter_when_the_index_download_fails_is_a_clear_error(client):
    FakeKite.errors = {"INDEX": kite_exc.DataException("nope")}
    res = post(client, regime_filter=True)
    assert res.status_code == 502 and "could not be downloaded" in res.json()["detail"]


@pytest.mark.parametrize("overrides", [{"regime_sma": 10}, {"regime_sma": 500}, {"holdout_pct": 90}, {"holdout_pct": -5}])
def test_crossover_new_options_are_validated(client, overrides):
    assert post(client, **overrides).status_code == 422


# ================================================================= hold-out ====
def test_holdout_splits_the_period_and_every_trade_lands_in_one_part(client):
    data = post(client, max_stocks=10).json()
    seg = data["segments"]
    assert seg["holdout_pct"] == 40
    days = [c["date"] for c in data["equity_curve"]]
    assert seg["split_date"] == days[round(len(days) * 0.6)]
    ins, oos = seg["in_sample"], seg["out_of_sample"]
    assert ins["period"]["start"] == days[0] and oos["period"]["end"] == days[-1]
    assert ins["period"]["trading_days"] + oos["period"]["trading_days"] == len(days)
    assert ins["trades"]["trades"] + oos["trades"]["trades"] == data["summary"]["trades"]
    for part in (ins, oos):
        assert part["strategy"] and part["nifty100"] and part["same_stocks"]
    # the two parts chain together: (1 + in-sample return) * (1 + out-of-sample return) = whole-period return
    whole = (1 + ins["strategy"]["total_return_pct"] / 100) * (1 + oos["strategy"]["total_return_pct"] / 100) - 1
    assert whole * 100 == pytest.approx(data["summary"]["total_return_pct"], abs=0.05)


def test_holdout_can_be_turned_off(client):
    assert post(client, holdout_pct=0).json()["segments"] is None
    assert post_m(client, holdout_pct=0).json()["segments"] is None


def test_holdout_size_is_respected(client):
    seg = post(client, holdout_pct=25).json()["segments"]
    n = seg["in_sample"]["period"]["trading_days"] + seg["out_of_sample"]["period"]["trading_days"]
    assert seg["out_of_sample"]["period"]["trading_days"] == pytest.approx(n * 0.25, abs=1)
