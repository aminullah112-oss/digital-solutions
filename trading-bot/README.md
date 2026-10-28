# tradebot: intraday + swing trading bot with portfolio risk controls

Automated trading for NSE cash equities (intraday via MIS, swing via CNC). It
can be adapted to any market by changing the session in the config and writing
one broker adapter. One codebase covers backtesting, paper trading and live
trading (Zerodha Kite Connect). Strategy and risk code are shared between them,
so what you backtest is what runs.

**Read this first.** Nothing here makes money by default. The strategies are
well-known, documented setups with no tuning. Their edge on *your* symbols, after
*your* costs, is unknown until you backtest on real data, check it out of sample,
and paper trade it. This project's job is to (1) keep any single trade, day,
or bad run from doing serious damage and (2) tell you honestly whether a
strategy has an edge before you fund it.

## Layout

```
tradebot/
  config.py       all tunables; JSON-loaded, unknown keys rejected, reckless values refused
  indicators.py   EMA/SMA/ATR/RSI/ADX/session VWAP/Donchian, all causal
  strategies.py   orb, vwap_pullback (intraday); trend_pullback, donchian (swing)
  risk.py         sizing + portfolio limits + circuit breakers
  backtest.py     bar-by-bar engine with pessimistic fills
  metrics.py      stats, Monte Carlo drawdown, red-flag verdicts
  broker.py       Broker interface, PaperBroker, yfinance feed
  kite.py         Zerodha Kite Connect v3 adapter (stdlib HTTP)
  live.py         live/paper loop: broker-side stops, reconciliation, kill switch
  alerts.py       Telegram / webhook alerts and a dead-man heartbeat
config/           intraday.json, swing.json (10-day hold), swing_40d.json (same, 40-day hold),
                  swing_2r.json (10-day hold + 2R profit target);
                  starting points, not recommendations
deploy/           systemd units, installer, operator CLI, backups (see "Deployment")
tests/            lookahead, risk maths, fill rules, live order flow, deployment scripts
```

## Strategies

| name | mode | entry | exit |
|---|---|---|---|
| `orb` | intraday 5m | first close beyond the 15-min opening range, on the VWAP side, volume ≥ 1.2× avg; skips ranges < 0.3% or > 2% | stop at range mid or 1.5 ATR (tighter), 2R target, breakeven at 1R, flat by 15:15 |
| `vwap_pullback` | intraday 5m | EMA9>EMA21, above VWAP, ADX>20, pullback touches VWAP/EMA21, bullish close back over EMA9 | stop under the pullback low, 2R target, breakeven at 1R |
| `trend_pullback` | swing daily | close>SMA200, EMA20>EMA50, ADX>18, RSI(5) dipped <35, close > prior high | 2.5 ATR / swing-low stop, 3 ATR chandelier trail, breakeven at 1R, time stop at `max_hold_bars` (10 in `swing.json`) |
| `donchian` | swing daily | 55-day closing high, above SMA200, volume ≥ 1.5× avg | 2 ATR stop, then the tighter of the 20-day low and a 3 ATR chandelier |

`max_hold_bars` (top-level config) caps every strategy's holding period in bars; the tighter of it and the strategy's own `max_bars` wins. With daily bars, 10 means ten trading days. A cap that short makes the time stop the main exit for trend-following trails; consider a profit target (`target_r`) alongside it.

Shorts only exist for intraday. You can't carry a cash-equity short overnight in India, so `live` refuses `allow_short` in swing mode.

## Risk controls

Strategies propose trades. `RiskManager` decides whether to take them and at what size.

| layer | default (intraday / swing) | behaviour |
|---|---|---|
| Per-trade risk | 0.5% / 0.75% of equity | qty = risk ÷ (stop distance + round-trip costs). A normal stop-out loses ~that much |
| Position cap | 25% / 20% notional | stops tight stops from producing huge positions |
| Gross exposure | 100% | no leverage. Config refuses >100% for swing |
| Concurrent positions | 4 / 6 | |
| Open-risk budget | 1.5% / 3% | sum of (entry − stop) × qty over open and pending positions. Six swing trades at 0.75% would otherwise put 4.5% at risk at once. A stop moved to breakeven frees its budget |
| Volume participation | ≤ 2% / ≤ 1% of the signal bar's volume | keeps size small relative to liquidity, so the slippage assumption holds |
| Sector caps | ≤ 2 positions and ≤ 1% / 1.5% open risk per sector | uses the config's `sectors` map. The six financials (5 banks + Bajaj Finance) count as one sector |
| Correlated-risk budget | ≤ 1% / 1.5% | new trade's risk + Σ max(0, ρ) × each open same-direction position's risk. ρ comes from 60-day daily returns using only days before the signal. Unknown ρ (thin history) counts as 0.5 |
| Stop width | ≤ 2% / ≤ 10% | wider stops are rejected, not shrunk |
| Reward:risk | ≥ 1.5 **after costs** | only for strategies with a target |
| Liquidity | price ≥ ₹50, avg daily turnover ≥ ₹50cr / ₹20cr | |
| Loss streak | ½ size after 3 losses; stop for the day after 4 / 6 | |
| Daily loss limit | 1.5% / 3% | no new entries today; intraday also flattens |
| Max drawdown | 10% / 15% from peak | flatten everything and halt until `tradebot reset` |
| Gap protection | | entry cancelled if the open gaps through the stop or adds > 0.5R. A gapped stop is booked at the open, not the stop price |
| Entry block | | any broker/bot mismatch, unreadable account state, or order whose outcome is unknown blocks new entries. It **doesn't** auto-exit, because acting on uncertain state can double-exit. Cleared only by `reset` |
| Kill switch | create a file named `STOP` | blocks entries, flattens at the next moment the market is open (stops stay live overnight), then exits |

Sizing includes costs: the per-share risk used for quantity is `|entry − stop| + 2 × price × (cost_pct + slippage_pct)`, not just the stop distance (`risk.py`, tested in `test_costs_reduce_size`). A stop is an order, not a loss cap. Gaps, circuit locks and failed orders can make a loss bigger than planned; the Monte Carlo and "stop (gap)" counts in the report show how often.

Live-only safeguards. Each row has a deterministic test.

**Order lifecycle.** The engine tags every order itself. Any request whose outcome is unknown is recorded in a persistent `pending` registry and resolved by tag on later cycles. Until it resolves, the bot sends nothing that could double up for that position. A cancel only counts once the broker reports a final state.

| failure | handling |
|---|---|
| Entry/exit request times out | recorded by tag, never retried blindly; resolved from the order book, or from the broker's position change if the order book lags. Market orders don't rest, so if the position hasn't moved after 120s the order didn't happen and is retried |
| Entry fills but the order shows up late (or never) | adopted and stopped as soon as the tag or the position change proves it; no new entries meanwhile |
| Stop placement times out | the stop may be resting unseen, so the bot **never** presumes it absent. No second stop and no exit for those shares. If the position drops, the stop fired and is booked. Otherwise, after 120s: CRITICAL alert, entries blocked, and you check Kite and run `reset`, which then lets the bot re-arm once |
| Ambiguous GTT creation | GTT IDs are snapshotted before submission; recovery considers only newly appearing matching IDs. If identity is missing or ambiguous, it remains unresolved rather than adopting an older matching trigger |
| GTT has triggered but child order isn't visible (or a status read fails) | state is `UNKNOWN`, never treated as protection: no cancel, no opposing exit, and new entries pause at once. If it's still `UNKNOWN` after 120s: persistent entry block and CRITICAL alert. A one-off failed read clears on the next good one without needing `reset` |
| Late duplicate/stray stop appears | cancelled (confirmed) |
| Cancel request unanswered (stop may still fill) | exit deferred while the stop stays live; retried until the broker confirms the cancel, so there's no market sell racing a live stop |
| Stop fills while being cancelled | booked as a stop exit; no market order sent |
| Position shrinks (partial exit/fill) | oversized stop cancelled and re-armed at the new quantity; entries paused until done |
| Price through an OPEN stop for 2 cycles (circuit, or GTT limit skipped on a gap) | stop cancelled (confirmed), then market exit |
| Stop re-arm and fallback exit both fail | CRITICAL alert every cycle; re-protection tried before re-exiting; other positions still reconciled; entries paused |
| Entry/exit partly fills | filled part tracked and booked; remainder protected |
| Stop expires or broker cancels it | re-placed next cycle (MIS); CNC uses GTT, which doesn't expire daily |
| Restart finds a position with no stop | stop armed before anything else, or position closed |
| Broker qty ≠ bot qty + recorded external holdings | entries blocked until `reset`; unexplained shares are never touched |
| Two bot processes on the same state | second one refuses to start (file lock) |
| Process crashes | broker-side stops keep working; state, pending orders, halts and blocks reload |

**Overnight protection (swing/CNC).** Protective stops for CNC positions are Kite **GTT** orders. They stay at Zerodha across sessions and fire even if the bot is down or its token expired before the open. MIS stops are SL-M DAY orders, which is fine because MIS never carries overnight. Neither protects against a gap: a GTT fires a LIMIT order 3% beyond the trigger, so an open that gaps further leaves it resting. The bot detects that (price through an open stop) and exits at market. `live --no-gtt` falls back to DAY stops re-placed each morning; then the gap between the open and the first cycle is unprotected.

**Holdings the bot didn't buy.** On first start (and after `reset`), the bot records any existing quantity of its symbols as *external*. It never sells those shares, and any later change it can't attribute to its own tagged orders blocks entries. A dedicated Zerodha account (or no manual positions in the bot's symbols) is still the cleanest setup.

**Holidays.** Fill `session.holidays` with the year's NSE trading holidays (`"YYYY-MM-DD"`) from the NSE circular. On those dates the bot makes no broker calls and sends no login reminder. It doesn't ship a list, because a wrong date there is worse than an empty one.

The order's status at the broker, not the bot's memory, decides whether a stop exit happened. Every cycle starts with reconciliation, before any new entry. Signals from stale bars are ignored. Daily-loss checks use realised plus open P&L.
- Risk maths uses **bot-scoped equity** (`initial_capital` + realised + open P&L), so the bot never sizes off money in the account that you didn't allocate to it.

## Alerts

Without alerts, "POSITION UNPROTECTED" only reaches a log file. Set any of these
environment variables (never in the config file) before `paper` or `live`:

| variable | effect |
|---|---|
| `TRADEBOT_TELEGRAM_TOKEN` + `TRADEBOT_TELEGRAM_CHAT` | Telegram messages via a bot you create with @BotFather |
| `TRADEBOT_WEBHOOK_URL` | POST `{"text": ...}`: Slack/Discord-style hooks, or an ntfy.sh topic for phone push |
| `TRADEBOT_HEARTBEAT_URL` | pinged after every clean cycle (at most once a minute) |

You're alerted on every ERROR/CRITICAL log line, every trade opened or closed, every new halt or entry block, and bot start/stop. Identical messages are suppressed for 5 minutes, so an expired Kite token doesn't send 200 messages. Alerts go out on a background thread; a failing channel is logged and never interrupts trading.

The heartbeat covers what self-reporting can't: a killed process, a frozen loop, or a dead VM. Point it at a dead-man service (e.g. healthchecks.io, with its period set to a few minutes). The service alerts you when the pings **stop**. Pings are sent only after a cycle completes, so a bot stuck on repeated errors also stops pinging.

## Concentration limits

Five bank longs aren't five independent bets; on a bad day for financials they're one bet at five times the size. Two checks catch that:

- **Sector caps** use the `sectors` map in each config (`symbol -> sector`). Paper and live refuse to start without one. Config loading fails if any traded symbol is missing from it, so a typo can't silently bypass the cap. Backtests without a map just print a note.
- **Correlated-risk budget** catches co-movement that sector labels miss, such as Reliance with the index, or IT with the rupee. A candidate correlated 0.9 with an open position gets sized as if 90% of that position's risk were already its own. Short positions get no hedge credit for long candidates, because correlations converge in sell-offs.

Both reduce size first, and reject only when the budget is used up. The rejection reason names the cap that bound (`size zero: sector financials risk budget exhausted`), so the backtest report shows how often each one fires. In live trading, daily closes for the correlation come from one history call per symbol per day. If that fails, ρ = 0.5 is assumed, and the warning is logged.

## Daily Kite login

Kite access tokens expire at **06:00 IST** every day. Zerodha requires a human
login (password + 2FA), so the bot deliberately does **not** automate that step:
scripted password/TOTP login breaks Zerodha's terms and SEBI's daily-login
expectation, and would put API access on your trading account at risk.
Everything around the login is automated:

1. From 08:45 on weekdays (`session.login_reminder`), the bot checks the session. If it's missing or expired, you get one alert with the login link.
2. Open the link, log in, and Kite redirects you to your app's redirect URL with a `request_token`.
3. Run `python -m tradebot login` on the bot's machine and paste the redirect URL. It exchanges the token (using `KITE_API_SECRET` locally to compute the checksum; the secret is never sent) and writes `state/kite_token.json` with mode 600.
4. The running bot notices the new file on its next cycle, alerts "resuming", and carries on. No restart.

Alternatively, set the app's redirect URL to `http://127.0.0.1:8765/` in the Kite developer console and run `tradebot login --listen 8765`. The redirect is then captured automatically when you log in from a browser on the same machine, or through `ssh -L 8765:127.0.0.1:8765 vm`.

While there's no valid session (missing, expired, or rejected by Kite with `TokenException`), the bot touches nothing at the broker. That avoids starting an exit it can't finish. Stops already at the exchange keep working. Trailing, targets and the intraday 15:15 flatten are paused, and the alert says how many positions are open. Zerodha auto-squares MIS positions near the close regardless. The token file lives under `state/`, which is git-ignored. Keep `KITE_API_SECRET` in the environment only.

## Fault injection (paper)

Zerodha has no sandbox, so the paper broker can inject the failures a real broker produces. That way, paper weeks also exercise the recovery code:

```bash
python -m tradebot paper -c config/swing.json --feed kite \
    --faults reject=0.05,partial=0.1,timeout=0.02,late=0.02,stop_reject=0.05,stop_cancel=0.02,cancel_unconfirmed=0.05 \
    --fault-seed 1
```

| fault | what the paper broker does |
|---|---|
| `reject` | market order rejected, nothing fills |
| `partial` | market order fills 30–90% of the quantity |
| `timeout` | the order **is** placed or filled, but the call raises `OrderUnknown` (the nastiest real case) |
| `late` | like `timeout`, and the order stays invisible in the order book for 3 more lookups |
| `stop_reject` | stop order rejected |
| `stop_cancel` | an open stop turns up cancelled (expiry, broker-side cancel) |
| `cancel_unconfirmed` | a cancel request goes unanswered; the order stays live and can still fill |

Each injected fault is logged as `[fault injected]`. The soak test runs the engine over hundreds of sessions × 3 symbols with heavy rates of every fault, polling every 30s. After **every cycle** it checks:

- the account is never oversold (a double sell);
- every position has a live stop for its exact size, or has been unprotected for at most 3 cycles with entries paused and a CRITICAL alert each cycle;
- broker and bot quantities match, except for symbols with an order still resolving, which must resolve within 4 cycles.

Across 20 seeds: 6,846 injected faults over 2,064 trades, no invariant failures, no halts needing a human, and a worst unprotected streak of 2 cycles. The soak found three engine bugs, all fixed:

- an ambiguous stop presumed absent could be followed by an exit while the stop was still live (a double sell);
- a stale stop wasn't resized after a late partial exit;
- one failed follow-up action aborted the rest of reconciliation.

Escalations, unexplained holdings and holidays have their own deterministic tests.

Use a separate `state_file` (or delete `state/`) when you switch from a fault-injected paper run to a clean one.

## Workflow

```bash
cd trading-bot
pip install -r requirements.txt
python -m unittest discover -s tests        # 102 tests

# 1. Plumbing check (random data, results meaningless)
python -m tradebot backtest -c config/swing.json --synthetic

# 2. Real data -> full evaluation report (70/30 split and 4 periods by default)
python -m tradebot backtest -c config/swing.json --download --out results/swing
#    Or your own adjusted CSVs: data/<SYMBOL>.csv with datetime,open,high,low,close,volume,
#    with a real index as the benchmark instead of the equal-weight universe:
python -m tradebot backtest -c config/swing.json --data data/ --benchmark data/NIFTY50.csv

# 2b. Freeze the data once, then compare holding periods on identical bars and windows
python -m tradebot backtest -c config/swing.json --download --save-data data/nse_daily
python -m tradebot compare -c config/swing.json -c config/swing_40d.json -c config/swing_2r.json \
    --data data/nse_daily --out results/hold_compare

# 3. Paper trade for at least 4-6 weeks. Zerodha has no Kite Connect sandbox, so
#    paper = real market data (delayed yfinance, or Kite with --feed kite) + fills
#    simulated locally by PaperBroker
python -m tradebot paper -c config/intraday.json --feed kite    # needs `tradebot login` too

# 4. Live, small, only if 2 and 3 agree
export KITE_API_KEY=... KITE_API_SECRET=...
python -m tradebot login                            # every morning; see "Daily Kite login"
export TRADEBOT_LIVE=I_ACCEPT_THE_RISK
python -m tradebot live -c config/intraday.json

touch STOP                                          # emergency flatten
python -m tradebot reset -c config/intraday.json    # clear a halt/entry block after checking the account
python -m tradebot status -c config/intraday.json   # positions, unresolved orders, halts, last trades (read-only)
```

## Evaluation report

`backtest` writes a Markdown report (`--out` saves `report.md`, `trades.csv`, `equity.csv`):

- In-sample, out-of-sample and full-period stats: return, CAGR, max drawdown, longest time underwater, Sharpe/Sortino/Calmar, win rate, average win/loss, profit factor, expectancy in R **with a bootstrap 95% confidence interval**, exposure, annual turnover, exit reasons, and which risk rules rejected signals.
- Buy-and-hold of the same universe (or `--benchmark`) over the same window.
- Consistency: the same parameters run over N consecutive periods.
- Cost sensitivity: 0×, 1×, 1.5× and 2× costs and slippage.
- Breakdowns by year, by market regime (benchmark above/below its 200-day SMA), and by symbol.
- Data audit warnings: overnight moves > 25% (unadjusted splits), missing stretches, zero-volume bars, short sessions.

Each test window still uses earlier history for indicator warmup, so the out-of-sample period isn't partly lost to warmup.

**Verdict: NOT APPROVED** if any of these hold, judged on out-of-sample data: < 100 trades; expectancy ≤ 0.05R; expectancy CI includes zero; profit factor < 1.2; Sharpe > 3 (suspicious); 95th-percentile Monte Carlo drawdown > 25%; out-of-sample expectancy under half of in-sample; positive in < 60% of periods; edge gone at 2× costs; buy-and-hold did better without a much larger drawdown; one symbol produced > 60% of profit. Passing is necessary, not sufficient.

Not addressed, and it matters: **survivorship bias.** The universe is today's symbol list, so stocks that were delisted or dropped out of the index are missing and results are flattered. Fixing it needs point-in-time index membership data, which this repo doesn't have.

## Things that will bite you

- **Costs dominate intraday.** At ~0.08% per side all-in, a 0.3% stop on 5-minute bars gives up about half its R to costs. On synthetic data the R:R-after-costs gate rejects most ORB signals for this reason. Expect the same on real data for low-volatility names. Prefer liquid, higher-ATR stocks, or use 15-minute bars.
- **yfinance intraday history is only 60 days.** That's too short to validate an intraday strategy. Use Kite historical data (paid add-on) or another vendor, and get 1–2 years.
- **Data must be split/bonus adjusted.** An unadjusted split looks like a 50% gap and will trigger stops in the backtest.
- **Not modelled:** circuit limits in backtests (live, a stop that can't fill is detected and exited at market once the price trades), auction sessions, F&O. Holidays need `session.holidays` filled in.
- **Kite specifics still unverified:** GTT field names and states, `filled_quantity` on cancelled orders, whether same-day CNC buys appear in both holdings and day positions (a double count would block entries, not trade), and order-book visibility timing. The adapter now fails closed on ambiguous GTT identity/state, but check each behavior with controlled live tests before trusting it.
- **Overfitting.** Changing parameters until the backtest looks good is the most common way to lose money with a bot. Pick parameters on in-sample data, look at out-of-sample once, and stop tweaking.
- **Kite adapter is unverified.** It follows the Kite Connect v3 REST docs but hasn't been run against a live account. There is no Kite Connect sandbox. Paper trade with `--feed kite`, then place 1-share live orders to check every path (entry, stop placement, stop modify, cancel, target exit, EOD flatten) before trusting it. Kite has restricted SL-M on some segments; if your stops are rejected, use `--stop-type SL` (stop-limit with a 0.5% buffer).
- **Regulation (verify with your broker).** SEBI's retail algo framework (rolled out 2025–26) puts API orders under broker-side controls: static-IP whitelisting, order-rate thresholds above which an algo must be registered and tagged with an exchange algo ID, and daily re-login. Zerodha currently documents a static-IP requirement for API order placement and a 10 orders/second per-account limit. Staying under the rate limit doesn't by itself mean every requirement is met. Treat compliance as a go-live gate and confirm your exact setup with Zerodha.
- **Run it on an always-on machine**; see "Deployment".

## Deployment

A small Linux VM in Mumbai (AWS `ap-south-1`, GCP `asia-south1`, or similar) with a **static public IP** is enough: 1 vCPU and 1–2 GB RAM. Zerodha requires a whitelisted static IP for API order placement. Register it in the Kite developer console.

```bash
git clone <this repo> && cd digital-solutions/trading-bot
sudo ./deploy/install.sh                 # user, venv, /etc/tradebot, systemd units
sudoedit /etc/tradebot/env               # alerts, Kite keys, TRADEBOT_MODE=paper
sudoedit /etc/tradebot/swing.json        # symbols, sectors, holidays, capital
sudo tradebot login                      # each trading morning
sudo systemctl enable --now tradebot@swing
sudo tradebot status -c /etc/tradebot/swing.json
journalctl -u tradebot@swing -f
```

| piece | what it does |
|---|---|
| `tradebot@.service` | one instance per config (`tradebot@swing` → `/etc/tradebot/swing.json`). Mode and flags come from `/etc/tradebot/env`. Runs as an unprivileged `tradebot` user that can only write `/var/lib/tradebot`. Restarts on crash (state and pending orders reload; broker-side stops keep working in between) but **not** after a clean exit (kill switch, `systemctl stop`). Gives up after 5 crashes in 15 minutes, because a crash loop needs a human |
| `SIGTERM` handling | `systemctl stop/restart` lets the bot finish its current cycle and save state. It never stops between cancelling a stop and sending the exit |
| `/etc/tradebot/env` | secrets and mode, `640 root:tradebot`. Read by systemd and by the `tradebot` CLI as plain `KEY=value` lines, never executed as shell |
| `tradebot` CLI | `/usr/local/bin/tradebot ...` runs any subcommand as the service user with the service's environment (`login`, `status`, `reset`, `backtest`) |
| `tradebot-backup.timer` | daily 16:05 IST snapshot of `/var/lib/tradebot` to `/var/backups/tradebot`, kept 30 days. The Kite token is excluded |
| logs | journald (`journalctl -u tradebot@swing`) plus `state/*/bot.log`, rotated at 10 MB × 5 |
| upgrades | re-run `install.sh`. Your configs and env are never overwritten, the previous code is kept in `/opt/tradebot/app.old`, and running instances aren't touched. Restart them when ready |

Also: keep the clock NTP-synced (`timedatectl set-ntp true`; the installer warns if it isn't), since bar timing depends on it. Point `TRADEBOT_HEARTBEAT_URL` at a dead-man service. One `STOP` file in `/var/lib/tradebot` stops every instance.

Verified here: shellcheck on all scripts, a full install into a temporary prefix with a real venv, the upgrade path, the CLI wrapper (including a secret containing `$`, backticks and `$(…)` that must not execute), backups, `status`, and SIGTERM shutdown (`tests/test_deploy.py`). **Not** verified here: systemd actually running the units, because this container has no init system; `systemd-analyze verify` parsed them without syntax errors. Do a first `systemctl start` in paper mode and watch `journalctl` before trusting it.
