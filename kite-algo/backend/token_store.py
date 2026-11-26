"""Tiny file-based store for the Kite session.

Why a file?  `uvicorn --reload` restarts the Python process on every code
change, so anything kept only in memory is lost. A small JSON file survives
restarts, which means you don't have to log in again after each edit.

What is saved:  api_key, access_token, user_id.
What is NOT saved:  api_secret (it is only needed once, to create the token).

The file lives in backend/.data/ which is git-ignored. Override the location
with the KITE_SESSION_FILE environment variable.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path(__file__).resolve().parent / ".data" / "session.json"
_REQUIRED_KEYS = ("api_key", "access_token")


def _path() -> Path:
    return Path(os.environ.get("KITE_SESSION_FILE") or DEFAULT_PATH)


def save_session(api_key: str, access_token: str, user_id: Optional[str]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_key": api_key,
        "access_token": access_token,
        "user_id": user_id,
        "saved_at": int(time.time()),
    }
    # Write to a temp file first, then swap it in, so a crash mid-write can
    # never leave a half-written (corrupt) session file behind.
    tmp = path.with_suffix(".tmp")
    # 0o600 = only the current OS user can read it (no effect on Windows).
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, path)


def load_session() -> Optional[dict]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not all(data.get(k) for k in _REQUIRED_KEYS):
        return None
    return data


def clear_session() -> None:
    try:
        _path().unlink()
    except FileNotFoundError:
        pass
