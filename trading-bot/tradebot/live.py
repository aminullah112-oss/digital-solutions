"""Live / paper trading loop.

Same Strategy and RiskManager as the backtester. Differences that matter:
  * Every position gets a broker-side stop order immediately after the entry
    fills. If the stop can't be placed, the position is closed at market. The
    bot never holds an unprotected position on purpose.
  * The stop order's status is the source of truth for stop exits, so a crashed
    bot still has its stops working at the broker.
  * A stop the bot didn't cancel (e.g. a DAY order that expired overnight) is
    re-placed on the next cycle.
  * Order requests that time out are never blindly retried (no duplicate
    orders); partial fills are tracked and protected for the quantity filled.
  * Every cycle starts by reconciling against the broker. A position without a
    stop gets one (or is closed); any quantity mismatch blocks new entries until
    a human runs `reset`.
  * Creating the kill-switch file blocks entries, flattens at the next moment the
    market is open, then exits.
  * State (positions, risk counters and halts) is written atomically after every
    cycle, so a restart doesn't clear a halt. A lock file prevents two engines
    running on the same state.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import add_turnover
from .broker import Broker, BrokerError, OrderUnknown
from .config import Config
from .models import Position, Trade
from .risk import RiskManager
from .strategies import Strategy

log = logging.getLogger("tradebot")

BAR_MINUTES = {"minute": 1, "3minute": 3, "5minute": 5, "10minute": 10, "15minute": 15,
               "30minute": 30, "60minute": 60}


class LiveEngine:
    def __init__(self, cfg: Config, strategy: Strategy, broker: Broker, now=None):
        if strategy.mode != cfg.mode:
            raise ValueError(f"strategy {strategy.name} is {strategy.mode}, config mode is {cfg.mode}")
        self.cfg, self.strat, self.broker = cfg, strategy, broker
        self.tz = cfg.session.timezone
        self.now = now or (lambda: pd.Timestamp.now(tz=self.tz))
        self.state_path = Path(cfg.state_file)
        self.trades_path = self.state_path.with_name("trades.csv")
        self.positions: dict[str, Position] = {}
        self.last_bar: dict[str, str] = {}
        self.last_px: dict[str, float] = {}
        self.realized = 0.0
        self.risk = RiskManager(cfg)
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self):
        if not self.state_path.exists():
            return
        s = json.loads(self.state_path.read_text())
        self.realized = s.get("realized", 0.0)
        self.last_bar = s.get("last_bar", {})
        self.risk = RiskManager(self.cfg, s.get("risk"))
        for d in s.get("positions", []):
            d["entry_time"] = pd.Timestamp(d["entry_time"])
            p = Position(**d)
            self.positions[p.symbol] = p
            self.last_px[p.symbol] = p.entry
        log.info("loaded state: %d positions, realized %.2f", len(self.positions), self.realized)

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        positions = []
        for p in self.positions.values():
            d = asdict(p)
            d["entry_time"] = str(p.entry_time)
            positions.append(d)
        s = {"realized": self.realized, "last_bar": self.last_bar, "risk": self.risk.to_dict(),
             "positions": positions, "broker": self.broker.to_dict(), "saved_at": str(self.now())}
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, indent=2, default=float))
        os.replace(tmp, self.state_path)

    # ---------------------------------------------------------------- helpers
    def equity(self) -> float:
        """Bot-scoped equity: allocated capital + realized + open P&L on bot positions.
        Keeps the bot's risk maths independent of anything else in the account."""
        upnl = sum(p.side * p.qty * (self.last_px.get(s, p.entry) - p.entry) for s, p in self.positions.items())
        return self.cfg.initial_capital + self.realized + upnl

    def market_open(self, now: pd.Timestamp) -> bool:
        s = self.cfg.session
        return now.weekday() < 5 and s.t("open") <= now.time() < s.t("close")

    def _closed_bars(self, df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
        """Drop the still-forming bar so signals are only judged on closed bars,
        exactly as in the backtest."""
        if df.empty:
            return df
        last = df.index[-1]
        if self.cfg.interval == "day":
            closed = last.date() < now.date() or now.time() >= self.cfg.session.t("close")
        else:
            closed = last + pd.Timedelta(minutes=BAR_MINUTES[self.cfg.interval]) <= now
        return df if closed else df.iloc[:-1]

    def _record(self, p: Position, px: float, why: str, keep: bool = False):
        c = self.cfg.costs.cost_pct
        pnl = p.side * p.qty * (px - p.entry) - c * p.qty * (p.entry + px)
        t = Trade(p.symbol, p.side, p.qty, p.entry_time, self.now(), p.entry, px, pnl,
                  pnl / (p.qty * p.r_per_share) if p.r_per_share else 0.0, why, p.reason, p.bars_held)
        self.realized += pnl
        self.risk.on_trade_closed(t)
        if not keep:
            self.positions.pop(p.symbol, None)
            self.last_px.pop(p.symbol, None)
        new = not self.trades_path.exists()
        self.trades_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trades_path.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(list(asdict(t)))
            w.writerow(list(asdict(t).values()))
        log.info("CLOSED %s %s qty=%d @ %.2f pnl=%.2f (%.2fR) [%s]",
                 "LONG" if p.side > 0 else "SHORT", p.symbol, p.qty, px, pnl, t.r_multiple, why,
                 extra={"notify": True})

    # ------------------------------------------------------------ order flows
    def _arm_stop(self, p: Position) -> bool:
        try:
            p.broker_stop_id = self.broker.place_stop(p.symbol, -p.side, p.qty, p.stop, tag="stop")
            return True
        except BrokerError as e:
            p.broker_stop_id = None
            if isinstance(e, OrderUnknown):
                self.risk.block_entries(f"{p.symbol}: stop placement outcome unknown")
            log.error("could not place stop for %s: %s", p.symbol, e)
            return False

    def exit(self, sym: str, why: str):
        p = self.positions[sym]
        if p.broker_stop_id and not self.broker.cancel(p.broker_stop_id):
            st, avg = self.broker.order_status(p.broker_stop_id)
            if st == "COMPLETE":
                self._record(p, avg, "stop")
                return
        p.broker_stop_id = None
        try:
            fill = self.broker.market(sym, -p.side, p.qty, tag="exit")
        except BrokerError as e:
            if isinstance(e, OrderUnknown):
                self.risk.block_entries(f"{sym}: exit order outcome unknown")
                held = self._held(sym)
                if held == 0:
                    # The exit went through. Re-arming a stop now would leave a stray
                    # order that could open a reverse position.
                    self._record(p, self.broker.ltp(sym), why + " (confirmed via positions)")
                    return
            # Stop is already cancelled; don't leave the position naked.
            if not self._arm_stop(p):
                log.critical("%s: exit failed AND stop re-arm failed - POSITION UNPROTECTED", sym)
            raise
        if fill.qty < p.qty:
            # Partial exit: book what filled, keep protecting the rest.
            self._record(replace(p, qty=fill.qty), fill.price, why + " (partial)", keep=True)
            p.qty -= fill.qty
            log.critical("%s: exit filled %d of %d; %d remain", sym, fill.qty, fill.qty + p.qty, p.qty)
            if not self._arm_stop(p):
                log.critical("%s: remainder UNPROTECTED", sym)
            raise BrokerError(f"{sym}: partial exit")
        self._record(p, fill.price, why)

    def _held(self, sym: str) -> int | None:
        """Broker's net quantity for sym, or None if it can't be read."""
        try:
            return self.broker.net_positions().get(sym, 0)
        except BrokerError:
            return None

    def flatten_all(self, why: str):
        for sym in list(self.positions):
            try:
                self.exit(sym, why)
            except BrokerError as e:
                log.error("FAILED to flatten %s: %s - CLOSE IT MANUALLY", sym, e)

    def enter(self, sig, qty: int):
        sym, side = sig.symbol, sig.side
        notional_cap = self.equity() * self.cfg.risk.max_position_pct / 100 * 1.05
        if qty * sig.ref_price > notional_cap:
            log.error("sanity check: %s order value %.0f > cap %.0f; skipped", sym, qty * sig.ref_price, notional_cap)
            return
        before = self._held(sym) or 0
        try:
            fill = self.broker.market(sym, side, qty, tag="entry")
        except OrderUnknown:
            # The entry may have filled. If the broker shows new shares, take
            # ownership and protect them rather than leave them stopless.
            self.risk.block_entries(f"{sym}: entry order outcome unknown")
            held = self._held(sym)
            got = (held - before) * side if held is not None else 0
            if got <= 0:
                raise
            log.critical("%s: entry timed out but %d filled; adopting and protecting it", sym, got)
            from .broker import Fill
            fill = Fill(self.broker.ltp(sym), min(got, qty))
        if fill.qty < qty:
            log.warning("%s entry partially filled: %d of %d", sym, fill.qty, qty)
        p = Position(sym, side, fill.qty, fill.price, sig.stop, sig.stop, sig.target, self.now(),
                     self.cfg.hold_limit(sig.max_bars), sig.reason)
        self.positions[sym] = p
        self.last_px[sym] = fill.price
        if side * (fill.price - sig.stop) <= 0 or \
                side * (fill.price - sig.ref_price) > self.cfg.risk.max_gap_slip_r * sig.risk_per_share:
            log.warning("%s filled at %.2f, too far past plan (ref %.2f stop %.2f); exiting",
                        sym, fill.price, sig.ref_price, sig.stop)
            self.exit(sym, "entry abort")
            return
        if not self._arm_stop(p):
            self.exit(sym, "no stop")
            return
        log.info("OPENED %s %s qty=%d @ %.2f stop=%.2f target=%s [%s]",
                 "LONG" if side > 0 else "SHORT", sym, p.qty, fill.price, sig.stop,
                 f"{sig.target:.2f}" if sig.target else "-", sig.reason, extra={"notify": True})

    # ---------------------------------------------------------------- cycle
    def reconcile(self):
        """Make the bot's view match the broker's before anything else happens.
        Anything it can't explain blocks new entries until a human runs `reset`."""
        for sym, p in list(self.positions.items()):
            try:
                self._protect(sym, p)
            except BrokerError as e:
                # Couldn't re-arm AND couldn't exit. Keep going so every other position
                # is still checked; this one is retried next cycle.
                log.critical("%s UNPROTECTED: stop and exit both failed (%s); retrying next cycle", sym, e)
        try:
            held = self.broker.net_positions()
        except BrokerError as e:
            self.risk.block_entries(f"could not read broker positions: {e}")
            return
        for sym in self.cfg.symbols:
            expect = self.positions[sym].side * self.positions[sym].qty if sym in self.positions else 0
            if held.get(sym, 0) == expect:
                continue
            p = self.positions.get(sym)
            if p and p.broker_stop_id:
                st, avg = self.broker.order_status(p.broker_stop_id)
                if st == "COMPLETE":          # stop filled between the two reads
                    self._record(p, avg, "stop")
                    if held.get(sym, 0) == 0:
                        continue
            msg = f"{sym}: broker qty {held.get(sym, 0)}, bot expects {expect}"
            log.error("reconcile mismatch, entries blocked: %s", msg)
            self.risk.block_entries(f"reconcile mismatch: {msg}")

    def _protect(self, sym: str, p: Position):
        if not p.broker_stop_id:
            log.warning("%s has no protective stop; arming at %.2f", sym, p.stop)
            if not self._arm_stop(p):
                self.exit(sym, "stop lost")
            return
        st, avg = self.broker.order_status(p.broker_stop_id)
        if st == "COMPLETE":
            self._record(p, avg, "trailing stop" if p.stop != p.initial_stop else "stop")
        elif st in ("CANCELLED", "REJECTED"):
            # e.g. a DAY stop that expired overnight, or a broker-side cancel
            log.warning("stop for %s is %s; re-placing at %.2f", sym, st, p.stop)
            if not self._arm_stop(p):
                self.exit(sym, "stop lost")

    def unprotected(self) -> list[str]:
        return [s for s, p in self.positions.items() if not p.broker_stop_id]

    def _kill_switch(self, now) -> bool:
        if not Path(self.cfg.kill_switch_file).exists():
            return False
        self.risk.block_entries("kill switch")
        if not self.positions:
            log.critical("kill switch: no open positions; stopping")
            self.save()
            raise SystemExit(0)
        if not self.market_open(now):
            # Market orders outside the session would be rejected (or queued as AMOs).
            log.critical("kill switch: market closed; will flatten at the open. Stops stay live.")
            self.save()
            return True
        log.critical("kill switch: flattening and stopping")
        self.flatten_all("kill switch")
        self.save()
        if self.positions:
            log.critical("kill switch: %s still open; retrying next cycle", list(self.positions))
            return True
        raise SystemExit(0)

    def _note_halt(self):
        h = self.risk.halted()
        if h and h != getattr(self, "_last_halt", ""):
            log.critical("TRADING HALTED: %s", h)
        self._last_halt = h

    def step(self):
        self._last_halt = getattr(self, "_last_halt", self.risk.halted())
        try:
            self._step()
        finally:
            self._note_halt()

    def _step(self):
        now = self.now()
        if self._kill_switch(now):
            return
        if not self.market_open(now):
            return
        self.risk.on_new_day(str(now.date()), self.equity())
        self.reconcile()
        self.risk.on_equity(self.equity())
        if why := self.risk.must_flatten():
            if self.positions:
                log.warning("risk flatten: %s", why)
            self.flatten_all(f"risk flatten: {why}")
        intraday = self.cfg.mode == "intraday"
        if intraday and now.time() >= self.cfg.session.t("flatten_at"):
            if self.positions:
                self.flatten_all("end of day")
            self.save()
            return
        for sym in self.cfg.symbols:
            try:
                self._process(sym, now)
            except OrderUnknown as e:
                self.risk.block_entries(str(e))
                log.error("%s: %s", sym, e)
            except BrokerError as e:
                log.error("%s: %s", sym, e)
        self.risk.on_equity(self.equity())
        self.save()

    def _process(self, sym: str, now: pd.Timestamp):
        lookback = 10 if self.cfg.mode == "intraday" else 420
        df = self._closed_bars(self.broker.bars(sym, self.cfg.interval, lookback), now)
        if len(df) <= self.strat.warmup:
            return
        p = self.positions.get(sym)

        # Target and price tracking on every poll, not just on new bars.
        if p is not None:
            ltp = self.broker.ltp(sym)
            self.last_px[sym] = ltp
            if p.target is not None and p.side * (ltp - p.target) >= 0:
                self.exit(sym, "target")
                return

        last_ts = df.index[-1]
        if self.last_bar.get(sym) == str(last_ts):
            return
        self.last_bar[sym] = str(last_ts)
        df = add_turnover(self.strat.prepare(df), self.cfg.mode)
        i = len(df) - 1
        bar = df.iloc[i]

        if p is not None:
            if last_ts <= p.entry_time:
                return
            p.bars_held += 1
            p.best_price = max(p.best_price, bar.high) if p.side > 0 else min(p.best_price, bar.low)
            if p.max_bars and p.bars_held >= p.max_bars:
                self.exit(sym, "time stop")
                return
            new_stop = self.strat.update_stop(p, df, i)
            if new_stop != p.stop and p.broker_stop_id:
                ltp = self.last_px.get(sym, bar.close)
                if p.side * (ltp - new_stop) <= 0:
                    self.exit(sym, "trailing stop (through)")
                    return
                self.broker.modify_stop(p.broker_stop_id, new_stop)
                log.info("%s stop %.2f -> %.2f", sym, p.stop, new_stop)
                p.stop = new_stop
            return

        if self.risk.halted():
            return
        if self.unprotected():
            return      # no new risk while any position lacks a stop; self-clears once re-armed
        if self.cfg.mode == "intraday" and now.time() >= self.cfg.session.t("last_entry"):
            return
        sig = self.strat.signal(sym, df, i, self.cfg.allow_short)
        if sig is None:
            return
        # The bar that produced the signal must be recent, or we'd be acting on stale data.
        max_age = pd.Timedelta(minutes=2 * BAR_MINUTES.get(self.cfg.interval, 0)) if self.cfg.interval != "day" else pd.Timedelta(days=5)
        if now - last_ts > max_age + pd.Timedelta(minutes=BAR_MINUTES.get(self.cfg.interval, 0)):
            log.info("%s: signal on stale bar %s ignored", sym, last_ts)
            return
        tv = bar.turnover
        qty, why = self.risk.size(sig, self.equity(), self.positions,
                                  None if np.isnan(tv) else float(tv), float(bar.volume))
        if not qty:
            log.info("%s %s rejected: %s", sym, sig.reason, why)
            return
        self.enter(sig, qty)

    def acquire_lock(self):
        """One engine per state file. Two processes managing the same positions
        would double-exit and fight over stops."""
        import fcntl
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = open(self.state_path.with_suffix(".lock"), "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock.close()
            raise SystemExit(f"another tradebot is already running on {self.state_path}") from None
        self._lock.write(str(os.getpid()))
        self._lock.flush()

    def run(self, poll_seconds: int = 20, heartbeat=None, alerts=None):
        self.acquire_lock()
        log.info("starting %s/%s on %s (%s)", self.cfg.mode, self.strat.name,
                 ",".join(self.cfg.symbols), type(self.broker).__name__, extra={"notify": True})
        try:
            while True:
                try:
                    self.step()
                    if heartbeat:
                        heartbeat.beat()       # only after a clean cycle: a stuck bot stops pinging
                except SystemExit:
                    raise
                except Exception:
                    log.exception("cycle failed; positions keep their broker-side stops")
                time.sleep(poll_seconds)
        except BaseException as e:
            log.critical("bot stopping: %s", e if str(e) else type(e).__name__)
            raise
        finally:
            if alerts:
                alerts.flush()
