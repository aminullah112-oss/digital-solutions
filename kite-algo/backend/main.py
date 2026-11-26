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

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
from kiteconnect import exceptions as kite_exc
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

import backtest
import backtest_runner
import nifty100
import scanner
import token_store

app = FastAPI(title="Kite Connect Login API")

# The Vite dev server proxies /api to this app, so CORS is normally not needed.
# These origins only matter if you call the API straight from the browser.
_origins = os.environ.get(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

KITE_TIMEOUT_SECONDS = 15


# ---------------------------------------------------------------- helpers ---
class SessionExpired(Exception):
    """Saved token is missing, or Kite says it is no longer valid."""


def _authed_kite() -> KiteConnect:
    session = token_store.load_session()
    if not session:
        raise SessionExpired()
    kite = KiteConnect(api_key=session["api_key"], timeout=KITE_TIMEOUT_SECONDS)
    kite.set_access_token(session["access_token"])
    return kite


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

    @model_validator(mode="after")
    def short_must_be_shorter(self):
        if self.short_sma >= self.long_sma:
            raise ValueError("Short SMA must be smaller than Long SMA.")
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


@app.post("/api/backtest/sma-crossover")
def sma_crossover_backtest(body: BacktestRequest):
    """Replay the SMA crossover rule over the last N years of Nifty 100 prices.

    The first run downloads prices (about 0.4 s per stock, Kite's rate limit).
    Prices are then saved on disk, so later runs are much faster.
    """
    try:
        kite = _authed_kite()
    except SessionExpired:
        raise _expired_http_error()

    try:
        return backtest_runner.run_backtest(kite, **body.model_dump())
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
