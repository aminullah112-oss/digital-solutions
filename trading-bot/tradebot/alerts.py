"""Push alerts and a heartbeat, so problems reach a phone instead of a log file.

Channels (each enabled by its environment variables; secrets never go in config):
  Telegram  TRADEBOT_TELEGRAM_TOKEN + TRADEBOT_TELEGRAM_CHAT
  Webhook   TRADEBOT_WEBHOOK_URL   (JSON {"text": ...}; works with Slack/Discord-style
                                    hooks, or ntfy.sh topic URLs which accept the body)
  Heartbeat TRADEBOT_HEARTBEAT_URL (pinged every cycle, at most once a minute; use a
                                    dead-man service such as healthchecks.io so you're
                                    told when pings STOP, i.e. the process or VM died)

What gets sent: every log record at ERROR or above, plus records logged with
extra={"notify": True} (trade opens/closes, halts). Sending happens on a
background thread; a slow or failing channel never blocks or breaks trading.
Identical messages within `dedupe_seconds` are suppressed.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.parse
import urllib.request

log = logging.getLogger("tradebot.alerts")


def _post(url: str, data: bytes, content_type: str, timeout: float = 10) -> None:
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": content_type})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read()


def telegram_sender(token: str, chat: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def send(text: str):
        _post(url, urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}).encode(),
              "application/x-www-form-urlencoded")
    return send


def webhook_sender(url: str):
    def send(text: str):
        _post(url, json.dumps({"text": text[:4000]}).encode(), "application/json")
    return send


def senders_from_env(env=os.environ) -> list:
    out = []
    if env.get("TRADEBOT_TELEGRAM_TOKEN") and env.get("TRADEBOT_TELEGRAM_CHAT"):
        out.append(telegram_sender(env["TRADEBOT_TELEGRAM_TOKEN"], env["TRADEBOT_TELEGRAM_CHAT"]))
    if env.get("TRADEBOT_WEBHOOK_URL"):
        out.append(webhook_sender(env["TRADEBOT_WEBHOOK_URL"]))
    return out


class AlertHandler(logging.Handler):
    def __init__(self, senders: list, prefix: str = "tradebot", level: int = logging.ERROR,
                 dedupe_seconds: float = 300, background: bool = True):
        super().__init__(logging.DEBUG)
        self.senders, self.prefix, self.alert_level = senders, prefix, level
        self.dedupe_seconds = dedupe_seconds
        self._recent: dict[str, float] = {}
        self.sent: list[str] = []          # what was handed to senders (for tests/inspection)
        self.failures = 0
        self._q: queue.Queue | None = None
        if background:
            self._q = queue.Queue(maxsize=200)
            threading.Thread(target=self._worker, daemon=True, name="tradebot-alerts").start()

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == log.name:
            return                         # never alert about alerting
        if record.levelno < self.alert_level and not getattr(record, "notify", False):
            return
        try:
            msg = record.getMessage()
        except Exception:
            return
        now = time.monotonic()
        if now - self._recent.get(msg, -1e9) < self.dedupe_seconds:
            return
        self._recent[msg] = now
        if len(self._recent) > 500:
            cutoff = now - self.dedupe_seconds
            self._recent = {k: v for k, v in self._recent.items() if v >= cutoff}
        text = f"[{self.prefix}] {record.levelname}: {msg}"
        if self._q is None:
            self._send(text)
        else:
            try:
                self._q.put_nowait(text)
            except queue.Full:
                self.failures += 1

    def _send(self, text: str) -> None:
        self.sent.append(text)
        for s in self.senders:
            try:
                s(text)
            except Exception as e:      # a dead channel must not take the bot down
                self.failures += 1
                log.warning("alert channel failed: %s", e)

    def _worker(self):
        while True:
            self._send(self._q.get())

    def flush(self, timeout: float = 5) -> None:
        """Wait briefly for queued alerts to go out (used on shutdown)."""
        if self._q is None:
            return
        end = time.monotonic() + timeout
        while not self._q.empty() and time.monotonic() < end:
            time.sleep(0.05)


class Heartbeat:
    def __init__(self, url: str | None, min_interval: float = 60):
        self.url, self.min_interval = url, min_interval
        self._last = -1e9

    def beat(self) -> None:
        if not self.url or time.monotonic() - self._last < self.min_interval:
            return
        self._last = time.monotonic()
        try:
            urllib.request.urlopen(self.url, timeout=5).read()
        except Exception as e:
            log.warning("heartbeat failed: %s", e)


def install(prefix: str, env=os.environ) -> tuple[AlertHandler | None, Heartbeat]:
    """Attach the alert handler to the 'tradebot' logger if any channel is configured."""
    hb = Heartbeat(env.get("TRADEBOT_HEARTBEAT_URL"))
    senders = senders_from_env(env)
    if not senders:
        logging.getLogger("tradebot").warning(
            "no alert channel configured (set TRADEBOT_TELEGRAM_TOKEN/CHAT or TRADEBOT_WEBHOOK_URL); "
            "errors will only appear in the log file")
        return None, hb
    h = AlertHandler(senders, prefix)
    lg = logging.getLogger("tradebot")
    if lg.getEffectiveLevel() > logging.INFO:
        lg.setLevel(logging.INFO)          # trade notifications are INFO records
    lg.addHandler(h)
    return h, hb
