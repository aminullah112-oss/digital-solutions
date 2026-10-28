"""Performance and risk statistics, plus a Monte Carlo drawdown estimate."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import BacktestResult


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(100 * (1 - equity / equity.cummax()).max())


def summarize(res: BacktestResult) -> dict:
    eq = res.equity
    trades = res.trades
    out: dict = {}
    if eq.empty:
        return {"trades": 0}
    start, end = float(eq.iloc[0]), float(eq.iloc[-1])
    init = res.config.initial_capital if res.config else start
    daily = eq.groupby(eq.index.date).last()
    rets = daily.pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1 / 365.25)
    out["start"] = str(eq.index[0].date())
    out["end"] = str(eq.index[-1].date())
    out["final_equity"] = round(end, 2)
    out["total_return_pct"] = round(100 * (end / init - 1), 2)
    out["cagr_pct"] = round(100 * ((end / init) ** (1 / years) - 1), 2) if end > 0 else -100.0
    out["max_drawdown_pct"] = round(max_drawdown(eq), 2)
    sd = rets.std()
    out["sharpe"] = round(float(rets.mean() / sd * np.sqrt(252)), 2) if sd > 0 else 0.0
    down = rets[rets < 0].std()
    out["sortino"] = round(float(rets.mean() / down * np.sqrt(252)), 2) if down and down > 0 else 0.0
    out["calmar"] = round(out["cagr_pct"] / out["max_drawdown_pct"], 2) if out["max_drawdown_pct"] else 0.0

    out["trades"] = len(trades)
    if trades:
        pnl = np.array([t.pnl for t in trades])
        r = np.array([t.r_multiple for t in trades])
        wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
        out["win_rate_pct"] = round(100 * len(wins) / len(pnl), 1)
        out["avg_win"] = round(float(wins.mean()), 2) if len(wins) else 0.0
        out["avg_loss"] = round(float(losses.mean()), 2) if len(losses) else 0.0
        out["profit_factor"] = round(float(wins.sum() / -losses.sum()), 2) if losses.sum() < 0 else float("inf")
        out["expectancy_r"] = round(float(r.mean()), 3)
        out["worst_trade_r"] = round(float(r.min()), 2)
        out["best_trade_r"] = round(float(r.max()), 2)
        out["avg_bars_held"] = round(float(np.mean([t.bars_held for t in trades])), 1)
        streak = worst = 0
        for x in pnl:
            streak = streak + 1 if x <= 0 else 0
            worst = max(worst, streak)
        out["longest_losing_streak"] = worst
        reasons = pd.Series([t.exit_reason.split(":")[0] for t in trades]).value_counts()
        out["exit_reasons"] = reasons.to_dict()
        out["total_costs_note"] = "pnl is net of costs and slippage"
    out["risk_halts"] = len(res.halts)
    return out


def monte_carlo_drawdown(res: BacktestResult, runs: int = 2000, seed: int = 7) -> dict:
    """Reshuffle trade order to see how bad drawdown could plausibly get with the
    same trades. The backtest's own drawdown is one lucky/unlucky ordering."""
    if len(res.trades) < 10:
        return {"note": "fewer than 10 trades; not meaningful"}
    init = res.config.initial_capital
    # Trade P&L as a fraction of equity at entry is unknown per-trade here, so use
    # P&L relative to starting capital; a fair approximation at fixed-fractional risk.
    f = np.array([t.pnl for t in res.trades]) / init
    rng = np.random.default_rng(seed)
    dds = np.empty(runs)
    for k in range(runs):
        path = np.cumprod(1 + rng.permutation(f))
        peak = np.maximum.accumulate(np.concatenate([[1.0], path]))[1:]
        dds[k] = 100 * (1 - path / peak).max()
    return {
        "median_max_dd_pct": round(float(np.median(dds)), 2),
        "p95_max_dd_pct": round(float(np.percentile(dds, 95)), 2),
        "p99_max_dd_pct": round(float(np.percentile(dds, 99)), 2),
    }


def trades_frame(res: BacktestResult) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in res.trades])


def format_report(stats: dict, mc: dict | None = None, rejections=None) -> str:
    lines = ["=" * 56, "BACKTEST REPORT", "=" * 56]
    for k, v in stats.items():
        if k == "exit_reasons":
            lines.append(f"{'exit_reasons':<24} " + ", ".join(f"{a}={b}" for a, b in v.items()))
        else:
            lines.append(f"{k:<24} {v}")
    if mc:
        lines += ["-" * 56, "MONTE CARLO (trade order reshuffled)"]
        lines += [f"{k:<24} {v}" for k, v in mc.items()]
    if rejections:
        lines += ["-" * 56, "SIGNALS REJECTED BY RISK / FILL RULES"]
        lines += [f"{n:>6}  {why}" for why, n in rejections.most_common(10)]
    lines.append("=" * 56)
    return "\n".join(lines)


def verdict(stats: dict, mc: dict | None) -> list[str]:
    """Plain-language red flags. Passing these is necessary, not sufficient."""
    flags = []
    n = stats.get("trades", 0)
    if n < 100:
        flags.append(f"Only {n} trades: too few to tell skill from luck (aim for 100+).")
    if stats.get("expectancy_r", 0) <= 0.05:
        flags.append("Expectancy <= 0.05R after costs: no demonstrable edge.")
    if stats.get("profit_factor", 0) < 1.2:
        flags.append("Profit factor < 1.2: thin edge, likely to vanish live.")
    if stats.get("sharpe", 0) > 3:
        flags.append("Sharpe > 3: suspiciously good; check for overfitting or data errors.")
    if mc and mc.get("p95_max_dd_pct", 0) > 25:
        flags.append(f"95th-pct Monte Carlo drawdown {mc['p95_max_dd_pct']}%: reduce risk_per_trade_pct.")
    return flags
