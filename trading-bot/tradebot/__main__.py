"""Command line.

  python -m tradebot backtest -c config/swing.json --data data/
  python -m tradebot backtest -c config/intraday.json --synthetic
  python -m tradebot paper    -c config/intraday.json --feed yfinance
  python -m tradebot live     -c config/intraday.json        (Zerodha Kite)
  python -m tradebot reset    -c config/intraday.json        (clear a risk halt)
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
from .data import download_yfinance, load_dir, synthetic
from .metrics import format_report, monte_carlo_drawdown, summarize, trades_frame, verdict
from .strategies import make_strategy


def _setup_logging(cfg: Config):
    Path(cfg.state_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(Path(cfg.state_file).with_name("bot.log"))],
    )


def cmd_backtest(cfg: Config, a):
    tz = cfg.session.timezone
    if a.synthetic:
        intr = cfg.mode == "intraday"
        data = {s: synthetic(days=a.days or (120 if intr else 1000), intraday=intr, seed=k, tz=tz)
                for k, s in enumerate(cfg.symbols)}
        print("NOTE: synthetic data tests the plumbing only. Results say nothing about real markets.\n")
    elif a.download:
        period = f"{a.days or (59 if cfg.mode == 'intraday' else 3650)}d"
        data = {s: download_yfinance(s + a.suffix, cfg.interval, period, tz) for s in cfg.symbols}
    else:
        data = load_dir(a.data, cfg.symbols, tz)

    strat = make_strategy(cfg.strategy, cfg.strategy_params, cfg.session.open)
    if a.split:
        first = min(df.index[0] for df in data.values())
        last = max(df.index[-1] for df in data.values())
        cut = first + (last - first) * a.split
        parts = {"IN-SAMPLE": {s: df[df.index < cut] for s, df in data.items()},
                 "OUT-OF-SAMPLE": {s: df[df.index >= cut] for s, df in data.items()}}
    else:
        parts = {"FULL": data}

    for label, d in parts.items():
        res = Backtester(cfg, strat).run(d)
        stats = summarize(res)
        mc = monte_carlo_drawdown(res)
        print(f"\n### {label}")
        print(format_report(stats, mc, res.rejections))
        flags = verdict(stats, mc)
        if flags:
            print("RED FLAGS:")
            for f in flags:
                print("  -", f)
        if a.out:
            out = Path(a.out)
            out.mkdir(parents=True, exist_ok=True)
            tag = label.lower()
            trades_frame(res).to_csv(out / f"trades_{tag}.csv", index=False)
            res.equity.to_csv(out / f"equity_{tag}.csv", header=["equity"])
            (out / f"stats_{tag}.json").write_text(json.dumps({**stats, "monte_carlo": mc}, indent=2, default=str))


def _engine(cfg: Config, broker):
    from .live import LiveEngine
    return LiveEngine(cfg, make_strategy(cfg.strategy, cfg.strategy_params, cfg.session.open), broker)


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
    broker = PaperBroker(feed, cfg.costs.slippage_pct, saved)
    _engine(cfg, broker).run(a.poll)


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
    _engine(cfg, broker).run(a.poll)


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
    for name in ("backtest", "paper", "live", "reset"):
        p = sub.add_parser(name)
        p.add_argument("-c", "--config", required=True)
        p.add_argument("--suffix", default=".NS", help="yfinance symbol suffix (.NS for NSE, '' for US)")
        if name == "backtest":
            g = p.add_mutually_exclusive_group(required=True)
            g.add_argument("--data", help="directory with <SYMBOL>.csv files")
            g.add_argument("--download", action="store_true", help="fetch from yfinance")
            g.add_argument("--synthetic", action="store_true", help="random data, plumbing test only")
            p.add_argument("--days", type=int)
            p.add_argument("--split", type=float, help="in-sample fraction, e.g. 0.7")
            p.add_argument("--out", help="write trades/equity/stats here")
        if name in ("paper", "live"):
            p.add_argument("--poll", type=int, default=20, help="seconds between cycles")
        if name == "paper":
            p.add_argument("--feed", choices=["yfinance", "kite"], default="yfinance")
        if name == "live":
            p.add_argument("--stop-type", choices=["SL-M", "SL"], default="SL-M")
    a = ap.parse_args(argv)
    cfg = Config.load(a.config)
    {"backtest": cmd_backtest, "paper": cmd_paper, "live": cmd_live, "reset": cmd_reset}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
