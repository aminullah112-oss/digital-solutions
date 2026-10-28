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
config/           intraday.json, swing.json (10-day hold), swing_40d.json (same, 40-day hold);
                  starting points, not recommendations
tests/            lookahead, risk maths, fill rules, live order flow
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

Live-only safeguards (each failure path below has a test):

| failure | handling |
|---|---|
| Order request times out | never retried blindly. Every order carries a unique tag; the bot looks it up in the order book. If it can't find it: `OrderUnknown`, entries blocked |
| Entry partly fills | position tracked and stopped for the filled quantity only |
| Market order not complete in 30s | cancelled; whatever filled is tracked |
| Stop rejected after entry | position closed at market immediately |
| Exit fails after its stop was cancelled | stop re-armed; logged CRITICAL if that fails too |
| Exit partly fills | filled part booked, remainder re-protected |
| Stop expires (DAY order) or broker cancels it | re-placed next cycle |
| Restart finds a position with no stop | stop armed before anything else, or position closed |
| Broker qty ≠ bot qty (manual trade, missed fill, duplicate) | entries blocked until `reset` |
| Two bot processes on the same state | second one refuses to start (file lock) |
| Process crashes | broker-side stops keep working; state reloads; halts and blocks persist |

The stop order's status, not the bot's memory, decides whether a stop exit happened. Every cycle starts with reconciliation, before any new entry. Signals from stale bars are ignored. Daily-loss checks use realised plus open P&L. Don't trade the bot's symbols by hand in the same product (MIS/CNC); the reconcile check will treat that as a mismatch.
- Risk maths uses **bot-scoped equity** (`initial_capital` + realised + open P&L), so the bot never sizes off money in the account that you didn't allocate to it.

## Workflow

```bash
cd trading-bot
pip install -r requirements.txt
python -m unittest discover -s tests        # 36 tests

# 1. Plumbing check (random data, results meaningless)
python -m tradebot backtest -c config/swing.json --synthetic

# 2. Real data -> full evaluation report (70/30 split and 4 periods by default)
python -m tradebot backtest -c config/swing.json --download --out results/swing
#    Or your own adjusted CSVs: data/<SYMBOL>.csv with datetime,open,high,low,close,volume,
#    with a real index as the benchmark instead of the equal-weight universe:
python -m tradebot backtest -c config/swing.json --data data/ --benchmark data/NIFTY50.csv

# 2b. Freeze the data once, then compare holding periods on identical bars and windows
python -m tradebot backtest -c config/swing.json --download --save-data data/nse_daily
python -m tradebot compare -c config/swing.json -c config/swing_40d.json \
    --data data/nse_daily --out results/hold_compare

# 3. Paper trade for at least 4-6 weeks. Zerodha has no Kite Connect sandbox, so
#    paper = real market data (delayed yfinance, or Kite with --feed kite) + fills
#    simulated locally by PaperBroker
python -m tradebot paper -c config/intraday.json --feed kite

# 4. Live, small, only if 2 and 3 agree
export KITE_API_KEY=... KITE_ACCESS_TOKEN=...      # token expires daily
export TRADEBOT_LIVE=I_ACCEPT_THE_RISK
python -m tradebot live -c config/intraday.json

touch STOP                                          # emergency flatten
python -m tradebot reset -c config/intraday.json    # clear a halt/entry block after checking the account
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
- **Not modelled:** market holidays (the bot just sees no new bars), circuit limits (a stop may not fill in an upper/lower circuit), auction sessions, F&O.
- **Overfitting.** Changing parameters until the backtest looks good is the most common way to lose money with a bot. Pick parameters on in-sample data, look at out-of-sample once, and stop tweaking.
- **Kite adapter is unverified.** It follows the Kite Connect v3 REST docs but hasn't been run against a live account. There is no Kite Connect sandbox. Paper trade with `--feed kite`, then place 1-share live orders to check every path (entry, stop placement, stop modify, cancel, target exit, EOD flatten) before trusting it. Kite has restricted SL-M on some segments; if your stops are rejected, use `--stop-type SL` (stop-limit with a 0.5% buffer).
- **Regulation (verify with your broker).** SEBI's retail algo framework (rolled out 2025–26) puts API orders under broker-side controls: static-IP whitelisting, order-rate thresholds above which an algo must be registered and tagged with an exchange algo ID, and daily re-login. Zerodha currently documents a static-IP requirement for API order placement and a 10 orders/second per-account limit. Staying under the rate limit doesn't by itself mean every requirement is met. Treat compliance as a go-live gate and confirm your exact setup with Zerodha.
- **Run it on an always-on machine** (a small cloud VM with a static IP, which you'll need for SEBI anyway) under a supervisor like `systemd` with `Restart=on-failure`. Watch `state/*/bot.log` and `trades.csv`.
