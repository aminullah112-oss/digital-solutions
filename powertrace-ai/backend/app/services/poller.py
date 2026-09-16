"""Polling scheduler.

One asyncio task per enabled controller.  Blocking protocol I/O runs in a
thread so a slow or dead controller cannot stall the event loop or any other
controller's polling — a single unreachable panel must not take the dashboard
down with it.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..domain import ConnectionState, DataSource, Quality, Severity, utcnow
from ..models import Alarm, Controller, Event
from ..protocols.base import ProtocolAdapter, RegisterSpec
from ..protocols.registry import build_adapter
from ..protocols.simulator import SimulatorAdapter
from .normalization import normalize
from .value_store import store

log = logging.getLogger("powertrace.poller")

#: Keys whose transitions are written to the event log for correlation.
DISCRETE_EVENT_KEYS_PREFIX = ("DO_", "DI_")
DISCRETE_EVENT_KEYS = {"breaker_status", "breaker_close_command", "breaker_closed_feedback"}


def specs_for(controller: Controller) -> list[RegisterSpec]:
    """Build the read list for a controller from its imported register map."""
    if controller.register_map is None:
        # A simulated controller with no map still exposes the simulator's own
        # parameter set; a real controller with no map reads nothing, which is
        # correct — inventing addresses is how people blow up commissioning.
        if controller.is_simulated:
            from .normalization import CATALOGUE

            keys = list(CATALOGUE) + ["DO_07", "DO_08", "DI_11", "DI_12"]
            return [RegisterSpec(parameter_name=k, address=0, normalized_key=k) for k in keys]
        return []
    return [
        RegisterSpec(
            parameter_name=r.parameter_name,
            address=r.address,
            function_code=r.function_code,
            data_type=str(r.data_type),
            word_order=str(r.word_order),
            length=r.length,
            scale=r.scale,
            offset=r.offset,
            unit=r.unit,
            bit_position=r.bit_position,
            normalized_key=r.normalized_key or r.parameter_name,
            description=r.description,
        )
        for r in controller.register_map.registers
    ]


class ControllerWorker:
    def __init__(self, controller_id: int, broadcast=None) -> None:
        self.controller_id = controller_id
        self.broadcast = broadcast
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._adapter: ProtocolAdapter | None = None

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name=f"poll-{self.controller_id}")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._adapter:
            await asyncio.to_thread(self._adapter.close)
            self._adapter = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            interval_ms = settings.default_poll_interval_ms
            try:
                interval_ms = await asyncio.to_thread(self._poll_once)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - a worker must never die silently
                log.exception("poll cycle failed for controller %s", self.controller_id)
            await asyncio.sleep(max(interval_ms, settings.min_poll_interval_ms) / 1000.0)

    # --- executed in a worker thread --------------------------------------
    def _poll_once(self) -> int:
        db = SessionLocal()
        try:
            controller = db.get(Controller, self.controller_id)
            if controller is None or not controller.enabled:
                return settings.default_poll_interval_ms
            cfg = controller.protocol_config
            interval = cfg.poll_interval_ms if cfg else settings.default_poll_interval_ms

            try:
                if self._adapter is None:
                    self._adapter = build_adapter(controller)
                self._adapter.connect()
                readings = self._adapter.read(specs_for(controller))
            except Exception as exc:  # noqa: BLE001
                self._mark_failure(db, controller, str(exc))
                db.commit()
                self._publish({"type": "controller_status", "controller_id": controller.id,
                               "state": controller.connection_state, "error": controller.last_error})
                if self._adapter:
                    with contextlib.suppress(Exception):
                        self._adapter.close()
                    self._adapter = None
                return interval

            simulated = self._adapter.produces_simulated_data
            values = normalize(readings, simulated=simulated)
            bad = [r for r in readings if r.quality in (Quality.BAD, Quality.TIMEOUT)]
            previous = store.latest(controller.id)
            changed = store.update(controller.id, values)

            if bad and len(bad) == len(readings):
                self._mark_failure(db, controller, bad[0].error or "all reads failed")
            else:
                self._mark_success(db, controller, degraded=bool(bad))

            self._record_transitions(db, controller, previous, changed)
            if simulated and isinstance(self._adapter, SimulatorAdapter):
                self._sync_simulated_alarms(db, controller, self._adapter)
            db.commit()

            self._publish({
                "type": "values",
                "controller_id": controller.id,
                "simulated": simulated,
                "values": values,
            })
            return interval
        finally:
            db.close()

    def _publish(self, message: dict[str, Any]) -> None:
        if self.broadcast is None:
            return
        try:
            self.broadcast(self.controller_id, message)
        except Exception:  # noqa: BLE001 - never let the UI fan-out break polling
            log.exception("broadcast failed")

    def _mark_success(self, db, controller: Controller, *, degraded: bool) -> None:
        was = controller.connection_state
        controller.connection_state = (
            ConnectionState.DEGRADED if degraded else ConnectionState.ONLINE
        )
        controller.last_ok_at = utcnow()
        controller.consecutive_failures = 0
        controller.last_error = None
        if was != controller.connection_state:
            db.add(Event(
                project_id=controller.project_id, controller_id=controller.id,
                category="COMMUNICATION", code="COMM_STATE",
                message=f"Controller communication {was} -> {controller.connection_state}",
                severity=Severity.EVENT, source=DataSource.CONTROLLER.value,
                timestamp=utcnow(),
            ))

    def _mark_failure(self, db, controller: Controller, error: str) -> None:
        was = controller.connection_state
        controller.consecutive_failures += 1
        controller.connection_state = ConnectionState.ERROR
        controller.last_error = error[:1000]
        store.clear(controller.id)
        if was != ConnectionState.ERROR:
            db.add(Event(
                project_id=controller.project_id, controller_id=controller.id,
                category="COMMUNICATION", code="COMM_LOST",
                message=f"Controller communication lost: {error[:300]}",
                severity=Severity.ALARM, source=DataSource.CONTROLLER.value,
                quality=Quality.BAD.value, timestamp=utcnow(),
            ))

    def _record_transitions(self, db, controller: Controller, previous, changed) -> None:
        """Log discrete transitions so they can be correlated later."""
        for key, env in changed.items():
            if not (key in DISCRETE_EVENT_KEYS or key.startswith(DISCRETE_EVENT_KEYS_PREFIX)):
                continue
            before = previous.get(key, {}).get("value")
            after = env.get("value")
            if before == after:
                continue
            db.add(Event(
                project_id=controller.project_id, controller_id=controller.id,
                category="IO", code=key,
                message=f"{key} {_fmt(before)} -> {_fmt(after)}",
                severity=Severity.EVENT,
                source=env.get("source", DataSource.CONTROLLER.value),
                quality=env.get("quality", Quality.GOOD.value),
                value=1.0 if after is True else 0.0 if after is False else None,
                payload={"key": key, "from": before, "to": after},
                timestamp=_parse(env.get("timestamp")),
            ))

    def _sync_simulated_alarms(self, db, controller: Controller, adapter: SimulatorAdapter) -> None:
        wanted = {a["code"]: a for a in adapter.simulated_alarms()}
        existing = db.scalars(
            select(Alarm).where(Alarm.controller_id == controller.id, Alarm.is_active.is_(True))
        ).all()
        for alarm in existing:
            if alarm.code not in wanted:
                alarm.is_active = False
                alarm.cleared_at = utcnow()
        have = {a.code for a in existing if a.is_active}
        for code, info in wanted.items():
            if code in have:
                continue
            db.add(Alarm(
                project_id=controller.project_id, controller_id=controller.id,
                code=code, description=info["description"],
                description_source="SIMULATOR",
                severity=Severity(info["severity"]), source=DataSource.SIMULATED.value,
                is_active=True, raised_at=utcnow(),
            ))


def _fmt(v: Any) -> str:
    return "—" if v is None else str(v)


def _parse(iso: str | None) -> datetime:
    if not iso:
        return utcnow()
    dt = datetime.fromisoformat(iso)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class PollingService:
    """Owns one worker per enabled controller."""

    def __init__(self) -> None:
        self._workers: dict[int, ControllerWorker] = {}
        self.broadcast = None

    async def start_all(self) -> None:
        db = SessionLocal()
        try:
            ids = [
                c.id for c in db.scalars(select(Controller).where(Controller.enabled.is_(True)))
            ]
        finally:
            db.close()
        for cid in ids:
            await self.ensure(cid)

    async def ensure(self, controller_id: int) -> None:
        if controller_id in self._workers:
            return
        worker = ControllerWorker(controller_id, broadcast=self.broadcast)
        self._workers[controller_id] = worker
        await worker.start()

    async def remove(self, controller_id: int) -> None:
        worker = self._workers.pop(controller_id, None)
        if worker:
            await worker.stop()
        store.clear(controller_id)

    async def restart(self, controller_id: int) -> None:
        await self.remove(controller_id)
        await self.ensure(controller_id)

    async def stop_all(self) -> None:
        for cid in list(self._workers):
            await self.remove(cid)

    @property
    def active_ids(self) -> list[int]:
        return sorted(self._workers)


polling_service = PollingService()
