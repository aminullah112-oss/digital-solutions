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


class TestPortfolioLimits(unittest.TestCase):
    def test_open_risk_budget_caps_new_trades(self):
        c = cfg(risk=dict(max_position_pct=100, max_open_risk_pct=1.0, max_open_positions=10))
        rm = RiskManager(c)
        t0 = pd.Timestamp("2024-01-01")
        # one position already risking 0.8% (800 of 100k)
        pos = {"B": Position("B", 1, 160, 100, 95, 95, None, t0)}
        qty, _ = rm.size(Signal("A", 1, 100.0, 95.0), 100_000, pos)
        self.assertEqual(qty, 40)                        # only 200 of budget left
        # a position whose stop is at breakeven no longer uses budget
        pos["B"].stop = 100
        self.assertEqual(rm.size(Signal("A", 1, 100.0, 95.0), 100_000, pos)[0], 100)

    def test_volume_participation_cap(self):
        c = cfg(risk=dict(max_position_pct=100, max_volume_pct=1.0))
        qty, _ = RiskManager(c).size(Signal("A", 1, 100.0, 95.0), 100_000, {}, None, 3_000)
        self.assertEqual(qty, 30)

    def test_oos_window_keeps_indicator_warmup(self):
        c = Config(mode="swing", strategy="donchian")
        c.risk.min_avg_turnover = 0
        data = {f"S{k}": synthetic(days=1200, seed=k) for k in range(6)}
        start = data["S0"].index[1000]          # 200-bar window < 210-bar warmup
        res = Backtester(c, make_strategy("donchian")).run(data, start=start)
        self.assertTrue(res.trades, "window should trade using prior history for indicators")
        self.assertTrue(all(t.entry_time >= start for t in res.trades))
        self.assertGreaterEqual(res.equity.index[0], start)

    def test_evaluation_report_runs_and_flags(self):
        from tradebot.evaluate import evaluate, to_markdown
        c = Config(mode="swing", strategy="donchian")
        c.risk.min_avg_turnover = 0
        data = {f"S{k}": synthetic(days=900, seed=k) for k in range(4)}
        rep = evaluate(c, make_strategy("donchian"), data, 0.7, 3)
        self.assertEqual(set(rep["periods"]), {"full", "in_sample", "out_of_sample"})
        self.assertEqual(len(rep["folds"]), 3)
        self.assertIn(2.0, rep["cost_sensitivity"].index)
        self.assertTrue(rep["flags"])            # too few trades on this little data
        self.assertIn("NOT APPROVED", to_markdown(rep, "x"))


class FakeKite:
    """Wraps KiteBroker with a scripted _req so order paths can be tested offline."""

    def __new__(cls, script):
        from tradebot.kite import KiteBroker
        b = KiteBroker(TZ, "MIS", api_key="k", access_token="t")
        b.calls = []

        def _req(method, path, params=None, raw=False):
            b.calls.append((method, path, params))
            return script(b, method, path, params)
        b._req = _req
        return b


class TestKiteOrderSafety(unittest.TestCase):
    def setUp(self):
        import tradebot.kite as k
        self._sleep = k.time.sleep
        k.time.sleep = lambda s: None

    def tearDown(self):
        import tradebot.kite as k
        k.time.sleep = self._sleep

    def test_post_is_never_retried_on_network_error(self):
        import urllib.error
        import urllib.request
        from tradebot.kite import AmbiguousRequest, KiteBroker
        b = KiteBroker(TZ, "MIS", api_key="k", access_token="t")
        n = [0]
        orig = urllib.request.urlopen

        def boom(*a, **kw):
            n[0] += 1
            raise urllib.error.URLError("timed out")
        urllib.request.urlopen = boom
        try:
            with self.assertRaises(AmbiguousRequest):
                b._req("POST", "/orders/regular", {"x": 1})
            self.assertEqual(n[0], 1)
            n[0] = 0
            with self.assertRaises(Exception):
                b._req("GET", "/orders")
            self.assertEqual(n[0], 3)            # reads are retried
        finally:
            urllib.request.urlopen = orig

    def test_timed_out_order_is_found_by_tag_not_resent(self):
        from tradebot.kite import AmbiguousRequest

        def script(b, method, path, params):
            if method == "POST":
                b.sent_tag = params["tag"]
                raise AmbiguousRequest("timeout")
            if path == "/orders":
                return [{"tag": "other", "order_id": "1"}, {"tag": b.sent_tag, "order_id": "42"}]
        b = FakeKite(script)
        oid = b.place_stop("INFY", -1, 10, 1500.0)
        self.assertEqual(oid, "42")
        self.assertEqual(sum(1 for m, *_ in b.calls if m == "POST"), 1)

    def test_unfound_order_raises_order_unknown(self):
        from tradebot.broker import OrderUnknown
        from tradebot.kite import AmbiguousRequest

        def script(b, method, path, params):
            if method == "POST":
                raise AmbiguousRequest("timeout")
            return []
        with self.assertRaises(OrderUnknown):
            FakeKite(script).market("INFY", 1, 10)

    def test_partial_market_fill_is_reported(self):
        def script(b, method, path, params):
            if method == "POST":
                return {"order_id": "7"}
            return [{"status": "CANCELLED", "filled_quantity": 40, "average_price": 101.5,
                     "status_message": "partially filled, rest cancelled"}]
        fill = FakeKite(script).market("INFY", 1, 100)
        self.assertEqual((fill.price, fill.qty), (101.5, 40))

    def test_unique_tags(self):
        b = FakeKite(lambda *a: None)
        tags = {b._new_tag("stop") for _ in range(500)}
        self.assertEqual(len(tags), 500)
        self.assertTrue(all(len(t) <= 20 for t in tags))


class FlakyPaper(PaperBroker):
    """Paper broker with injectable failures."""
    fill_frac = 1.0
    fail_stop = False

    def market(self, symbol, side, qty, tag=""):
        return super().market(symbol, side, max(1, int(qty * self.fill_frac)) if tag == "entry" else qty, tag)

    def place_stop(self, *a, **kw):
        if self.fail_stop:
            from tradebot.broker import BrokerError
            raise BrokerError("stop rejected")
        return super().place_stop(*a, **kw)


class TestLiveFailurePaths(TestLiveEngine):
    def setUp(self):
        super().setUp()
        self.broker = FlakyPaper(self.feed, 0.0)

    def test_partial_entry_is_tracked_and_protected_for_filled_qty(self):
        self.broker.fill_frac = 0.5
        eng = self.engine()
        self.tick(eng, 3)
        p = eng.positions["A"]
        self.assertEqual(self.broker.net_positions(), {"A": p.qty})
        self.assertEqual(self.broker.orders[p.broker_stop_id]["qty"], p.qty)

    def test_rejected_stop_closes_position_immediately(self):
        self.broker.fail_stop = True
        eng = self.engine()
        self.tick(eng, 3)
        self.assertEqual(eng.positions, {})
        self.assertEqual(self.broker.net_positions(), {})

    def test_mismatch_blocks_entries_and_survives_restart(self):
        eng = self.engine()
        self.tick(eng, 3)
        self.broker.pos["A"] += 5               # someone traded the symbol by hand
        self.tick(eng, 4)
        self.assertIn("reconcile mismatch", eng.risk.halted())
        self.assertEqual(eng.risk.must_flatten(), "")   # block never auto-exits
        eng2 = LiveEngine(self.c, OneShot(at=2), self.broker, now=lambda: self.clock[0])
        self.assertIn("reconcile mismatch", eng2.risk.halted())
        eng2.risk.reset(eng2.equity())
        self.assertEqual(eng2.risk.halted(), "")

    def test_restart_finds_unprotected_position_and_arms_stop(self):
        eng = self.engine()
        self.tick(eng, 3)
        p = eng.positions["A"]
        self.broker.orders[p.broker_stop_id]["status"] = "CANCELLED"
        p.broker_stop_id = None
        eng.save()
        eng2 = LiveEngine(self.c, OneShot(at=2), self.broker, now=lambda: self.clock[0])
        self.tick(eng2, 4)
        sid = eng2.positions["A"].broker_stop_id
        self.assertIsNotNone(sid)
        self.assertEqual(self.broker.orders[sid]["status"], "OPEN")

    def test_kill_switch_outside_hours_waits_for_open(self):
        eng = self.engine()
        self.tick(eng, 3)
        Path(self.c.kill_switch_file).touch()
        self.clock[0] = self.df.index[3] + pd.Timedelta(hours=20)   # night
        eng.step()
        self.assertIn("A", eng.positions)        # no orders sent while closed
        self.assertIn("kill switch", eng.risk.halted())
        self.clock[0] = self.df.index[4] + pd.Timedelta(hours=10)   # next session
        with self.assertRaises(SystemExit):
            eng.step()
        self.assertEqual(self.broker.net_positions(), {})

    def test_second_engine_on_same_state_refuses_to_start(self):
        eng = self.engine()
        eng.acquire_lock()
        with self.assertRaises(SystemExit):
            self.engine().acquire_lock()


if __name__ == "__main__":
    unittest.main()
