"""Command line.

  python -m tradebot backtest -c config/swing.json --data data/
  python -m tradebot backtest -c config/intraday.json --synthetic
  python -m tradebot compare  -c config/swing.json -c config/swing_40d.json --data data/
  python -m tradebot paper    -c config/intraday.json --feed yfinance
  python -m tradebot live     -c config/intraday.json        (Zerodha Kite)
  python -m tradebot reset    -c config/intraday.json        (clear a risk halt)
  python -m tradebot login                                   (daily Kite session)
  python -m tradebot web --configs /etc/tradebot --workdir /var/lib/tradebot   (browser panel)
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
    from logging.handlers import RotatingFileHandler
    Path(cfg.state_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),                     # -> journald under systemd
                  RotatingFileHandler(Path(cfg.state_file).with_name("bot.log"),
                                      maxBytes=10_000_000, backupCount=5)],
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
    if not cfg.sectors:
        print("NOTE: no 'sectors' map in config; sector caps are off for this backtest.\n")
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


def _require_sectors(cfg: Config):
    if not cfg.sectors:
        sys.exit("paper/live need a 'sectors' map in the config (symbol -> sector) so the "
                 "sector caps apply; see config/swing.json")


def _engine(cfg: Config, broker):
    from .live import LiveEngine
    return LiveEngine(cfg, make_strategy(cfg.strategy, cfg.strategy_params, cfg.session.open), broker)


def _run(cfg: Config, broker, a, label: str):
    from .alerts import install
    alerts, hb = install(f"tradebot {label} {cfg.mode}/{cfg.strategy}")
    _engine(cfg, broker).run(a.poll, heartbeat=hb, alerts=alerts)


def cmd_paper(cfg: Config, a):
    from .broker import PaperBroker, YFinanceFeed
    _require_sectors(cfg)
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
    _require_sectors(cfg)
    if os.environ.get("TRADEBOT_LIVE") != "I_ACCEPT_THE_RISK":
        sys.exit("Live trading is locked. Paper trade first, then set TRADEBOT_LIVE=I_ACCEPT_THE_RISK.")
    if cfg.mode == "swing" and cfg.allow_short:
        sys.exit("Cash equities can't be held short overnight in India; set allow_short=false for swing.")
    _setup_logging(cfg)
    product = "MIS" if cfg.mode == "intraday" else "CNC"
    broker = KiteBroker(cfg.session.timezone, product, stop_order_type=a.stop_type,
                        gtt_for_cnc=not a.no_gtt)
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


def cmd_web(a):
    from .web import Panel, make_server
    host, _, port = a.bind.rpartition(":")
    host = host.strip("[]") or "127.0.0.1"
    loopback = host in ("127.0.0.1", "::1", "localhost")
    if not loopback and not a.allow_remote_bind:
        sys.exit(f"refusing to listen on {host}: put the panel behind an HTTPS reverse proxy on localhost "
                 "(deploy/Caddyfile), or pass --allow-remote-bind if a private network provides TLS")
    pw = os.environ.get("TRADEBOT_PANEL_PASSWORD_HASH")
    totp = os.environ.get("TRADEBOT_PANEL_TOTP_SECRET") or None
    if not pw:
        sys.exit("set TRADEBOT_PANEL_PASSWORD_HASH (generate it with: python -m tradebot web-passwd)")
    if not totp and not a.dev:
        sys.exit("set TRADEBOT_PANEL_TOTP_SECRET: this panel can stop trading and reset halts, so it needs "
                 "a second factor (web-passwd --totp prints one). --dev skips this for local testing only.")
    panel = Panel(a.configs, a.workdir, pw, totp, secure_cookies=not a.dev)
    srv = make_server(panel, host, int(port))
    print(f"tradebot panel on http://{a.bind}  (configs {a.configs}, workdir {a.workdir})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def cmd_web_passwd(a):
    import getpass
    from .web import hash_password, new_totp_secret
    pw = getpass.getpass("panel password (12+ chars): ")
    if len(pw) < 12:
        sys.exit("use at least 12 characters")
    if getpass.getpass("again: ") != pw:
        sys.exit("passwords differ")
    print("\nAdd to /etc/tradebot/env:\n")
    print(f"TRADEBOT_PANEL_PASSWORD_HASH={hash_password(pw)}")
    if a.totp:
        secret = new_totp_secret()
        print(f"TRADEBOT_PANEL_TOTP_SECRET={secret}")
        print("\nAdd this to your authenticator app (manual entry, TOTP, 6 digits, 30 s):")
        print(f"  secret: {secret}")
        print(f"  otpauth://totp/tradebot?secret={secret}&issuer=tradebot")


def cmd_status(cfg: Config, a):
    """Read-only view of the bot's saved state. Safe to run while the bot runs."""
    p = Path(cfg.state_file)
    if not p.exists():
        sys.exit(f"no state yet at {p}")
    s = json.loads(p.read_text())
    risk = s.get("risk", {})
    age = pd.Timestamp.now(tz=cfg.session.timezone) - pd.Timestamp(s.get("saved_at"))
    print(f"{cfg.mode}/{cfg.strategy}  state saved {s.get('saved_at')} ({age.total_seconds() / 60:.0f} min ago)")
    print(f"capital {cfg.initial_capital:,.0f}  realised P&L {s.get('realized', 0):+,.2f}")
    halts = [(k, risk.get(k)) for k in ("hard_halted", "entry_block", "day_halted") if risk.get(k)]
    print("halts: " + ("; ".join(f"{k}={v}" for k, v in halts) if halts else "none")
          + f"  | loss streak {risk.get('loss_streak', 0)}  | peak equity {risk.get('peak_equity', 0):,.0f}")
    pos = s.get("positions", [])
    print(f"\npositions ({len(pos)}):")
    for d in pos:
        flags = [f for f, on in (("STOP UNCONFIRMED", d.get("stop_tag")), ("EXIT PENDING", d.get("exit_tag")),
                                 (f"exit wanted: {d.get('exit_wanted')}", d.get("exit_wanted")),
                                 ("NO STOP", not d.get("broker_stop_id") and not d.get("stop_tag"))) if on]
        print(f"  {'LONG' if d['side'] > 0 else 'SHORT':5} {d['symbol']:<12} qty {d['qty']:>6}  entry {d['entry']:>9.2f}"
              f"  stop {d['stop']:>9.2f}  target {d['target'] or '-':>9}  held {d.get('bars_held', 0)} bars"
              f"  stop id {d.get('broker_stop_id') or '-'}  {' '.join(flags)}")
    pend = s.get("pending", {})
    print(f"\nunresolved orders ({len(pend)}):")
    for r in pend.values():
        state = "ESCALATED: check Kite" if r.get("escalated") else ("presumed absent" if r.get("absent") else "resolving")
        print(f"  {r['kind']:<5} {r['symbol']:<12} qty {r['qty']}  tag {r['tag']}  since {r['created']}  [{state}]")
    if s.get("external"):
        print(f"\nexternal holdings (never traded): {s['external']}")
    tp = p.with_name("trades.csv")
    if tp.exists():
        rows = tp.read_text().strip().splitlines()
        print(f"\nlast trades ({len(rows) - 1} total):")
        for r in rows[-5:] if len(rows) > 1 else []:
            if not r.startswith("symbol,"):
                print("  " + r)
    if Path(cfg.kill_switch_file).exists():
        print(f"\nKILL SWITCH FILE PRESENT: {cfg.kill_switch_file}")


def cmd_reset(cfg: Config, a):
    from .live import engine_running, request_control
    p = Path(cfg.state_file)
    if not p.exists():
        sys.exit("no state file")
    if engine_running(p):
        # A running engine would overwrite a direct edit on its next save.
        request_control(p, reset={"by": "cli", "at": str(pd.Timestamp.now(tz="UTC"))})
        print("reset queued; the running bot applies it on its next cycle (watch the log/alerts)")
        return
    _offline_reset(cfg, p, "cli")


def _offline_reset(cfg: Config, p: Path, by: str) -> list[str]:
    from .live import reset_state
    from .risk import RiskManager

    class _State:
        def __init__(self, s):
            self.s, self.risk = s, RiskManager(cfg, s.get("risk"))
            self.pending = s.get("pending", {})
            self.rebaseline = s.get("rebaseline", True)

        def equity(self):
            return cfg.initial_capital + self.s.get("realized", 0.0)

    s = json.loads(p.read_text())
    st = _State(s)
    notes = reset_state(st, by)
    s["risk"], s["rebaseline"], s["pending"] = st.risk.to_dict(), st.rebaseline, st.pending
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2, default=float))
    os.replace(tmp, p)
    for n in notes:
        print(n)
    return notes


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tradebot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("backtest", "compare", "paper", "live", "reset", "status"):
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
            p.add_argument("--no-gtt", action="store_true",
                           help="swing: use DAY stops re-placed each morning instead of GTT")
    lp = sub.add_parser("login", help="daily Kite login: exchange request_token for an access token")
    lp.add_argument("--request-token", help="request_token or the full redirect URL (skips the prompt)")
    lp.add_argument("--listen", type=int, metavar="PORT",
                    help="capture the redirect on 127.0.0.1:PORT (set as the app's redirect URL)")
    lp.add_argument("--token-file", help="default: $KITE_TOKEN_FILE or state/kite_token.json")
    wp = sub.add_parser("web", help="browser control panel (run behind an HTTPS reverse proxy)")
    wp.add_argument("--configs", default="/etc/tradebot", help="directory of <name>.json configs")
    wp.add_argument("--workdir", default=".", help="the bots' working dir (relative state paths resolve here)")
    wp.add_argument("--bind", default="127.0.0.1:8080")
    wp.add_argument("--dev", action="store_true", help="local testing: plain-HTTP cookies, TOTP optional")
    wp.add_argument("--allow-remote-bind", action="store_true")
    pp = sub.add_parser("web-passwd", help="generate the panel password hash (and TOTP secret)")
    pp.add_argument("--totp", action="store_true", help="also generate a TOTP secret")
    a = ap.parse_args(argv)
    if a.cmd == "web":
        return cmd_web(a)
    if a.cmd == "web-passwd":
        return cmd_web_passwd(a)
    if a.cmd == "login":
        return cmd_login(a)
    if getattr(a, "save_data", None) and not a.download:
        ap.error("--save-data only applies with --download")
    if a.cmd == "compare":
        return cmd_compare([Config.load(c) for c in a.config], [Path(c).stem for c in a.config], a)
    cfg = Config.load(a.config)
    {"backtest": cmd_backtest, "paper": cmd_paper, "live": cmd_live, "reset": cmd_reset,
     "status": cmd_status}[a.cmd](cfg, a)


if __name__ == "__main__":
    main()
