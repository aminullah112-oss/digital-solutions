# Kite Algo: Zerodha Kite Connect login + dashboard

A small starter app: **React + Vite** frontend, **Python FastAPI** backend.

- You enter your **API Key**, **API Secret** and **Request Token** on a login page.
- The backend uses the official `kiteconnect` SDK to create the **access token** and saves it on disk. **The browser never sees the access token.**
- The saved token is reused, so restarting the backend or editing code does not log you out.
- A dark-mode dashboard with tabs:
  - **User**: your name, user ID, products and exchanges.
  - **Signals**: a Nifty 100 SMA crossover scanner (see [Signals tab](#signals-tab-sma-crossover-scanner)).
  - **Backtest**: replays the same rule on past prices, with costs and benchmarks (see [Backtest tab](#backtest-tab)).
  - **Algo Signals**: a high-volume breakout and retest scanner, with live prices (see [Algo Signals and GTT Placement](#algo-signals-and-gtt-placement)).
  - **GTT Placement**: a read-only view of what a buy GTT for each signal would look like. **Simulation only unless you switch on live mode (see [Live mode](#live-mode-real-orders-off-by-default)).**

```
kite-algo/
├── backend/            FastAPI + kiteconnect
│   ├── main.py         API endpoints
│   ├── token_store.py  saves/loads the session file
│   ├── nifty100.py     downloads the Nifty 100 list (official NSE CSV)
│   ├── scanner.py      maps symbols to Kite tokens, fetches candles, ranks results
│   ├── signals.py      SMA and crossover maths (pure, easy to read)
│   ├── candles.py      daily OHLC candles with a disk cache (backend/.data/candles/)
│   ├── charges.py      Zerodha delivery charges: edit the rates here
│   ├── backtest.py     the backtest engine (pure, easy to read)
│   ├── backtest_runner.py  gets the data for a backtest and calls the engine
│   ├── scanner_data.py  Nifty 100 candles for the Algo Signals scanner, price snapshot
│   ├── ticks.py        live price websocket (relays Kite's ticker to the browser)
│   ├── gtt_sim.py      the GTT SIMULATION: checks Kite state, writes dummy records
│   ├── broker_guard.py makes every Kite client read-only
│   └── tests/          pytest tests (no real credentials needed)
└── frontend/           React + Vite
    └── src/
        ├── styles/theme.css   colors, fonts, radius: edit this to restyle
        ├── tabs/index.js      list of dashboard tabs: add yours here
        ├── tabs/UserTab.jsx   the User tab
        ├── tabs/SignalsTab.jsx  the Signals tab
        ├── tabs/BacktestTab.jsx the Backtest tab
        ├── tabs/AlgoSignalsTab.jsx, GttPlacementTab.jsx   the two Algo tabs
        ├── lib/breakoutScanner.js  the scanner (pure functions, unit-tested)
        ├── lib/gtt.js              GTT candidate and row helpers (pure, unit-tested)
        ├── state/AlgoContext.jsx   state shared by both Algo tabs (signals, prices, GTT rows)
        ├── components/EquityChart.jsx  the equity curve (plain SVG)
        └── pages/             Login and Dashboard pages
```

## 1. One-time Kite Connect setup

1. Create an app at <https://developers.kite.trade/apps>.
2. Set its **Redirect URL** to exactly:
   ```
   http://localhost:5173/login
   ```
3. Copy the app's **API Key** and **API Secret**.

The redirect URL is what makes the login smooth: after you sign in on Zerodha, Kite sends you back to this app and the **Request Token is filled in for you**.

## 2. Install and run

You need **Python 3.9+** and **Node.js 18+**. Use two terminals.

**Terminal 1: backend**

Windows (PowerShell):
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

macOS / Linux:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and retry.

**Terminal 2: frontend**
```bash
cd frontend
npm install
npm run dev
```

Open **<http://localhost:5173>**.

## 3. Log in

1. Type your **API Key**. An **Open Kite login** link appears under Request Token.
2. Click it, sign in to Zerodha (user ID, password, TOTP). You land back on this app with the Request Token already filled in.
3. Type your **API Secret** and press **Login**.

You are taken to the dashboard.

**Request tokens are single-use and expire within minutes.** If login fails with "Token is invalid or has expired", get a fresh one with the link and try again.

## How "stay logged in" works

The backend writes `api_key` and `access_token` to `backend/.data/session.json` (git-ignored, owner-only permissions on macOS/Linux). On every page load the frontend asks the backend `GET /api/auth/status`, which checks the saved token with Kite. Because the file survives `uvicorn --reload`, code changes don't log you out.

**Kite access tokens expire every day (around 6 AM IST).** When that happens the backend deletes the dead token and the app sends you to the login page. That is a Kite rule; the app can't avoid it.

The **API Secret is never saved.** It is only used once, in memory, to create the token.

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/api/auth/login` | `{api_key, api_secret, request_token}` → creates and saves the token. Returns user id/name only. |
| GET | `/api/auth/status` | Is the saved token still valid? |
| POST | `/api/auth/logout` | Invalidates the token at Kite and deletes the saved file. |
| GET | `/api/profile` | Returns `user_name`, `user_id`, `products`, `exchanges`. |
| POST | `/api/signals/sma-crossover` | `{short_sma, long_sma, lookback_days, max_stocks}` → ranked crossover signals. Slow (see below). |
| POST | `/api/backtest/sma-crossover` | `{short_sma, long_sma, years, max_stocks, starting_capital, max_positions, stop_loss_pct, slippage_pct, include_charges, regime_filter, regime_sma, holdout_pct}` → trades, equity curve, metrics, benchmarks, held-out segments. Slow the first time. |
| POST | `/api/backtest/momentum` | `{lookback_days, skip_days, top_n, keep_rank, years, max_stocks, starting_capital, stop_loss_pct, slippage_pct, include_charges, regime_filter, regime_sma, holdout_pct}` → same shape. Needs about a year more history, so the first run is slower. |
| GET | `/api/scanner-data` | Nifty 100 daily candles with volume for the Algo Signals scanner. Cached for 5 minutes. |
| POST | `/api/scanner-data/refresh` | Rebuild that cache and re-download the newest candles. |
| GET | `/api/ohlc?symbols=A,B` | Latest price snapshot (`last_price`) for NSE symbols. Read-only. |
| WS | `/ws/ticks?tokens=1,2&mode=full` | Live prices for those instrument tokens, relayed from Kite. Read-only. |
| POST | `/api/algo-orders/gtt-state` | Read-only: would each candidate get a buy GTT? Creates nothing. |
| POST | `/api/algo-orders/live-gtt` | Creates **dummy** buy GTT records only. Needs `confirm_live: true`. Never sends anything to Kite. |
| GET | `/api/health` | Liveness check. |

Interactive docs: <http://127.0.0.1:8000/docs>.

## Signals tab (SMA crossover scanner)

Open the **Signals** tab, adjust the inputs, press **Generate Signals**.

| Input | Default | Meaning |
|---|---|---|
| Short SMA | 6 | Fast moving average, in days |
| Long SMA | 30 | Slow moving average, in days. Must be larger than Short SMA |
| Lookback Days | 20 | Only show crossovers from the last N **trading days** (not calendar days) |
| Max Stocks | 100 | Scan the first N stocks of the Nifty 100 list (1 to 100). Use 10 for a quick test |

The results table shows **Rank, Ticker, Company, Crossover Type, Crossover Date, Close, SMA 6, SMA 30** (the SMA headings follow your inputs).

**How it works**

1. The Nifty 100 list comes from the official NSE Indices CSV (`ind_nifty100list.csv`). The backend tries `niftyindices.com` first and falls back to NSE's mirror, `nsearchives.nseindia.com`. It is cached for 24 hours in `backend/.data/`.
2. Each symbol is matched to its Kite NSE equity instrument token. Symbols Kite doesn't list are reported under "stocks were skipped", not hidden.
3. Daily candles are fetched with `kite.historical_data`.
4. A **bullish** crossover is the short SMA moving from below the long SMA to above it. **Bearish** is the reverse. If a stock has several in the window, only its most recent is shown.
5. Rows are ranked by crossover date, newest first (ties sorted by ticker).

**Things to know**

- **Close and SMA values are from the crossover day**, not today.
- **It is slow on purpose.** Kite limits historical data to 3 requests per second, so 100 stocks take about 40 seconds. The backend spaces requests 0.4 s apart. Downloaded candles are reused for 10 minutes, so re-running with different SMA settings is nearly instant.
- **Only one scan runs at a time.** A second one gets a "scan already running" message.
- **Historical data needs a Kite Connect plan that includes it.** If Kite refuses, the tab says so. Check your plan at developers.kite.trade.
- **Market hours:** while NSE is open (9:15 to 15:30 IST) today's candle is still forming, so a crossover dated today can change by the close. The tab shows a warning. The check doesn't know exchange holidays.
- **This is a screener, not advice.** Moving-average crossovers lag price and often misfire in sideways markets. Treat the list as a shortlist to research.
- If NSE renames a stock, the old symbol may not exist in Kite until the list is updated. It shows up as skipped.

## Backtest tab

Open the **Backtest** tab, pick a **Strategy**, adjust the inputs, press **Run Backtest**. It replays the strategy on past Nifty 100 prices and shows what would have happened, after costs, next to two benchmarks.

**Strategies**

| Strategy | What it does | Trades |
|---|---|---|
| **SMA crossover** | Buys the day after the short average crosses above the long one, sells the day after it crosses below. The same rule as the Signals tab. | Often |
| **Momentum rotation** | Once a month, ranks the stocks by past return and holds the top ones, selling any that drop out of the ranking. | Monthly, at most |

| Input | Default | Meaning |
|---|---|---|
| Short SMA / Long SMA | 6 / 30 | Crossover only |
| Max open positions | 10 | Crossover only. Each position gets capital ÷ this |
| Lookback (trading days) | 252 | Momentum only. How far back each stock's return is measured (about a year) |
| Skip latest (trading days) | 21 | Momentum only. The most recent days are ignored when ranking (about a month) |
| Stocks to hold | 10 | Momentum only. Equal money in each |
| Keep until rank (advanced) | 2 × stocks held | Momentum only. A holding is sold only when it falls below this rank, which avoids selling a stock for slipping from 10th to 11th |
| Years of history | 5 | 1 to 5 |
| Max Stocks | 100 | First N stocks of the Nifty 100 list |
| Starting capital | ₹10,00,000 | |
| Stop-loss % (advanced) | Off | Optional, for both strategies |
| Slippage per side % (advanced) | 0.05 | How much worse each fill is than the quoted price |
| Include charges (advanced) | On | Zerodha delivery charges on each buy and sell |
| Regime filter (advanced) | Off | "Only trade in an uptrend", see below |
| Index average (days) | 200 | The Nifty 100 must close above this many days' average |
| Hold out the last % (advanced) | 40 | See "Held-out check" below. 0 turns it off |

**The rules** (agreed in the design review)

1. **Long-only.** Delivery (CNC) can't short. For the crossover, a bullish crossover opens a position and a bearish one closes it.
2. **Next-day open.** Every decision is made at a close and executed at the **open of the next trading day**, never at the close that produced it.
3. **Fixed position size, no compounding.** Each position gets starting capital ÷ slots (max positions, or stocks held for momentum), sized so that shares plus buy charges fit inside it. When all slots are full, new buys are **skipped and counted**; same-day candidates are served in ticker order (crossover) or rank order (momentum).
4. **Stop-loss (optional).** If the day's low touches the stop, the position sells at the stop price, or at the open if the stock gapped below it. If a stop and a strategy exit fall on the same day, the stop wins. A stock stopped out of a momentum portfolio is bought again only at the next monthly rebalance, if it still ranks.
5. **Costs.** Zerodha delivery charges plus slippage. A round trip on ₹1,00,000 costs about ₹340 (0.34%) with the defaults.
6. Positions still open on the last day are sold at that day's close and marked "End of test". Prices exclude dividends, for the strategy and both benchmarks.

**Momentum details.** On the first trading day of each month, and on the first day of the test, stocks are ranked by their return from `lookback` trading days ago to `skip` days ago, using the previous close. Held stocks stay while they rank inside "Keep until rank"; free slots are filled from the top "Stocks to hold", best first. Stocks without enough history yet are not ranked.

**Regime filter.** When on, the Nifty 100 must have closed above its N-day average on the signal day. For the crossover it blocks new buys while the index is below the average (open positions still exit normally, and the skipped signals are counted). For momentum it sells everything at a rebalance when the index is below the average and waits in cash. It needs index history for the whole average, so the first run downloads extra index days.

**Held-out check.** The last N% of the period (40% by default) is reported separately from the first part: strategy and benchmark returns, max drawdown, trades and win rate for each. The chart shades the held-out part. The rule for using it: choose your settings first, look at the held-out column once, and treat any further tweaking as a new test on new data. If you keep changing settings until the held-out numbers look good, you have tuned to that period and it no longer tells you anything. Note that with fixed rules and no fitted parameters it shows consistency across time, not a true out-of-sample proof, and five years is mostly one market regime.

**The results page** shows summary cards (total return and CAGR, both benchmarks, max drawdown, win rate, profit factor, average win/loss, average holding days, costs paid), an equity curve with hover values, and the trades table (newest entry first). Benchmarks: the **Nifty 100 index**, and the **same stocks held equal-weight** from day one. The second one shows how much of the result comes from the stock list rather than the signal.

**Things to know**

- **Survivorship bias.** The test uses today's Nifty 100 members. Stocks that dropped out are missing, which flatters a long-only test, and momentum most of all: stocks that rose are the ones that are in the index today. Kite has no history for delisted stocks, so this can't be fixed with free data. The page says so every time.
- **Possible unadjusted splits.** I don't know whether Kite's daily candles are adjusted for splits and bonuses. A stock with a one-day move above 35% is **excluded and listed**, because an unadjusted split would create fake crossovers and fake losses. Check this against a known split on your own account.
- **Overfitting.** Trying many settings on the same years will find some that look good by luck. There is deliberately no parameter sweep, and the held-out check only helps if you respect it.
- **The first run is slow, later runs are fast.** Candles are saved in `backend/.data/candles/`. The first 5-year run downloads about 100 stocks plus the index at 3 requests per second (about 40 seconds). After that only the newest few days are downloaded, and changing the rules (SMA lengths, slots, stop, costs) needs no download at all. A bigger Long SMA, a momentum lookback or a regime filter needs more history before the start, so only those extra earlier days are downloaded. Long SMAs above about 100, and the momentum strategy (about 250 extra trading days), need a second request per stock the first time, so the first momentum run takes roughly twice as long.
- **Scans and backtests share one lock.** Only one runs at a time, because Kite's rate limit is shared.
- **Edit the charge rates in `backend/charges.py`.** They are my best knowledge of Zerodha's delivery rates, not verified against your account. Compare one trade with Zerodha's brokerage calculator before relying on the numbers.
- **It is not advice.** Don't assume either strategy has an edge; the tab exists to measure whether they do. Past results do not predict future returns.

## Algo Signals and GTT Placement

> **By default, nothing in these two tabs can place, change, cancel or delete a real order or GTT.** "Run Live", the `/api/algo-orders/live-gtt` URL and the `confirm_live` field keep their names for compatibility, but with live mode off (the default) they only write a **dummy record** to `backend/.data/dummy_gtts.json` on your computer. `confirm_live` authorises that simulation and nothing else. Real placement exists, but only when you start the backend with `ALGO_LIVE_ORDERS=1` ([Live mode](#live-mode-real-orders-off-by-default)).
>
> This is enforced in code, not just by convention: every Kite client the backend uses is wrapped by `broker_guard.py`, which allows only `profile`, `get_gtts`, `orders`, `positions`, `holdings`, `instruments`, `ohlc` and `historical_data`. Anything else (for example `place_gtt` or `place_order`) raises an error. The only code that can call `place_gtt` is `backend/live_gtt.py` (one call site), and a test scans the source to keep it that way.

### Algo Signals

A scanner for **high-volume breakouts that are now being retested**. It runs in your browser on the candles from `/api/scanner-data`, with these fixed parameters: volume lookback 20 candles, volume multiplier 3, price lookback 20 candles, maximum breakout age 20 candles, midpoint tolerance 1%.

A stock needs at least 25 daily candles. Starting at the second-last candle and walking back, a candle is a breakout when:

1. its close is above its open,
2. its volume is at least 3 times the average volume of the 20 candles before it,
3. its close is above the highest high of the 20 candles before it,

and afterwards price made a **higher high than the breakout candle's high**. The setup is accepted when the latest close is within **1% of the breakout candle's midpoint** (average of its high and low) and the breakout is at most 20 candles old. Each stock shows at most one setup, its most recent. Results are sorted by age, then by distance from the midpoint, and **the order stays fixed until the scanner runs again**, even while prices move.

The table shows Rank, Symbol, Current Price, Breakout Date, Age, Breakout Vol (like `2.50x`), Retest Distance, Peak Gains and Retracement. **Current Price** is the live websocket price, else the price snapshot, else the latest candle's close. Click a row to highlight it.

**Live prices.** The browser opens one websocket (`/ws/ticks`) for only the stocks currently shown. The backend relays Kite's ticker and keeps its subscriptions in line with what is shown. Both Algo tabs share that one connection. The backend refuses websocket connections from other websites (origin check) and never sends the access token to the browser.

**The data loads when you first open one of the two tabs**, not at login, so it doesn't compete with Signals and Backtest for Kite's rate limit.

### Run Live and GTT Placement

**GTT Placement** is read-only: it has no buttons. Each row is a current Algo Signal, with:

| What | Rule |
|---|---|
| Quantity | 1 |
| Buy | the breakout candle's **low** (never the live price), rounded to the instrument's tick size |
| Stoploss | buy × 0.95, rounded to the tick size. No ATR. It is only ever **planned after buy**: no stoploss order, real or dummy, is created before a buy exists, and no buy is ever simulated as filled |
| State | read from Kite: GTTs, today's orders, positions and holdings |

Tick sizes come from Kite's instrument list, and all price arithmetic uses exact decimals (no floating-point rounding). A stock whose tick size is unknown is shown as invalid, never guessed.

**Run Live** (on the Algo Signals tab) refreshes the scanner data, reruns the scanner, loads a price snapshot, builds the candidates from the fresh signals, checks Kite's state, and then asks the backend to create dummy records for the rows that are clear. A row is **blocked** (no dummy record) when any of these holds, checked in this order:

1. an active buy GTT for the stock already exists (or an active GTT with the same buy trigger),
2. an active dummy GTT already exists for it,
3. a BUY delivery order (CNC) placed today on NSE exists that is not cancelled or rejected,
4. you hold a position or holding in it (settled or T+1 quantity above zero).

A row with no buy price or no live/snapshot price is not created either ("Buy price is not available for this row.", "Waiting for LTP."). **The backend repeats every check itself** under a lock, on a fresh read of the dummy file, so repeated clicks, repeated requests, concurrent requests and backend restarts can never create a second dummy record for the same stock. The server also recomputes the stoploss from the buy price, so a tampered request can't change it.

Dummy records look like real ones (`DUMMY-SIEMENS-000001`, BUY, CNC, NSE, LIMIT, qty 1, trigger price = order price) but are stored only on your computer and never change your Kite account. A stock that leaves Algo Signals leaves the GTT table, while its dummy record stays until you delete the file.

**Things to know**

- **Run one backend process** (the command in this README does). The duplicate lock lives inside the process.
- **Day orders are judged by date in IST.** Kite stamps orders in IST. A time-zone-aware time is converted to IST.
- **If Kite's state can't be read, nothing is created.** The error is shown above both tables.
- **The first Algo Signals load takes about 40 seconds** if the candles aren't saved yet (100 stocks at Kite's 3 requests per second). After a code update the saved candles are in a new format (they now include volume), so the first run after updating downloads them once more.
- **Live prices need `uvicorn[standard]`** (the install in this README includes it), which provides the websocket library.
- The scanner treats a stock whose 20-candle average volume is zero as having no usable average, and drops candles with missing or non-numeric values.
- To forget every dummy record, stop the backend and delete `backend/.data/dummy_gtts.json`.

## Live mode (real orders, off by default)

Live mode lets **Run Live** place **real buy GTT orders** on your Zerodha account. It is off unless you turn it on, and it still asks you to confirm every batch.

**Turn it on** by setting an environment variable in the same PowerShell window before you start the backend:

```powershell
$env:ALGO_LIVE_ORDERS = "1"
uvicorn main:app --port 8000
```

Anything else (unset, `0`, `false`) keeps the simulation. Both tabs show a red **LIVE** badge when it is on.

**What happens**

1. **Run Live** refreshes the scanner, checks Kite's state, and asks the backend for a **preview**. Nothing is placed yet.
2. A dialog lists exactly the orders that would be placed (symbol, qty 1, trigger = limit price, planned stoploss, last price, total value). **Cancel has the focus.** Escape or Cancel places nothing.
3. Only **Place N real GTT orders** sends them. The backend accepts the request only with a single-use preview token (valid 5 minutes) and re-checks everything on a fresh read of your GTTs, orders, positions and holdings. A request without a valid token is refused whatever the page does.

**What is placed:** one single-trigger **BUY** GTT per row: NSE, CNC, LIMIT, quantity 1, trigger price = limit price = the breakout candle's low (rounded to the tick). The same blocking rules as the simulation apply (existing GTT, day order, position or holding, recent live placement), so repeated clicks, restarts and concurrent requests cannot place the same stock twice.

**What is NOT placed: the stoploss.** The stoploss is shown as "planned after buy" and nothing is sent for it. If a buy GTT fires, you hold an unprotected position until you place a stoploss yourself. The app never places one.

**Limits** (backend environment variables, set before `uvicorn`):

| Variable | Default | Meaning |
|---|---|---|
| `ALGO_LIVE_MAX_ORDERS` | 5 (max 20) | orders per run |
| `ALGO_LIVE_MAX_ORDER_VALUE` | 25000 | rupees, per order (price × qty) |
| `ALGO_LIVE_MAX_ORDERS_PER_DAY` | 10 (max 50) | orders per calendar day (IST) |

Rows over a limit are shown as "Skipped: live order limit reached (...)".

**Records.** `backend/.data/live_gtts.json` remembers what was placed (it is read back as a duplicate guard) and `backend/.data/live_gtt_audit.jsonl` logs every attempt, including rejections. If the live log is corrupt the backend refuses to place anything until you fix or delete it.

**Failures.** If Kite rejects one order (for example an invalid trigger), that row shows `Unable to place buy GTT: <Kite's reason>` and the run continues. If the token expires, or the network or an unknown error happens mid-run, the run **stops** and says the remaining orders were not placed, or that the last one "may have been created": check Kite's GTT list before retrying.

**Before you use it with money**

- The strategy is untested with real money. The backtest tab measures history; it does not promise anything.
- I could not test against the real Kite API from the build environment. Kite's own GTT validation (for example, a buy trigger below the current price) may reject orders; the app reports what Kite says. Start with one small order and look at it on Kite web.
- A buy GTT can fill days later at a different market regime. Review and cancel stale GTTs on Kite yourself; this app never cancels or modifies anything.
- Check Zerodha's and SEBI's current rules for API-placed orders (for example static IP requirements) for your account.

## Customize the look

- **Colors, fonts, roundness, page width:** edit the variables in `frontend/src/styles/theme.css`. Every component reads from them. For example, change `--accent` and `--accent-soft` for a new brand color.
- **Layout and components:** `frontend/src/styles/app.css`.
- **Chart colors:** the equity curve lines use `--chart-strategy`, `--chart-index` and `--chart-same` in `theme.css`.
- **Add a tab:** create `frontend/src/tabs/HoldingsTab.jsx`, then add one line to `frontend/src/tabs/index.js`:
  ```js
  { id: "holdings", label: "Holdings", component: HoldingsTab },
  ```
  Add a matching endpoint in `backend/main.py` that uses `_authed_kite()` (it returns a ready-to-use `KiteConnect` client) and call it from the tab with a function in `frontend/src/api.js`.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The tests use a fake Kite client and a saved copy of the NSE CSV, so they need no credentials or internet. They check that the token and secret never appear in a response, that the session survives a restart, that expired tokens are cleared, the SMA and crossover maths (with hand-worked examples), ranking, symbol mapping, rate-limit spacing, caching, and each error path of the scanner.

The frontend has unit tests for the scanner and the GTT helpers (`cd frontend && npm test`, using Node's built-in test runner). The scanner tests build small candle series by hand and check each rule on both sides of its boundary (exactly 3x volume, a higher high that only equals the breakout high, exactly 1% from the midpoint, a breakout 20 versus 21 candles old, and so on). The GTT tests check the exact example from the design (buy 3903.3, stoploss 3708.1 on a 0.1 tick), tick-size rounding in exact decimals, every blocking rule, duplicate prevention under concurrent requests, backend restarts, failed writes and a corrupt store, and that no order-changing Kite method is ever called: a fake Kite fails the test if one is.

The backtest tests check the engine against hand-worked trades (for example 8,333 shares bought at an open of 12 and sold at 8 lose exactly ₹33,332), gap-through-stop fills, charges, slot limits, benchmarks, the candle cache, and invariants that must hold for any run: total profit equals the sum of trade profits, and never more positions are open than slots. The strategy tests check momentum rankings, the skip window, the buffer, the regime filter (re-derived independently from the index prices) and the held-out split against hand-worked numbers.

## Security notes (read these)

- **Run the backend on `127.0.0.1` only**, as shown above. There is no app-level password, so anyone who can reach port 8000 can use your saved Kite session. Don't expose it to a network, a tunnel, or `0.0.0.0`.
- This stores the access token **unencrypted** in `backend/.data/session.json`. That is fine for local development on your own machine. Before using this anywhere shared or hosted, move it to an encrypted store or a secrets manager and add real authentication.
- Never commit `backend/.data/` or any `.env` file. The included `.gitignore` already excludes them.
- The API Secret passes through the browser form once on its way to the backend (over `localhost`). Keep it out of screenshots and chat messages.
- Never paste an access token or API secret into an AI chat or an issue.
- By default this app only reads data (your profile, historical prices, live prices, and your GTTs, orders, positions and holdings) and GTT Placement is a simulation that writes a local file. Only with `ALGO_LIVE_ORDERS=1` can it place buy GTTs, after your confirmation (see Live mode).
- The live price websocket only accepts connections from this app's own pages, and requires you to be logged in. If you add order placement later, add confirmation steps and test with small quantities first; the Kite API has no sandbox.
