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
from pydantic import BaseModel, ConfigDict, Field, SecretStr

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
