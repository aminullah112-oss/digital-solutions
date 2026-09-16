"""In-memory live value cache and trend buffers.

Polling at 1 Hz across a dozen controllers is tens of thousands of rows an
hour.  Writing every sample to Postgres synchronously would make the database
the bottleneck and buy nothing: the recent window is what a technician looks
at, and it is needed in milliseconds.  So the recent window lives in memory as
a ring buffer, and only decimated samples and discrete transitions go to the
database.
"""
from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import Any

from ..config import settings
from .normalization import apply_staleness


class ValueStore:
    def __init__(self, depth: int | None = None) -> None:
        self._depth = depth or settings.history_depth
        self._latest: dict[int, dict[str, dict]] = defaultdict(dict)
        self._history: dict[tuple[int, str], deque[tuple[float, float]]] = {}
        self._lock = threading.RLock()

    # --- writes -----------------------------------------------------------
    def update(self, controller_id: int, values: dict[str, dict]) -> dict[str, dict]:
        """Store a poll result; returns the envelopes that changed."""
        changed: dict[str, dict] = {}
        with self._lock:
            current = self._latest[controller_id]
            for key, env in values.items():
                previous = current.get(key)
                current[key] = env
                if previous is None or previous.get("value") != env.get("value") \
                        or previous.get("quality") != env.get("quality"):
                    changed[key] = env
                value = env.get("value")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    buf = self._history.setdefault((controller_id, key), deque(maxlen=self._depth))
                    buf.append((_epoch(env["timestamp"]), float(value)))
                elif isinstance(value, bool):
                    buf = self._history.setdefault((controller_id, key), deque(maxlen=self._depth))
                    buf.append((_epoch(env["timestamp"]), 1.0 if value else 0.0))
        return changed

    def clear(self, controller_id: int) -> None:
        with self._lock:
            self._latest.pop(controller_id, None)

    # --- reads ------------------------------------------------------------
    def latest(self, controller_id: int) -> dict[str, dict]:
        with self._lock:
            return {k: apply_staleness(v) for k, v in self._latest.get(controller_id, {}).items()}

    def get(self, controller_id: int, key: str) -> dict | None:
        with self._lock:
            env = self._latest.get(controller_id, {}).get(key)
        return apply_staleness(env) if env else None

    def history(
        self, controller_id: int, key: str, *, seconds: float | None = None,
        max_points: int = 1200,
    ) -> list[dict[str, Any]]:
        with self._lock:
            buf = list(self._history.get((controller_id, key), ()))
        if not buf:
            return []
        if seconds:
            cutoff = buf[-1][0] - seconds
            buf = [p for p in buf if p[0] >= cutoff]
        if len(buf) > max_points:
            step = len(buf) / max_points
            buf = [buf[int(i * step)] for i in range(max_points)]
        return [{"t": t, "v": v} for t, v in buf]

    def statistics(self, controller_id: int, key: str, *, seconds: float | None = None) -> dict:
        points = [p["v"] for p in self.history(controller_id, key, seconds=seconds, max_points=10**6)]
        if not points:
            return {"count": 0}
        return {
            "count": len(points),
            "min": min(points),
            "max": max(points),
            "avg": sum(points) / len(points),
            "last": points[-1],
        }

    def keys(self, controller_id: int) -> list[str]:
        with self._lock:
            return sorted(self._latest.get(controller_id, {}))


def _epoch(iso: str) -> float:
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


store = ValueStore()
