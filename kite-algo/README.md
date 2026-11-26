# Kite Algo: Zerodha Kite Connect login + dashboard

A small starter app: **React + Vite** frontend, **Python FastAPI** backend.

- You enter your **API Key**, **API Secret** and **Request Token** on a login page.
- The backend uses the official `kiteconnect` SDK to create the **access token** and saves it on disk. **The browser never sees the access token.**
- The saved token is reused, so restarting the backend or editing code does not log you out.
- A dark-mode dashboard with tabs:
  - **User**: your name, user ID, products and exchanges.
  - **Signals**: a Nifty 100 SMA crossover scanner (see [Signals tab](#signals-tab-sma-crossover-scanner)).
  - **Backtest**: replays the same rule on past prices, with costs and benchmarks (see [Backtest tab](#backtest-tab)).

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
│   └── tests/          pytest tests (no real credentials needed)
└── frontend/           React + Vite
    └── src/
        ├── styles/theme.css   colors, fonts, radius: edit this to restyle
        ├── tabs/index.js      list of dashboard tabs: add yours here
        ├── tabs/UserTab.jsx   the User tab
        ├── tabs/SignalsTab.jsx  the Signals tab
        ├── tabs/BacktestTab.jsx the Backtest tab
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
| POST | `/api/backtest/sma-crossover` | `{short_sma, long_sma, years, max_stocks, starting_capital, max_positions, stop_loss_pct, slippage_pct, include_charges}` → trades, equity curve, metrics, benchmarks. Slow the first time. |
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

Open the **Backtest** tab, adjust the inputs, press **Run Backtest**. It replays the Signals rule on past Nifty 100 prices and shows what would have happened, after costs, next to two benchmarks.

| Input | Default | Meaning |
|---|---|---|
| Short SMA / Long SMA | 6 / 30 | Same as the Signals tab |
| Years of history | 5 | 1 to 5 |
| Max Stocks | 100 | First N stocks of the Nifty 100 list |
| Starting capital | ₹10,00,000 | |
| Max open positions | 10 | Each position gets capital ÷ this (₹1,00,000 by default) |
| Stop-loss % (advanced) | Off | Optional |
| Slippage per side % (advanced) | 0.05 | How much worse each fill is than the quoted price |
| Include charges (advanced) | On | Zerodha delivery charges on each buy and sell |

**The rules** (agreed in the design review)

1. **Long-only.** A bullish crossover opens a position; a bearish one closes it. Delivery (CNC) can't short.
2. **Next-day open.** A crossover is only known at the close, so the trade happens at the **open of the next trading day**, never at the close that produced the signal.
3. **Fixed position size, no compounding.** Each position gets starting capital ÷ max positions, sized so that shares plus buy charges fit inside it. When all slots are full, new signals are **skipped and counted**; same-day signals are served in ticker order.
4. **Stop-loss (optional).** If the day's low touches the stop, the position sells at the stop price, or at the open if the stock gapped below it. If a stop and a bearish exit fall on the same day, the stop wins.
5. **Costs.** Zerodha delivery charges plus slippage. A round trip on ₹1,00,000 costs about ₹340 (0.34%) with the defaults.
6. Positions still open on the last day are sold at that day's close and marked "End of test". Prices exclude dividends, for the strategy and both benchmarks.

**The results page** shows summary cards (total return and CAGR, both benchmarks, max drawdown, win rate, profit factor, average win/loss, average holding days, costs paid), an equity curve with hover values, and the trades table (newest entry first). Benchmarks: the **Nifty 100 index**, and the **same stocks held equal-weight** from day one. The second one shows how much of the result comes from the stock list rather than the signal.

**Things to know**

- **Survivorship bias.** The test uses today's Nifty 100 members. Stocks that dropped out are missing, which flatters a long-only test. Kite has no history for delisted stocks, so this can't be fixed with free data. The page says so every time.
- **Possible unadjusted splits.** I don't know whether Kite's daily candles are adjusted for splits and bonuses. A stock with a one-day move above 35% is **excluded and listed**, because an unadjusted split would create fake crossovers and fake losses. Check this against a known split on your own account.
- **Overfitting.** Trying many SMA lengths on the same years will find one that looks good by luck. There is deliberately no parameter sweep.
- **The first run is slow, later runs are fast.** Candles are saved in `backend/.data/candles/`. The first 5-year run downloads about 100 stocks plus the index at 3 requests per second (about 40 seconds). After that only the newest few days are downloaded, and changing the rules (SMA lengths, slots, stop, costs) needs no download at all. A bigger Long SMA needs a little more history before the start, so only those extra earlier days are downloaded. Long SMAs above about 100 may need a second request per stock.
- **Scans and backtests share one lock.** Only one runs at a time, because Kite's rate limit is shared.
- **Edit the charge rates in `backend/charges.py`.** They are my best knowledge of Zerodha's delivery rates, not verified against your account. Compare one trade with Zerodha's brokerage calculator before relying on the numbers.
- **It is not advice.** Don't assume the crossover rule has an edge; the tab exists to measure whether it does. Past results do not predict future returns.

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

The backtest tests check the engine against hand-worked trades (for example 8,333 shares bought at an open of 12 and sold at 8 lose exactly ₹33,332), gap-through-stop fills, charges, slot limits, benchmarks, the candle cache, and invariants that must hold for any run: total profit equals the sum of trade profits, and never more positions are open than slots.

## Security notes (read these)

- **Run the backend on `127.0.0.1` only**, as shown above. There is no app-level password, so anyone who can reach port 8000 can use your saved Kite session. Don't expose it to a network, a tunnel, or `0.0.0.0`.
- This stores the access token **unencrypted** in `backend/.data/session.json`. That is fine for local development on your own machine. Before using this anywhere shared or hosted, move it to an encrypted store or a secrets manager and add real authentication.
- Never commit `backend/.data/` or any `.env` file. The included `.gitignore` already excludes them.
- The API Secret passes through the browser form once on its way to the backend (over `localhost`). Keep it out of screenshots and chat messages.
- Never paste an access token or API secret into an AI chat or an issue.
- This app only reads data (your profile and historical prices). It does not place orders. If you add order placement later, add confirmation steps and test with small quantities first; the Kite API has no sandbox.
