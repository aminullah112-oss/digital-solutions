"""GET /api/scanner-data, POST /api/scanner-data/refresh and GET /api/ohlc (all read-only)."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kiteconnect import exceptions as kite_exc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

import candles  # noqa: E402
import main  # noqa: E402
import nifty100  # noqa: E402
import scanner  # noqa: E402
import scanner_data  # noqa: E402
import token_store  # noqa: E402
from fakes_algo import SpyKite, instrument  # noqa: E402

CSV_TEXT = (Path(__file__).parent / "fixtures" / "ind_nifty100list.csv").read_text(encoding="utf-8")
ROWS = nifty100.parse_csv(CSV_TEXT)
SYMBOLS = [r["symbol"] for r in ROWS]
NIFTY50_CSV = "\n".join(CSV_TEXT.splitlines()[:51]) + "\n"  # header + the first 50 symbols
IST = scanner.IST
WITH_DATA = SYMBOLS[:4] + SYMBOLS[60:63]  # 4 in the fake Nifty 50, 3 outside it
TOKENS = {s: 1000 + i for i, s in enumerate(SYMBOLS)}


def business_days_ending(end, n):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def candle_rows(n=90, base=100.0):
    return [
        {"date": datetime(d.year, d.month, d.day, tzinfo=IST), "open": base + i * 0.1, "high": base + i * 0.1 + 1, "low": base + i * 0.1 - 1, "close": base + i * 0.1 + 0.5, "volume": 1000 + i}
        for i, d in enumerate(business_days_ending(date(2026, 11, 26), n))
    ]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("KITE_SESSION_FILE", str(tmp_path / "session.json"))
    monkeypatch.setenv("NIFTY100_CACHE_FILE", str(tmp_path / "nifty100.csv"))
    monkeypatch.setenv("CANDLES_DIR", str(tmp_path / "candles"))
    monkeypatch.setattr(main, "KiteConnect", SpyKite)
    monkeypatch.setattr(nifty100, "_download", lambda url: NIFTY50_CSV if "nifty50" in url else CSV_TEXT)
    nifty100._memory.update(rows=None, at=0.0, source=None)
    nifty100._other_memory.clear()
    scanner.reset_caches()
    scanner_data.reset_cache()
    candles.reset_memory()
    monkeypatch.setattr(scanner, "THROTTLE_SECONDS", 0)
    monkeypatch.setattr(scanner, "_sleep", lambda s: None)
    monkeypatch.setattr(scanner, "_wall_clock", lambda: datetime(2026, 11, 26, 11, 0, tzinfo=IST))
    SpyKite.reset()
    SpyKite.instrument_rows = [instrument(s, TOKENS[s], 0.05) for s in WITH_DATA]
    SpyKite.candles = {TOKENS[s]: candle_rows(base=100 + i) for i, s in enumerate(WITH_DATA)}
    token_store.save_session("key123", "secret-token", "AB1234")
    yield
    assert SpyKite.mutating_calls == []
    scanner.reset_caches()
    scanner_data.reset_cache()
    candles.reset_memory()


@pytest.fixture
def client():
    return TestClient(main.app)


def history_calls():
    return SpyKite.read_calls.count("historical_data")


# ============================================================ scanner data ====
def test_response_shape(client):
    res = client.get("/api/scanner-data")
    assert res.status_code == 200
    data = res.json()
    assert set(data) == {"metadata", "stocks"}
    md = data["metadata"]
    assert md["interval"] == "day" and md["universe"] == "Nifty 100" and md["stock_count"] == len(WITH_DATA) == len(data["stocks"])
    assert md["cached"] is False and md["days"] == 120 and md["candles_to"] == "2026-11-26" and md["candles_from"] == "2026-07-29"
    stock = data["stocks"][0]
    assert set(stock) == {"symbol", "company_name", "instrument_token", "nifty_flags", "candles"}
    assert stock["symbol"] == SYMBOLS[0] and stock["company_name"] == ROWS[0]["company"] and stock["instrument_token"] == TOKENS[SYMBOLS[0]]
    assert set(stock["candles"][0]) == {"date", "open", "high", "low", "close", "volume"}


def test_candles_are_daily_with_iso_dates_and_numbers_oldest_first(client):
    for stock in client.get("/api/scanner-data").json()["stocks"]:
        dates = [c["date"] for c in stock["candles"]]
        assert dates == sorted(set(dates)) and all(len(d) == 10 and d[4] == "-" for d in dates)
        assert all(isinstance(c[k], (int, float)) for c in stock["candles"] for k in ("open", "high", "low", "close", "volume"))
        assert stock["candles"][-1]["volume"] == 1089 and stock["candles"][-1]["date"] == "2026-11-26"


def test_only_candles_inside_the_requested_window_are_returned(client):
    candles_ = client.get("/api/scanner-data?days=60").json()["stocks"][0]["candles"]
    assert candles_[0]["date"] >= "2026-09-27" and candles_[-1]["date"] == "2026-11-26"


def test_nifty_flags(client):
    flags = {s["symbol"]: s["nifty_flags"] for s in client.get("/api/scanner-data").json()["stocks"]}
    assert all(flags[s] == {"nifty100": True, "nifty50": True} for s in SYMBOLS[:4])
    assert all(flags[s] == {"nifty100": True, "nifty50": False} for s in SYMBOLS[60:63])


def test_nifty50_flag_is_unknown_not_false_when_that_list_cannot_be_loaded(client, monkeypatch):
    def download(url):
        if "nifty50" in url:
            raise ConnectionError("offline")
        return CSV_TEXT

    monkeypatch.setattr(nifty100, "_download", download)
    assert {s["nifty_flags"]["nifty50"] for s in client.get("/api/scanner-data").json()["stocks"]} == {None}


def test_stocks_missing_in_kite_are_listed_not_hidden(client):
    md = client.get("/api/scanner-data").json()["metadata"]
    assert len(md["skipped"]) == 100 - len(WITH_DATA)
    assert md["skipped"][0] == {"symbol": SYMBOLS[4], "reason": "Not found in Kite's NSE instrument list"}


def test_a_suspected_unadjusted_split_is_excluded_and_listed(client):
    rows = candle_rows()
    for r in rows[50:]:
        r["close"] /= 2  # a 2-for-1 split that was not adjusted for
        r["open"], r["high"], r["low"] = r["open"] / 2, r["high"] / 2, r["low"] / 2
    SpyKite.candles[TOKENS[SYMBOLS[0]]] = rows
    data = client.get("/api/scanner-data").json()
    assert SYMBOLS[0] not in {s["symbol"] for s in data["stocks"]}
    assert data["metadata"]["excluded"][0]["symbol"] == SYMBOLS[0] and "split" in data["metadata"]["excluded"][0]["reason"]


def test_a_failing_stock_is_skipped_not_fatal(client, monkeypatch):
    real = SpyKite.historical_data

    def flaky(self, token, a, b, interval):
        if token == TOKENS[SYMBOLS[0]]:
            raise kite_exc.DataException("bad data")
        return real(self, token, a, b, interval)

    monkeypatch.setattr(SpyKite, "historical_data", flaky)
    md = client.get("/api/scanner-data").json()["metadata"]
    assert md["stock_count"] == len(WITH_DATA) - 1 and any(s["symbol"] == SYMBOLS[0] and s["reason"].startswith("Kite error") for s in md["skipped"])


def test_second_request_comes_from_the_scanner_cache(client):
    client.get("/api/scanner-data")
    n = history_calls()
    again = client.get("/api/scanner-data").json()
    assert again["metadata"]["cached"] is True and history_calls() == n


def test_refresh_rebuilds_and_downloads_the_newest_candles_again(client):
    client.get("/api/scanner-data")
    n = history_calls()
    res = client.post("/api/scanner-data/refresh")
    assert res.status_code == 200 and res.json()["metadata"]["cached"] is False
    assert history_calls() == n + len(WITH_DATA)  # one fresh tail request per stock
    assert client.get("/api/scanner-data").json()["metadata"]["cached"] is True


def test_a_different_days_value_is_not_served_from_the_cache(client):
    client.get("/api/scanner-data?days=120")
    assert client.get("/api/scanner-data?days=90").json()["metadata"]["cached"] is False


@pytest.mark.parametrize("days", [0, 59, 366, "x"])
def test_days_is_validated(client, days):
    assert client.get(f"/api/scanner-data?days={days}").status_code == 422


def test_failures_are_clear(client):
    with scanner.exclusive():
        assert client.get("/api/scanner-data").status_code == 409
        assert client.post("/api/scanner-data/refresh").status_code == 409
    SpyKite.candles = {}
    SpyKite.state_error = None
    nifty100._memory.update(rows=None, at=0.0, source=None)
    scanner_data.reset_cache()


def test_missing_historical_permission_is_explained(client, monkeypatch):
    def denied(self, *a):
        raise kite_exc.PermissionException("Insufficient permission for that call.")

    monkeypatch.setattr(SpyKite, "historical_data", denied)
    res = client.get("/api/scanner-data")
    assert res.status_code == 403 and "Historical Data" in res.json()["detail"]


def test_an_expired_login_gives_401_and_clears_the_session(client, monkeypatch):
    def expired(self, *a):
        raise kite_exc.TokenException("expired")

    monkeypatch.setattr(SpyKite, "historical_data", expired)
    assert client.get("/api/scanner-data").status_code == 401 and token_store.load_session() is None
    assert client.get("/api/scanner-data").status_code == 401  # and stays 401


def test_the_nifty_list_failing_is_a_502(client, monkeypatch):
    def boom(url):
        raise ConnectionError("offline")

    monkeypatch.setattr(nifty100, "_download", boom)
    assert client.get("/api/scanner-data").status_code == 502


def test_no_access_token_in_the_response(client):
    assert "secret-token" not in client.get("/api/scanner-data").text


# ================================================================== ohlc ====
@pytest.fixture
def prices():
    SpyKite.ohlc_data = {
        "NSE:SIEMENS": {"instrument_token": 5, "last_price": 4043.5, "ohlc": {"open": 4000, "high": 4050, "low": 3990, "close": 4010}},
        "NSE:TCS": {"instrument_token": 6, "last_price": 3300.0, "ohlc": {"open": 3290, "high": 3310, "low": 3280, "close": 3295}},
    }


def test_ohlc_snapshot_maps_symbols_to_last_price(client, prices):
    res = client.get("/api/ohlc?symbols=SIEMENS,TCS")
    assert res.status_code == 200
    assert res.json() == {
        "prices": {
            "SIEMENS": {"last_price": 4043.5, "instrument_token": 5, "ohlc": {"open": 4000, "high": 4050, "low": 3990, "close": 4010}},
            "TCS": {"last_price": 3300.0, "instrument_token": 6, "ohlc": {"open": 3290, "high": 3310, "low": 3280, "close": 3295}},
        }
    }


def test_ohlc_leaves_out_symbols_kite_does_not_return_and_cleans_the_list(client, prices):
    res = client.get("/api/ohlc?symbols=siemens, NOSUCH ,siemens,,../x")
    assert list(res.json()["prices"]) == ["SIEMENS"]


def test_ohlc_needs_at_least_one_valid_symbol(client, prices):
    assert client.get("/api/ohlc?symbols=../../x").status_code == 422
    assert client.get("/api/ohlc").status_code == 422


def test_ohlc_limits_the_number_of_symbols(client, prices):
    many = ",".join(f"S{i}" for i in range(201))
    assert client.get(f"/api/ohlc?symbols={many}").status_code == 422


def test_ohlc_needs_a_login(client, prices):
    token_store.clear_session()
    assert client.get("/api/ohlc?symbols=SIEMENS").status_code == 401


def test_ohlc_asks_kite_with_nse_prefixes(client, prices, monkeypatch):
    seen = []
    real = SpyKite.ohlc
    monkeypatch.setattr(SpyKite, "ohlc", lambda self, ins: (seen.append(list(ins)), real(self, ins))[1])
    client.get("/api/ohlc?symbols=SIEMENS,TCS")
    assert seen == [["NSE:SIEMENS", "NSE:TCS"]]
