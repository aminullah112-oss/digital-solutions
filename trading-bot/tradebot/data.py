"""Market data loading: CSV, optional yfinance download, and a synthetic generator
for smoke tests. Every frame is OHLCV with a tz-aware DatetimeIndex."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

COLS = ["open", "high", "low", "close", "volume"]


def normalize(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    for c in ("datetime", "date", "timestamp", "time"):
        if c in df.columns:
            df = df.set_index(c)
            break
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize(tz) if df.index.tz is None else df.index.tz_convert(tz)
    missing = set(COLS) - set(df.columns)
    if missing:
        raise ValueError(f"missing columns {sorted(missing)}")
    df = df[COLS].astype(float).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    bad = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))
    if bad.any():
        raise ValueError(f"{int(bad.sum())} bars have high/low inconsistent with open/close")
    return df.dropna()


def audit(df: pd.DataFrame, mode: str) -> list[str]:
    """Data problems that silently corrupt a backtest."""
    w = []
    if len(df) < 2:
        return ["fewer than 2 bars"]
    c = df["close"]
    day_close = c.groupby(df.index.date).last()
    day_open = df["open"].groupby(df.index.date).first()
    gap = (day_open.shift(-1) / day_close - 1).dropna()
    big = gap[gap.abs() > 0.25]
    if len(big):
        w.append(f"{len(big)} overnight moves > 25% (first {big.index[0]}): unadjusted split/bonus?")
    gaps = pd.to_datetime(pd.Series(sorted(set(df.index.date)))).diff().dt.days.dropna()
    long_gaps = gaps[gaps > 6]
    if len(long_gaps):
        w.append(f"{len(long_gaps)} gaps of more than 6 calendar days between bars (missing data?)")
    if (df["volume"] <= 0).mean() > 0.02:
        w.append(f"{100 * (df['volume'] <= 0).mean():.1f}% of bars have zero volume")
    if mode == "intraday":
        per_day = df.groupby(df.index.date).size()
        short = per_day[per_day < 0.8 * per_day.median()]
        if len(short):
            w.append(f"{len(short)} sessions with <80% of the usual bar count")
    return w


def load_csv(path: str | Path, tz: str) -> pd.DataFrame:
    return normalize(pd.read_csv(path), tz)


def load_dir(directory: str | Path, symbols: list[str], tz: str) -> dict[str, pd.DataFrame]:
    """Expects <directory>/<SYMBOL>.csv for each symbol."""
    d = Path(directory)
    out = {}
    for s in symbols:
        f = d / f"{s}.csv"
        if not f.exists():
            raise FileNotFoundError(f"no data file {f}")
        out[s] = load_csv(f, tz)
    return out


def download_yfinance(symbol: str, interval: str, period: str, tz: str) -> pd.DataFrame:
    """yfinance is optional. NSE symbols need a .NS suffix (RELIANCE.NS).
    Intraday history is limited (5m: last 60 days)."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise SystemExit("pip install yfinance to download data") from e
    yf_interval = {"5minute": "5m", "15minute": "15m", "day": "1d", "minute": "1m"}.get(interval, interval)
    df = yf.download(symbol, interval=yf_interval, period=period, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"no data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return normalize(df, tz)


def synthetic(days: int = 500, intraday: bool = False, seed: int = 0, start_price: float = 500.0,
              tz: str = "Asia/Kolkata", bars_per_day: int = 75) -> pd.DataFrame:
    """Random walk with regime-switching drift and volatility clustering. For
    plumbing tests only; profits or losses on this data mean nothing."""
    rng = np.random.default_rng(seed)
    n = days * (bars_per_day if intraday else 1)
    regime = np.repeat(rng.choice([-1, 0, 1], size=n // 40 + 1, p=[0.3, 0.3, 0.4]), 40)[:n]
    base_vol = 0.0025 if intraday else 0.015
    vol = base_vol * np.exp(np.cumsum(rng.normal(0, 0.05, n)) * 0.1).clip(0.5, 2)
    rets = regime * base_vol * 0.08 + vol * rng.standard_t(4, n) / np.sqrt(2)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start_price], close[:-1]]) * (1 + rng.normal(0, base_vol / 4, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, vol / 2)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, vol / 2)))
    volume = rng.lognormal(12, 0.5, n) * (1 + 3 * np.abs(rets) / base_vol)
    if intraday:
        days_idx = pd.bdate_range("2024-01-01", periods=days)
        idx = [d + pd.Timedelta(hours=9, minutes=15 + 5 * k) for d in days_idx for k in range(bars_per_day)]
        idx = pd.DatetimeIndex(idx).tz_localize(tz)
    else:
        idx = pd.bdate_range("2020-01-01", periods=n).tz_localize(tz)
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": volume}, index=idx)
