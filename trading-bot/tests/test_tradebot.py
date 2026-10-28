import json
import logging
import math
import os
import tempfile
import time
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

    def test_max_hold_bars_caps_strategy_time_stop(self):
        flat = [(100, 101, 99, 100, 1e6)] * 12
        c = cfg(max_hold_bars=3, risk=dict(max_position_pct=100))
        res = Backtester(c, OneShot(max_bars=40)).run({"A": bars(flat)})
        self.assertEqual(res.trades[0].exit_reason, "time stop")
        self.assertEqual(res.trades[0].bars_held, 3)
        c.max_hold_bars = 5
        res = Backtester(c, OneShot(max_bars=2)).run({"A": bars(flat)})
        self.assertEqual(res.trades[0].bars_held, 2)    # the tighter limit wins

    def test_target_exit_pays_slippage(self):
        c = cfg(risk=dict(max_position_pct=100))
        c.costs.slippage_pct = 0.001
        rows = [(100, 101, 99, 100, 1e6)] * 3 + [(100, 115, 99, 101, 1e6)]
        res = Backtester(c, OneShot(target=110.0)).run({"A": bars(rows)})
        t = res.trades[0]
        self.assertEqual(t.exit_reason, "target")
        self.assertAlmostEqual(t.exit, 110 * 0.999)

    def test_swing_2r_config_sets_target(self):
        root = Path(__file__).resolve().parents[1]
        c = Config.load(root / "config/swing_2r.json")
        base = Config.load(root / "config/swing.json")
        self.assertEqual(c.strategy_params["target_r"], 2.0)
        self.assertEqual(c.max_hold_bars, base.max_hold_bars)
        self.assertNotEqual(c.state_file, base.state_file)
        s = make_strategy(c.strategy, c.strategy_params)
        df = s.prepare(synthetic(days=800, seed=2))
        sigs = [x for x in (s.signal("X", df, i, False) for i in range(s.warmup, len(df))) if x]
        self.assertTrue(sigs)
        for x in sigs:
            self.assertAlmostEqual(x.target - x.ref_price, 2.0 * (x.ref_price - x.stop))

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


class TestCompareCommand(unittest.TestCase):
    def test_compare_runs_configs_on_identical_data(self):
        import contextlib
        import io
        from tradebot.__main__ import main
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for name, hold in (("short", 10), ("long", 40)):
                raw = {"mode": "swing", "strategy": "trend_pullback", "symbols": ["A", "B"],
                       "interval": "day", "max_hold_bars": hold, "risk": {"min_avg_turnover": 0}}
                f = Path(d) / f"{name}.json"
                f.write_text(json.dumps(raw))
                paths.append(str(f))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main(["compare", "-c", paths[0], "-c", paths[1], "--synthetic", "--days", "700",
                      "--folds", "2", "--out", d])
            md = (Path(d) / "compare.md").read_text()
            self.assertIn("| metric | short | long |", md)
            self.assertIn("benchmark_return_pct", md)
            self.assertTrue((Path(d) / "report_short.md").exists())


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


class TestAlerts(unittest.TestCase):
    def handler(self, senders=None, **kw):
        from tradebot.alerts import AlertHandler
        self.got = []
        h = AlertHandler(senders if senders is not None else [self.got.append], "t",
                         background=False, **kw)
        lg = logging.getLogger("tradebot.test_alerts")
        lg.setLevel(logging.DEBUG)
        lg.addHandler(h)
        self.addCleanup(lg.removeHandler, h)
        return lg, h

    def test_errors_and_notify_records_are_sent_info_is_not(self):
        lg, _ = self.handler()
        lg.info("routine")
        lg.info("OPENED LONG A", extra={"notify": True})
        lg.error("could not place stop")
        self.assertEqual(len(self.got), 2)
        self.assertIn("OPENED LONG A", self.got[0])
        self.assertTrue(self.got[1].startswith("[t] ERROR"))

    def test_duplicates_suppressed(self):
        lg, _ = self.handler(dedupe_seconds=300)
        for _ in range(5):
            lg.error("token expired")
        lg.error("something else")
        self.assertEqual(len(self.got), 2)

    def test_failing_channel_never_raises(self):
        def broken(text):
            raise OSError("network down")
        lg, h = self.handler([broken, lambda t: self.got.append(t)])
        lg.critical("POSITION UNPROTECTED")      # must not raise into the trading loop
        self.assertEqual(h.failures, 1)
        self.assertEqual(len(self.got), 1)       # the working channel still delivered

    def test_background_delivery(self):
        from tradebot.alerts import AlertHandler
        got = []
        h = AlertHandler([got.append], "t")
        lg = logging.getLogger("tradebot.test_alerts_bg")
        lg.addHandler(h)
        self.addCleanup(lg.removeHandler, h)
        lg.error("halted")
        h.flush()
        self.assertEqual(len(got), 1)

    def test_channels_from_env(self):
        from tradebot.alerts import install, senders_from_env
        self.assertEqual(senders_from_env({}), [])
        self.assertEqual(len(senders_from_env({"TRADEBOT_TELEGRAM_TOKEN": "x", "TRADEBOT_TELEGRAM_CHAT": "1",
                                               "TRADEBOT_WEBHOOK_URL": "https://h"})), 2)
        self.assertEqual(len(senders_from_env({"TRADEBOT_TELEGRAM_TOKEN": "x"})), 0)  # needs both
        h, hb = install("t", env={})
        self.assertIsNone(h)
        hb.beat()                                # no URL: no-op, no error

    def test_engine_alerts_on_halt_and_trades(self):
        got = []
        from tradebot.alerts import AlertHandler
        h = AlertHandler([got.append], "t", background=False)
        lg = logging.getLogger("tradebot")
        lg.addHandler(h)
        old = lg.level
        lg.setLevel(logging.INFO)
        self.addCleanup(lg.setLevel, old)
        self.addCleanup(lg.removeHandler, h)
        with tempfile.TemporaryDirectory() as d:
            c = cfg(symbols=["A"], interval="day", state_file=str(Path(d) / "s.json"),
                    kill_switch_file=str(Path(d) / "STOP"), risk=dict(max_position_pct=100))
            df = bars([(100, 101, 99, 100, 1e6)] * 6, freq="B")
            feed = FakeFeed(df)
            broker = PaperBroker(feed, 0.0)
            clock = [None]
            eng = LiveEngine(c, OneShot(at=2), broker, now=lambda: clock[0])
            feed.n, clock[0] = 4, df.index[3] + pd.Timedelta(hours=10)
            eng.step()
            broker.pos["A"] += 1                 # manual trade -> mismatch -> halt
            feed.n, clock[0] = 5, df.index[4] + pd.Timedelta(hours=10)
            eng.step()
        self.assertTrue(any("OPENED" in m for m in got))
        self.assertTrue(any("TRADING HALTED" in m for m in got))


class EveryN(Strategy):
    """Long signal every n bars when flat; stop 3% below, optional 2R target."""
    name = "every_n"
    mode = "swing"
    defaults = dict(n=4, target=True, breakeven_r=1.0)

    @property
    def warmup(self):
        return 1

    def prepare(self, df):
        return df

    def signal(self, symbol, df, i, allow_short):
        if i % self.p["n"]:
            return None
        c = df["close"].iat[i]
        return Signal(symbol, 1, c, c * 0.97, c * 1.06 if self.p["target"] else None, 6)


class TestFaultInjection(unittest.TestCase):
    def test_parse_faults(self):
        from tradebot.broker import parse_faults
        self.assertEqual(parse_faults("reject=0.1, partial=0.2"), {"reject": 0.1, "partial": 0.2})
        self.assertEqual(parse_faults(None), {})
        with self.assertRaises(ValueError):
            parse_faults("explode=0.1")
        with self.assertRaises(ValueError):
            parse_faults("reject=2")

    def soak(self, faults, seed, bars_n=300, symbols=("A", "B", "C")):
        """Run the engine over many sessions with faults; check invariants every cycle."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        c = cfg(symbols=list(symbols), interval="day", state_file=str(Path(tmp.name) / "s.json"),
                kill_switch_file=str(Path(tmp.name) / "STOP"),
                risk=dict(max_position_pct=30, max_open_risk_pct=3, loss_streak_halt=10**6,
                          daily_loss_limit_pct=50, max_drawdown_pct=90))
        frames = {s: synthetic(days=bars_n, seed=seed * 10 + k) for k, s in enumerate(symbols)}

        class Feed:
            n = 1

            def bars(self, s, interval, lookback):
                return frames[s].iloc[: self.n]

            def ltp(self, s):
                return float(frames[s]["close"].iat[self.n - 1])
        feed = Feed()
        broker = PaperBroker(feed, 0.0005, faults=faults, seed=seed)
        clock = [None]
        eng = LiveEngine(c, EveryN(), broker, now=lambda: clock[0])
        idx = frames[symbols[0]].index
        for n in range(3, bars_n):
            feed.n = n + 1
            for hour in (10, 14):            # two polls per session
                clock[0] = idx[n] + pd.Timedelta(hours=hour)
                eng.step()
                self.check(eng, broker)
        return eng, broker

    def check(self, eng, broker):
        held = dict(broker.pos)
        bad = set()
        for sym, p in eng.positions.items():
            o = broker.orders.get(p.broker_stop_id or "")
            if not (o is not None and o["status"] == "OPEN" and o["qty"] == p.qty):
                bad.add(sym)
        # A stop can fail AND its fallback exit can fail in the same cycle. That's
        # tolerated for one cycle only: the next cycle must re-protect or close it.
        persistent = bad & getattr(self, "_bad_prev", set())
        if persistent and not eng.risk.halted():
            self.fail(f"{persistent} unprotected for two cycles in a row")
        self._bad_prev = bad
        self.max_unprotected_streak = max(getattr(self, "max_unprotected_streak", 0), len(persistent))
        expected = {s: p.side * p.qty for s, p in eng.positions.items()}
        if held != expected:
            self.assertTrue(eng.risk.halted(), f"broker {held} != bot {expected} and no halt")

    def test_soak_unambiguous_faults_never_leave_a_position_unprotected(self):
        # Every one of these is detectable, so the bot must recover without halting.
        faults = dict(reject=0.15, partial=0.3, stop_reject=0.15, stop_cancel=0.1)
        for seed in (1, 2, 3):
            eng, broker = self.soak(faults, seed)
            kinds = {k for k, _ in broker.injected}
            self.assertEqual(kinds, set(faults), f"seed {seed}: not every fault fired")
            self.assertEqual(eng.risk.halted(), "", f"seed {seed}: unexpected halt")
            self.assertEqual(dict(broker.pos), {s: p.side * p.qty for s, p in eng.positions.items()})
            self.assertGreater(len(Path(eng.trades_path).read_text().splitlines()), 20)

    def test_soak_with_timeouts_keeps_invariants(self):
        faults = dict(reject=0.1, partial=0.2, timeout=0.05, stop_reject=0.1, stop_cancel=0.05)
        for seed in (4, 5):
            eng, broker = self.soak(faults, seed)
            self.assertIn("timeout", {k for k, _ in broker.injected})

    def engine_with(self, faults):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        c = cfg(symbols=["A"], interval="day", state_file=str(Path(tmp.name) / "s.json"),
                kill_switch_file=str(Path(tmp.name) / "STOP"), risk=dict(max_position_pct=100))
        df = bars([(100, 101, 99, 100, 1e6)] * 8, freq="B")
        feed = FakeFeed(df)
        broker = PaperBroker(feed, 0.0)
        clock = [None]
        eng = LiveEngine(c, OneShot(at=2, max_bars=1), broker, now=lambda: clock[0])

        def tick(n):
            feed.n, clock[0] = n + 1, df.index[n] + pd.Timedelta(hours=10)
            eng.step()
        broker.faults = faults
        return eng, broker, tick

    def test_entry_timeout_that_filled_is_adopted_and_protected(self):
        eng, broker, tick = self.engine_with({})
        orig = broker.market

        def market(sym, side, qty, tag=""):
            orig(sym, side, qty, tag)
            from tradebot.broker import OrderUnknown
            raise OrderUnknown("timeout after fill")
        broker.market = market
        tick(3)
        p = eng.positions["A"]
        self.assertEqual(broker.pos["A"], p.qty)
        self.assertEqual(broker.orders[p.broker_stop_id]["status"], "OPEN")
        self.assertIn("outcome unknown", eng.risk.halted())   # still flagged for a human

    def test_exit_timeout_that_filled_leaves_no_stray_stop(self):
        eng, broker, tick = self.engine_with({})
        tick(3)                                  # enter; max_bars=1 -> time stop next bar
        orig = broker.market

        def market(sym, side, qty, tag=""):
            r = orig(sym, side, qty, tag)
            if tag == "exit":
                from tradebot.broker import OrderUnknown
                raise OrderUnknown("timeout after fill")
            return r
        broker.market = market
        tick(5)                                  # first bar after entry -> time stop -> exit
        self.assertEqual(eng.positions, {})
        self.assertEqual(broker.pos, {})
        self.assertEqual([o for o in broker.orders.values() if o["status"] == "OPEN"], [])


class TestKiteSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tok.json"

    def test_checksum_and_login_url(self):
        import hashlib
        from tradebot.kite import checksum, login_url
        self.assertEqual(checksum("k", "rt", "sec"), hashlib.sha256(b"krtsec").hexdigest())
        self.assertEqual(login_url("abc"), "https://kite.zerodha.com/connect/login?v=3&api_key=abc")

    def test_token_expires_at_six_next_morning(self):
        from tradebot.kite import token_expiry
        ist = lambda s: pd.Timestamp(s, tz="Asia/Kolkata")
        self.assertEqual(token_expiry(ist("2026-10-28 08:10")), ist("2026-10-29 06:00"))
        self.assertEqual(token_expiry(ist("2026-10-28 03:00")), ist("2026-10-28 06:00"))
        self.assertEqual(token_expiry(ist("2026-10-28 06:00")), ist("2026-10-29 06:00"))
        self.assertEqual(token_expiry(pd.Timestamp("2026-10-28 02:40", tz="UTC")), ist("2026-10-29 06:00"))

    def test_parse_request_token(self):
        from tradebot.kite import parse_request_token
        url = "https://my.app/cb?action=login&type=login&status=success&request_token=AbC123"
        self.assertEqual(parse_request_token(url), "AbC123")
        self.assertEqual(parse_request_token("  AbC123\n"), "AbC123")
        with self.assertRaises(ValueError):
            parse_request_token("https://my.app/cb?status=cancelled&request_token=x")
        with self.assertRaises(ValueError):
            parse_request_token("not a token")

    def test_store_is_private_and_reloads_on_change(self):
        from tradebot.kite import TokenStore
        st = TokenStore(self.path)
        self.assertIsNone(st.load())
        st.save("t1", "AB1234", pd.Timestamp("2026-10-28 08:00", tz="Asia/Kolkata"))
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        self.assertEqual(st.load()["access_token"], "t1")
        other = TokenStore(self.path)          # e.g. `tradebot login` in another process
        os.utime(self.path, ns=(1, 1))
        other.save("t2", "AB1234", pd.Timestamp("2026-10-29 08:00", tz="Asia/Kolkata"))
        self.assertEqual(st.load()["access_token"], "t2")

    def broker(self):
        from tradebot.kite import KiteBroker, TokenStore
        return KiteBroker(TZ, "MIS", api_key="k", token_store=TokenStore(self.path))

    def test_auth_status_lifecycle(self):
        import io
        import urllib.error
        import urllib.request
        from tradebot.broker import TokenExpired
        b = self.broker()
        ok, why = b.auth_status()
        self.assertFalse(ok)
        self.assertIn("no Kite access token", why)
        with self.assertRaises(TokenExpired):
            b._req("GET", "/user/profile")                  # never sends 'token k:None'
        b.store.save("t1", "u", pd.Timestamp("2026-10-28 08:00", tz="Asia/Kolkata"))
        self.assertTrue(b.auth_status(pd.Timestamp("2026-10-28 15:00", tz=TZ))[0])
        self.assertFalse(b.auth_status(pd.Timestamp("2026-10-29 06:01", tz=TZ))[0])

        sent = []

        def fake(req, timeout=None):
            sent.append(req.get_header("Authorization"))
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {},
                                         io.BytesIO(b'{"status":"error","error_type":"TokenException"}'))
        orig = urllib.request.urlopen
        urllib.request.urlopen = fake
        try:
            with self.assertRaises(TokenExpired):
                b._req("GET", "/portfolio/positions")
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(sent, ["token k:t1"])
        self.assertIn("rejected", b.auth_status(pd.Timestamp("2026-10-28 15:00", tz=TZ))[1])
        os.utime(self.path, ns=(1, 1))
        b.store.save("t2", "u", pd.Timestamp("2026-10-28 15:05", tz="Asia/Kolkata"))
        self.assertTrue(b.auth_status(pd.Timestamp("2026-10-28 15:06", tz=TZ))[0])   # new token clears it

    def test_exchange_sends_checksum(self):
        import io
        import urllib.parse
        import urllib.request
        from tradebot.kite import checksum, exchange_request_token
        seen = {}

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(req, timeout=None):
            seen.update(urllib.parse.parse_qs(req.data.decode()))
            seen["url"] = req.full_url
            return R(b'{"status":"success","data":{"access_token":"AT","user_id":"AB1234"}}')
        orig = urllib.request.urlopen
        urllib.request.urlopen = fake
        try:
            d = exchange_request_token("k", "sec", "rt")
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(d["access_token"], "AT")
        self.assertEqual(seen["url"], "https://api.kite.trade/session/token")
        self.assertEqual(seen["checksum"], [checksum("k", "rt", "sec")])
        self.assertNotIn("api_secret", seen)                 # the secret itself never leaves

    def test_capture_redirect(self):
        import socket
        import threading
        import urllib.request
        from tradebot.kite import capture_redirect
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        out = {}
        t = threading.Thread(target=lambda: out.update(tok=capture_redirect(port, timeout=10)))
        t.start()
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/?status=success&request_token=XYZ",
                                       timeout=2).read()
                break
            except OSError:
                time.sleep(0.1)
        t.join(5)
        self.assertEqual(out.get("tok"), "XYZ")

    def test_login_command_writes_token(self):
        import tradebot.kite as k
        from tradebot.__main__ import main
        orig = k.exchange_request_token
        k.exchange_request_token = lambda key, sec, rt: {"access_token": f"AT-{rt}", "user_id": "AB1234"}
        env = {"KITE_API_KEY": "k", "KITE_API_SECRET": "s"}
        old = {x: os.environ.get(x) for x in env}
        os.environ.update(env)
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                main(["login", "--request-token", "https://cb?status=success&request_token=RT9",
                      "--token-file", str(self.path)])
        finally:
            k.exchange_request_token = orig
            for x, v in old.items():
                os.environ.pop(x) if v is None else os.environ.__setitem__(x, v)
        self.assertEqual(json.loads(self.path.read_text())["access_token"], "AT-RT9")
        self.assertNotIn("AT-RT9", buf.getvalue())           # token never printed


class SessionPaper(PaperBroker):
    """Paper broker whose session can be switched off; counts broker calls."""
    session_ok = True
    calls = 0

    def auth_status(self, now=None):
        return (True, "") if self.session_ok else (False, "Kite access token expired at 06:00")

    def bars(self, *a, **kw):
        type(self).calls += 1
        if not self.session_ok:
            from tradebot.broker import TokenExpired
            raise TokenExpired("Kite session invalid")
        return super().bars(*a, **kw)


class TestEngineSessionHandling(TestLiveEngine):
    def setUp(self):
        super().setUp()
        SessionPaper.calls = 0
        self.broker = SessionPaper(self.feed, 0.0)
        self.got = []
        from tradebot.alerts import AlertHandler
        h = AlertHandler([self.got.append], "t", background=False)
        lg = logging.getLogger("tradebot")
        old = lg.level
        lg.setLevel(logging.INFO)
        lg.addHandler(h)
        self.addCleanup(lg.setLevel, old)
        self.addCleanup(lg.removeHandler, h)

    def test_expired_session_pauses_alerts_once_and_resumes(self):
        eng = self.engine()
        self.broker.session_ok = False
        day = self.df.index[3]
        for hhmm in ("08:50", "09:20", "10:00", "11:00"):      # pre-open reminder + session
            self.feed.n = 4
            self.clock[0] = day + pd.Timedelta(hours=int(hhmm[:2]), minutes=int(hhmm[3:]))
            eng.step()
        self.assertEqual(SessionPaper.calls, 0)                # broker never touched
        alerts = [m for m in self.got if "BROKER LOGIN NEEDED" in m]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(eng.positions, {})
        self.broker.session_ok = True                          # user ran `tradebot login`
        self.clock[0] = day + pd.Timedelta(hours=11, minutes=30)
        eng.step()
        self.assertIn("A", eng.positions)
        self.assertTrue(any("resuming" in m for m in self.got))

    def test_token_rejected_mid_cycle_does_not_crash(self):
        eng = self.engine()
        self.tick(eng, 3)
        self.assertIn("A", eng.positions)
        self.broker.auth_status = lambda now=None: (True, "")  # clock says fine...
        self.broker.session_ok = False                          # ...but Kite rejects it
        self.tick(eng, 4)                                       # must not raise
        self.assertTrue(any("BROKER LOGIN NEEDED" in m for m in self.got))
        self.assertIn("1 open position", [m for m in self.got if "LOGIN" in m][0])

    def test_no_reminder_on_weekends_or_overnight(self):
        eng = self.engine()
        self.broker.session_ok = False
        sat = pd.Timestamp("2024-01-06 10:00", tz=TZ)
        night = pd.Timestamp("2024-01-08 22:00", tz=TZ)
        for t in (sat, night):
            self.clock[0] = t
            eng.step()
        self.assertFalse(any("LOGIN" in m for m in self.got))


if __name__ == "__main__":
    unittest.main()
