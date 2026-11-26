"""Candle store: downloads, disk cache, refresh rules, request splitting."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candles  # noqa: E402
import scanner  # noqa: E402

IST = scanner.IST


def at(y, m, d, h=11, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=IST)


class FakeKite:
    def __init__(self):
        self.calls = []

    def historical_data(self, token, from_dt, to_dt, interval):
        assert interval == "day"
        self.calls.append((from_dt.date(), to_dt.date()))
        out, d = [], from_dt.date()
        while d <= to_dt.date():
            if d.weekday() < 5:
                p = 100 + (d - date(2018, 1, 1)).days * 0.01
                out.append(
                    {"date": datetime(d.year, d.month, d.day, tzinfo=IST), "open": p, "high": p + 1, "low": p - 1, "close": p + 0.5, "volume": 1}
                )
            d += timedelta(days=1)
        return out


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("CANDLES_DIR", str(tmp_path / "c"))
    candles.reset_memory()
    monkeypatch.setattr(scanner, "THROTTLE_SECONDS", 0)
    monkeypatch.setattr(scanner, "_sleep", lambda s: None)
    clock = {"now": at(2026, 11, 26, 16, 0)}  # Thursday, after the close
    monkeypatch.setattr(scanner, "_wall_clock", lambda: clock["now"])
    return clock


def unique_and_sorted(rows):
    days = [r[0] for r in rows]
    return days == sorted(set(days))


def test_first_call_downloads_once_and_saves(tmp_path):
    kite = FakeKite()
    rows = candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    assert kite.calls == [(date(2026, 11, 2), date(2026, 11, 26))]
    assert (rows[0][0], rows[-1][0], len(rows)) == ("2026-11-02", "2026-11-26", 19)
    assert (tmp_path / "c" / "5.json").exists()


def test_no_request_when_data_was_fetched_after_the_close(env):
    kite = FakeKite()
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    env["now"] = at(2026, 11, 26, 20, 0)
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    assert len(kite.calls) == 1


def test_next_day_downloads_only_the_recent_tail_and_merges(env):
    kite = FakeKite()
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    env["now"] = at(2026, 11, 27, 10, 0)  # Friday morning
    rows = candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 27))
    assert kite.calls[-1] == (date(2026, 11, 19), date(2026, 11, 27))  # 7 days overlap, not 5 years
    assert rows[0][0] == "2026-11-02" and rows[-1][0] == "2026-11-27"
    assert unique_and_sorted(rows) and len(rows) == 20


def test_data_fetched_during_market_hours_is_trusted_for_ten_minutes(env):
    kite = FakeKite()
    env["now"] = at(2026, 11, 26, 11, 0)
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    env["now"] = at(2026, 11, 26, 11, 5)
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    assert len(kite.calls) == 1
    env["now"] = at(2026, 11, 26, 11, 15)  # today's candle has moved on
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    assert len(kite.calls) == 2 and kite.calls[1] == (date(2026, 11, 19), date(2026, 11, 26))


def test_data_fetched_before_the_close_is_refreshed_the_next_morning(env):
    kite = FakeKite()
    env["now"] = at(2026, 11, 26, 11, 0)  # partial candle saved
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    env["now"] = at(2026, 11, 27, 9, 0)
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 27))
    assert len(kite.calls) == 2


def test_asking_for_older_history_downloads_only_the_missing_head(env):
    kite = FakeKite()
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    rows = candles.get_ohlc(kite, 5, date(2026, 10, 1), date(2026, 11, 26))
    assert len(kite.calls) == 2
    assert kite.calls[1] == (date(2026, 10, 1), date(2026, 11, 2))
    assert rows[0][0] == "2026-10-01" and rows[-1][0] == "2026-11-26"
    assert unique_and_sorted(rows)


def test_asking_for_a_shorter_range_needs_no_request_and_is_trimmed(env):
    kite = FakeKite()
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    rows = candles.get_ohlc(kite, 5, date(2026, 11, 16), date(2026, 11, 26))
    assert len(kite.calls) == 1
    assert rows[0][0] == "2026-11-16"


def test_long_ranges_are_split_into_requests_of_at_most_1995_days():
    kite = FakeKite()
    rows = candles.get_ohlc(kite, 5, date(2018, 1, 1), date(2026, 11, 26))
    assert len(kite.calls) == 2
    for a, b in kite.calls:
        assert (b - a).days + 1 <= 1995
    assert kite.calls[1][0] == kite.calls[0][1] + timedelta(days=1)  # contiguous, no gap, no overlap
    assert unique_and_sorted(rows) and rows[0][0] == "2018-01-01"


def test_weekend_asks_for_the_last_trading_day(env):
    kite = FakeKite()
    env["now"] = at(2026, 11, 28, 12, 0)  # Saturday
    rows = candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 28))
    assert kite.calls[0][1] == date(2026, 11, 27)
    assert rows[-1][0] == "2026-11-27"


def test_cache_survives_a_restart():
    kite = FakeKite()
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    candles.reset_memory()  # a new process: only the file is left
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    assert len(kite.calls) == 1


def test_corrupt_cache_file_is_ignored(tmp_path):
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "5.json").write_text("{not json")
    kite = FakeKite()
    rows = candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    assert len(kite.calls) == 1 and len(rows) == 19


def test_each_instrument_has_its_own_cache():
    kite = FakeKite()
    candles.get_ohlc(kite, 5, date(2026, 11, 2), date(2026, 11, 26))
    candles.get_ohlc(kite, 6, date(2026, 11, 2), date(2026, 11, 26))
    assert len(kite.calls) == 2


def test_rows_have_open_high_low_close():
    rows = candles.get_ohlc(FakeKite(), 5, date(2026, 11, 2), date(2026, 11, 3))
    day, o, h, low, c = rows[0]
    assert (h, low, c) == (o + 1, o - 1, o + 0.5)


def test_suspect_moves_flags_a_halving_but_not_normal_days():
    rows = [("d0", 0, 0, 0, 100.0), ("d1", 0, 0, 0, 104.0), ("d2", 0, 0, 0, 52.0), ("d3", 0, 0, 0, 53.0)]
    assert candles.suspect_moves(rows) == [{"date": "d2", "change_pct": -50.0}]
    assert candles.suspect_moves(rows[:2]) == []
    assert candles.suspect_moves([("a", 0, 0, 0, 100.0), ("b", 0, 0, 0, 134.0)]) == []  # +34% is under the line
    assert candles.suspect_moves([("a", 0, 0, 0, 100.0), ("b", 0, 0, 0, 136.0)])[0]["change_pct"] == 36.0
