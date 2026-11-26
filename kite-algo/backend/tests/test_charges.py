"""Charges. The expected numbers were worked out by hand from the rates in charges.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import charges  # noqa: E402


def test_buy_charges_on_one_lakh():
    # STT 100 + stamp 15 + NSE 2.97 + SEBI 0.10 + GST 18% of (2.97 + 0.10) = 0.5526
    assert charges.buy_charges(100_000) == 118.62


def test_sell_charges_on_one_lakh():
    # STT 100 + NSE 2.97 + SEBI 0.10 + GST 0.5526 + DP 15.93
    assert charges.sell_charges(100_000) == 119.55


def test_round_trip_with_default_slippage_is_about_a_third_of_a_percent():
    round_trip = charges.buy_charges(100_000) + charges.sell_charges(100_000)
    slippage = 2 * 100_000 * 0.05 / 100  # 0.05% each side
    assert round_trip + slippage == pytest.approx(338.17, abs=0.01)  # the "about 338 rupees" in the design doc


def test_rates_are_editable(monkeypatch):
    monkeypatch.setitem(charges.RATES, "stt_buy_pct", 0.0)
    monkeypatch.setitem(charges.RATES, "stamp_buy_pct", 0.0)
    assert charges.buy_charges(100_000) == pytest.approx(2.97 + 0.10 + 0.5526, abs=0.01)
