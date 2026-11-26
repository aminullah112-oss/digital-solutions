"""FastAPI backend for Zerodha Kite Connect login.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000

Security rules this file follows:
  * The access token is saved on disk (see token_store.py) and is NEVER put in
    any API response.
  * The API secret is used once to create the session and is never stored,
    logged, or returned.
  * Bind to 127.0.0.1 (the default below in the README) so only your own
    computer can reach this API. There is no app-level password, so do not
    expose it to a network.
"""

import asyncio
import json
import os
from decimal import Decimal
from typing import List

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
from kiteconnect import exceptions as kite_exc
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, model_validator

import backtest
import backtest_runner
import broker_guard
import gtt_sim
import nifty100
import scanner
import scanner_data
import ticks
import token_store

app = FastAPI(title="Kite Connect Login API")

# The Vite dev server proxies /api to this app, so CORS is normally not needed.
# These origins only matter if you call the API straight from the browser.
_origins = os.environ.get(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
ALLOWED_ORIGINS = [o.strip() for o in _origins if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

KITE_TIMEOUT_SECONDS = 15


# ---------------------------------------------------------------- helpers ---
class SessionExpired(Exception):
    """Saved token is missing, or Kite says it is no longer valid."""


def _authed_kite():
    """The logged-in Kite client, wrapped so it can only READ (see broker_guard.py)."""
    session = token_store.load_session()
    if not session:
        raise SessionExpired()
    kite = KiteConnect(api_key=session["api_key"], timeout=KITE_TIMEOUT_SECONDS)
    kite.set_access_token(session["access_token"])
    return broker_guard.ReadOnlyKite(kite)


def _fetch_profile() -> dict:
    """Call Kite's profile API with the saved token.

    Raises SessionExpired if there is no valid session (and deletes the dead
    token so we don't keep retrying it), or HTTPException(502) for other
    Kite / network problems.
    """
    kite = _authed_kite()
    try:
        return kite.profile()
    except kite_exc.TokenException:
        # Kite tokens expire every day (around 6 AM IST), so this is normal.
        token_store.clear_session()
        raise SessionExpired()
    except kite_exc.KiteException as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}")
    except Exception:
        raise HTTPException(status_code=502, detail="Could not reach Kite. Check your internet.")


def _expired_http_error() -> HTTPException:
    return HTTPException(status_code=401, detail="Session expired. Please log in again.")


# ----------------------------------------------------------------- models ---
class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    api_key: str = Field(min_length=1, max_length=64)
    # SecretStr keeps the value out of logs and error messages by accident.
    api_secret: SecretStr
    request_token: str = Field(min_length=1, max_length=128)


class SmaCrossoverRequest(BaseModel):
    short_sma: int = Field(6, ge=2, le=200)
    long_sma: int = Field(30, ge=3, le=400)
    lookback_days: int = Field(20, ge=1, le=250)  # trading days
    max_stocks: int = Field(100, ge=1, le=100)

    @model_validator(mode="after")
    def short_must_be_shorter(self):
        if self.short_sma >= self.long_sma:
            raise ValueError("Short SMA must be smaller than Long SMA.")
        return self


class BacktestRequest(BaseModel):
    short_sma: int = Field(6, ge=2, le=200)
    long_sma: int = Field(30, ge=3, le=400)
    years: int = Field(5, ge=1, le=5)
    max_stocks: int = Field(100, ge=1, le=100)
    starting_capital: float = Field(1_000_000, ge=10_000, le=1_000_000_000)
    max_positions: int = Field(10, ge=1, le=100)
    stop_loss_pct: Optional[float] = Field(None, gt=0, le=50)  # None = no stop-loss
    slippage_pct: float = Field(0.05, ge=0, le=2)
    include_charges: bool = True
    regime_filter: bool = False  # only open positions while the Nifty 100 is above its average
    regime_sma: int = Field(200, ge=20, le=400)
    holdout_pct: int = Field(40, ge=0, le=80)  # report the last N% of the period separately; 0 = off

    @model_validator(mode="after")
    def short_must_be_shorter(self):
        if self.short_sma >= self.long_sma:
            raise ValueError("Short SMA must be smaller than Long SMA.")
        return self


class MomentumRequest(BaseModel):
    lookback_days: int = Field(252, ge=20, le=500)  # trading days, about 12 months
    skip_days: int = Field(21, ge=0, le=60)  # ignore the latest ~month
    top_n: int = Field(10, ge=1, le=50)  # stocks held
    keep_rank: Optional[int] = Field(None, ge=1, le=100)  # keep a holding while it ranks this well (default 2 x top_n)
    years: int = Field(5, ge=1, le=5)
    max_stocks: int = Field(100, ge=1, le=100)
    starting_capital: float = Field(1_000_000, ge=10_000, le=1_000_000_000)
    stop_loss_pct: Optional[float] = Field(None, gt=0, le=50)
    slippage_pct: float = Field(0.05, ge=0, le=2)
    include_charges: bool = True
    regime_filter: bool = False
    regime_sma: int = Field(200, ge=20, le=400)
    holdout_pct: int = Field(40, ge=0, le=80)

    @model_validator(mode="after")
    def check_relations(self):
        if self.skip_days >= self.lookback_days:
            raise ValueError("Skip days must be smaller than the lookback.")
        if self.keep_rank is not None and self.keep_rank < self.top_n:
            raise ValueError("Keep-until rank can't be smaller than the number of stocks held.")
        return self


# -------------------------------------------------------------- endpoints ---
# These are plain `def` (not `async def`) on purpose: the Kite SDK makes
# blocking network calls, and FastAPI runs plain `def` endpoints in a thread
# pool so one slow call doesn't freeze the whole server.


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/auth/login")
def login(body: LoginRequest):
    api_secret = body.api_secret.get_secret_value().strip()
    if not api_secret:
        raise HTTPException(status_code=422, detail="API secret is required.")

    kite = KiteConnect(api_key=body.api_key, timeout=KITE_TIMEOUT_SECONDS)
    try:
        data = kite.generate_session(body.request_token, api_secret=api_secret)
    except kite_exc.KiteException as exc:
        # Typical causes: wrong secret, or the request token was already used
        # / has expired (it is single-use and lasts only a few minutes).
        raise HTTPException(status_code=400, detail=f"Kite rejected the login: {exc}")
    except Exception:
        raise HTTPException(status_code=502, detail="Could not reach Kite. Check your internet.")

    token_store.save_session(
        api_key=body.api_key,
        access_token=data["access_token"],
        user_id=data.get("user_id"),
    )
    # Deliberately no token in the response.
    return {"logged_in": True, "user_id": data.get("user_id"), "user_name": data.get("user_name")}


@app.get("/api/auth/status")
def auth_status():
    """Is there a saved session that Kite still accepts?

    The frontend calls this on page load. Because the token is saved on disk,
    a page refresh or a backend reload keeps you logged in.
    """
    if not token_store.load_session():
        return {"logged_in": False}
    try:
        profile = _fetch_profile()
    except SessionExpired:
        return {"logged_in": False, "reason": "expired"}
    return {
        "logged_in": True,
        "user_id": profile.get("user_id"),
        "user_name": profile.get("user_name"),
    }


@app.post("/api/auth/logout")
def logout():
    session = token_store.load_session()
    if session:
        # Best effort: also tell Kite to kill the token.
        try:
            kite = KiteConnect(api_key=session["api_key"], timeout=KITE_TIMEOUT_SECONDS)
            kite.invalidate_access_token(session["access_token"])
        except Exception:
            pass
    token_store.clear_session()
    return {"logged_in": False}


@app.get("/api/profile")
def profile():
    try:
        data = _fetch_profile()
    except SessionExpired:
        raise _expired_http_error()
    # Only return the fields the dashboard needs.
    return {
        "user_name": data.get("user_name"),
        "user_id": data.get("user_id"),
        "products": data.get("products") or [],
        "exchanges": data.get("exchanges") or [],
    }


@app.post("/api/signals/sma-crossover")
def sma_crossover(body: SmaCrossoverRequest):
    """Scan the Nifty 100 for SMA crossovers, newest first.

    This takes a while (about 0.4 s per stock) because Kite limits historical
    data requests to 3 per second.
    """
    try:
        kite = _authed_kite()
    except SessionExpired:
        raise _expired_http_error()

    try:
        return scanner.run_scan(
            kite,
            short_sma=body.short_sma,
            long_sma=body.long_sma,
            lookback_days=body.lookback_days,
            max_stocks=body.max_stocks,
        )
    except scanner.ScanBusy:
        raise HTTPException(status_code=409, detail="A scan is already running. Wait for it to finish.")
    except scanner.HistoricalAccessDenied:
        raise HTTPException(
            status_code=403,
            detail=(
                "Kite refused the historical data request. Your Kite Connect app probably "
                "doesn't include the Historical Data add-on. Check your plan on developers.kite.trade."
            ),
        )
    except kite_exc.TokenException:
        token_store.clear_session()
        raise _expired_http_error()
    except nifty100.ConstituentsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except kite_exc.KiteException as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}")
    except Exception:
        raise HTTPException(status_code=502, detail="Scan failed. Check your internet connection and try again.")


def _run_backtest(fn):
    """Shared by both backtest routes: login check, then one run with friendly errors."""
    try:
        kite = _authed_kite()
    except SessionExpired:
        raise _expired_http_error()

    try:
        return fn(kite)
    except scanner.ScanBusy:
        raise HTTPException(status_code=409, detail="A scan or backtest is already running. Wait for it to finish.")
    except scanner.HistoricalAccessDenied:
        raise HTTPException(
            status_code=403,
            detail=(
                "Kite refused the historical data request. Your Kite Connect app probably "
                "doesn't include the Historical Data add-on. Check your plan on developers.kite.trade."
            ),
        )
    except kite_exc.TokenException:
        token_store.clear_session()
        raise _expired_http_error()
    except (nifty100.ConstituentsError, backtest_runner.NoUsableData, backtest.NoDataError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except kite_exc.KiteException as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}")
    except Exception:
        raise HTTPException(status_code=502, detail="Backtest failed. Check your internet connection and try again.")


@app.post("/api/backtest/sma-crossover")
def sma_crossover_backtest(body: BacktestRequest):
    """Replay the SMA crossover rule over the last N years of Nifty 100 prices.

    The first run downloads prices (about 0.4 s per stock, Kite's rate limit).
    Prices are then saved on disk, so later runs are much faster.
    """
    return _run_backtest(lambda kite: backtest_runner.run_backtest(kite, **body.model_dump()))


@app.post("/api/backtest/momentum")
def momentum_backtest(body: MomentumRequest):
    """Monthly momentum rotation: hold the top-ranked Nifty 100 stocks by past return.

    Needs about a year more history than the crossover test, so the first run
    downloads more and takes longer.
    """
    return _run_backtest(lambda kite: backtest_runner.run_momentum_backtest(kite, **body.model_dump()))


# ====================================================== Algo Signals data ====
def _guarded(fn):
    """Login check, then one call with friendly errors. Used by the read-only Algo Signals / GTT endpoints."""
    try:
        kite = _authed_kite()
    except SessionExpired:
        raise _expired_http_error()
    try:
        return fn(kite)
    except scanner.ScanBusy:
        raise HTTPException(status_code=409, detail="A scan, backtest or scanner refresh is already running. Wait for it to finish.")
    except scanner.HistoricalAccessDenied:
        raise HTTPException(
            status_code=403,
            detail=(
                "Kite refused the historical data request. Your Kite Connect app probably "
                "doesn't include the Historical Data add-on. Check your plan on developers.kite.trade."
            ),
        )
    except kite_exc.TokenException:
        token_store.clear_session()
        raise _expired_http_error()
    except nifty100.ConstituentsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except gtt_sim.DummyStoreError as exc:
        raise HTTPException(status_code=500, detail=f"Dummy GTT store problem: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except kite_exc.KiteException as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}")
    except Exception:
        raise HTTPException(status_code=502, detail="Request failed. Check your internet connection and try again.")


@app.get("/api/scanner-data")
def get_scanner_data(days: int = Query(scanner_data.DEFAULT_DAYS, ge=scanner_data.MIN_DAYS, le=scanner_data.MAX_DAYS)):
    """Nifty 100 daily candles (with volume) for the Algo Signals scanner. Cached for 5 minutes."""
    return _guarded(lambda kite: scanner_data.get_scanner_data(kite, days=days))


@app.post("/api/scanner-data/refresh")
def refresh_scanner_data(days: int = Query(scanner_data.DEFAULT_DAYS, ge=scanner_data.MIN_DAYS, le=scanner_data.MAX_DAYS)):
    """Rebuild the scanner response and re-download the newest candles."""
    return _guarded(lambda kite: scanner_data.get_scanner_data(kite, days=days, force=True))


@app.get("/api/ohlc")
def get_ohlc_snapshot(symbols: str = Query(..., min_length=1, max_length=4000, description="Comma-separated NSE symbols")):
    """Latest price snapshot (last_price and OHLC) for NSE symbols. Read-only."""
    return _guarded(lambda kite: {"prices": scanner_data.ohlc_snapshot(kite, symbols.split(","))})


# ================================================== GTT placement (DUMMY) ====
class GttOrder(BaseModel):
    """One GTT candidate. Prices are Decimals so rounding is exact."""

    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str = Field(pattern=r"^[A-Za-z0-9&\-]{1,20}$")
    quantity: int = 1
    buy_price: Optional[Decimal] = None
    stoploss: Optional[Decimal] = None  # accepted for compatibility; the server computes its own (buy x 0.95)
    last_price: Optional[Decimal] = None


class GttStateRequest(BaseModel):
    orders: List[GttOrder] = Field(max_length=100)


class LiveGttRequest(GttStateRequest):
    # Kept for compatibility. It authorises DUMMY records only; it can never enable real placement.
    confirm_live: StrictBool = False


def _gtt_results(kite, orders: List[GttOrder], create: bool) -> dict:
    """Read Kite's state (read-only), then check, or check-and-create dummy records."""
    state = gtt_sim.KiteState.read(kite)  # if this fails nothing is created
    instruments = scanner.get_instruments(kite)
    wanted = {o.symbol.upper() for o in orders}
    tick_sizes = {sym: instruments[sym].get("tick_size") for sym in wanted if sym in instruments}
    today = scanner.now_ist().date()
    rows = [o.model_dump() for o in orders]
    results = gtt_sim.create_dummy_orders(rows, state, tick_sizes, today) if create else gtt_sim.check_orders(rows, state, tick_sizes, today)
    return {"dummy": True, "message": "Simulation only: no order is ever sent to Kite.", "results": results}


@app.post("/api/algo-orders/gtt-state")
def gtt_state(body: GttStateRequest):
    """Read-only: would each candidate get a buy GTT? Creates nothing, sends nothing."""
    return _guarded(lambda kite: _gtt_results(kite, body.orders, create=False))


@app.post("/api/algo-orders/live-gtt")
def live_gtt(body: LiveGttRequest):
    """Create DUMMY buy GTT records for candidates that pass every check.

    The name and `confirm_live` are kept for compatibility. This never sends an
    order or a GTT to Kite: it only writes a local record (backend/.data/dummy_gtts.json).
    """
    if body.confirm_live is not True:
        raise HTTPException(
            status_code=400,
            detail="confirm_live must be true. (It only authorises dummy simulation: no order is ever sent to Kite.)",
        )
    return _guarded(lambda kite: _gtt_results(kite, body.orders, create=True))


# ================================================================ live ticks ====
@app.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket):
    """Live prices for the instrument tokens in ?tokens=1,2,3 (&mode=full|quote|ltp). Read-only."""
    # A web page on another site must not be able to open this stream.
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return
    session = token_store.load_session()
    if not session:
        await websocket.close(code=4401)  # not logged in
        return

    await websocket.accept()
    mode = websocket.query_params.get("mode", "full")
    try:
        if mode not in ticks.VALID_MODES:
            raise ValueError("mode must be ltp, quote or full.")
        tokens = ticks.parse_tokens(websocket.query_params.get("tokens", ""))
    except ValueError as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        await websocket.close(code=1008)
        return

    hub = ticks.get_hub()
    client = ticks.Client(asyncio.get_running_loop(), set(tokens), mode)
    try:
        hub.register(client, session["api_key"], session["access_token"])
    except Exception:
        await websocket.send_text(json.dumps({"type": "error", "message": "Could not start the live price connection."}))
        await websocket.close(code=1011)
        return
    try:
        await websocket.send_text(hub.status_message(client))

        async def pump():
            while True:
                await websocket.send_text(await client.queue.get())

        async def watch():
            try:
                while True:
                    await websocket.receive_text()  # the browser sends nothing; this notices when it leaves
            except WebSocketDisconnect:
                pass

        tasks = {asyncio.create_task(pump()), asyncio.create_task(watch())}
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    except Exception:
        pass
    finally:
        hub.unregister(client)
