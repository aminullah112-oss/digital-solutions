from __future__ import annotations

import asyncio
import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...domain import ConnectionState, Protocol, ProtocolError, utcnow
from ...models import Controller, Project, ProtocolConfiguration, RegisterDefinition, RegisterMap
from ...protocols.registry import build_adapter
from ...schemas import (
    ConnectionTestOut, ControllerIn, ControllerOut, ControllerUpdate, ProtocolConfigIn,
    RegisterIn, RegisterMapIn, RegisterMapOut,
)
from ...security import current_user, requires
from ...services.poller import polling_service
from ...services.value_store import store

router = APIRouter(prefix="/api/controllers", tags=["controllers"])


def _to_out(c: Controller) -> ControllerOut:
    out = ControllerOut.model_validate(c)
    if c.protocol_config:
        out.protocol = ProtocolConfigIn(
            protocol=Protocol(c.protocol_config.protocol), host=c.protocol_config.host,
            port=c.protocol_config.port, unit_id=c.protocol_config.unit_id,
            poll_interval_ms=c.protocol_config.poll_interval_ms,
            timeout_s=c.protocol_config.timeout_s, retries=c.protocol_config.retries,
            options=c.protocol_config.options or {},
        )
    out.register_map_verified = c.register_map.verified if c.register_map else None
    return out


@router.get("", response_model=list[ControllerOut])
def list_controllers(project_id: int | None = None, db: Session = Depends(get_db),
                     _=Depends(current_user)) -> list[ControllerOut]:
    stmt = select(Controller).order_by(Controller.name)
    if project_id:
        stmt = stmt.where(Controller.project_id == project_id)
    return [_to_out(c) for c in db.scalars(stmt)]


@router.post("", response_model=ControllerOut, status_code=status.HTTP_201_CREATED)
async def create_controller(payload: ControllerIn, db: Session = Depends(get_db),
                            _=Depends(requires("configure_controllers"))) -> ControllerOut:
    if db.get(Project, payload.project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if payload.protocol.protocol is Protocol.MODBUS_TCP and not payload.protocol.host:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "host is required for Modbus TCP")
    data = payload.model_dump(exclude={"protocol"})
    controller = Controller(**data)
    db.add(controller)
    db.flush()
    db.add(ProtocolConfiguration(controller_id=controller.id,
                                 **payload.protocol.model_dump()))
    db.commit()
    db.refresh(controller)
    if controller.enabled:
        await polling_service.ensure(controller.id)
    return _to_out(controller)


@router.get("/{controller_id}", response_model=ControllerOut)
def get_controller(controller_id: int, db: Session = Depends(get_db),
                   _=Depends(current_user)) -> ControllerOut:
    controller = db.get(Controller, controller_id)
    if controller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "controller not found")
    return _to_out(controller)


@router.put("/{controller_id}", response_model=ControllerOut)
async def update_controller(controller_id: int, payload: ControllerUpdate,
                            db: Session = Depends(get_db),
                            _=Depends(requires("configure_controllers"))) -> ControllerOut:
    controller = db.get(Controller, controller_id)
    if controller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "controller not found")
    data = payload.model_dump(exclude_unset=True, exclude={"protocol"})
    for key, value in data.items():
        setattr(controller, key, value)
    if payload.protocol is not None:
        cfg = controller.protocol_config or ProtocolConfiguration(controller_id=controller.id)
        for key, value in payload.protocol.model_dump().items():
            setattr(cfg, key, value)
        db.add(cfg)
    db.commit()
    db.refresh(controller)
    await polling_service.remove(controller.id)
    if controller.enabled:
        await polling_service.ensure(controller.id)
    return _to_out(controller)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(controller_id: int, db: Session = Depends(get_db),
                            _=Depends(requires("configure_controllers"))) -> None:
    controller = db.get(Controller, controller_id)
    if controller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "controller not found")
    await polling_service.remove(controller_id)
    db.delete(controller)
    db.commit()


@router.post("/{controller_id}/test", response_model=ConnectionTestOut)
async def test_connection(controller_id: int, db: Session = Depends(get_db),
                          _=Depends(requires("configure_controllers"))) -> ConnectionTestOut:
    controller = db.get(Controller, controller_id)
    if controller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "controller not found")

    def run() -> ConnectionTestOut:
        try:
            adapter = build_adapter(controller)
            info = adapter.test_connection()
            adapter.close()
        except ProtocolError as exc:
            return ConnectionTestOut(ok=False, detail=str(exc), checked_at=utcnow())
        return ConnectionTestOut(ok=info.ok, detail=info.detail, latency_ms=info.latency_ms,
                                 checked_at=info.checked_at)

    return await asyncio.to_thread(run)


@router.post("/{controller_id}/polling")
async def set_polling(controller_id: int, enabled: bool = Query(...),
                      interval_ms: int | None = Query(None, ge=100, le=600_000),
                      db: Session = Depends(get_db),
                      _=Depends(requires("configure_controllers"))) -> dict:
    controller = db.get(Controller, controller_id)
    if controller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "controller not found")
    controller.enabled = enabled
    if not enabled:
        controller.connection_state = ConnectionState.DISABLED
    if interval_ms and controller.protocol_config:
        controller.protocol_config.poll_interval_ms = interval_ms
    db.commit()
    if enabled:
        await polling_service.restart(controller_id)
    else:
        await polling_service.remove(controller_id)
    return {"controller_id": controller_id, "enabled": enabled,
            "poll_interval_ms": controller.protocol_config.poll_interval_ms
            if controller.protocol_config else None}


@router.get("/{controller_id}/live-data")
def live_data(controller_id: int, db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    controller = db.get(Controller, controller_id)
    if controller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "controller not found")
    values = store.latest(controller_id)
    groups: dict[str, dict] = {}
    for key, env in values.items():
        groups.setdefault(env.get("group", "other"), {})[key] = env
    return {
        "controller_id": controller_id,
        "controller_name": controller.name,
        "connection_state": str(controller.connection_state),
        "last_ok_at": controller.last_ok_at.isoformat() if controller.last_ok_at else None,
        "last_error": controller.last_error,
        "simulated": controller.is_simulated,
        "register_map": {
            "id": controller.register_map.id, "name": controller.register_map.name,
            "verified": controller.register_map.verified,
            "simulator_only": controller.register_map.is_simulator_only,
        } if controller.register_map else None,
        "values": values,
        "groups": groups,
        "note": (
            "No register map is configured for this controller, so nothing is being read. "
            "Import a verified register map."
        ) if controller.register_map is None and not controller.is_simulated else None,
    }


@router.get("/{controller_id}/history")
def history(controller_id: int, key: str, seconds: float = 300.0,
            _=Depends(current_user)) -> dict:
    return {
        "controller_id": controller_id, "key": key, "seconds": seconds,
        "points": store.history(controller_id, key, seconds=seconds),
        "statistics": store.statistics(controller_id, key, seconds=seconds),
        "note": "Trend buffer is in memory and resets when the server restarts.",
    }


# --- Register maps --------------------------------------------------------
maps_router = APIRouter(prefix="/api/register-maps", tags=["register-maps"])


def _map_out(m: RegisterMap) -> RegisterMapOut:
    out = RegisterMapOut.model_validate(m)
    out.register_count = len(m.registers)
    return out


@maps_router.get("", response_model=list[RegisterMapOut])
def list_maps(db: Session = Depends(get_db), _=Depends(current_user)) -> list[RegisterMapOut]:
    return [_map_out(m) for m in db.scalars(select(RegisterMap).order_by(RegisterMap.name))]


@maps_router.get("/{map_id}")
def get_map(map_id: int, db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    rmap = db.get(RegisterMap, map_id)
    if rmap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "register map not found")
    return {
        **_map_out(rmap).model_dump(),
        "registers": [{
            "id": r.id, "parameter_name": r.parameter_name, "address": r.address,
            "function_code": r.function_code, "data_type": str(r.data_type),
            "word_order": str(r.word_order), "length": r.length, "scale": r.scale,
            "offset": r.offset, "unit": r.unit, "description": r.description,
            "bit_position": r.bit_position, "normalized_key": r.normalized_key,
            "source": r.source,
        } for r in rmap.registers],
    }


@maps_router.post("", response_model=RegisterMapOut, status_code=status.HTTP_201_CREATED)
def create_map(payload: RegisterMapIn, db: Session = Depends(get_db),
               _=Depends(requires("configure_controllers"))) -> RegisterMapOut:
    if db.scalars(select(RegisterMap).where(RegisterMap.name == payload.name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "a register map with that name exists")
    rmap = RegisterMap(**payload.model_dump(exclude={"registers"}))
    db.add(rmap)
    db.flush()
    for reg in payload.registers:
        db.add(RegisterDefinition(register_map_id=rmap.id,
                                  controller_type=payload.controller_type,
                                  **reg.model_dump()))
    db.commit()
    db.refresh(rmap)
    return _map_out(rmap)


@maps_router.post("/{map_id}/import", response_model=RegisterMapOut)
async def import_registers(map_id: int, file: UploadFile, db: Session = Depends(get_db),
                           replace: bool = Query(True),
                           _=Depends(requires("configure_controllers"))) -> RegisterMapOut:
    """Import register definitions from CSV or JSON.

    Nothing is inferred: a row missing an address or a data type is rejected
    with its line number rather than defaulted.
    """
    rmap = db.get(RegisterMap, map_id)
    if rmap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "register map not found")

    raw = (await file.read()).decode("utf-8-sig")
    rows: list[dict]
    if file.filename and file.filename.lower().endswith(".json"):
        parsed = json.loads(raw)
        rows = parsed["registers"] if isinstance(parsed, dict) else parsed
    else:
        rows = list(csv.DictReader(io.StringIO(raw)))

    errors: list[str] = []
    parsed_rows: list[RegisterIn] = []
    for index, row in enumerate(rows, start=2):
        clean = {k.strip(): (v.strip() if isinstance(v, str) else v)
                 for k, v in row.items() if k}
        clean = {k: v for k, v in clean.items() if v not in ("", None)}
        try:
            parsed_rows.append(RegisterIn(**clean))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"row {index}: {exc}")
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            {"message": "import rejected", "errors": errors[:25]})

    if replace:
        for existing in list(rmap.registers):
            db.delete(existing)
        db.flush()
    for reg in parsed_rows:
        db.add(RegisterDefinition(register_map_id=rmap.id,
                                  controller_type=rmap.controller_type, **reg.model_dump()))
    # An import invalidates any previous verification: the new content has not
    # been checked by anyone.
    rmap.verified = False
    rmap.verified_by = ""
    db.commit()
    db.refresh(rmap)
    return _map_out(rmap)


@maps_router.post("/{map_id}/verify", response_model=RegisterMapOut)
def verify_map(map_id: int, verified_by: str, db: Session = Depends(get_db),
               user=Depends(requires("configure_controllers"))) -> RegisterMapOut:
    rmap = db.get(RegisterMap, map_id)
    if rmap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "register map not found")
    if not rmap.source_document.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "source_document must name the document and revision the addresses came from "
            "before this map can be marked verified",
        )
    if rmap.is_simulator_only:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "a simulator-only map cannot be marked verified")
    rmap.verified = True
    rmap.verified_by = verified_by or user.email
    db.commit()
    db.refresh(rmap)
    return _map_out(rmap)


@maps_router.get("/template/csv")
def csv_template(_=Depends(current_user)) -> dict:
    header = ("parameter_name,address,function_code,data_type,word_order,length,scale,offset,"
              "unit,description,bit_position,normalized_key,source")
    return {
        "header": header,
        "example_row": ("generator_voltage_ab,0,3,UINT16,BIG,1,0.1,0,V,"
                        "Generator L1-L2 voltage,,voltage_L1_L2,"
                        "<document and revision you read this from>"),
        "note": (
            "PowerTrace AI ships no vendor register addresses. Fill this from your "
            "controller's published register list and record where each address came from."
        ),
    }
