"""PowerTrace AI — application entry point.

  PowerTrace AI is an industrial electrical troubleshooting aid.
  It is NOT a safety-rated protection system, it issues no control
  commands, and nothing it displays establishes that a circuit is
  de-energized.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api import ws as ws_module
from .api.routes import (
    alarms, auth, circuits, controllers, diagnostics, measurements, misc, projects, schematics,
)
from .config import settings
from .db import SessionLocal, init_db
from .domain import MV_SAFETY_NOTICE
from .security import ensure_seed_admin
from .services.poller import polling_service
from .services.value_store import store

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("powertrace")

DESCRIPTION = f"""
Industrial electrical troubleshooting and diagnostic platform.

**Safety**

* This application issues **no control commands**. It does not start or stop
  engines, open or close breakers, or modify controller configuration.
* It is **not a safety-rated protection system**.
* Controller-reported state is never presented as a measurement. A point with
  no physical measurement is reported as `NOT_MEASURED`.
* {MV_SAFETY_NOTICE}

**Data provenance**

Every value carries `value`, `unit`, `timestamp`, `quality` and `source`.
`source` is one of MEASURED, CONTROLLER, SCHEMATIC, EXPECTATION, INFERENCE,
SIMULATED or UNKNOWN, and is set where the value is produced.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        created = ensure_seed_admin(db)
        if created:
            log.warning("Created initial admin %s — change this password.", created.email)
        if settings.environment != "development" and \
                settings.secret_key.startswith("dev-only"):
            raise RuntimeError(
                "POWERTRACE_SECRET_KEY must be set outside development."
            )
    finally:
        db.close()

    ws_module.hub.bind_loop(asyncio.get_running_loop())
    polling_service.broadcast = ws_module.broadcast_from_poller
    await polling_service.start_all()
    log.info("PowerTrace AI started. Demo mode: %s. Control writes: %s.",
             settings.demo_mode, settings.allow_control_writes)
    try:
        yield
    finally:
        await polling_service.stop_all()


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, misc, projects, controllers, circuits, measurements,
               diagnostics, alarms, schematics):
    app.include_router(module.router)

app.include_router(controllers.maps_router)
app.include_router(misc.demo_router)


@app.get("/api/health", tags=["application"])
def health() -> dict:
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "control_writes_enabled": settings.allow_control_writes,
        "polling_controllers": polling_service.active_ids,
    }


@app.websocket("/ws/controllers/{controller_id}")
async def controller_socket(websocket: WebSocket, controller_id: int) -> None:
    """Live values for one controller.

    Pushes the current cache immediately on connect so a newly opened screen
    is populated without waiting for the next poll.
    """
    topic = f"controller:{controller_id}"
    await ws_module.hub.connect(topic, websocket)
    try:
        await websocket.send_json({
            "type": "values", "controller_id": controller_id,
            "values": store.latest(controller_id), "initial": True,
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_module.hub.disconnect(topic, websocket)


@app.websocket("/ws/all")
async def all_socket(websocket: WebSocket) -> None:
    await ws_module.hub.connect("all", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_module.hub.disconnect("all", websocket)
