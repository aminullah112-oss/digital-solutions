import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from tradebot import indicators as ind
from tradebot.backtest import Backtester
from tradebot.broker import PaperBroker
from tradebot.config import Config
from tradebot.data import synthetic
from tradebot.live import LiveEngine
from tradebot.models import Position, Signal, Trade
from tradebot.risk import RiskManager
from tradebot.strategies import STRATEGIES, Strategy, make_strategy

TZ = "Asia/Kolkata"


def cfg(**kw):
    kw.setdefault("mode", "swing")
    kw.setdefault("initial_capital", 100_000.0)
    c = Config(**{k: v for k, v in kw.items() if k not in ("risk",)})
    c.costs.cost_pct = c.costs.slippage_pct = 0.0
    c.risk.min_avg_turnover = 0
    c.risk.min_price = 0
    for k, v in kw.get("risk", {}).items():
        setattr(c.risk, k, v)
    return c


def bars(rows, start="2024-01-01", freq="D"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz=TZ)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx).astype(float)


class OneShot(Strategy):
    """Emits a single long signal at bar `at`."""
    name = "oneshot"
    mode = "swing"
    defaults = dict(at=1, stop=95.0, target=None, max_bars=None, breakeven_r=None)

    @property
    def warmup(self):
        return 0

    def prepare(self, df):
        return df

    def signal(self, symbol, df, i, allow_short):
        if i == self.p["at"]:
            return Signal(symbol, 1, df["close"].iat[i], self.p["stop"], self.p["target"], self.p["max_bars"])
        return None


class TestIndicatorsAndStrategiesAreCausal(unittest.TestCase):
    def test_indicators_do_not_use_future_bars(self):
        df = synthetic(days=300, seed=3)
        k = 250
        for fn in (lambda d: ind.atr(d), lambda d: ind.adx(d), lambda d: ind.rsi(d["close"]),
                   lambda d: ind.ema(d["close"], 20), lambda d: ind.rolling_high(d["close"], 55)):
            full, cut = fn(df), fn(df.iloc[:k])
            np.testing.assert_allclose(full.iloc[:k].to_numpy(), cut.to_numpy(), equal_nan=True)

    def test_signals_identical_on_truncated_data(self):
        for name, cls in STRATEGIES.items():
            intr = cls.mode == "intraday"
            df = synthetic(days=40 if intr else 400, intraday=intr, seed=11)
            s = make_strategy(name)
            full = s.prepare(df)
            for i in range(s.warmup, len(df), 37):
                a = s.signal("X", full, i, True)
                b = s.signal("X", s.prepare(df.iloc[: i + 1]), i, True)
                self.assertEqual(a, b, f"{name} lookahead at bar {i}")


class TestRisk(unittest.TestCase):
    def test_stop_out_costs_risk_pct(self):
        c = cfg(risk=dict(max_position_pct=100))
        rm = RiskManager(c)
        sig = Signal("A", 1, 100.0, 95.0)
        qty, _ = rm.size(sig, 100_000, {})
        self.assertEqual(qty, 100)               # 0.5% of 100k = 500 / 5 per share
        self.assertAlmostEqual(qty * 5, 500)

    def test_costs_reduce_size(self):
        c = cfg(risk=dict(max_position_pct=100))
        c.costs.cost_pct = c.costs.slippage_pct = 0.001
        qty, _ = RiskManager(c).size(Signal("A", 1, 100.0, 95.0), 100_000, {})
        self.assertLess(qty, 100)

    def test_caps_and_rejections(self):
        c = cfg(risk=dict(max_position_pct=10))
        rm = RiskManager(c)
        qty, _ = rm.size(Signal("A", 1, 100.0, 99.0), 100_000, {})
        self.assertEqual(qty, 100)               # 10% notional cap binds, not 500 shares
        self.assertEqual(rm.size(Signal("A", 1, 100.0, 101.0), 100_000, {})[0], 0)   # stop wrong side
        self.assertEqual(rm.size(Signal("A", 1, 100.0, 80.0), 100_000, {})[0], 0)    # stop too wide
        self.assertEqual(rm.size(Signal("A", 1, 100.0, 95.0, 102.0), 100_000, {})[0], 0)  # R:R < 1.5
        pos = {s: Position(s, 1, 1, 1, 0.5, 0.5, None, pd.Timestamp("2024-01-01")) for s in "BCDEF"}
        self.assertEqual(rm.size(Signal("A", 1, 100.0, 95.0), 100_000, pos)[1], "max open positions")

    def test_daily_limit_drawdown_and_streak(self):
        c = cfg(mode="intraday", risk=dict(daily_loss_limit_pct=2, max_drawdown_pct=10,
                                           loss_streak_reduce=2, loss_streak_halt=3))
        rm = RiskManager(c)
        rm.on_new_day("d1", 100_000)
        rm.on_equity(98_100)
        self.assertEqual(rm.halted(), "")
        rm.on_equity(97_900)
        self.assertIn("daily loss", rm.halted())
        self.assertTrue(rm.must_flatten())       # intraday flattens on daily stop
        rm.on_new_day("d2", 97_900)
        self.assertEqual(rm.halted(), "")
        rm.on_equity(89_000)
        self.assertIn("max drawdown", rm.halted())
        rm.on_new_day("d3", 89_000)
        self.assertIn("max drawdown", rm.halted())   # survives a new day
        rm.reset(89_000)
        loss = Trade("A", 1, 1, None, None, 1, 0, -1, -1, "stop")
        rm.on_trade_closed(loss); rm.on_trade_closed(loss)
        self.assertEqual(rm.risk_multiplier(), 0.5)
        rm.on_trade_closed(loss)
        self.assertIn("losses in a row", rm.halted())

    def test_config_rejects_reckless_settings(self):
        with self.assertRaises(ValueError):
            Config.from_dict({"risk": {"risk_per_trade_pct": 5}})
        with self.assertRaises(ValueError):
            Config.from_dict({"mode": "swing", "risk": {"max_gross_exposure_pct": 300}})
        with self.assertRaises(ValueError):
            Config.from_dict({"risk_per_trade": 1})


class TestBacktestFills(unittest.TestCase):
    def run_bt(self, rows, **sp):
        c = cfg(risk=dict(max_position_pct=100))
        return Backtester(c, OneShot(**sp)).run({"A": bars(rows)})

    def test_entry_at_next_open_and_stop(self):
        res = self.run_bt([
            (100, 101, 99, 100, 1e6),
            (100, 101, 99, 100, 1e6),   # signal on this close
            (101, 102, 100, 101, 1e6),  # fill at open 101
            (100, 100, 94, 95, 1e6),    # stop 95 hit
        ])
        t = res.trades[0]
        self.assertEqual(t.entry, 101)
        self.assertEqual(t.exit, 95)
        self.assertEqual(t.exit_reason, "stop")

    def test_gap_through_stop_fills_at_open(self):
        res = self.run_bt([
            (100, 101, 99, 100, 1e6), (100, 101, 99, 100, 1e6), (100, 101, 99, 100, 1e6),
            (90, 92, 89, 91, 1e6),
        ])
        self.assertEqual(res.trades[0].exit, 90)
        self.assertEqual(res.trades[0].exit_reason, "stop (gap)")

    def test_stop_and_target_same_bar_assumes_stop(self):
        res = self.run_bt([
            (100, 101, 99, 100, 1e6), (100, 101, 99, 100, 1e6), (100, 101, 99, 100, 1e6),
            (100, 120, 90, 100, 1e6),
        ], target=110.0)
        self.assertEqual(res.trades[0].exit_reason, "stop")

    def test_entry_cancelled_if_open_gaps_below_stop(self):
        res = self.run_bt([
            (100, 101, 99, 100, 1e6), (100, 101, 99, 100, 1e6),
            (94, 95, 93, 94, 1e6), (94, 95, 93, 94, 1e6),
        ])
        self.assertEqual(res.trades, [])
        self.assertEqual(res.rejections["entry cancelled: gapped through stop"], 1)

    def test_intraday_never_holds_overnight(self):
        c = Config(mode="intraday", strategy="orb", allow_short=True)
        c.risk.min_avg_turnover = 0
        res = Backtester(c, make_strategy("orb")).run(
            {f"S{k}": synthetic(days=60, intraday=True, seed=k) for k in range(3)})
        for t in res.trades:
            self.assertEqual(t.entry_time.date(), t.exit_time.date())
            self.assertLessEqual(t.exit_time.time(), c.session.t("flatten_at"))

    def test_loss_per_trade_bounded(self):
        c = Config(mode="swing", strategy="donchian")
        c.risk.min_avg_turnover = 0
        res = Backtester(c, make_strategy("donchian")).run(
            {f"S{k}": synthetic(days=1200, seed=k) for k in range(6)})
        self.assertTrue(res.trades)
        for t in res.trades:
            if t.exit_reason != "stop (gap)":
                # 1R plus costs/slippage, never a blow-up
                self.assertGreater(t.r_multiple, -1.3, t)


class FakeFeed:
    def __init__(self, df):
        self.df, self.n = df, 1

    def bars(self, symbol, interval, lookback_days):
        return self.df.iloc[: self.n]

    def ltp(self, symbol):
        return float(self.df["close"].iat[self.n - 1])


class TestLiveEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.c = cfg(symbols=["A"], interval="day", state_file=str(d / "s.json"),
                     kill_switch_file=str(d / "STOP"), risk=dict(max_position_pct=100))
        rows = [(100, 101, 99, 100, 1e6)] * 5 + [(100, 100, 94, 94.5, 1e6)]
        self.df = bars(rows, start="2024-01-01", freq="B")
        self.feed = FakeFeed(self.df)
        self.broker = PaperBroker(self.feed, 0.0)
        self.clock = [None]

    def tearDown(self):
        self.tmp.cleanup()

    def engine(self):
        return LiveEngine(self.c, OneShot(at=2), self.broker, now=lambda: self.clock[0])

    def tick(self, eng, n):
        """Advance to the session after bar n-1 closed."""
        self.feed.n = n + 1     # bar n is today's forming bar
        self.clock[0] = self.df.index[n] + pd.Timedelta(hours=10)
        eng.step()

    def test_entry_places_stop_then_stop_fill_is_recorded(self):
        eng = self.engine()
        self.tick(eng, 3)       # bar 2 closed -> signal -> entry
        p = eng.positions["A"]
        self.assertEqual(self.broker.orders[p.broker_stop_id]["status"], "OPEN")
        self.assertEqual(self.broker.net_positions(), {"A": p.qty})
        self.tick(eng, 5)       # today's bar trades down to 94
        self.assertNotIn("A", eng.positions)
        self.assertEqual(self.broker.net_positions(), {})
        self.assertLess(eng.realized, 0)
        self.assertAlmostEqual(eng.realized, -p.qty * 5, delta=1)

    def test_state_survives_restart_and_kill_switch_flattens(self):
        eng = self.engine()
        self.tick(eng, 3)
        qty = eng.positions["A"].qty
        eng2 = LiveEngine(self.c, OneShot(at=2), self.broker, now=lambda: self.clock[0])
        self.assertEqual(eng2.positions["A"].qty, qty)
        Path(self.c.kill_switch_file).touch()
        with self.assertRaises(SystemExit):
            eng2.step()
        self.assertEqual(eng2.positions, {})
        self.assertEqual(self.broker.net_positions(), {})

    def test_expired_stop_is_replaced(self):
        eng = self.engine()
        self.tick(eng, 3)
        p = eng.positions["A"]
        self.broker.orders[p.broker_stop_id]["status"] = "CANCELLED"   # DAY order expired
        old = p.broker_stop_id
        self.tick(eng, 4)
        self.assertNotEqual(eng.positions["A"].broker_stop_id, old)
        self.assertEqual(self.broker.orders[eng.positions["A"].broker_stop_id]["status"], "OPEN")


if __name__ == "__main__":
    unittest.main()
