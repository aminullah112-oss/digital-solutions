"""Tests for the scanner and POST /api/signals/sma-crossover.

A fake Kite client supplies instruments and candles, so no network or
credentials are needed.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kiteconnect import exceptions as kite_exc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
import nifty100  # noqa: E402
import scanner  # noqa: E402
import signals  # noqa: E402
import token_store  # noqa: E402

CSV_TEXT = (Path(__file__).parent / "fixtures" / "ind_nifty100list.csv").read_text(encoding="utf-8")
SYMBOLS = [r["symbol"] for r in nifty100.parse_csv(CSV_TEXT)]
NOT_IN_KITE = SYMBOLS[-1]  # pretend Kite has no instrument for the last symbol
TOKENS = {sym: 1000 + i for i, sym in enumerate(SYMBOLS)}
SYMBOL_OF = {tok: sym for sym, tok in TOKENS.items()}

TODAY = date(2026, 11, 26)  # a Thursday
ACCESS_TOKEN = "secret-token-xyz"


def business_days_ending(end, n):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def down_then_up(n_down, n_up):
    """Falls (short SMA below long), then rises: produces a bullish crossover."""
    closes = [150.0 - i for i in range(n_down)]
    last = closes[-1]
    return closes + [last + 3.0 * (i + 1) for i in range(n_up)]


class FakeScanKite:
    series = {}  # symbol -> closes (oldest first, ending today)
    errors = {}  # symbol -> exception to raise (or a list, consumed one per call)
    calls = []  # symbols requested, in order
    call_times = []

    def __init__(self, api_key, timeout=None):
        pass

    def set_access_token(self, token):
        pass

    def instruments(self, exchange):
        assert exchange == "NSE"
        rows = [
            {"tradingsymbol": s, "instrument_token": TOKENS[s], "name": s, "segment": "NSE", "instrument_type": "EQ"}
            for s in SYMBOLS
            if s != NOT_IN_KITE
        ]
        # Noise that must be ignored: same symbol on BSE, an index, a bond-like row.
        rows += [
            {"tradingsymbol": SYMBOLS[0], "instrument_token": 1, "name": "x", "segment": "BSE", "instrument_type": "EQ"},
            {"tradingsymbol": "NIFTY 50", "instrument_token": 2, "name": "x", "segment": "INDICES", "instrument_type": "EQ"},
            {"tradingsymbol": NOT_IN_KITE, "instrument_token": 3, "name": "x", "segment": "NSE", "instrument_type": "BE"},
        ]
        return rows

    def historical_data(self, token, from_date, to_date, interval):
        sym = SYMBOL_OF[token]
        FakeScanKite.calls.append(sym)
        FakeScanKite.call_times.append(scanner._now())
        assert interval == "day"
        assert isinstance(from_date, datetime) and isinstance(to_date, datetime)
        err = FakeScanKite.errors.get(sym)
        if isinstance(err, list):
            err = err.pop(0) if err else None
        if err:
            raise err
        closes = FakeScanKite.series.get(sym, [100.0] * 80)
        days = business_days_ending(TODAY, len(closes))
        tz = scanner.IST
        return [
            {"date": datetime(d.year, d.month, d.day, tzinfo=tz), "open": c, "high": c, "low": c, "close": c, "volume": 1}
            for d, c in zip(days, closes)
        ]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("KITE_SESSION_FILE", str(tmp_path / "session.json"))
    monkeypatch.setenv("NIFTY100_CACHE_FILE", str(tmp_path / "nifty100.csv"))
    monkeypatch.setattr(main, "KiteConnect", FakeScanKite)
    monkeypatch.setattr(nifty100, "_download", lambda url: CSV_TEXT)
    nifty100._memory.update(rows=None, at=0.0, source=None)
    scanner.reset_caches()
    monkeypatch.setattr(scanner, "THROTTLE_SECONDS", 0)
    monkeypatch.setattr(scanner, "_sleep", lambda s: None)
    monkeypatch.setattr(
        scanner, "_wall_clock", lambda: datetime(2026, 11, 26, 11, 0, tzinfo=scanner.IST)  # 11:00 IST, market open
    )
    FakeScanKite.series = {}
    FakeScanKite.errors = {}
    FakeScanKite.calls = []
    FakeScanKite.call_times = []
    token_store.save_session("key123", ACCESS_TOKEN, "AB1234")
    yield
    scanner.reset_caches()


@pytest.fixture
def client():
    return TestClient(main.app)


def scan(client, **overrides):
    body = {"short_sma": 6, "long_sma": 30, "lookback_days": 20, "max_stocks": 100}
    body.update(overrides)
    return client.post("/api/signals/sma-crossover", json=body)


def expected_hit(closes, short=6, long=30, lookback=20):
    dates = [d.isoformat() for d in business_days_ending(TODAY, len(closes))]
    return signals.latest_crossover(dates, closes, short, long, lookback)


# ----------------------------------------------------------- happy path ----
def test_ranks_most_recent_crossover_first_and_numbers_rows(client):
    FakeScanKite.series = {
        SYMBOLS[0]: down_then_up(60, 12),  # older crossover
        SYMBOLS[1]: down_then_up(60, 8),  # newer crossover
        SYMBOLS[2]: down_then_up(60, 8),  # same day as SYMBOLS[1]: tie broken by ticker
    }
    res = scan(client)
    assert res.status_code == 200
    data = res.json()

    older = expected_hit(FakeScanKite.series[SYMBOLS[0]])
    newer = expected_hit(FakeScanKite.series[SYMBOLS[1]])
    assert older and newer and older["date"] < newer["date"], "test data must produce distinct dates"

    rows = data["results"]
    assert [r["symbol"] for r in rows] == sorted([SYMBOLS[1], SYMBOLS[2]]) + [SYMBOLS[0]]
    assert [r["rank"] for r in rows] == [1, 2, 3]
    assert [r["crossover_date"] for r in rows] == [newer["date"], newer["date"], older["date"]]

    first = rows[0]
    assert first["company"] == "Adani Energy Solutions Ltd."
    assert first["crossover_type"] == "bullish"
    assert first["close"] == round(newer["close"], 2)
    assert first["sma_short"] == round(newer["sma_short"], 2)
    assert first["sma_long"] == round(newer["sma_long"], 2)


def test_stock_that_has_not_crossed_yet_is_not_listed(client):
    # 6 up-days are not enough for a 6-day SMA to overtake a 30-day SMA.
    FakeScanKite.series = {SYMBOLS[0]: down_then_up(60, 6)}
    assert scan(client, max_stocks=1).json()["results"] == []


def test_bearish_crossover_reported(client):
    closes = [100.0 + i for i in range(60)]
    closes += [closes[-1] - 3.0 * (i + 1) for i in range(8)]
    FakeScanKite.series = {SYMBOLS[0]: closes}
    rows = scan(client).json()["results"]
    assert [r["crossover_type"] for r in rows] == ["bearish"]


def test_flat_stocks_produce_no_signals(client):
    data = scan(client).json()
    assert data["results"] == []


def test_response_metadata(client):
    data = scan(client, short_sma=5, long_sma=20, lookback_days=10, max_stocks=7).json()
    assert data["params"] == {"short_sma": 5, "long_sma": 20, "lookback_days": 10, "max_stocks": 7}
    assert data["universe"] == {
        "name": "Nifty 100",
        "requested": 7,
        "scanned": 7,
        "source": nifty100.SOURCES[0],
        "stale": False,
    }
    assert data["market_open"] is True
    assert data["data_as_of"] == TODAY.isoformat()
    assert data["generated_at"].startswith("2026-11-26T11:00:00")


def test_market_open_flag_false_after_close(client, monkeypatch):
    monkeypatch.setattr(
        scanner, "_wall_clock", lambda: datetime(2026, 11, 26, 16, 0, tzinfo=scanner.IST)
    )
    assert scan(client, max_stocks=1).json()["market_open"] is False


def test_max_stocks_limits_how_many_are_scanned(client):
    scan(client, max_stocks=5)
    assert FakeScanKite.calls == SYMBOLS[:5]


def test_instrument_mapping_ignores_bse_index_and_non_eq_rows(client):
    scan(client, max_stocks=1)  # SYMBOLS[0] also exists on BSE with token 1
    assert FakeScanKite.calls == [SYMBOLS[0]]  # would KeyError in the fake if the BSE token were used


def test_symbol_missing_in_kite_is_reported_not_fatal(client):
    data = scan(client).json()
    assert data["universe"]["requested"] == 100
    assert data["universe"]["scanned"] == 99
    assert data["skipped"] == [{"symbol": NOT_IN_KITE, "reason": "Not found in Kite's NSE instrument list"}]


# ------------------------------------------------------ per-stock errors ----
def test_one_failing_stock_is_skipped_and_scan_continues(client):
    FakeScanKite.errors = {SYMBOLS[0]: kite_exc.DataException("bad candle data")}
    FakeScanKite.series = {SYMBOLS[1]: down_then_up(60, 8)}
    data = scan(client, max_stocks=3).json()
    assert [s["symbol"] for s in data["skipped"]] == [SYMBOLS[0]]
    assert data["skipped"][0]["reason"].startswith("Kite error:")
    assert [r["symbol"] for r in data["results"]] == [SYMBOLS[1]]


def test_short_history_is_skipped_with_reason(client):
    FakeScanKite.series = {SYMBOLS[0]: [100.0] * 10}
    data = scan(client, max_stocks=1).json()
    assert data["skipped"] == [{"symbol": SYMBOLS[0], "reason": "Only 10 days of price history"}]


def test_too_many_requests_is_retried_once(client, monkeypatch):
    sleeps = []
    monkeypatch.setattr(scanner, "_sleep", sleeps.append)
    FakeScanKite.errors = {SYMBOLS[0]: [kite_exc.NetworkException("Too many requests", code=429)]}
    data = scan(client, max_stocks=1).json()
    assert data["skipped"] == []
    assert FakeScanKite.calls == [SYMBOLS[0], SYMBOLS[0]]
    assert 1.0 in sleeps


# ------------------------------------------------------- fatal conditions ----
def test_missing_historical_permission_gives_clear_403(client):
    FakeScanKite.errors = {SYMBOLS[0]: kite_exc.PermissionException("Insufficient permission for that call.")}
    res = scan(client, max_stocks=3)
    assert res.status_code == 403
    assert "Historical Data" in res.json()["detail"]
    assert FakeScanKite.calls == [SYMBOLS[0]]  # stops immediately, no point hammering Kite


def test_expired_token_returns_401_and_clears_session(client, tmp_path):
    FakeScanKite.errors = {SYMBOLS[0]: kite_exc.TokenException("Incorrect `api_key` or `access_token`.")}
    res = scan(client, max_stocks=3)
    assert res.status_code == 401
    assert token_store.load_session() is None


def test_not_logged_in_returns_401(client):
    token_store.clear_session()
    assert scan(client).status_code == 401


def test_concurrent_scan_is_rejected_with_409(client):
    assert scanner._scan_lock.acquire(blocking=False)
    try:
        res = scan(client)
    finally:
        scanner._scan_lock.release()
    assert res.status_code == 409
    assert scan(client, max_stocks=1).status_code == 200  # lock released: works again


def test_constituents_failure_gives_502(client, monkeypatch):
    def boom(url):
        raise ConnectionError("offline")

    monkeypatch.setattr(nifty100, "_download", boom)
    res = scan(client)
    assert res.status_code == 502
    assert "Nifty 100" in res.json()["detail"]


def test_response_never_contains_the_access_token(client):
    FakeScanKite.series = {SYMBOLS[0]: down_then_up(60, 8)}
    assert ACCESS_TOKEN not in scan(client).text


# ------------------------------------------------------------ validation ----
@pytest.mark.parametrize(
    "overrides",
    [
        {"short_sma": 30, "long_sma": 30},
        {"short_sma": 40, "long_sma": 30},
        {"short_sma": 1},
        {"long_sma": 1000},
        {"lookback_days": 0},
        {"max_stocks": 0},
        {"max_stocks": 101},
    ],
)
def test_invalid_inputs_are_rejected(client, overrides):
    assert scan(client, **overrides).status_code == 422
    assert FakeScanKite.calls == []


def test_short_not_smaller_than_long_message(client):
    res = scan(client, short_sma=30, long_sma=6)
    assert "Short SMA must be smaller than Long SMA" in str(res.json()["detail"])


def test_defaults_are_6_30_20_100(client):
    res = client.post("/api/signals/sma-crossover", json={})
    assert res.json()["params"] == {"short_sma": 6, "long_sma": 30, "lookback_days": 20, "max_stocks": 100}


# -------------------------------------------------- throttling and caching ----
def test_requests_are_spaced_to_respect_kite_rate_limit(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(scanner, "_now", lambda: clock[0])
    monkeypatch.setattr(scanner, "_sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    monkeypatch.setattr(scanner, "THROTTLE_SECONDS", 0.4)
    scanner.reset_caches()
    scan(client, max_stocks=5)
    gaps = [b - a for a, b in zip(FakeScanKite.call_times, FakeScanKite.call_times[1:])]
    assert len(gaps) == 4
    assert all(g >= 0.4 - 1e-9 for g in gaps)  # never faster than 2.5 requests/second


def test_candles_are_cached_between_scans_with_same_or_shorter_range(client):
    scan(client, max_stocks=4)
    first = len(FakeScanKite.calls)
    assert first == 4
    scan(client, max_stocks=4, short_sma=5, long_sma=20, lookback_days=10)  # needs fewer days
    assert len(FakeScanKite.calls) == first  # no new downloads


def test_longer_range_forces_a_fresh_download(client):
    scan(client, max_stocks=4)
    scan(client, max_stocks=4, long_sma=100, lookback_days=100)  # needs more history than cached
    assert len(FakeScanKite.calls) == 8


def test_cache_expires(client, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(scanner, "_now", lambda: now[0])
    scan(client, max_stocks=2)
    now[0] += scanner.CANDLES_TTL_SECONDS + 1
    scan(client, max_stocks=2)
    assert len(FakeScanKite.calls) == 4
