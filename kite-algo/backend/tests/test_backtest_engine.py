"""Backtest engine tests. Every expected number is worked out by hand in the comments.

Test series (short SMA 2, long SMA 3), closes by day index:

    idx    0   1   2   3   4   5   6   7   8   9  10
    close 10   9   8   9  11  13  14  12   9   7   6
    open  10  10   9   8   9  12  13  14  11   8   7

  * bullish crossover on idx 4 (SMA2 10 vs SMA3 9.33)  -> buy at the OPEN of idx 5 = 12
  * idx 7 has SMA2 == SMA3 == 13 exactly (a touch, not a crossover)
  * bearish crossover on idx 8                          -> sell at the OPEN of idx 9 = 8
  * with 100,000 per position: 100000 // 12 = 8333 shares
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest  # noqa: E402
import signals  # noqa: E402


def business_days(n, start=date(2026, 1, 5)):  # a Monday
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


CLOSES = [10, 9, 8, 9, 11, 13, 14, 12, 9, 7, 6]
OPENS = [10, 10, 9, 8, 9, 12, 13, 14, 11, 8, 7]
DATES = business_days(11)  # idx 0 = Mon 5 Jan ... idx 5 = Mon 12 Jan, idx 9 = Fri 16 Jan


def make_rows(closes=CLOSES, opens=OPENS, overrides=None):
    rows = []
    for i, (c, o) in enumerate(zip(closes, opens)):
        row_open, high, low = o, max(o, c) + 0.1, min(o, c) - 0.1
        if overrides and i in overrides:
            row_open, high, low = overrides[i]
        rows.append((DATES[i], row_open, high, low, c))
    return rows


def run(stocks, **overrides):
    params = dict(
        short_sma=2,
        long_sma=3,
        starting_capital=100_000,
        max_positions=1,
        stop_loss_pct=None,
        slippage_pct=0,
        include_charges=False,
        start_date=DATES[0],
    )
    params.update(overrides)
    return backtest.run(stocks, **params)


def one(rows=None, **kw):
    return run({"AAA": {"company": "Alpha Ltd.", "rows": rows or make_rows()}}, **kw)


def test_the_test_series_crosses_where_the_docstring_says():
    assert [(i, k) for i, k, _, _ in signals.crossovers(CLOSES, 2, 3)] == [(4, "bullish"), (8, "bearish")]


# ------------------------------------------------------------ basic trade ----
def test_buys_next_open_and_sells_next_open_after_exit_signal():
    res = one()
    assert len(res["trades"]) == 1
    t = res["trades"][0]
    assert (t["symbol"], t["company"]) == ("AAA", "Alpha Ltd.")
    assert (t["entry_date"], t["entry_price"]) == (DATES[5], 12.0)  # the open after the signal, not the signal day's close of 11
    assert (t["exit_date"], t["exit_price"]) == (DATES[9], 8.0)
    assert t["shares"] == 8333  # 100000 // 12
    assert t["days_held"] == 4  # Mon 12 Jan -> Fri 16 Jan
    assert t["exit_reason"] == "bearish crossover"
    assert t["pnl"] == -33_332.0  # 8333 * (8 - 12)
    assert t["pnl_pct"] == -33.33  # -33332 / 99996


def test_summary_of_a_single_losing_trade():
    s = one()["summary"]
    assert s["final_value"] == 66_668.0  # 100000 - 99996 + 66664
    assert s["net_profit"] == -33_332.0
    assert s["total_return_pct"] == -33.33
    assert (s["trades"], s["wins"], s["losses"]) == (1, 0, 1)
    assert s["win_rate_pct"] == 0.0 and s["profit_factor"] == 0.0
    assert s["avg_win_pct"] is None and s["avg_loss_pct"] == -33.33


def test_equity_curve_is_marked_to_market_each_day():
    curve = {c["date"]: c["strategy"] for c in one()["equity_curve"]}
    assert curve[DATES[4]] == 100_000.0  # signal day: nothing bought yet
    assert curve[DATES[5]] == 108_333.0  # 4 cash + 8333 * close 13
    assert curve[DATES[10]] == 66_668.0  # all cash again
    assert len(curve) == 11


def test_no_look_ahead_a_signal_on_the_last_day_is_never_traded():
    res = one(make_rows()[:5])  # idx 4 is the last candle and the bullish crossover day
    assert res["trades"] == [] and res["summary"]["final_value"] == 100_000.0


def test_position_still_open_is_sold_at_the_last_close():
    res = one(make_rows()[:8])  # ends on idx 7, bought on idx 5, no exit signal yet
    t = res["trades"][0]
    assert (t["exit_reason"], t["exit_date"], t["exit_price"]) == ("end of test", DATES[7], 12.0)
    assert t["pnl"] == 0.0  # 8333 * (12 - 12)
    assert res["equity_curve"][-1]["strategy"] == 100_000.0  # 4 cash + 99996 sale proceeds


def test_signals_from_the_warm_up_period_trade_on_the_first_test_day():
    res = one(start_date=DATES[5])  # the crossover happened on idx 4, before the test starts
    assert res["period"]["start"] == DATES[5]
    assert res["trades"][0]["entry_date"] == DATES[5]


def test_no_data_in_period_raises():
    with pytest.raises(backtest.NoDataError):
        one(start_date="2027-01-01")


# ----------------------------------------------------------------- costs ----
def test_charges_are_deducted_on_both_legs_and_shares_are_sized_to_fit_the_slot():
    res = one(include_charges=True)
    t = res["trades"][0]
    # 8333 shares would cost 99,996 + 118.62 of charges = 100,114.62: over the 100,000 slot.
    # So the engine buys 8323 instead:
    #   buy  99,876: STT 99.876 + stamp 14.9814 + NSE 2.9663 + SEBI 0.0999 + GST 0.5519 = 118.48  (total 99,994.48)
    #   sell 66,584: STT 66.584 + NSE 1.9775 + SEBI 0.0666 + GST 0.3679 + DP 15.93      =  84.93
    assert t["shares"] == 8323
    assert t["charges"] == pytest.approx(203.41, abs=0.02)
    assert t["pnl"] == pytest.approx(66_584 - 84.93 - 99_994.48, abs=0.05)  # about -33,495.41
    assert res["costs"]["charges"] == pytest.approx(203.41, abs=0.02)


def test_a_trade_is_not_dropped_just_because_charges_push_it_over_the_slot():
    # The bug this guards against: sizing by price alone, then skipping the trade when charges did not fit.
    res = one(include_charges=True, max_positions=1)
    assert len(res["trades"]) == 1 and res["signals_skipped"]["not_enough_cash"] == 0


def test_equity_after_a_buy_with_charges_is_leftover_cash_plus_shares_at_the_close():
    curve = {c["date"]: c["strategy"] for c in one(include_charges=True)["equity_curve"]}
    # cash left = 100,000 - 99,994.48 = 5.52;  shares = 8323 * close 13 = 108,199
    assert curve[DATES[5]] == pytest.approx(5.52 + 8323 * 13, abs=0.05)
    assert all(v > 0 for v in curve.values())


def test_slippage_makes_both_fills_worse():
    res = one(slippage_pct=1.0)
    t = res["trades"][0]
    assert t["entry_price"] == 12.12  # 12 * 1.01
    assert t["exit_price"] == 7.92  # 8 * 0.99
    assert t["shares"] == 8250  # 100000 // 12.12
    assert t["pnl"] == -34_650.0  # 8250 * 7.92 - 8250 * 12.12
    assert res["costs"]["slippage"] == pytest.approx(1650.0)  # 8250 * 0.12 + 8250 * 0.08


# ------------------------------------------------------------- stop-loss ----
def test_stop_fills_at_the_stop_price_when_the_low_touches_it():
    # stop = 12 * 0.9 = 10.80; idx 6 opens at 13 and trades down to 10.50
    res = one(make_rows(overrides={6: (13.0, 14.1, 10.5)}), stop_loss_pct=10)
    t = res["trades"][0]
    assert (t["exit_reason"], t["exit_date"], t["exit_price"]) == ("stop-loss", DATES[6], 10.8)
    assert t["pnl"] == pytest.approx(-9_999.6)  # 8333 * (10.8 - 12)


def test_stop_fills_at_the_open_when_the_stock_gaps_below_it():
    res = one(make_rows(overrides={6: (10.0, 14.1, 9.5)}), stop_loss_pct=10)  # opens below the 10.80 stop
    t = res["trades"][0]
    assert (t["exit_reason"], t["exit_price"]) == ("stop-loss", 10.0)  # the gap is a real loss
    assert t["pnl"] == pytest.approx(-16_666.0)  # 8333 * (10 - 12)


def test_stop_can_trigger_on_the_day_of_entry():
    res = one(make_rows(overrides={5: (12.0, 13.1, 10.0)}), stop_loss_pct=10)
    t = res["trades"][0]
    assert t["entry_date"] == t["exit_date"] == DATES[5]
    assert (t["exit_reason"], t["exit_price"], t["days_held"]) == ("stop-loss", 10.8, 0)


def test_stop_wins_when_it_and_a_bearish_exit_fall_on_the_same_day():
    # bearish exit would sell at idx 9's open of 9; the 30% stop is 8.40 and idx 9 trades down to 8.00
    res = one(make_rows(overrides={9: (9.0, 9.5, 8.0)}), stop_loss_pct=30)
    t = res["trades"][0]
    assert (t["exit_reason"], t["exit_price"]) == ("stop-loss", 8.4)


def test_no_stop_means_no_stop_exits():
    assert one(make_rows(overrides={6: (10.0, 14.1, 5.0)}))["trades"][0]["exit_reason"] == "bearish crossover"


# ------------------------------------------------- slots and position size ----
def two_identical(**kw):
    stocks = {name: {"company": name, "rows": make_rows()} for name in ("BBB", "AAA")}  # BBB listed first on purpose
    return run(stocks, **kw)


def test_when_slots_are_full_extra_signals_are_skipped_in_ticker_order():
    res = two_identical(max_positions=1)
    assert [t["symbol"] for t in res["trades"]] == ["AAA"]  # alphabetical, whatever the input order
    assert res["signals_skipped"] == {"no_free_slot": 1, "not_enough_cash": 0}


def test_with_enough_slots_both_trade_and_each_gets_capital_divided_by_slots():
    res = two_identical(max_positions=2, starting_capital=200_000)
    assert [t["symbol"] for t in res["trades"]] == ["AAA", "BBB"]  # same entry day: ties by ticker
    assert all(t["shares"] == 8333 for t in res["trades"])  # 100000 // 12 each
    assert res["signals_skipped"]["no_free_slot"] == 0


def test_a_price_above_the_position_size_is_skipped_and_counted():
    res = one(make_rows(overrides={5: (200_000.0, 200_001.0, 199_999.0)}))
    assert res["trades"] == [] and res["signals_skipped"]["not_enough_cash"] == 1


# --------------------------------------------------------------- metrics ----
def test_win_rate_profit_factor_and_averages_across_two_trades():
    opens_b = list(OPENS)
    opens_b[9] = 20  # BBB sells at 20 instead of 8
    stocks = {"AAA": {"company": "A", "rows": make_rows()}, "BBB": {"company": "B", "rows": make_rows(opens=opens_b)}}
    res = run(stocks, max_positions=2, starting_capital=200_000)
    s = res["summary"]
    # AAA: 8333 * (8 - 12) = -33332     BBB: 8333 * (20 - 12) = +66664
    assert (s["trades"], s["wins"], s["losses"]) == (2, 1, 1)
    assert s["win_rate_pct"] == 50.0
    assert s["profit_factor"] == 2.0  # 66664 / 33332
    assert s["avg_win_pct"] == 66.67 and s["avg_loss_pct"] == -33.33
    assert s["avg_holding_days"] == 4.0
    assert s["net_profit"] == 33_332.0


def test_max_drawdown_is_the_worst_peak_to_trough_fall():
    assert backtest.max_drawdown_pct([100, 120, 90, 110, 60, 130]) == -50.0  # 120 -> 60
    assert backtest.max_drawdown_pct([100, 110, 120]) == 0.0


def test_summary_drawdown_matches_the_equity_curve():
    res = one()
    values = [c["strategy"] for c in res["equity_curve"]]
    assert res["summary"]["max_drawdown_pct"] == backtest.max_drawdown_pct(values)
    assert res["summary"]["max_drawdown_pct"] == pytest.approx(-100 * (116_666 - 66_668) / 116_666, abs=0.01)  # peak: 4 + 8333 * close 14


def test_cagr_is_none_for_periods_shorter_than_a_month():
    assert one()["summary"]["cagr_pct"] is None  # only 11 trading days


def test_cagr_for_a_full_year():
    assert backtest._cagr_pct(100.0, 121.0, "2025-01-01", "2026-01-01") == pytest.approx(21.0, abs=0.05)
    assert backtest._cagr_pct(100.0, 121.0, "2024-01-01", "2026-01-01") == pytest.approx(10.0, abs=0.1)


# ------------------------------------------------------------- benchmarks ----
def test_index_benchmark_tracks_the_index():
    index_rows = [(DATES[i], 0, 0, 0, 100 + 10 * i) for i in range(11)]  # 100 -> 200
    res = one(index_rows=index_rows)
    assert res["benchmarks"]["nifty100"]["final_value"] == 200_000.0
    assert res["benchmarks"]["nifty100"]["total_return_pct"] == 100.0
    assert res["equity_curve"][0]["nifty100"] == 100_000.0


def test_same_stocks_benchmark_holds_everything_equal_weight_from_day_one():
    res = one()  # one stock: close 10 on day one, 6 on the last day
    b = res["benchmarks"]["same_stocks"]
    assert (b["stocks"], b["final_value"], b["total_return_pct"]) == (1, 60_000.0, -40.0)


def test_same_stocks_benchmark_splits_capital_equally():
    up = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 20]  # doubles on the last day
    flat = [10] * 11
    stocks = {
        "UP": {"company": "", "rows": make_rows(closes=up, opens=up)},
        "FLAT": {"company": "", "rows": make_rows(closes=flat, opens=flat)},
    }
    b = run(stocks)["benchmarks"]["same_stocks"]
    assert b["final_value"] == 150_000.0  # 50k doubled + 50k flat


def test_missing_index_gives_no_index_benchmark():
    assert one()["benchmarks"]["nifty100"] is None
    assert all(c["nifty100"] is None for c in one()["equity_curve"])


def test_index_gaps_are_forward_filled():
    index_rows = [(DATES[0], 0, 0, 0, 100), (DATES[5], 0, 0, 0, 150)]  # only two prints
    curve = {c["date"]: c["nifty100"] for c in one(index_rows=index_rows)["equity_curve"]}
    assert curve[DATES[3]] == 100_000.0 and curve[DATES[5]] == 150_000.0 and curve[DATES[10]] == 150_000.0


# ----------------------------------------------------------------- order ----
def test_trades_are_listed_newest_entry_first():
    # second stock is bought a day later because its series starts one day later
    late = business_days(12)[1:]
    rows_late = [(late[i], OPENS[i], max(OPENS[i], CLOSES[i]) + 0.1, min(OPENS[i], CLOSES[i]) - 0.1, CLOSES[i]) for i in range(11)]
    stocks = {"AAA": {"company": "", "rows": make_rows()}, "ZZZ": {"company": "", "rows": rows_late}}
    res = run(stocks, max_positions=2, starting_capital=200_000)
    assert [t["symbol"] for t in res["trades"]] == ["ZZZ", "AAA"]
    assert res["trades"][0]["entry_date"] > res["trades"][1]["entry_date"]
