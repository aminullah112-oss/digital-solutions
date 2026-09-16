"""WebSocket fan-out.

One hub, topic per controller plus a broadcast topic. The poller runs in a
worker thread, so messages are handed to the event loop with
`call_soon_threadsafe` rather than touched directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("powertrace.ws")


class Hub:
    def __init__(self) -> None:
        self._topics: dict[str, set[WebSocket]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, topic: str, ws: WebSocket) -> None:
        await ws.accept()
        self._topics.setdefault(topic, set()).add(ws)

    def disconnect(self, topic: str, ws: WebSocket) -> None:
        self._topics.get(topic, set()).discard(ws)

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in list(self._topics.get(topic, ())):
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001 - client vanished
                dead.append(ws)
        for ws in dead:
            self.disconnect(topic, ws)

    def publish_threadsafe(self, topic: str, message: dict[str, Any]) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self.publish(topic, message))
        )


hub = Hub()


def broadcast_from_poller(controller_id: int, message: dict[str, Any]) -> None:
    hub.publish_threadsafe(f"controller:{controller_id}", message)
    hub.publish_threadsafe("all", message)
