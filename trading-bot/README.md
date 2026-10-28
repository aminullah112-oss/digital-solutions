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
config/           intraday.json, swing.json (starting points, not recommendations)
tests/            lookahead, risk maths, fill rules, live order flow
```

## Strategies

| name | mode | entry | exit |
|---|---|---|---|
| `orb` | intraday 5m | first close beyond the 15-min opening range, on the VWAP side, volume ≥ 1.2× avg; skips ranges < 0.3% or > 2% | stop at range mid or 1.5 ATR (tighter), 2R target, breakeven at 1R, flat by 15:15 |
| `vwap_pullback` | intraday 5m | EMA9>EMA21, above VWAP, ADX>20, pullback touches VWAP/EMA21, bullish close back over EMA9 | stop under the pullback low, 2R target, breakeven at 1R |
| `trend_pullback` | swing daily | close>SMA200, EMA20>EMA50, ADX>18, RSI(5) dipped <35, close > prior high | 2.5 ATR / swing-low stop, 3 ATR chandelier trail, breakeven at 1R, 40-bar time stop |
| `donchian` | swing daily | 55-day closing high, above SMA200, volume ≥ 1.5× avg | 2 ATR stop, then the tighter of the 20-day low and a 3 ATR chandelier |

Shorts only exist for intraday. You can't carry a cash-equity short overnight in India, so `live` refuses `allow_short` in swing mode.

## Risk controls

Strategies propose trades. `RiskManager` decides whether to take them and at what size.

| layer | default (intraday / swing) | behaviour |
|---|---|---|
| Per-trade risk | 0.5% / 0.75% of equity | qty = risk ÷ (stop distance + round-trip costs). A normal stop-out loses ~that much |
| Position cap | 25% / 20% notional | stops tight stops from producing huge positions |
| Gross exposure | 100% | no leverage. Config refuses >100% for swing |
| Concurrent positions | 4 / 6 | |
| Stop width | ≤ 2% / ≤ 10% | wider stops are rejected, not shrunk |
| Reward:risk | ≥ 1.5 **after costs** | only for strategies with a target |
| Liquidity | price ≥ ₹50, avg daily turnover ≥ ₹50cr / ₹20cr | |
| Loss streak | ½ size after 3 losses; stop for the day after 4 / 6 | |
| Daily loss limit | 1.5% / 3% | no new entries today; intraday also flattens |
| Max drawdown | 10% / 15% from peak | flatten everything and halt until `tradebot reset` |
| Gap protection | | entry cancelled if the open gaps through the stop or adds > 0.5R. A gapped stop is booked at the open, not the stop price |
| Kill switch | create a file named `STOP` | flattens and exits on the next cycle |

Live-only safeguards:
- A broker-side stop (SL-M) goes in right after every entry fill. If placing it fails, the position is closed at market.
- If an exit fails after its stop was cancelled, the stop is re-armed.
- Stops that expire overnight (DAY validity) or get cancelled by the broker are re-placed.
- The stop order's status, not the bot's memory, decides whether a stop exit happened. A crashed bot still has live stops.
- State is written atomically every cycle and reloaded on restart.
- Signals from stale bars are ignored.
- Risk maths uses **bot-scoped equity** (`initial_capital` + realised + open P&L), so the bot never sizes off money in the account that you didn't allocate to it.

## Workflow

```bash
cd trading-bot
pip install -r requirements.txt
python -m unittest discover -s tests        # 16 tests

# 1. Plumbing check (random data, results meaningless)
python -m tradebot backtest -c config/swing.json --synthetic

# 2. Real data. Swing: 10y daily from yfinance, 70/30 in/out-of-sample split
python -m tradebot backtest -c config/swing.json --download --split 0.7 --out results/swing
#    Or your own adjusted CSVs: data/<SYMBOL>.csv with datetime,open,high,low,close,volume
python -m tradebot backtest -c config/intraday.json --data data/ --split 0.7

# 3. Paper trade for at least 4-6 weeks (simulated fills on a delayed yfinance feed,
#    or on Kite data with --feed kite)
python -m tradebot paper -c config/intraday.json --feed kite

# 4. Live, small, only if 2 and 3 agree
export KITE_API_KEY=... KITE_ACCESS_TOKEN=...      # token expires daily
export TRADEBOT_LIVE=I_ACCEPT_THE_RISK
python -m tradebot live -c config/intraday.json

touch STOP                                          # emergency flatten
python -m tradebot reset -c config/intraday.json    # clear a drawdown halt after review
```

The report prints red flags automatically: < 100 trades, expectancy ≤ 0.05R,
profit factor < 1.2, Sharpe > 3 (likely overfit), Monte Carlo 95th-percentile
drawdown > 25%. A strategy should clear all of them **out of sample** before
paper trading.

## Things that will bite you

- **Costs dominate intraday.** At ~0.08% per side all-in, a 0.3% stop on 5-minute bars gives up about half its R to costs. On synthetic data the R:R-after-costs gate rejects most ORB signals for this reason. Expect the same on real data for low-volatility names. Prefer liquid, higher-ATR stocks, or use 15-minute bars.
- **yfinance intraday history is only 60 days.** That's too short to validate an intraday strategy. Use Kite historical data (paid add-on) or another vendor, and get 1–2 years.
- **Data must be split/bonus adjusted.** An unadjusted split looks like a 50% gap and will trigger stops in the backtest.
- **Not modelled:** market holidays (the bot just sees no new bars), circuit limits (a stop may not fill in an upper/lower circuit), auction sessions, F&O.
- **Overfitting.** Changing parameters until the backtest looks good is the most common way to lose money with a bot. Pick parameters on in-sample data, look at out-of-sample once, and stop tweaking.
- **Kite adapter is unverified.** It follows the Kite Connect v3 REST docs but hasn't been run against a live account. Paper trade with `--feed kite` and then place 1-share live orders to check every path (entry, stop placement, stop modify, cancel, target exit, EOD flatten) before trusting it. Kite has restricted SL-M on some segments; if your stops are rejected, use `--stop-type SL` (stop-limit with a 0.5% buffer).
- **Regulation (verify with your broker).** SEBI's retail algo framework (rolled out 2025–26) puts API orders under broker-side controls: static-IP whitelisting, order-rate thresholds above which an algo must be registered and tagged with an exchange algo ID, and daily re-login. This bot places a handful of orders a day, well under rate thresholds, but the rules are still changing. Confirm current requirements with Zerodha before going live.
- **Run it on an always-on machine** (a small cloud VM with a static IP, which you'll need for SEBI anyway) under a supervisor like `systemd` with `Restart=on-failure`. Watch `state/*/bot.log` and `trades.csv`.
