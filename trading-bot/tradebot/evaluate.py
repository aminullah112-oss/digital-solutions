"""Strategy evaluation report.

A profitable backtest is not enough. This report asks whether the edge
survives: fresh data, several periods, doubled costs, different market regimes,
and a passive benchmark. It also states plainly when there isn't enough evidence.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from . import indicators as ind
from .backtest import Backtester, BacktestResult
from .config import Config
from .metrics import max_drawdown, monte_carlo_drawdown, summarize, verdict


def _window(data: dict[str, pd.DataFrame], start, end) -> pd.DatetimeIndex:
    idx = sorted(set().union(*(df.index for df in data.values())))
    return pd.DatetimeIndex([t for t in idx if (start is None or t >= start) and (end is None or t < end)])


def equal_weight_index(data: dict[str, pd.DataFrame]) -> pd.Series:
    """Daily equal-weight index of the universe (buy-and-hold proxy)."""
    closes = pd.DataFrame({s: df["close"].groupby(df.index.date).last() for s, df in data.items()})
    closes.index = pd.to_datetime(closes.index)
    rets = closes.pct_change().mean(axis=1).fillna(0)
    return (1 + rets).cumprod()


def benchmark_stats(bench: pd.Series, start, end) -> dict:
    """Buy-and-hold of the benchmark over the same window."""
    b = bench
    if start is not None:
        b = b[b.index >= pd.Timestamp(start.date())]
    if end is not None:
        b = b[b.index < pd.Timestamp(end.date())]
    if len(b) < 2:
        return {}
    years = max((b.index[-1] - b.index[0]).days / 365.25, 1 / 365.25)
    tot = b.iloc[-1] / b.iloc[0]
    return {"total_return_pct": round(100 * (tot - 1), 2),
            "cagr_pct": round(100 * (tot ** (1 / years) - 1), 2),
            "max_drawdown_pct": round(max_drawdown(b), 2)}


def _group_stats(trades, key) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame({"key": [key(t) for t in trades], "pnl": [t.pnl for t in trades],
                       "r": [t.r_multiple for t in trades]})
    g = df.groupby("key")
    out = pd.DataFrame({
        "trades": g.size(),
        "net_pnl": g["pnl"].sum().round(0),
        "win_pct": (g["pnl"].apply(lambda x: (x > 0).mean()) * 100).round(1),
        "expectancy_r": g["r"].mean().round(3),
        "profit_factor": g["pnl"].apply(
            lambda x: round(x[x > 0].sum() / -x[x <= 0].sum(), 2) if (x <= 0).any() and x[x <= 0].sum() < 0 else np.inf),
    })
    return out


def by_year(res: BacktestResult) -> pd.DataFrame:
    out = _group_stats(res.trades, lambda t: t.exit_time.year).rename_axis("year")
    if out.empty:
        return out
    yearly = res.equity.groupby(res.equity.index.year)
    last = yearly.last()
    base = last.shift(1).fillna(yearly.first())   # prior year-end, or the first value
    out["return_pct"] = (100 * (last / base - 1)).round(2).reindex(out.index)
    out["max_dd_pct"] = yearly.apply(max_drawdown).round(2).reindex(out.index)
    return out


def by_symbol(res: BacktestResult) -> pd.DataFrame:
    return _group_stats(res.trades, lambda t: t.symbol).rename_axis("symbol")


def regime_series(bench: pd.Series) -> pd.Series:
    """'bull' when the benchmark is above its 200-day average, else 'bear'.
    Shifted one day so the regime at a trade's entry uses only prior closes."""
    sma = ind.sma(bench, 200)
    reg = pd.Series(np.where(bench > sma, "bull", "bear"), index=bench.index).where(sma.notna(), "n/a")
    return reg.shift(1).fillna("n/a")


def by_regime(res: BacktestResult, bench: pd.Series) -> pd.DataFrame:
    reg = regime_series(bench)

    def key(t):
        d = pd.Timestamp(t.entry_time.date())
        i = reg.index.searchsorted(d, side="right") - 1
        return reg.iloc[i] if i >= 0 else "n/a"
    return _group_stats(res.trades, key).rename_axis("regime")


def _with_cost_mult(cfg: Config, m: float) -> Config:
    c = copy.deepcopy(cfg)
    c.costs.cost_pct *= m
    c.costs.slippage_pct *= m
    return c


def evaluate(cfg: Config, strategy, data: dict[str, pd.DataFrame], split: float | None = 0.7,
             folds: int = 4, benchmark: pd.Series | None = None) -> dict:
    """Run the full battery. Returns a dict of tables/stats plus red flags."""
    idx = _window(data, None, None)
    if len(idx) < 2:
        raise ValueError("not enough data")
    first, last = idx[0], idx[-1]
    bench = benchmark if benchmark is not None else equal_weight_index(data)
    bt = Backtester(cfg, strategy)

    def cut(frac):
        return first + (last - first) * frac

    periods = {"full": (None, None)}
    if split:
        periods["in_sample"] = (None, cut(split))
        periods["out_of_sample"] = (cut(split), None)

    report: dict = {"periods": {}, "flags": []}
    results = {}
    for name, (a, b) in periods.items():
        res = bt.run(data, a, b)
        results[name] = res
        st = summarize(res)
        report["periods"][name] = {
            "stats": st,
            "monte_carlo": monte_carlo_drawdown(res),
            "benchmark": benchmark_stats(bench, res.equity.index[0] if len(res.equity) else a,
                                         res.equity.index[-1] if len(res.equity) else b),
            "rejections": dict(res.rejections.most_common(8)),
        }

    full = results["full"]
    report["by_year"] = by_year(full)
    report["by_symbol"] = by_symbol(full)
    report["by_regime"] = by_regime(full, bench)

    # Same parameters across consecutive periods: does the edge show up in most of them?
    fold_rows = []
    if folds and folds > 1:
        edges = [first + (last - first) * k / folds for k in range(folds + 1)]
        for k in range(folds):
            res = bt.run(data, edges[k], edges[k + 1] if k < folds - 1 else None)
            st = summarize(res)
            fold_rows.append({"fold": k + 1, "start": str(edges[k].date()), "trades": st.get("trades", 0),
                              "return_pct": st.get("total_return_pct"), "max_dd_pct": st.get("max_drawdown_pct"),
                              "expectancy_r": st.get("expectancy_r"), "profit_factor": st.get("profit_factor")})
    report["folds"] = pd.DataFrame(fold_rows).set_index("fold") if fold_rows else pd.DataFrame()

    # Cost sensitivity on the evaluation period (out-of-sample if we have one).
    eval_name = "out_of_sample" if split else "full"
    a, b = periods[eval_name]
    sens = []
    for m in (0.0, 1.0, 1.5, 2.0):
        st = summarize(Backtester(_with_cost_mult(cfg, m), strategy).run(data, a, b))
        sens.append({"cost_x": m, "trades": st.get("trades", 0), "return_pct": st.get("total_return_pct"),
                     "expectancy_r": st.get("expectancy_r"), "profit_factor": st.get("profit_factor")})
    report["cost_sensitivity"] = pd.DataFrame(sens).set_index("cost_x")

    # ---- red flags, judged on the evaluation period
    ev = report["periods"][eval_name]
    flags = verdict(ev["stats"], ev["monte_carlo"])
    if split:
        flags = [f"[out-of-sample] {f}" for f in flags]
        ins = report["periods"]["in_sample"]["stats"].get("expectancy_r", 0) or 0
        oos = ev["stats"].get("expectancy_r", 0) or 0
        if ins > 0 and oos < 0.5 * ins:
            flags.append(f"Out-of-sample expectancy {oos}R is under half of in-sample {ins}R: likely overfit or regime-dependent.")
    if not report["folds"].empty:
        e = report["folds"]["expectancy_r"].dropna()
        pos = (e > 0).mean() if len(e) else 0
        if pos < 0.6:
            flags.append(f"Edge positive in only {int(pos * len(e))}/{len(e)} periods: inconsistent.")
    cs = report["cost_sensitivity"]
    if 2.0 in cs.index and (cs.loc[2.0, "expectancy_r"] or 0) <= 0:
        flags.append("Edge disappears at 2x costs/slippage: too fragile for live execution.")
    bm = ev["benchmark"]
    st = ev["stats"]
    if bm and st.get("total_return_pct") is not None and st["total_return_pct"] < bm["total_return_pct"] \
            and st.get("max_drawdown_pct", 0) > 0.5 * bm["max_drawdown_pct"]:
        flags.append("Buy-and-hold of the same universe returned more without a much larger drawdown.")
    if not report["by_symbol"].empty:
        pnl = report["by_symbol"]["net_pnl"]
        total = pnl.sum()
        if total > 0 and pnl.max() > 0.6 * total:
            flags.append(f"One symbol ({pnl.idxmax()}) produced >60% of net profit: concentration, not a broad edge.")
    report["flags"] = flags
    report["caveats"] = [
        "Universe is today's symbol list: survivorship bias flatters results (delisted/demoted stocks are missing).",
        "Fills assume you get the open/stop price +/- slippage; circuit locks and partial fills are not simulated.",
        "Parameters were not optimised here. If you tuned them on this data, the in-sample numbers are not evidence.",
    ]
    return report


def _md_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_none_\n"
    cols = [df.index.name or ""] + list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for k in df.index:
        lines.append("| " + " | ".join(map(str, [k, *(df.at[k, c] for c in df.columns)])) + " |")
    return "\n".join(lines) + "\n"


def to_markdown(report: dict, title: str) -> str:
    out = [f"# {title}\n"]
    flags = report["flags"]
    out.append("## Verdict\n")
    if flags:
        out.append("**NOT APPROVED.** Red flags:\n")
        out += [f"- {f}" for f in flags]
    else:
        out.append("No red flags. That is necessary, not sufficient: paper trade before funding it.")
    out.append("")
    for name, p in report["periods"].items():
        out.append(f"## {name.replace('_', ' ').title()}\n")
        rows = {k: v for k, v in p["stats"].items() if k not in ("exit_reasons", "total_costs_note")}
        df = pd.DataFrame({"strategy": pd.Series(rows, dtype=object)})
        for k, v in (p["benchmark"] or {}).items():
            df.loc[k, "buy_and_hold"] = v
        df.index.name = "metric"
        out.append(_md_table(df.fillna("")))
        if p["monte_carlo"]:
            out.append("Monte Carlo drawdown: " + ", ".join(f"{k}={v}" for k, v in p["monte_carlo"].items()) + "\n")
        if p["stats"].get("exit_reasons"):
            out.append("Exits: " + ", ".join(f"{k}={v}" for k, v in p["stats"]["exit_reasons"].items()) + "\n")
        if p["rejections"]:
            out.append("Top rejections: " + "; ".join(f"{k} ({v})" for k, v in p["rejections"].items()) + "\n")
    for key, title_ in (("folds", "Consistency across periods (same parameters)"),
                        ("cost_sensitivity", "Cost / slippage sensitivity"),
                        ("by_year", "By year"), ("by_regime", "By market regime (benchmark vs 200-day SMA)"),
                        ("by_symbol", "By symbol")):
        out.append(f"## {title_}\n")
        out.append(_md_table(report[key]))
    out.append("## Caveats\n")
    out += [f"- {c}" for c in report["caveats"]]
    return "\n".join(out) + "\n"
