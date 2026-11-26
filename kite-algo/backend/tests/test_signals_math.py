"""Tests for the pure SMA / crossover maths (signals.py).

The expected numbers in the comments were worked out by hand.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from signals import latest_crossover, sma  # noqa: E402


def d(n):
    return [f"d{i}" for i in range(n)]


def test_sma_values_and_warmup():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]


def test_sma_period_longer_than_data_is_all_none():
    assert sma([1, 2], 5) == [None, None]


def test_bullish_crossover_detected_with_exact_values():
    # SMA2 = [-, 9.5, 8.5, 8.5, 10, 12]   SMA3 = [-, -, 9, 8.667, 9.333, 11]
    # short is below long on days 2-3, above on day 4  ->  bullish on d4
    closes = [10, 9, 8, 9, 11, 13]
    hit = latest_crossover(d(6), closes, 2, 3, lookback=10)
    assert hit["type"] == "bullish"
    assert hit["date"] == "d4"
    assert hit["close"] == 11
    assert hit["sma_short"] == pytest.approx(10)
    assert hit["sma_long"] == pytest.approx(9.3333, abs=1e-3)


def test_bearish_crossover_detected():
    # Mirror image of the case above.
    closes = [10, 11, 12, 11, 9, 7]
    hit = latest_crossover(d(6), closes, 2, 3, lookback=10)
    assert hit["type"] == "bearish"
    assert hit["date"] == "d4"
    assert hit["close"] == 9


def test_no_crossover_when_short_stays_above():
    closes = [10, 11, 12, 13, 14, 15, 16]
    assert latest_crossover(d(7), closes, 2, 3, lookback=10) is None


def test_first_sign_is_not_a_crossover():
    # Short is only ever above long. Nothing "crossed".
    closes = [10, 10, 10, 12, 14, 16]
    assert latest_crossover(d(6), closes, 2, 3, lookback=10) is None


def test_lookback_window_is_respected():
    closes = [10, 9, 8, 9, 11, 13]  # crossover on index 4 (the 2nd-to-last candle)
    assert latest_crossover(d(6), closes, 2, 3, lookback=1) is None  # last candle only
    assert latest_crossover(d(6), closes, 2, 3, lookback=2)["date"] == "d4"


def test_returns_most_recent_when_there_are_several():
    # up, cross down, then cross up again: the later one wins.
    closes = [10, 11, 12, 11, 9, 7, 6, 9, 13, 18]
    hit = latest_crossover(d(10), closes, 2, 3, lookback=10)
    assert hit["type"] == "bullish"
    assert hit["date"] > "d5"


def test_touch_then_same_direction_is_not_a_crossover():
    # short=1 means "the close itself"; long=2 is a 2-day average.
    # diff = half of the day-to-day change: + , 0 (flat day), +   -> no reversal
    assert latest_crossover(d(4), [1, 2, 2, 3], 1, 2, lookback=10) is None


def test_flat_day_does_not_hide_a_real_reversal():
    # + , 0 (flat day), -   -> a real bearish crossover on the last day
    hit = latest_crossover(d(4), [1, 2, 2, 1], 1, 2, lookback=10)
    assert hit["type"] == "bearish"
    assert hit["date"] == "d3"


def test_too_little_data_returns_none():
    assert latest_crossover(d(3), [1, 2, 3], 2, 30, lookback=10) is None
