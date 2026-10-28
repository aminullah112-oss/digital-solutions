"""Live / paper trading loop.

Same Strategy and RiskManager as the backtester. Differences that matter:
  * Every position gets a broker-side stop immediately after the entry fills
    (GTT for CNC, so it survives overnight and token expiry; SL-M for MIS).
  * Every order carries an engine-chosen tag. Ambiguous outcomes are recorded in
    `pending` and resolved by tag (or by the broker's position change) on later
    cycles; nothing that could double up is sent meanwhile. A resting stop is
    never presumed absent by the bot: that needs an operator `reset`.
  * Cancels count only when the broker reports a final state, so an exit never
    races a stop that might still fill.
  * Every cycle starts by reconciling against the broker. Shares the bot can't
    attribute to its own orders (beyond the recorded external baseline) block
    entries until a human runs `reset`; the bot never touches them.
  * Creating the kill-switch file blocks entries, flattens at the next moment the
    market is open, then exits.
  * State (positions, pending orders, risk counters and halts) is written
    atomically after every cycle. A lock file prevents two engines running on
    the same state.
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
from .broker import Broker, BrokerError, Fill, OrderState, OrderUnknown, TokenExpired
from .config import Config
from .models import Position, Trade
from .risk import Correlations, RiskManager
from .strategies import Strategy

log = logging.getLogger("tradebot")


def control_path(state_file) -> Path:
    """Requests to a running engine (from the CLI or the web panel) go here; the
    engine applies them at the start of its next cycle. Writing state directly
    doesn't work while it runs: it saves its in-memory state every cycle."""
    return Path(state_file).with_name("control.json")


def engine_running(state_file) -> bool:
    """True if an engine currently holds the lock for this state file."""
    import fcntl
    lock = Path(state_file).with_suffix(".lock")
    if not lock.exists():
        return False
    with open(lock, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
    return False


def request_control(state_file, **request) -> None:
    p = control_path(state_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(p.read_text()) if p.exists() else {}
    current.update(request)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(current))
    os.replace(tmp, p)


def reset_state(engine_like, by: str) -> list[str]:
    """Operator reset, shared by the engine (in memory) and offline edits.
    `engine_like` has .risk, .rebaseline, .pending and .equity()."""
    notes = [f"current halt: {engine_like.risk.halted() or 'none'}"]
    engine_like.risk.reset(engine_like.equity())
    engine_like.rebaseline = True             # re-capture shares the bot doesn't own
    for r in engine_like.pending.values():
        if r.get("kind") == "stop" and r.get("escalated"):
            # The operator has checked the order book (and cancelled any stray stop).
            r["confirmed_absent"] = True
            notes.append(f"stop {r['tag']} for {r['symbol']} marked absent; a fresh one will be placed")
    notes.append(f"risk state reset by {by}; peak re-based to {engine_like.equity():,.2f}")
    return notes

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
        self.pending: dict[str, dict] = {}      # tag -> unresolved order record
        self.external: dict[str, int] = {}      # shares in the account the bot doesn't own
        self.rebaseline = True                  # capture `external` on first reconcile
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self):
        if not self.state_path.exists():
            return
        s = json.loads(self.state_path.read_text())
        self.realized = s.get("realized", 0.0)
        self.last_bar = s.get("last_bar", {})
        self.risk = RiskManager(self.cfg, s.get("risk"))
        self.pending = s.get("pending", {})
        self.external = s.get("external", {})
        self.rebaseline = s.get("rebaseline", "external" not in s)
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
             "positions": positions, "pending": self.pending, "external": self.external,
             "rebaseline": self.rebaseline, "broker": self.broker.to_dict(), "saved_at": str(self.now())}
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
        return self.trading_day(now) and s.t("open") <= now.time() < s.t("close")

    def trading_day(self, now: pd.Timestamp) -> bool:
        return now.weekday() < 5 and str(now.date()) not in self.cfg.session.holidays

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
    # Rules (see broker.py for the broker side of the contract):
    #  1. Every order carries a tag the engine chose. If a request's outcome is
    #     unknown, the tag goes into self.pending and is resolved on later cycles;
    #     nothing that could double up (another exit, another stop) is sent for that
    #     position until it resolves or RESOLVE_SECONDS pass with no trace of it.
    #  2. A protective order is only treated as dead after the broker reports a
    #     final state. "Cancel requested" is not "cancelled".
    #  3. Shares the bot can attribute to its own tagged orders are adopted and
    #     protected. Shares it can't attribute are never touched: entries are
    #     blocked and a human is alerted.
    RESOLVE_SECONDS = 120
    FALLBACK_EXITS = ("stop lost", "no stop")   # exits that only exist because a stop failed
    STUCK_STOP_PCT = 0.5     # price this far through an OPEN stop for 2 cycles = not executing

    def _tag(self, kind: str) -> str:
        self._seq = (getattr(self, "_seq", 0) + 1) % 100
        return f"tb{kind[0]}{int(time.time() * 1000) % 10**12:012d}{self._seq:02d}"

    def _remember(self, tag: str, kind: str, sym: str, side: int, qty: int, **extra):
        now = self.now()
        self.pending[tag] = dict(tag=tag, kind=kind, symbol=sym, side=side, qty=qty,
                                 created=str(now), deadline=str(now + pd.Timedelta(seconds=self.RESOLVE_SECONDS)),
                                 absent=False, **extra)

    def _status(self, oid: str) -> OrderState:
        try:
            return self.broker.order_status(oid)
        except BrokerError as e:
            log.warning("status of %s unavailable: %s", oid, e)
            return OrderState("UNKNOWN")

    def _cancel(self, oid: str) -> OrderState:
        try:
            return self.broker.cancel(oid)
        except BrokerError as e:
            log.warning("cancel of %s unconfirmed: %s", oid, e)
            return OrderState("UNKNOWN")

    def _fill_against(self, p: Position, qty: int, px: float, why: str):
        """Book `qty` shares of p as closed at px (all of it, or a partial)."""
        if qty >= p.qty:
            self._record(p, px, why)
        else:
            self._record(replace(p, qty=qty), px, why + " (partial)", keep=True)
            p.qty -= qty

    def _arm_stop(self, p: Position) -> str:
        """Place p's protective stop. Returns 'ok', 'pending' (outcome unknown, being
        resolved) or 'failed' (definitely not placed)."""
        tag = self._tag("stop")
        try:
            p.broker_stop_id = self.broker.place_stop(p.symbol, -p.side, p.qty, p.stop, tag=tag)
            p.stop_tag, p.stop_qty = None, p.qty
            return "ok"
        except OrderUnknown as e:
            p.broker_stop_id, p.stop_tag, p.stop_qty = None, tag, p.qty
            self._remember(tag, "stop", p.symbol, -p.side, p.qty, trigger=p.stop,
                           **e.metadata)
            log.error("%s: stop placement outcome unknown (%s); resolving before any other order", p.symbol, e)
            return "pending"
        except BrokerError as e:
            p.broker_stop_id = None
            log.error("could not place stop for %s: %s", p.symbol, e)
            return "failed"

    def exit(self, sym: str, why: str) -> bool:
        """Close sym at market. Returns True once fully closed. Defers (returns
        False, keeps p.exit_wanted) whenever acting now could double up."""
        p = self.positions[sym]
        if p.exit_tag or p.stop_tag:
            p.exit_wanted = why
            return False
        if p.broker_stop_id:
            st = self._cancel(p.broker_stop_id)
            if st.filled and st.final:
                self._fill_against(p, st.filled, st.avg, "stop")
                if sym not in self.positions:
                    return True
            if not st.final:
                p.exit_wanted = why
                log.warning("%s: stop cancel not confirmed (%s); exit deferred, stop still live", sym, st.status)
                return False
            p.broker_stop_id = None
        tag = self._tag("exit")
        try:
            fill = self.broker.market(sym, -p.side, p.qty, tag=tag)
        except OrderUnknown as e:
            p.exit_tag, p.exit_wanted = tag, why
            self._remember(tag, "exit", sym, -p.side, p.qty, why=why)
            log.critical("%s: exit outcome unknown (%s); resolving by tag before anything else", sym, e)
            return False
        except BrokerError:
            # Definitely rejected: nothing sold. Re-protect, retry the exit next cycle.
            p.exit_wanted = why
            if self._arm_stop(p) == "failed":
                log.critical("%s: exit rejected AND stop re-arm failed - POSITION UNPROTECTED", sym)
            raise
        p.exit_wanted = ""
        self._fill_against(p, fill.qty, fill.price, why)
        if sym in self.positions:
            p.exit_wanted = why
            log.critical("%s: exit filled %d; %d remain, re-protecting", sym, fill.qty, p.qty)
            self._arm_stop(p)
            return False
        return True

    def flatten_all(self, why: str):
        for sym in list(self.positions):
            try:
                self.exit(sym, why)
            except BrokerError as e:
                log.error("FAILED to flatten %s: %s - retrying next cycle", sym, e)

    def enter(self, sig, qty: int):
        sym, side = sig.symbol, sig.side
        notional_cap = self.equity() * self.cfg.risk.max_position_pct / 100 * 1.05
        if qty * sig.ref_price > notional_cap:
            log.error("sanity check: %s order value %.0f > cap %.0f; skipped", sym, qty * sig.ref_price, notional_cap)
            return
        plan = dict(ref=sig.ref_price, stop=sig.stop, target=sig.target,
                    max_bars=self.cfg.hold_limit(sig.max_bars), reason=sig.reason)
        tag = self._tag("entry")
        try:
            fill = self.broker.market(sym, side, qty, tag=tag)
        except OrderUnknown as e:
            self._remember(tag, "entry", sym, side, qty, plan=plan)
            log.critical("%s: entry outcome unknown (%s); will adopt and protect it if it filled", sym, e)
            return
        self._open(sym, side, fill, plan)

    def _open(self, sym: str, side: int, fill, plan: dict, adopted: bool = False):
        if fill.qty <= 0:
            return
        p = Position(sym, side, fill.qty, fill.price, plan["stop"], plan["stop"], plan["target"],
                     self.now(), plan["max_bars"], plan["reason"])
        self.positions[sym] = p
        self.last_px[sym] = fill.price
        R = abs(plan["ref"] - plan["stop"])
        if side * (fill.price - plan["stop"]) <= 0 or side * (fill.price - plan["ref"]) > self.cfg.risk.max_gap_slip_r * R:
            log.warning("%s filled at %.2f, too far past plan (ref %.2f stop %.2f); exiting",
                        sym, fill.price, plan["ref"], plan["stop"])
            self.exit(sym, "entry abort")
            return
        if self._arm_stop(p) == "failed":
            self.exit(sym, "no stop")
            return
        log.info("%s %s %s qty=%d @ %.2f stop=%.2f target=%s [%s]", "ADOPTED" if adopted else "OPENED",
                 "LONG" if side > 0 else "SHORT", sym, p.qty, fill.price, p.stop,
                 f"{p.target:.2f}" if p.target else "-", p.reason, extra={"notify": True})

    # ---------------------------------------------------------- resolution
    def _resolve_pending(self):
        now = self.now()
        for tag, r in list(self.pending.items()):
            try:
                self._resolve_one(tag, r, now)
            except BrokerError as e:
                # One record's follow-up (e.g. exiting an adopted fill) failing must not
                # stop the rest of reconciliation; _protect retries next cycle.
                log.error("resolving %s (%s %s): %s", tag, r["kind"], r["symbol"], e)

    def _resolve_one(self, tag: str, r: dict, now):
        try:
            hit = self.broker.find_by_tag(tag, hint=r)
        except BrokerError as e:
            log.warning("lookup of %s failed: %s", tag, e)
            return
        sym, p = r["symbol"], self.positions.get(r["symbol"])
        if hit is None and r["kind"] == "stop":
            # A stop RESTS at the broker, so "not visible yet" never proves it isn't
            # there. Placing another stop or exiting could sell the same shares
            # twice. Only a human (after checking the order book) can rule it out.
            if self._infer_from_positions(r):
                # Shares left the account with this stop outstanding: it fired.
                if r["inferred"] >= r["qty"]:
                    del self.pending[tag]
                return
            if r.get("confirmed_absent"):
                del self.pending[tag]
                if p and p.stop_tag == tag:
                    p.stop_tag = None            # _protect re-arms
                log.warning("%s: stop %s confirmed absent by operator; re-arming", sym, tag)
            elif now >= pd.Timestamp(r["deadline"]) and not r.get("escalated"):
                r["escalated"] = True
                msg = (f"{sym}: can't confirm whether protective stop {tag} exists. Not placing another "
                       f"or exiting (could sell twice). Check the Kite order book/GTTs, cancel any stray "
                       f"stop, then run `tradebot reset`")
                log.critical(msg)
                self.risk.block_entries(msg)
            return
        if hit is None:
            if not r["absent"] and now >= pd.Timestamp(r["deadline"]):
                # Market orders don't rest: if the position hasn't moved by now, the
                # order didn't happen and retrying is safe.
                r["absent"] = True
                if p and r["kind"] == "exit" and p.exit_tag == tag:
                    p.exit_tag = None            # _protect re-arms, exit retried
                if self._infer_from_positions(r):
                    return
                log.error("%s order %s (%s) not found after %ds and positions show no fill; "
                          "treating as not placed, still watching today", sym, tag, r["kind"], self.RESOLVE_SECONDS)
            elif r["absent"] and now.date() > pd.Timestamp(r["created"]).date():
                del self.pending[tag]
            return
        oid, st = hit
        if not st.final:
            self._resolve_live(tag, r, oid, st, p, now)
            return
        del self.pending[tag]
        if r.get("inferred") is not None:
            # Already booked from the position change; the order book now confirms it.
            if st.filled != r["inferred"]:
                msg = f"{sym}: order {tag} filled {st.filled} but {r['inferred']} was inferred"
                log.critical(msg)
                self.risk.block_entries(msg)
            return
        if r["kind"] == "entry":
            if st.filled:
                if p:
                    log.critical("%s: late entry fill of %d but a position already exists; entries blocked", sym, st.filled)
                    self.risk.block_entries(f"{sym}: late entry fill alongside an existing position")
                else:
                    log.critical("%s: entry %s resolved: %d filled @ %.2f; adopting", sym, tag, st.filled, st.avg)
                    self._open(sym, r["side"], Fill(st.avg, st.filled), r["plan"], adopted=True)
        elif r["kind"] == "exit" and p:
            if p.exit_tag == tag:
                p.exit_tag = None
            if st.filled:
                self._fill_against(p, st.filled, st.avg, r["why"] + " (resolved)")
        elif r["kind"] == "stop" and p:
            if p.stop_tag == tag:
                p.stop_tag = None
            if st.filled:
                self._fill_against(p, st.filled, st.avg, "stop (resolved)")
                q = self.positions.get(sym)
                if q and q.broker_stop_id:
                    # A replacement stop now covers more shares than we hold. Pull it
                    # and let _protect re-arm the right quantity.
                    c = self._cancel(q.broker_stop_id)
                    if c.final:
                        q.broker_stop_id = None
                    else:
                        self.risk.block_entries(f"{sym}: oversized replacement stop could not be cancelled")

    def _escalate_unknown(self, what: str, since: str, now) -> None:
        """UNKNOWN covers both a GTT that fired with its child order not yet visible
        and a single failed status read. Pause entries at once (self-clearing via
        unprotected()); escalate to a persistent block and CRITICAL alert only when
        it outlasts RESOLVE_SECONDS, so one network blip doesn't need an operator."""
        age = (now - pd.Timestamp(since)).total_seconds()
        if age < self.RESOLVE_SECONDS:
            log.warning("%s for %.0fs; entries paused while it resolves", what, age)
            return
        msg = f"{what} for {age:.0f}s; new entries blocked, check Kite"
        if not self.risk.state.entry_block:
            log.critical(msg, extra={"notify": True})
        self.risk.block_entries(msg)

    def _held(self, sym: str) -> int | None:
        """Broker net quantity for sym excluding shares the bot doesn't own, or None."""
        try:
            return self.broker.net_positions().get(sym, 0) - self.external.get(sym, 0)
        except BrokerError:
            return None

    def _infer_from_positions(self, r: dict) -> bool:
        """An order didn't show up in the order book in time. If the broker's
        position moved in that order's direction, the order happened: book it from
        the position change (at LTP) instead of acting as if it didn't."""
        sym = r["symbol"]
        if r.get("inferred") is not None:
            return False                     # already booked once
        held = self._held(sym)
        if held is None:
            return False
        p = self.positions.get(sym)
        moved = (held - self._bot_qty(sym)) * r["side"]   # shares moved in the order's direction
        if moved <= 0:
            return False
        moved = min(moved, r["qty"])
        try:
            px = self.broker.ltp(sym)
        except BrokerError:
            px = p.entry if p else r.get("plan", {}).get("ref", 0.0)
        r["inferred"] = moved
        log.critical("%s: %s order %s not visible but positions moved by %d; booking it (price approx. LTP %.2f)",
                     sym, r["kind"], r["tag"], moved, px)
        if r["kind"] == "entry" and not p:
            self._open(sym, r["side"], Fill(px, moved), r["plan"], adopted=True)
        elif r["kind"] in ("exit", "stop") and p:
            self._fill_against(p, moved, px, (r.get("why") or "stop") + " (inferred)")
        return True

    def _resolve_live(self, tag, r, oid, st, p, now):
        """A tagged order turned up and can still fill."""
        if st.status == "UNKNOWN":
            # A GTT can be triggered while its child limit order is not yet visible.
            # UNKNOWN is not equivalent to an active protective order.
            if p and r["kind"] == "stop":
                p.stop_uncertain = True
            r.setdefault("unknown_since", str(now))
            self._escalate_unknown(f"{r['symbol']}: order {tag} exists but its live state is UNKNOWN",
                                   r["unknown_since"], now)
            return
        if r["kind"] == "stop":
            if p and p.stop_tag == tag and not p.broker_stop_id:
                p.broker_stop_id, p.stop_tag = oid, None
                p.stop_uncertain = False
                del self.pending[tag]
                log.warning("%s: stop %s resolved as live (%s); protected", p.symbol, tag, oid)
                return
            # Duplicate (we already placed a replacement) or stray (no position): cancel it.
            c = self._cancel(oid)
            if c.final:
                del self.pending[tag]
                if c.filled and p:
                    self._fill_against(p, c.filled, c.avg, "stop (duplicate)")
            log.warning("%s: duplicate/stray stop %s cancel -> %s", r["symbol"], oid, c.status)
        elif now >= pd.Timestamp(r["deadline"]) and not r.get("cancel_sent"):
            r["cancel_sent"] = True              # a market order still working after 2 minutes
            log.error("%s: %s order %s still working; cancelling", r["symbol"], r["kind"], oid)
            self._cancel(oid)

    # ---------------------------------------------------------------- cycle
    def reconcile(self):
        """Make the bot's view match the broker's before anything else happens."""
        self._resolve_pending()
        for sym, p in list(self.positions.items()):
            try:
                self._protect(sym, p)
            except BrokerError as e:
                # Keep going so every other position is still checked; retried next cycle.
                log.critical("%s UNPROTECTED: stop and exit both failed (%s); retrying next cycle", sym, e)
        try:
            held = self.broker.net_positions()
        except BrokerError as e:
            self.risk.block_entries(f"could not read broker positions: {e}")
            return
        in_flux = {r["symbol"] for r in self.pending.values() if not r["absent"]}
        if self.rebaseline and not in_flux:
            self.external = {s: held.get(s, 0) - (self._bot_qty(s)) for s in self.cfg.symbols}
            self.external = {s: q for s, q in self.external.items() if q}
            self.rebaseline = False
            log.warning("external holdings baseline set: %s (bot never trades these shares)",
                        self.external or "none", extra={"notify": True})
        for sym in self.cfg.symbols:
            if sym in in_flux:
                continue
            expect = self._bot_qty(sym) + self.external.get(sym, 0)
            if held.get(sym, 0) == expect:
                continue
            p = self.positions.get(sym)
            if p and p.broker_stop_id:
                st = self._status(p.broker_stop_id)
                if st.final and st.filled:          # stop filled between the two reads
                    self._fill_against(p, st.filled, st.avg, "stop")
                    if held.get(sym, 0) == self._bot_qty(sym) + self.external.get(sym, 0):
                        continue
            msg = f"{sym}: broker qty {held.get(sym, 0)}, bot {self._bot_qty(sym)} + external {self.external.get(sym, 0)}"
            log.error("reconcile mismatch, entries blocked: %s", msg)
            self.risk.block_entries(f"reconcile mismatch: {msg}")

    def _bot_qty(self, sym: str) -> int:
        p = self.positions.get(sym)
        return p.side * p.qty if p else 0

    def _protect(self, sym: str, p: Position):
        if p.exit_tag or p.stop_tag:
            return                                   # the resolver owns this position for now
        if p.broker_stop_id:
            st = self._status(p.broker_stop_id)
            if st.status == "UNKNOWN":
                now = self.now()
                p.stop_uncertain = True                  # pauses entries; clears on the next good read
                p.uncertain_since = p.uncertain_since or str(now)
                self._escalate_unknown(f"{sym}: protective stop {p.broker_stop_id} state UNKNOWN",
                                       p.uncertain_since, now)
                return
            p.stop_uncertain, p.uncertain_since = False, ""
            if st.final and st.filled:
                self._fill_against(p, st.filled, st.avg, "trailing stop" if p.stop != p.initial_stop else "stop")
                if sym not in self.positions:
                    return
                p.broker_stop_id = None              # partly filled, rest cancelled
            elif st.final:
                # e.g. a DAY stop that expired, or a broker-side cancel/rejection
                log.warning("stop for %s is %s; re-placing at %.2f", sym, st.status, p.stop)
                p.broker_stop_id = None
            elif st.status == "OPEN":
                if p.stop_qty and p.stop_qty != p.qty:
                    # Position changed size (partial exit/fill) but the stop didn't. An
                    # oversized stop could sell shares we don't hold: resize it.
                    c = self._cancel(p.broker_stop_id)
                    if c.final and c.filled:
                        self._fill_against(p, c.filled, c.avg, "stop")
                    if not c.final:
                        log.error("%s: stop covers %d but position is %d; cancel unconfirmed, retrying",
                                  sym, p.stop_qty, p.qty)
                        return
                    p.broker_stop_id = None
                    if sym in self.positions:
                        self._arm_stop(p)
                    return
                if p.exit_wanted:
                    self.exit(sym, p.exit_wanted)
                    return
                ltp = self.broker.ltp(sym)
                self.last_px[sym] = ltp
                through = p.side * (p.stop - ltp) > p.stop * self.STUCK_STOP_PCT / 100
                p.through = p.through + 1 if through else 0
                if p.through >= 2:
                    log.critical("%s: price %.2f is through stop %.2f but the stop hasn't filled "
                                 "(circuit, or GTT limit skipped); exiting at market", sym, ltp, p.stop)
                    self.exit(sym, "stop not filling")
                return
            else:
                return                               # UNKNOWN: don't act on a guess
        if p.exit_wanted and p.exit_wanted not in self.FALLBACK_EXITS:
            self.exit(sym, p.exit_wanted)
            return
        ltp = self.broker.ltp(sym)
        self.last_px[sym] = ltp
        if p.side * (ltp - p.stop) <= 0:
            self.exit(sym, "price through stop")
            return
        # Protection first: if the stop goes in, the fallback exit is no longer needed.
        r = self._arm_stop(p)
        if r == "ok" and p.exit_wanted in self.FALLBACK_EXITS:
            p.exit_wanted = ""
        elif r == "failed":
            self.exit(sym, "stop lost")

    def unprotected(self) -> list[str]:
        return [s for s, p in self.positions.items()
                if not p.broker_stop_id or p.stop_uncertain]

    def entries_paused(self) -> str:
        """Self-clearing reasons not to take new risk (unlike risk halts)."""
        if self.unprotected():
            return f"unprotected: {self.unprotected()}"
        if any(p.stop_qty and p.stop_qty != p.qty for p in self.positions.values()):
            return "stop being resized"
        if any(not r["absent"] for r in self.pending.values()):
            return "unresolved orders"
        return ""

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
        except TokenExpired as e:
            self._auth_wait(str(e), self.now())
        finally:
            self._note_halt()

    def _auth_wait(self, detail: str, now) -> None:
        """No valid broker session: do nothing that touches the broker. Alert once
        per day per reason. Orders already at the broker (stops) keep working."""
        key = (str(now.date()), detail)
        if getattr(self, "_auth_alerted", None) != key:
            self._auth_alerted = key
            note = (f" {len(self.positions)} open position(s); their broker-side stops stay active, "
                    "but trailing, targets and the intraday flatten are paused") if self.positions else ""
            hint = ""
            if hasattr(self.broker, "api_key"):
                from .kite import login_url
                hint = f" Log in: {login_url(self.broker.api_key)} then run `python -m tradebot login`."
            log.critical("BROKER LOGIN NEEDED: %s.%s%s", detail, hint, note)
        self._auth_waiting = True

    def _check_auth(self, now) -> bool:
        ok, detail = self.broker.auth_status(now)
        if not ok:
            self._auth_wait(detail, now)
            return False
        if getattr(self, "_auth_waiting", False):
            self._auth_waiting = False
            log.info("broker session OK again; resuming", extra={"notify": True})
        return True

    def _apply_control(self):
        p = control_path(self.state_path)
        if not p.exists():
            return
        try:
            req = json.loads(p.read_text())
        except (OSError, ValueError) as e:
            log.error("ignoring unreadable control file %s: %s", p, e)
            p.unlink(missing_ok=True)
            return
        p.unlink(missing_ok=True)
        if req.get("reset"):
            for line in reset_state(self, req["reset"].get("by", "operator")):
                log.warning(line, extra={"notify": True})
            self.save()

    def _step(self):
        self._apply_control()
        now = self.now()
        s = self.cfg.session
        # From the reminder time to the close on weekdays, a dead session is alerted
        # before the open and blocks the cycle, so no order flow starts half-way.
        if self.trading_day(now) and s.t("login_reminder") <= now.time() < s.t("close"):
            if not self._check_auth(now):
                return
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
            if new_stop != p.stop and p.broker_stop_id and not (p.exit_tag or p.stop_tag or p.exit_wanted):
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
        if self.entries_paused() or any(r["symbol"] == sym for r in self.pending.values()):
            return      # no new risk while anything is unprotected or unresolved; self-clears
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
                                  None if np.isnan(tv) else float(tv), float(bar.volume),
                                  corr=lambda a, b: self._corr(a, b, now))
        if not qty:
            log.info("%s %s rejected: %s", sym, sig.reason, why)
            return
        self.enter(sig, qty)

    def _daily(self, sym: str, now) -> pd.Series | None:
        """Daily closes for sym, fetched at most once per day per symbol."""
        cache = self.__dict__.setdefault("_daily_cache", {})
        hit = cache.get(sym)
        if hit and hit[0] == now.date():
            return hit[1]
        try:
            days = int(self.cfg.risk.corr_lookback * 1.6) + 15      # trading days -> calendar
            closes = Correlations.daily_closes(self.broker.history(sym, "day", days))
        except BrokerError as e:
            log.warning("%s: no daily history for correlations (%s); assuming rho=%.2f",
                        sym, e, self.cfg.risk.corr_unknown)
            closes = None
        cache[sym] = (now.date(), closes)
        return closes

    def _corr(self, a: str, b: str, now) -> float | None:
        if a == b:
            return 1.0
        ca, cb = self._daily(a, now), self._daily(b, now)
        if ca is None or cb is None:
            return None
        return Correlations({a: ca, b: cb}, self.cfg.risk.corr_lookback).corr(a, b, now)

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

    def request_stop(self, signum=None, frame=None):
        """SIGTERM/SIGINT: finish the current cycle (never stop between cancelling a
        stop and sending its exit), save state, then exit."""
        self._stop_requested = True

    def run(self, poll_seconds: int = 20, heartbeat=None, alerts=None, max_cycles: int | None = None):
        import signal
        self.acquire_lock()
        self._stop_requested = False
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self.request_stop)
        log.info("starting %s/%s on %s (%s)", self.cfg.mode, self.strat.name,
                 ",".join(self.cfg.symbols), type(self.broker).__name__, extra={"notify": True})
        cycles = 0
        reason = "stop requested (SIGTERM/SIGINT)"
        try:
            while not self._stop_requested:
                try:
                    self.step()
                    if heartbeat:
                        heartbeat.beat()       # only after a clean cycle: a stuck bot stops pinging
                except SystemExit:
                    raise
                except Exception:
                    log.exception("cycle failed; positions keep their broker-side stops")
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    reason = "max cycles reached"
                    break
                end = time.monotonic() + poll_seconds
                while not self._stop_requested and time.monotonic() < end:
                    time.sleep(min(1.0, poll_seconds))
            self.save()
            log.warning("bot stopping: %s; broker-side stops stay active", reason, extra={"notify": True})
        except BaseException as e:
            log.critical("bot stopping: %s", e if str(e) else type(e).__name__)
            raise
        finally:
            if alerts:
                alerts.flush()
