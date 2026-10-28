"""Command line.

  python -m tradebot backtest -c config/swing.json --data data/
  python -m tradebot backtest -c config/intraday.json --synthetic
  python -m tradebot compare  -c config/swing.json -c config/swing_40d.json --data data/
  python -m tradebot paper    -c config/intraday.json --feed yfinance
  python -m tradebot live     -c config/intraday.json        (Zerodha Kite)
  python -m tradebot reset    -c config/intraday.json        (clear a risk halt)
  python -m tradebot login                                   (daily Kite session)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .backtest import Backtester
from .config import Config
import pandas as pd

from .data import audit, download_yfinance, load_csv, load_dir, synthetic
from .evaluate import evaluate, to_markdown
from .metrics import trades_frame
from .strategies import make_strategy


def _setup_logging(cfg: Config):
    Path(cfg.state_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(Path(cfg.state_file).with_name("bot.log"))],
    )


def _load_data(cfg: Config, a):
    tz = cfg.session.timezone
    if a.synthetic:
        intr = cfg.mode == "intraday"
        print("NOTE: synthetic data tests the plumbing only. Results say nothing about real markets.\n")
        return {s: synthetic(days=a.days or (120 if intr else 1000), intraday=intr, seed=k, tz=tz)
                for k, s in enumerate(cfg.symbols)}
    if a.download:
        period = f"{a.days or (59 if cfg.mode == 'intraday' else 3650)}d"
        data = {s: download_yfinance(s + a.suffix, cfg.interval, period, tz) for s in cfg.symbols}
        if a.save_data:
            # Freeze the download so every later run (and every reviewer) uses identical bars.
            d = Path(a.save_data)
            d.mkdir(parents=True, exist_ok=True)
            for s, df in data.items():
                df.to_csv(d / f"{s}.csv", index_label="datetime")
            print(f"saved {len(data)} files to {d}; rerun with --data {d}")
    else:
        data = load_dir(a.data, cfg.symbols, tz)
    for s, df in data.items():
        for w in audit(df, cfg.mode):
            print(f"DATA WARNING {s}: {w}")
    return data


def cmd_backtest(cfg: Config, a):
    data = _load_data(cfg, a)
    strat = make_strategy(cfg.strategy, cfg.strategy_params, cfg.session.open)
    bench = None
    if a.benchmark:
        b = load_csv(a.benchmark, cfg.session.timezone)["close"]
        bench = b.groupby(b.index.date).last()
        bench.index = pd.to_datetime(bench.index)
    rep = evaluate(cfg, strat, data, a.split, a.folds, bench)
    md = to_markdown(rep, f"{cfg.strategy} ({cfg.mode}) on {len(data)} symbols")
    print(md)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text(md)
        res = Backtester(cfg, strat).run(data)
        trades_frame(res).to_csv(out / "trades.csv", index=False)
        res.equity.to_csv(out / "equity.csv", header=["equity"])
        print(f"wrote {out}/report.md, trades.csv, equity.csv")


COMPARE_ROWS = ["trades", "total_return_pct", "cagr_pct", "max_drawdown_pct", "longest_underwater_days",
                "win_rate_pct", "profit_factor", "expectancy_r", "expectancy_r_ci95", "avg_bars_held",
                "exposure_pct", "annual_turnover_x"]


def cmd_compare(cfgs: list[Config], names: list[str], a):
    """Evaluate several configs on the same data and the same windows."""
    keys = {(c.mode, c.interval, tuple(c.symbols), c.session.timezone) for c in cfgs}
    if len(keys) > 1:
        sys.exit("compare needs configs with the same mode, interval, symbols and timezone")
    data = _load_data(cfgs[0], a)
    reps = {}
    for name, c in zip(names, cfgs):
        strat = make_strategy(c.strategy, c.strategy_params, c.session.open)
        reps[name] = evaluate(c, strat, data, a.split, a.folds)
    period = "out_of_sample" if a.split else "full"
    table = pd.DataFrame({n: {k: r["periods"][period]["stats"].get(k) for k in COMPARE_ROWS} for n, r in reps.items()})
    table.loc["benchmark_return_pct"] = [r["periods"][period]["benchmark"].get("total_return_pct") for r in reps.values()]
    for m in (1.0, 2.0):
        table.loc[f"expectancy_r_at_{m:g}x_costs"] = [r["cost_sensitivity"].loc[m, "expectancy_r"] for r in reps.values()]
    table.loc["periods_positive"] = [
        f"{int((r['folds']['expectancy_r'] > 0).sum())}/{len(r['folds'])}" if not r["folds"].empty else "-"
        for r in reps.values()]
    table.loc["red_flags"] = [len(r["flags"]) for r in reps.values()]
    table.index.name = "metric"
    lines = [f"# Comparison ({period.replace('_', '-')}, identical data and windows)\n", _md(table), ""]
    for n, r in reps.items():
        lines.append(f"## {n}: {'NOT APPROVED' if r['flags'] else 'no red flags'}\n")
        lines += [f"- {f}" for f in r["flags"]] or ["- none"]
        lines.append("")
    lines.append("Pick between these on the in-sample period or on reasoning, not on this table: "
                 "choosing the winner here turns the out-of-sample period into another in-sample one.")
    md = "\n".join(lines) + "\n"
    print(md)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "compare.md").write_text(md)
        for n, r in reps.items():
            (out / f"report_{n}.md").write_text(to_markdown(r, n))
        print(f"wrote {out}/compare.md and one full report per config")


def _md(df: pd.DataFrame) -> str:
    cols = [df.index.name or ""] + list(df.columns)
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    rows += ["| " + " | ".join(map(str, [k, *(df.at[k, c] for c in df.columns)])) + " |" for k in df.index]
    return "\n".join(rows)


def _engine(cfg: Config, broker):
    from .live import LiveEngine
    return LiveEngine(cfg, make_strategy(cfg.strategy, cfg.strategy_params, cfg.session.open), broker)


def _run(cfg: Config, broker, a, label: str):
    from .alerts import install
    alerts, hb = install(f"tradebot {label} {cfg.mode}/{cfg.strategy}")
    _engine(cfg, broker).run(a.poll, heartbeat=hb, alerts=alerts)


def cmd_paper(cfg: Config, a):
    from .broker import PaperBroker, YFinanceFeed
    _setup_logging(cfg)
    if a.feed == "kite":
        from .kite import KiteBroker
        feed = KiteBroker(cfg.session.timezone, "MIS" if cfg.mode == "intraday" else "CNC")
    else:
        feed = YFinanceFeed(cfg.session.timezone, a.suffix)
    state_file = Path(cfg.state_file)
    saved = json.loads(state_file.read_text()).get("broker") if state_file.exists() else None
    from .broker import parse_faults
    faults = parse_faults(a.faults)
    broker = PaperBroker(feed, cfg.costs.slippage_pct, saved, faults=faults, seed=a.fault_seed)
    if faults:
        logging.getLogger("tradebot").warning("paper fault injection ON: %s", faults)
    _run(cfg, broker, a, "PAPER")


def cmd_live(cfg: Config, a):
    from .kite import KiteBroker
    if os.environ.get("TRADEBOT_LIVE") != "I_ACCEPT_THE_RISK":
        sys.exit("Live trading is locked. Paper trade first, then set TRADEBOT_LIVE=I_ACCEPT_THE_RISK.")
    if cfg.mode == "swing" and cfg.allow_short:
        sys.exit("Cash equities can't be held short overnight in India; set allow_short=false for swing.")
    _setup_logging(cfg)
    product = "MIS" if cfg.mode == "intraday" else "CNC"
    broker = KiteBroker(cfg.session.timezone, product, stop_order_type=a.stop_type)
    logging.getLogger("tradebot").warning(
        "LIVE: capital %.0f, risk/trade %.2f%%, daily stop %.1f%%, max DD %.1f%%, symbols %s",
        cfg.initial_capital, cfg.risk.risk_per_trade_pct, cfg.risk.daily_loss_limit_pct,
        cfg.risk.max_drawdown_pct, cfg.symbols)
    _run(cfg, broker, a, "LIVE")


def cmd_login(a):
    """Daily Kite login. You log in on Kite's page (password + 2FA, by hand, as
    Zerodha requires); this exchanges the resulting request_token for an access
    token and saves it. A running bot picks it up on its next cycle."""
    from .kite import TokenStore, capture_redirect, exchange_request_token, login_url, parse_request_token
    key, secret = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_API_SECRET")
    if not key or not secret:
        sys.exit("set KITE_API_KEY and KITE_API_SECRET")
    if a.request_token:
        rt = parse_request_token(a.request_token)
    else:
        print("1. Open this link and log in to Kite:\n\n   " + login_url(key) + "\n")
        if a.listen:
            print(f"2. Waiting for Kite to redirect to http://127.0.0.1:{a.listen}/ ...")
            rt = capture_redirect(a.listen)
        else:
            rt = parse_request_token(input("2. Paste the URL Kite redirected you to (or the request_token): "))
    data = exchange_request_token(key, secret, rt)
    store = TokenStore(a.token_file)
    d = store.save(data["access_token"], data.get("user_id", ""), pd.Timestamp.now(tz="Asia/Kolkata"))
    print(f"Saved session for {d['user_id'] or 'user'} to {store.path} (valid until {d['expires']}).")


def cmd_reset(cfg: Config, a):
    p = Path(cfg.state_file)
    if not p.exists():
        sys.exit("no state file")
    s = json.loads(p.read_text())
    eq = cfg.initial_capital + s.get("realized", 0.0)
    from .risk import RiskManager
    rm = RiskManager(cfg, s.get("risk"))
    print("current halt:", rm.halted() or "none")
    rm.reset(eq)
    s["risk"] = rm.to_dict()
    p.write_text(json.dumps(s, indent=2, default=float))
    print(f"risk state reset; peak re-based to {eq:,.2f}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tradebot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("backtest", "compare", "paper", "live", "reset"):
        p = sub.add_parser(name)
        if name == "compare":
            p.add_argument("-c", "--config", action="append", required=True,
                           help="repeat for each config, e.g. -c config/swing.json -c config/swing_40d.json")
        else:
            p.add_argument("-c", "--config", required=True)
        p.add_argument("--suffix", default=".NS", help="yfinance symbol suffix (.NS for NSE, '' for US)")
        if name in ("backtest", "compare"):
            g = p.add_mutually_exclusive_group(required=True)
            g.add_argument("--data", help="directory with <SYMBOL>.csv files")
            g.add_argument("--download", action="store_true", help="fetch from yfinance")
            g.add_argument("--synthetic", action="store_true", help="random data, plumbing test only")
            p.add_argument("--days", type=int)
            p.add_argument("--save-data", help="with --download: write the CSVs here for reproducible reruns")
            p.add_argument("--split", type=float, default=0.7, help="in-sample fraction (0 = none)")
            p.add_argument("--folds", type=int, default=4, help="consecutive periods for the consistency check")
            p.add_argument("--benchmark", help="CSV of a benchmark index (e.g. NIFTY 50); default: equal-weight universe")
            p.add_argument("--out", help="write report.md, trades.csv, equity.csv here")
        if name in ("paper", "live"):
            p.add_argument("--poll", type=int, default=20, help="seconds between cycles")
        if name == "paper":
            p.add_argument("--feed", choices=["yfinance", "kite"], default="yfinance")
            p.add_argument("--faults", help="inject failures, e.g. reject=0.05,partial=0.1,timeout=0.02,"
                                            "stop_reject=0.05,stop_cancel=0.02")
            p.add_argument("--fault-seed", type=int, help="make an injected-fault run repeatable")
        if name == "live":
            p.add_argument("--stop-type", choices=["SL-M", "SL"], default="SL-M")
    lp = sub.add_parser("login", help="daily Kite login: exchange request_token for an access token")
    lp.add_argument("--request-token", help="request_token or the full redirect URL (skips the prompt)")
    lp.add_argument("--listen", type=int, metavar="PORT",
                    help="capture the redirect on 127.0.0.1:PORT (set as the app's redirect URL)")
    lp.add_argument("--token-file", help="default: $KITE_TOKEN_FILE or state/kite_token.json")
    a = ap.parse_args(argv)
    if a.cmd == "login":
        return cmd_login(a)
    if getattr(a, "save_data", None) and not a.download:
        ap.error("--save-data only applies with --download")
    if a.cmd == "compare":
        return cmd_compare([Config.load(c) for c in a.config], [Path(c).stem for c in a.config], a)
    cfg = Config.load(a.config)
    {"backtest": cmd_backtest, "paper": cmd_paper, "live": cmd_live, "reset": cmd_reset}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
