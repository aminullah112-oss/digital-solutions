# Kite Algo: Zerodha Kite Connect login + dashboard

A small starter app: **React + Vite** frontend, **Python FastAPI** backend.

- You enter your **API Key**, **API Secret** and **Request Token** on a login page.
- The backend uses the official `kiteconnect` SDK to create the **access token** and saves it on disk. **The browser never sees the access token.**
- The saved token is reused, so restarting the backend or editing code does not log you out.
- A dark-mode dashboard with tabs:
  - **User**: your name, user ID, products and exchanges.
  - **Signals**: a Nifty 100 SMA crossover scanner (see [Signals tab](#signals-tab-sma-crossover-scanner)).

```
kite-algo/
├── backend/            FastAPI + kiteconnect
│   ├── main.py         API endpoints
│   ├── token_store.py  saves/loads the session file
│   ├── nifty100.py     downloads the Nifty 100 list (official NSE CSV)
│   ├── scanner.py      maps symbols to Kite tokens, fetches candles, ranks results
│   ├── signals.py      SMA and crossover maths (pure, easy to read)
│   └── tests/          pytest tests (no real credentials needed)
└── frontend/           React + Vite
    └── src/
        ├── styles/theme.css   colors, fonts, radius: edit this to restyle
        ├── tabs/index.js      list of dashboard tabs: add yours here
        ├── tabs/UserTab.jsx   the User tab
        ├── tabs/SignalsTab.jsx  the Signals tab
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

## Customize the look

- **Colors, fonts, roundness, page width:** edit the variables in `frontend/src/styles/theme.css`. Every component reads from them. For example, change `--accent` and `--accent-soft` for a new brand color.
- **Layout and components:** `frontend/src/styles/app.css`.
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

## Security notes (read these)

- **Run the backend on `127.0.0.1` only**, as shown above. There is no app-level password, so anyone who can reach port 8000 can use your saved Kite session. Don't expose it to a network, a tunnel, or `0.0.0.0`.
- This stores the access token **unencrypted** in `backend/.data/session.json`. That is fine for local development on your own machine. Before using this anywhere shared or hosted, move it to an encrypted store or a secrets manager and add real authentication.
- Never commit `backend/.data/` or any `.env` file. The included `.gitignore` already excludes them.
- The API Secret passes through the browser form once on its way to the backend (over `localhost`). Keep it out of screenshots and chat messages.
- Never paste an access token or API secret into an AI chat or an issue.
- This app only reads data (your profile and historical prices). It does not place orders. If you add order placement later, add confirmation steps and test with small quantities first; the Kite API has no sandbox.
