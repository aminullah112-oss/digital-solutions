# Kite Algo: project handoff notes

Read this first. `README.md` has the full user guide; this file is the context a new chat needs.

## What this is

A Zerodha Kite Connect dashboard: **FastAPI backend** (`backend/`) + **React/Vite frontend** (`frontend/`). The owner runs it on a Windows PC at `C:\Users\User\kite-algo-repo\kite-algo`. It was built in a cloud session, so nothing here has been tested against the real Kite API from the build environment, only against a fake Kite and stub backends.

## Tabs

| Tab | What it does |
|---|---|
| User | Profile (name, ID, products, exchanges) |
| Signals | Nifty 100 SMA crossover scanner (default SMA 6/30) |
| Backtest | SMA crossover and momentum strategies, regime filter, held-out segments, Zerodha delivery charges, slippage, two benchmarks |
| Algo Signals | High-volume breakout and retest scanner, live prices over a websocket, "Run Live" button |
| GTT Placement | Read-only table of the buy GTT each Algo Signal would get. No buttons |

Login takes API key, secret and request token. The backend exchanges them, saves the access token locally and never sends it to the browser. Tokens expire about 6 AM IST daily.

## Execution modes (the part that matters most)

- **Simulation (default).** Run Live writes dummy records (`DUMMY-...` ids) to `backend/.data/dummy_gtts.json`. No order or GTT is ever sent to Kite. The original spec was "simulate only"; the labels `Run Live`, `/api/algo-orders/live-gtt` and `confirm_live` are kept for compatibility.
- **Live (opt-in).** Only when the backend starts with `ALGO_LIVE_ORDERS=1`. The owner explicitly asked for this ("make it live").

Live-mode rules that must not be weakened:
1. Off unless `ALGO_LIVE_ORDERS` is 1/true/yes/on. Never default it on.
2. Run Live first asks the backend for a **preview** (single-use token, 5-minute expiry), then a dialog lists exactly the orders. Cancel has the focus. Only the explicit confirm button places orders.
3. `place_gtt` has **one call site**, in `backend/live_gtt.py` (`GttWriter.place_buy_gtt`). A static test (`tests/test_no_order_path.py`) enforces this. Every other Kite client goes through `broker_guard.ReadOnlyKite`, which allows only `profile`, `get_gtts`, `orders`, `positions`, `holdings`, `instruments`, `ohlc`, `historical_data`.
4. Order shape: single-trigger BUY, NSE, CNC, LIMIT, **quantity 1**, trigger = limit price = the breakout candle's low, rounded to the tick size with exact decimals.
5. **No stoploss is ever placed.** It's shown as "planned after buy" (buy x 0.95, rounded to tick).
6. Duplicate prevention is in the backend, under a lock, on fresh reads: existing active GTT, dummy record, live record, day BUY order, position or holding.
7. Limits (env vars): `ALGO_LIVE_MAX_ORDERS` (5, cap 20), `ALGO_LIVE_MAX_ORDER_VALUE` (25000), `ALGO_LIVE_MAX_ORDERS_PER_DAY` (10, cap 50).
8. Audit trail: `.data/live_gtts.json`, `.data/live_gtt_audit.jsonl`. A corrupt live log makes the backend refuse to place anything.
9. After an unclear error (token expiry, network) the run stops and says what may have been created. It never retries blindly.

Never ask the user for the API secret, request token or access token in chat.

## Run it (Windows PowerShell)

Backend (needs the venv active, otherwise `uvicorn` is "not recognized"):

```powershell
cd C:\Users\User\kite-algo-repo\kite-algo\backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# optional, only for real orders:
# $env:ALGO_LIVE_ORDERS = "1"
# $env:ALGO_LIVE_MAX_ORDERS = "1"
uvicorn main:app --port 8000
```

Frontend (second window):

```powershell
cd C:\Users\User\kite-algo-repo\kite-algo\frontend
npm install
npm run dev
```

Open http://localhost:5173. Update with `git pull` in `C:\Users\User\kite-algo-repo`. Branch: `claude/zealous-mayer-7xhtna`.

Tests: `cd backend; pytest` (487 pass) and `cd frontend; npm test` (43 pass).

## Code map

Backend (`backend/`): `main.py` (all endpoints, websocket `/ws/ticks`), `live_gtt.py` (the only real-order code), `gtt_sim.py` (state evaluation and dummy store), `broker_guard.py`, `scanner.py` (Nifty 100 SMA scan, shared lock, throttle), `scanner_data.py` and `candles.py` (OHLCV cache in `.data/candles`), `signals.py`, `backtest.py` and `backtest_runner.py`, `charges.py`, `ticks.py`, `nifty100.py`, `token_store.py`.

Frontend (`frontend/src/`): `tabs/` (one file per tab, registered in `tabs/index.js`), `state/AlgoContext.jsx` (Algo/GTT state and the live preview-then-confirm flow), `state/useLiveTicks.js`, `components/LiveConfirmDialog.jsx`, `lib/breakoutScanner.js` and `lib/gtt.js` (pure, unit tested), `api.js`.

## Kite constraints that shaped the design

- Historical data: 3 requests/second, about 2000 days per request (chunked at 1995). The first Algo Signals load takes about 40 s.
- One long-lived KiteTicker (a Twisted reactor can't restart).
- Scans, backtests and scanner-data refreshes share one lock.
- Run a single backend process: the duplicate lock lives in the process.

## Not verified against real Kite

- The live ticker relay and the exact shape of `get_gtts()`.
- Whether `instruments()` returns `tick_size` as the code assumes.
- Kite's GTT validation (for example a BUY trigger below the last price may be rejected). The app shows Kite's message per row.
- Zerodha/SEBI rules for API-placed orders (such as static IP requirements).
- Backtest charge rates are best-knowledge delivery rates; compare with Zerodha's calculator.

## Advice given to the owner

The strategy has no proven edge. The backtest tab exists to measure it, with a regime filter, momentum test and held-out check. A buy GTT can fill days later, and no stoploss is placed, so live use needs manual follow-up on Kite. Start with one small order.
