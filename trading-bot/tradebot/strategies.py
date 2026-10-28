"""Strategies.

Contract, shared by the backtester and the live engine:
  prepare(df)            -> df with indicator columns (causal only)
  signal(sym, df, i, ..) -> Signal or None, judged on the CLOSE of bar i
  update_stop(pos, df, i)-> new stop after bar i closes; may only tighten

Every strategy has a fixed stop at entry. Nothing here averages down, martingales,
or widens a stop.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import indicators as ind
from .models import Position, Signal


class Strategy:
    name = "base"
    mode = "swing"
    defaults: dict = {}

    def __init__(self, **params):
        unknown = set(params) - set(self.defaults)
        if unknown:
            raise ValueError(f"{self.name}: unknown params {sorted(unknown)}")
        self.p = {**self.defaults, **params}

    @property
    def warmup(self) -> int:
        return 30

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    def signal(self, symbol: str, df: pd.DataFrame, i: int, allow_short: bool) -> Signal | None:
        raise NotImplementedError

    def update_stop(self, pos: Position, df: pd.DataFrame, i: int) -> float:
        """Default: move to breakeven once the trade is breakeven_r in profit."""
        be_r = self.p.get("breakeven_r")
        stop = pos.stop
        if be_r and pos.side * (pos.best_price - pos.entry) >= be_r * pos.r_per_share:
            stop = _tighter(pos.side, stop, pos.entry)
        return stop


def _tighter(side: int, current: float, proposed: float) -> float:
    if proposed is None or math.isnan(proposed):
        return current
    return max(current, proposed) if side > 0 else min(current, proposed)


def _ok(*vals) -> bool:
    return all(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in vals)


# --------------------------------------------------------------------------- intraday

class OpeningRangeBreakout(Strategy):
    """First clean break of the opening range, in the direction of VWAP, on volume.

    Filters out days where the range is too narrow (noise, false breaks) or too
    wide (stop too far for the reward). One signal per direction per day.
    """
    name = "orb"
    mode = "intraday"
    defaults = dict(
        or_minutes=15, min_or_pct=0.3, max_or_pct=2.0, vol_mult=1.2,
        stop_atr=1.5, target_r=2.0, breakeven_r=1.0, atr_n=14,
        session_open="09:15",
    )

    @property
    def warmup(self) -> int:
        return self.p["atr_n"] + 5

    def prepare(self, df):
        df = df.copy()
        h, m = map(int, self.p["session_open"].split(":"))
        mins = (df.index.hour * 60 + df.index.minute) - (h * 60 + m)
        in_or = (mins >= 0) & (mins < self.p["or_minutes"])
        day = pd.Series(df.index.date, index=df.index)
        or_hi = df["high"].where(in_or).groupby(day).transform("max")
        or_lo = df["low"].where(in_or).groupby(day).transform("min")
        after = mins >= self.p["or_minutes"]
        df["or_high"] = or_hi.where(after)
        df["or_low"] = or_lo.where(after)
        df["vwap"] = ind.session_vwap(df)
        df["atr"] = ind.atr(df, self.p["atr_n"])
        df["vol_avg"] = ind.sma(df["volume"], 20).shift(1)
        up = (df["close"] > df["or_high"]).astype(int)
        dn = (df["close"] < df["or_low"]).astype(int)
        # Was there already a close beyond the range earlier today?
        df["up_before"] = up.groupby(day).transform(lambda s: s.shift(1).cummax()).fillna(0)
        df["dn_before"] = dn.groupby(day).transform(lambda s: s.shift(1).cummax()).fillna(0)
        return df

    def signal(self, symbol, df, i, allow_short):
        r = df.iloc[i]
        if not _ok(r.or_high, r.or_low, r.atr, r.vwap, r.vol_avg):
            return None
        mid = (r.or_high + r.or_low) / 2
        width_pct = 100 * (r.or_high - r.or_low) / mid
        if not self.p["min_or_pct"] <= width_pct <= self.p["max_or_pct"]:
            return None
        if r.volume < self.p["vol_mult"] * r.vol_avg:
            return None
        if r.close > r.or_high and not r.up_before and r.close > r.vwap:
            stop = max(mid, r.close - self.p["stop_atr"] * r.atr)
            return Signal(symbol, 1, r.close, stop, r.close + self.p["target_r"] * (r.close - stop),
                          reason="ORB long")
        if allow_short and r.close < r.or_low and not r.dn_before and r.close < r.vwap:
            stop = min(mid, r.close + self.p["stop_atr"] * r.atr)
            return Signal(symbol, -1, r.close, stop, r.close - self.p["target_r"] * (stop - r.close),
                          reason="ORB short")
        return None


class VwapPullback(Strategy):
    """Trend day continuation: trend up on 5m (EMA9>EMA21, above VWAP, ADX>20),
    price pulls back to VWAP/EMA21, then a bar closes back above EMA9."""
    name = "vwap_pullback"
    mode = "intraday"
    defaults = dict(adx_min=20.0, touch_pct=0.15, lookback=3, target_r=2.0,
                    breakeven_r=1.0, skip_first_bars=3, atr_n=14)

    @property
    def warmup(self) -> int:
        return 40

    def prepare(self, df):
        df = df.copy()
        df["ema9"] = ind.ema(df["close"], 9)
        df["ema21"] = ind.ema(df["close"], 21)
        df["vwap"] = ind.session_vwap(df)
        df["adx"] = ind.adx(df, 14)
        df["atr"] = ind.atr(df, self.p["atr_n"])
        day = pd.Series(df.index.date, index=df.index)
        df["bar_of_day"] = day.groupby(day).cumcount()
        lb = self.p["lookback"]
        tol = self.p["touch_pct"] / 100
        support = np.maximum(df["vwap"], df["ema21"])
        resist = np.minimum(df["vwap"], df["ema21"])
        df["touched_dn"] = (df["low"] <= support * (1 + tol)).rolling(lb).max()
        df["touched_up"] = (df["high"] >= resist * (1 - tol)).rolling(lb).max()
        df["swing_lo"] = df["low"].rolling(lb).min()
        df["swing_hi"] = df["high"].rolling(lb).max()
        return df

    def signal(self, symbol, df, i, allow_short):
        r = df.iloc[i]
        if r.bar_of_day < self.p["skip_first_bars"] or not _ok(r.ema9, r.ema21, r.vwap, r.adx, r.atr):
            return None
        if r.adx < self.p["adx_min"]:
            return None
        if (r.ema9 > r.ema21 and r.close > r.vwap and r.touched_dn and r.close > r.ema9
                and r.close > r.open):
            stop = r.swing_lo - 0.1 * r.atr
            return Signal(symbol, 1, r.close, stop, r.close + self.p["target_r"] * (r.close - stop),
                          reason="VWAP pullback long")
        if (allow_short and r.ema9 < r.ema21 and r.close < r.vwap and r.touched_up
                and r.close < r.ema9 and r.close < r.open):
            stop = r.swing_hi + 0.1 * r.atr
            return Signal(symbol, -1, r.close, stop, r.close - self.p["target_r"] * (stop - r.close),
                          reason="VWAP pullback short")
        return None


# --------------------------------------------------------------------------- swing

class TrendPullback(Strategy):
    """Buy a dip inside an established uptrend, exit on a chandelier trail.

    Trend: close > SMA200, EMA20 > EMA50, ADX > adx_min.
    Dip:   short-period RSI (default 5) went below rsi_dip in the last 5 bars.
    Trigger: close above the previous bar's high (buyers back in control).
    """
    name = "trend_pullback"
    mode = "swing"
    defaults = dict(adx_min=18.0, rsi_n=5, rsi_dip=35.0, stop_atr=2.5, trail_atr=3.0,
                    breakeven_r=1.0, max_bars=40, target_r=None)

    @property
    def warmup(self) -> int:
        return 210

    def prepare(self, df):
        df = df.copy()
        c = df["close"]
        df["sma200"] = ind.sma(c, 200)
        df["ema20"] = ind.ema(c, 20)
        df["ema50"] = ind.ema(c, 50)
        df["adx"] = ind.adx(df, 14)
        df["rsi"] = ind.rsi(c, self.p["rsi_n"])
        df["rsi_min5"] = df["rsi"].rolling(5).min()
        df["rsi_max5"] = df["rsi"].rolling(5).max()
        df["atr"] = ind.atr(df, 14)
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)
        df["low5"] = df["low"].rolling(5).min()
        df["high5"] = df["high"].rolling(5).max()
        return df

    def signal(self, symbol, df, i, allow_short):
        r = df.iloc[i]
        if not _ok(r.sma200, r.ema50, r.adx, r.rsi_min5, r.atr):
            return None
        if r.adx < self.p["adx_min"]:
            return None
        tr = self.p["target_r"]
        if (r.close > r.sma200 and r.ema20 > r.ema50 and r.rsi_min5 < self.p["rsi_dip"]
                and r.close > r.prev_high and r.close > r.ema50):
            stop = max(r.low5 - 0.2 * r.atr, r.close - self.p["stop_atr"] * r.atr)
            stop = min(stop, r.close - r.atr)  # never tighter than 1 ATR
            tgt = r.close + tr * (r.close - stop) if tr else None
            return Signal(symbol, 1, r.close, stop, tgt, self.p["max_bars"], "trend pullback long")
        if (allow_short and r.close < r.sma200 and r.ema20 < r.ema50
                and r.rsi_max5 > 100 - self.p["rsi_dip"] and r.close < r.prev_low and r.close < r.ema50):
            stop = min(r.high5 + 0.2 * r.atr, r.close + self.p["stop_atr"] * r.atr)
            stop = max(stop, r.close + r.atr)
            tgt = r.close - tr * (stop - r.close) if tr else None
            return Signal(symbol, -1, r.close, stop, tgt, self.p["max_bars"], "trend pullback short")
        return None

    def update_stop(self, pos, df, i):
        stop = super().update_stop(pos, df, i)
        a = df["atr"].iat[i]
        if _ok(a):
            stop = _tighter(pos.side, stop, pos.best_price - pos.side * self.p["trail_atr"] * a)
        return stop


class DonchianBreakout(Strategy):
    """Turtle-style: new 55-bar closing high, above SMA200, on 1.5x volume.
    Exit on a 20-bar low or a 3 ATR chandelier, whichever is tighter."""
    name = "donchian"
    mode = "swing"
    defaults = dict(entry_n=55, exit_n=20, vol_mult=1.5, stop_atr=2.0,
                    trail_atr=3.0, breakeven_r=1.5, max_bars=60)

    @property
    def warmup(self) -> int:
        return 210

    def prepare(self, df):
        df = df.copy()
        df["sma200"] = ind.sma(df["close"], 200)
        df["hi_n"] = ind.rolling_high(df["close"], self.p["entry_n"])
        df["lo_n"] = ind.rolling_low(df["close"], self.p["entry_n"])
        df["exit_lo"] = df["low"].rolling(self.p["exit_n"]).min()
        df["exit_hi"] = df["high"].rolling(self.p["exit_n"]).max()
        df["vol_avg"] = ind.sma(df["volume"], 50).shift(1)
        df["atr"] = ind.atr(df, 20)
        return df

    def signal(self, symbol, df, i, allow_short):
        r = df.iloc[i]
        if not _ok(r.sma200, r.hi_n, r.atr, r.vol_avg) or r.volume < self.p["vol_mult"] * r.vol_avg:
            return None
        if r.close > r.hi_n and r.close > r.sma200:
            return Signal(symbol, 1, r.close, r.close - self.p["stop_atr"] * r.atr, None,
                          self.p["max_bars"], "55-bar breakout long")
        if allow_short and r.close < r.lo_n and r.close < r.sma200:
            return Signal(symbol, -1, r.close, r.close + self.p["stop_atr"] * r.atr, None,
                          self.p["max_bars"], "55-bar breakdown short")
        return None

    def update_stop(self, pos, df, i):
        stop = super().update_stop(pos, df, i)
        r = df.iloc[i]
        chand = pos.best_price - pos.side * self.p["trail_atr"] * r.atr
        channel = r.exit_lo if pos.side > 0 else r.exit_hi
        for s in (chand, channel):
            stop = _tighter(pos.side, stop, s)
        return stop


STRATEGIES = {s.name: s for s in (OpeningRangeBreakout, VwapPullback, TrendPullback, DonchianBreakout)}


def make_strategy(name: str, params: dict | None = None, session_open: str | None = None) -> Strategy:
    if name not in STRATEGIES:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(STRATEGIES)}")
    cls = STRATEGIES[name]
    params = dict(params or {})
    if session_open and "session_open" in cls.defaults:
        params.setdefault("session_open", session_open)
    return cls(**params)
