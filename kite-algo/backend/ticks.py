"""Live ticks: relays Kite's websocket stream (KiteTicker) to the browser.

Browser  --ws-->  GET /ws/ticks?tokens=1,2,3&mode=full  (main.py)  -->  TickHub  -->  KiteTicker

* One KiteTicker connection is shared by every browser connection. Kite allows
  very few connections per API key, and the Twisted reactor under KiteTicker
  can't be restarted inside one process, so the ticker lives as long as the
  backend does.
* Each browser connection only receives ticks for the instrument tokens it
  asked for, and the hub only keeps Kite subscribed to tokens somebody wants.
* The browser never sees the access token. The hub gets credentials from the
  saved session on the backend.
* This is a read-only data stream. Nothing here can place an order.

Messages sent to the browser (JSON text):
    {"type": "status", "connected": true|false, "tokens": 12}
    {"type": "ticks", "ticks": [{"instrument_token": 1, "last_price": 100.5, ...}, ...]}
    {"type": "error", "message": "..."}
"""

import asyncio
import json
import threading
from typing import Callable, Dict, List, Optional, Set

MAX_TOKENS_PER_CLIENT = 200
VALID_MODES = ("ltp", "quote", "full")
_MODE_RANK = {m: i for i, m in enumerate(VALID_MODES)}
QUEUE_SIZE = 200


class Client:
    """One browser connection."""

    def __init__(self, loop: asyncio.AbstractEventLoop, tokens: Set[int], mode: str):
        self.loop = loop
        self.tokens = set(tokens)
        self.mode = mode
        self.queue: "asyncio.Queue[str]" = asyncio.Queue(QUEUE_SIZE)

    def offer(self, message: str) -> None:
        """Queue a message. Runs on the event loop. If the browser is slow, drop the oldest tick: newer ones replace it."""
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(message)

    def post(self, message: str) -> None:
        """Queue a message from any thread."""
        try:
            self.loop.call_soon_threadsafe(self.offer, message)
        except RuntimeError:
            pass  # the event loop is closed: the client is gone


def parse_tokens(raw: str) -> List[int]:
    """'738561,5633' -> [738561, 5633]. Raises ValueError for anything else."""
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    if not parts:
        raise ValueError("No instrument tokens given.")
    if len(parts) > MAX_TOKENS_PER_CLIENT:
        raise ValueError(f"At most {MAX_TOKENS_PER_CLIENT} instrument tokens at a time.")
    tokens = []
    for p in parts:
        if not p.isdigit():
            raise ValueError(f"Not an instrument token: {p[:20]}")
        t = int(p)
        if t not in tokens:
            tokens.append(t)
    return tokens


def _kite_ticker_factory(api_key: str, access_token: str):
    from kiteconnect import KiteTicker

    return KiteTicker(api_key, access_token)


class TickHub:
    def __init__(self, ticker_factory: Optional[Callable] = None):
        self._factory = ticker_factory or _kite_ticker_factory
        self._lock = threading.RLock()
        self._clients: Set[Client] = set()
        self._ticker = None
        self._credentials = None
        self._connected = False
        self._subscribed: Dict[int, str] = {}  # token -> mode currently set on the ticker

    # -------------------------------------------------------------- clients ---
    def register(self, client: Client, api_key: str, access_token: str) -> None:
        with self._lock:
            self._clients.add(client)
            self._ensure_ticker(api_key, access_token)
            self._sync()

    def unregister(self, client: Client) -> None:
        with self._lock:
            self._clients.discard(client)
            self._sync()

    def status_message(self, client: Client) -> str:
        return json.dumps({"type": "status", "connected": self._connected, "tokens": len(client.tokens)})

    # --------------------------------------------------------------- ticker ---
    def _ensure_ticker(self, api_key: str, access_token: str) -> None:
        creds = (api_key, access_token)
        if self._ticker is not None and self._credentials == creds:
            return
        if self._ticker is not None:  # you logged in again: the old connection has a dead token
            try:
                self._ticker.stop_retry()
                self._ticker.close()
            except Exception:
                pass
            self._connected = False
            self._subscribed.clear()
        ticker = self._factory(api_key, access_token)
        ticker.on_ticks = self._on_ticks
        ticker.on_connect = self._on_connect
        ticker.on_close = self._on_close
        ticker.on_error = lambda ws, code, reason: None
        self._ticker, self._credentials = ticker, creds
        ticker.connect(threaded=True)

    def _desired(self) -> Dict[int, str]:
        want: Dict[int, str] = {}
        for c in self._clients:
            for t in c.tokens:
                if t not in want or _MODE_RANK[c.mode] > _MODE_RANK[want[t]]:
                    want[t] = c.mode
        return want

    def _sync(self) -> None:
        """Make Kite's subscriptions match what the connected browsers want."""
        if self._ticker is None or not self._connected:
            return  # _on_connect syncs as soon as the connection is up
        want = self._desired()
        drop = [t for t in self._subscribed if t not in want]
        if drop:
            self._ticker.unsubscribe(drop)
            for t in drop:
                del self._subscribed[t]
        new = [t for t in want if t not in self._subscribed]
        if new:
            self._ticker.subscribe(new)
        for mode in VALID_MODES:
            tokens = [t for t, m in want.items() if m == mode and self._subscribed.get(t) != mode]
            if tokens:
                self._ticker.set_mode(mode, tokens)
                for t in tokens:
                    self._subscribed[t] = mode

    def _on_connect(self, ws, response) -> None:
        with self._lock:
            self._connected = True
            self._subscribed.clear()
            self._sync()
            self._broadcast_status()

    def _on_close(self, ws, code, reason) -> None:
        with self._lock:
            self._connected = False
            self._subscribed.clear()
            self._broadcast_status()

    def _on_ticks(self, ws, ticks) -> None:
        self.dispatch(ticks)

    def _broadcast_status(self) -> None:
        for c in list(self._clients):
            c.post(self.status_message(c))

    # -------------------------------------------------------------- routing ---
    def dispatch(self, ticks: list) -> None:
        """Send each browser the ticks for its own tokens. Called from the ticker's thread."""
        with self._lock:
            clients = list(self._clients)
        for c in clients:
            mine = [t for t in ticks if t.get("instrument_token") in c.tokens]
            if mine:
                c.post(json.dumps({"type": "ticks", "ticks": mine}, default=str))


hub = TickHub()


def get_hub() -> TickHub:
    return hub


def set_ticker_factory(factory: Optional[Callable]) -> TickHub:
    """Replace the hub (tests use this to plug in a fake ticker)."""
    global hub
    hub = TickHub(factory)
    return hub
