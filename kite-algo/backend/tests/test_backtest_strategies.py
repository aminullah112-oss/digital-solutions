"""Regime filter, momentum rotation and the hold-out split. Expected numbers are worked out by hand.

Momentum fixture: 40 business days from Mon 5 Jan 2026 (idx 0..39; Feb 2 is idx 20). Open = close.

    AAA  100 + 2*i                          (steady riser)
    BBB  100 + i  up to idx 14, then 114 + 12*(i-14)   (takes off after idx 14)
    CCC  100 - 0.5*i                        (faller)

Lookback 5, skip 1: the score at signal day p is  close[p-1] / close[p-5] - 1.
  first rebalance (signal idx 9):  AAA 116/108 = +7.41%   BBB 108/104 = +3.85%   CCC 96/98 = -2.04%
  second rebalance (signal idx19): BBB 162/114 = +42.1%   AAA 136/128 = +6.25%   CCC 91/93  = -2.15%
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest  # noqa: E402


def business_days(n, start=date(2026, 1, 5)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


D40 = business_days(40)


def flat_rows(closes, dates=D40):
    return [(dates[i], c, c, c, c) for i, c in enumerate(closes)]


AAA = [100 + 2 * i for i in range(40)]
BBB = [100 + i if i <= 14 else 114 + 12 * (i - 14) for i in range(40)]
CCC = [100 - 0.5 * i for i in range(40)]
STOCKS = {name: {"company": name, "rows": flat_rows(c)} for name, c in (("AAA", AAA), ("BBB", BBB), ("CCC", CCC))}


def momentum(stocks=None, **kw):
    params = dict(
        lookback_days=5, skip_days=1, top_n=1, keep_rank=1, starting_capital=100_000,
        stop_loss_pct=None, slippage_pct=0, include_charges=False, start_date=D40[10],
    )
    params.update(kw)
    return backtest.run_momentum(stocks or STOCKS, **params)


# ------------------------------------------------------------------ regime ----
def test_regime_is_on_only_when_the_index_closes_above_its_average():
    # closes 10,10,10,12,8   SMA3 = -, -, 10, 10.667, 10
    days = business_days(5)
    regime = backtest.Regime([(days[i], 0, 0, 0, c) for i, c in enumerate([10, 10, 10, 12, 8])], 3)
    assert regime.is_on(days[0]) is False  # SMA not defined yet counts as OFF
    assert regime.is_on(days[2]) is False  # 10 is not above 10
    assert regime.is_on(days[3]) is True  # 12 > 10.667
    assert regime.is_on(days[4]) is False  # 8 < 10
    assert regime.is_on(None) is False
    assert regime.is_on("2030-01-01") is False  # a day after the data uses the latest known value (8 < 10)


# ----------------------------------------------------- crossover + regime ----
CLOSES = [10, 9, 8, 9, 11, 13, 14, 12, 9, 7, 6]  # bullish idx 4 (buy idx 5), bearish idx 8 (sell idx 9)
OPENS = [10, 10, 9, 8, 9, 12, 13, 14, 11, 8, 7]
D11 = business_days(11)


def crossover(index_closes=None, regime_sma=None):
    rows = [(D11[i], OPENS[i], max(OPENS[i], CLOSES[i]) + 0.1, min(OPENS[i], CLOSES[i]) - 0.1, CLOSES[i]) for i in range(11)]
    index = [(D11[i], c, c, c, c) for i, c in enumerate(index_closes)] if index_closes else None
    return backtest.run(
        {"AAA": {"company": "A", "rows": rows}},
        short_sma=2, long_sma=3, starting_capital=100_000, max_positions=1, stop_loss_pct=None,
        slippage_pct=0, include_charges=False, start_date=D11[0], index_rows=index, regime_sma=regime_sma,
    )


def test_regime_on_lets_the_crossover_trade_normally():
    res = crossover(index_closes=list(range(100, 111)), regime_sma=3)  # rising index: close 104 > SMA3 103 at the signal
    assert len(res["trades"]) == 1 and res["signals_skipped"]["regime_off"] == 0
    assert res["trades"][0]["entry_date"] == D11[5]


def test_regime_off_blocks_the_entry_and_counts_it():
    res = crossover(index_closes=list(range(110, 99, -1)), regime_sma=3)  # falling: 106 < SMA3 107 at the signal
    assert res["trades"] == []
    assert res["signals_skipped"]["regime_off"] == 1
    assert res["summary"]["final_value"] == 100_000.0


def test_regime_only_gates_entries_exits_still_happen():
    index = [100, 101, 102, 103, 104, 105, 104, 100, 96, 92, 88]  # on at the signal, falling afterwards
    res = crossover(index_closes=index, regime_sma=3)
    assert [t["exit_reason"] for t in res["trades"]] == ["bearish crossover"]


def test_no_regime_sma_means_no_filter_even_with_an_index():
    res = crossover(index_closes=list(range(110, 99, -1)), regime_sma=None)
    assert len(res["trades"]) == 1 and res["signals_skipped"]["regime_off"] == 0


# ---------------------------------------------------------------- momentum ----
def test_buys_the_top_ranked_stock_at_the_next_open_then_rotates_when_leadership_changes():
    res = momentum()
    first, second = sorted(res["trades"], key=lambda t: t["entry_date"])

    # rebalance 1 (start day, signal idx 9): AAA is best -> bought at idx 10's open = 120; 100000 // 120 = 833 shares
    assert (first["symbol"], first["entry_date"], first["entry_price"], first["shares"]) == ("AAA", D40[10], 120.0, 833)
    # rebalance 2 (Mon 2 Feb = idx 20, signal idx 19): BBB overtakes. AAA sold at 140, BBB bought at 186
    assert (first["exit_date"], first["exit_price"], first["exit_reason"]) == (D40[20], 140.0, "rank dropped")
    assert first["pnl"] == 16_660.0  # 833 * (140 - 120)
    assert (second["symbol"], second["entry_date"], second["entry_price"], second["shares"]) == ("BBB", D40[20], 186.0, 537)
    assert (second["exit_reason"], second["exit_price"]) == ("end of test", 414.0)
    assert second["pnl"] == 122_436.0  # 537 * 414 - 537 * 186
    assert res["summary"]["final_value"] == 239_096.0  # 100000 + 16660 + 122436 - 0
    assert res["summary"]["rebalances"] == 2
    assert res["strategy"] == "momentum"


def test_a_buffer_keeps_a_holding_that_is_still_in_the_top_keep_rank():
    res = momentum(keep_rank=2)  # AAA is only 2nd at the second rebalance, so it stays
    assert [t["symbol"] for t in res["trades"]] == ["AAA"]
    assert res["trades"][0]["exit_reason"] == "end of test"
    assert res["trades"][0]["pnl"] == 48_314.0  # 833 * (178 - 120)
    assert res["signals_skipped"]["no_free_slot"] == 1  # BBB was wanted but the only slot is taken


def test_holds_top_n_stocks_with_equal_slots_in_rank_order():
    res = momentum(top_n=2, keep_rank=None)  # 50,000 per slot; AAA and BBB are the top two
    by = {t["symbol"]: t for t in res["trades"]}
    assert set(by) == {"AAA", "BBB"} and "CCC" not in by
    assert (by["AAA"]["shares"], by["AAA"]["entry_price"]) == (416, 120.0)  # 50000 // 120
    assert (by["BBB"]["shares"], by["BBB"]["entry_price"]) == (454, 110.0)  # 50000 // 110
    assert by["AAA"]["pnl"] == 24_128.0  # 416 * (178 - 120)
    assert by["BBB"]["pnl"] == 138_016.0  # 454 * (414 - 110)
    assert all(t["exit_reason"] == "end of test" for t in res["trades"])  # both stay inside the top 4


def test_skipping_the_latest_days_ignores_a_last_minute_spike():
    spike = [100.0] * 9 + [150.0] * 31  # jumps on idx 9, the signal day
    stocks = {"AAA": STOCKS["AAA"], "DDD": {"company": "DDD", "rows": flat_rows(spike)}}
    skip_one = momentum(stocks, skip_days=1)  # DDD scores 100/100 - 1 = 0%: AAA (+7.4%) wins
    skip_none = momentum(stocks, skip_days=0)  # DDD scores 150/100 - 1 = +50%: DDD wins
    assert skip_one["trades"][-1]["symbol"] == "AAA"
    assert skip_none["trades"][-1]["symbol"] == "DDD"


def test_stocks_without_enough_history_are_not_ranked_yet():
    res = momentum(start_date=D40[3])  # at the first rebalance (signal idx 2) nobody has 5 days of history
    assert [t["symbol"] for t in res["trades"]] == ["BBB"]  # first real ranking is at idx 20
    assert res["trades"][0]["entry_date"] == D40[20]
    assert res["trades"][0]["pnl"] == 122_436.0


def index_rows_regime_flips():
    # rising to idx 14, then falling 4 a day. SMA5 at signal idx 9 = 107 (close 109, ON); at idx 19 = 102 (close 94, OFF)
    closes = [100 + i if i <= 14 else 114 - 4 * (i - 14) for i in range(40)]
    return flat_rows(closes)


def test_regime_off_sells_everything_and_buys_nothing():
    res = momentum(index_rows=index_rows_regime_flips(), regime_sma=5)
    assert len(res["trades"]) == 1
    t = res["trades"][0]
    assert (t["symbol"], t["exit_reason"], t["exit_date"], t["exit_price"]) == ("AAA", "regime off", D40[20], 140.0)
    assert res["summary"]["final_value"] == 116_660.0  # 100000 - 99960 + 116620, then all cash
    assert res["signals_skipped"]["regime_off"] == 1
    assert res["summary"]["rebalances"] == 2


def test_regime_on_at_the_first_rebalance_lets_it_buy():
    assert momentum(index_rows=index_rows_regime_flips(), regime_sma=5)["trades"][0]["entry_date"] == D40[10]


def test_stop_loss_works_for_momentum_too_and_the_stock_is_bought_again_at_the_next_rebalance():
    rows = list(STOCKS["AAA"]["rows"])
    rows[12] = (D40[12], 124.0, 124.0, 100.0, 124.0)  # open 124, low 100 on idx 12; AAA bought at 120 -> 10% stop = 108
    res = momentum({"AAA": {"company": "AAA", "rows": rows}}, stop_loss_pct=10)
    first, again = sorted(res["trades"], key=lambda t: t["entry_date"])
    assert (first["exit_reason"], first["exit_date"], first["exit_price"]) == ("stop-loss", D40[12], 108.0)
    assert again["entry_date"] == D40[20]  # a stopped-out stock waits for the next monthly rebalance
    assert again["exit_reason"] == "end of test"


# --------------------------------------------------------------- hold-out ----
def line_curve(n=40):
    days = business_days(n)
    return [{"date": days[i], "strategy": 100.0 + i, "nifty100": 100.0 + 2 * i, "same_stocks": None} for i in range(n)]


def test_segments_split_the_curve_and_use_the_boundary_day_as_the_base():
    curve = line_curve()
    trades = [
        {"exit_date": curve[10]["date"], "pnl": 5.0, "pnl_pct": 1.0, "days_held": 3},
        {"exit_date": curve[23]["date"], "pnl": -2.0, "pnl_pct": -1.0, "days_held": 5},  # last in-sample day
        {"exit_date": curve[24]["date"], "pnl": 9.0, "pnl_pct": 2.0, "days_held": 7},  # first out-of-sample day
    ]
    seg = backtest._segments(curve, trades, 40)  # round(40 * 0.6) = 24 in-sample days
    assert seg["holdout_pct"] == 40 and seg["split_date"] == curve[24]["date"]
    ins, oos = seg["in_sample"], seg["out_of_sample"]
    assert (ins["period"]["start"], ins["period"]["end"], ins["period"]["trading_days"]) == (curve[0]["date"], curve[23]["date"], 24)
    assert (oos["period"]["start"], oos["period"]["end"], oos["period"]["trading_days"]) == (curve[24]["date"], curve[39]["date"], 16)
    assert ins["strategy"]["total_return_pct"] == 23.0  # 123 / 100
    assert oos["strategy"]["total_return_pct"] == 13.01  # 139 / 123 (the boundary day is the base)
    assert ins["nifty100"]["total_return_pct"] == 46.0  # 146 / 100
    assert oos["nifty100"]["total_return_pct"] == 21.92  # 178 / 146
    assert ins["strategy"]["max_drawdown_pct"] == 0.0 and oos["strategy"]["max_drawdown_pct"] == 0.0
    assert ins["same_stocks"] is None and oos["same_stocks"] is None  # a missing series stays missing
    assert (ins["trades"]["trades"], oos["trades"]["trades"]) == (2, 1)  # split by exit date
    assert oos["trades"]["win_rate_pct"] == 100.0 and ins["trades"]["win_rate_pct"] == 50.0


def test_segment_drawdown_is_measured_inside_each_part():
    curve = line_curve()
    for i, v in {5: 130.0, 6: 90.0}.items():  # a dip inside the in-sample part: 130 -> 90
        curve[i]["strategy"] = v
    seg = backtest._segments(curve, [], 40)
    assert seg["in_sample"]["strategy"]["max_drawdown_pct"] == pytest.approx(-30.77, abs=0.01)  # 90 / 130 - 1
    assert seg["out_of_sample"]["strategy"]["max_drawdown_pct"] == 0.0


def test_no_hold_out_or_too_few_days_gives_no_segments():
    assert backtest._segments(line_curve(), [], 0) is None
    assert backtest._segments(line_curve(30), [], 40) is None


def test_simulate_reports_segments_and_every_trade_lands_in_exactly_one_part():
    res = momentum(start_date=D40[0], holdout_pct=40)  # 40 test days
    seg = res["segments"]
    assert seg["split_date"] == D40[24]
    assert seg["in_sample"]["trades"]["trades"] + seg["out_of_sample"]["trades"]["trades"] == res["summary"]["trades"]
    assert res["summary"]["trades"] >= 1
    assert momentum(start_date=D40[0], holdout_pct=0)["segments"] is None
