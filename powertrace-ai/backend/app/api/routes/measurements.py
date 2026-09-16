from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db
from ...domain import DataSource, Quality, utcnow
from ...models import CircuitNode, Measurement, MeasurementChannel, MeasurementDevice
from ...schemas import (
    MeasurementChannelIn, MeasurementDeviceIn, MeasurementIn, MeasurementOut,
)
from ...security import current_user, requires
from ...services.measurement_safety import blocking, validate_channel

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


@router.get("/devices")
def list_devices(project_id: int | None = None, db: Session = Depends(get_db),
                 _=Depends(current_user)) -> list[dict]:
    stmt = select(MeasurementDevice).order_by(MeasurementDevice.name)
    if project_id:
        stmt = stmt.where(MeasurementDevice.project_id == project_id)
    return [{
        "id": d.id, "project_id": d.project_id, "name": d.name,
        "manufacturer": d.manufacturer, "model": d.model, "transport": d.transport,
        "host": d.host, "port": d.port, "unit_id": d.unit_id, "enabled": d.enabled,
        "is_simulated": d.is_simulated, "connection_state": d.connection_state,
        "channel_count": len(d.channels),
    } for d in db.scalars(stmt)]


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def create_device(payload: MeasurementDeviceIn, db: Session = Depends(get_db),
                  _=Depends(requires("measure"))) -> dict:
    device = MeasurementDevice(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"id": device.id, "name": device.name}


@router.get("/channels")
def list_channels(device_id: int | None = None, db: Session = Depends(get_db),
                  _=Depends(current_user)) -> list[dict]:
    stmt = select(MeasurementChannel).order_by(MeasurementChannel.channel_tag)
    if device_id:
        stmt = stmt.where(MeasurementChannel.device_id == device_id)
    out = []
    for c in db.scalars(stmt):
        cfg = _channel_cfg(c)
        out.append({
            **cfg, "id": c.id, "device_id": c.device_id,
            "safety_checks": [chk.as_dict() for chk in validate_channel(cfg)],
        })
    return out


def _channel_cfg(c: MeasurementChannel) -> dict:
    return {
        "channel_tag": c.channel_tag, "description": c.description, "input_type": c.input_type,
        "max_rated_input": c.max_rated_input, "max_rated_input_unit": c.max_rated_input_unit,
        "isolation_rating_v": c.isolation_rating_v, "isolated": c.isolated,
        "signal_conditioning": c.signal_conditioning, "conditioning_ratio": c.conditioning_ratio,
        "conditioning_note": c.conditioning_note, "scale": c.scale, "offset": c.offset,
        "unit": c.unit, "calibrated_at": c.calibrated_at,
        "calibration_due_at": c.calibration_due_at,
        "calibration_reference": c.calibration_reference,
        "circuit_node_id": c.circuit_node_id, "terminal_id": c.terminal_id,
        "nominal_circuit_voltage_v": c.nominal_circuit_voltage_v,
    }


@router.post("/channels/validate")
def validate_channel_config(payload: MeasurementChannelIn, _=Depends(current_user)) -> dict:
    checks = validate_channel(payload.model_dump())
    return {
        "checks": [c.as_dict() for c in checks],
        "accepted": not blocking(checks),
        "direct_input_voltage_limit_v": settings.direct_input_voltage_limit_v,
    }


@router.post("/channels", status_code=status.HTTP_201_CREATED)
def create_channel(payload: MeasurementChannelIn, db: Session = Depends(get_db),
                   _=Depends(requires("measure"))) -> dict:
    """Create a channel, refusing a configuration that implies an unsafe input.

    This check is on the configuration only. It cannot verify that the
    hardware in the field matches what was entered here.
    """
    cfg = payload.model_dump()
    checks = validate_channel(cfg)
    errors = blocking(checks)
    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "channel configuration refused",
             "errors": [c.as_dict() for c in errors]},
        )
    channel = MeasurementChannel(**cfg)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return {"id": channel.id, "channel_tag": channel.channel_tag,
            "warnings": [c.as_dict() for c in checks if c.level != "ERROR"]}


@router.get("", response_model=list[MeasurementOut])
def list_measurements(project_id: int, circuit_node_id: int | None = None,
                      limit: int = Query(200, le=2000), db: Session = Depends(get_db),
                      _=Depends(current_user)) -> list[Measurement]:
    stmt = (select(Measurement).where(Measurement.project_id == project_id)
            .order_by(Measurement.timestamp.desc()).limit(limit))
    if circuit_node_id:
        stmt = stmt.where(Measurement.circuit_node_id == circuit_node_id)
    return list(db.scalars(stmt))


@router.post("", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
def record_measurement(payload: MeasurementIn, db: Session = Depends(get_db),
                       user=Depends(requires("measure"))) -> Measurement:
    if payload.circuit_node_id and db.get(CircuitNode, payload.circuit_node_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "circuit node not found")

    quality = Quality.GOOD
    source = DataSource.MEASURED
    if payload.method == "SIM":
        quality, source = Quality.SIMULATED, DataSource.SIMULATED

    channel = db.get(MeasurementChannel, payload.channel_id) if payload.channel_id else None
    if channel:
        checks = validate_channel(_channel_cfg(channel))
        if blocking(checks):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                {"message": "channel configuration is not valid; measurement not recorded",
                 "errors": [c.as_dict() for c in blocking(checks)]},
            )
        if any(c.code in ("CALIBRATION_OVERDUE", "NO_CALIBRATION") for c in checks):
            # Recorded, but the quality tag says the instrument's calibration
            # is not current so the number is not treated as trustworthy.
            quality = Quality.UNKNOWN

    measurement = Measurement(
        **payload.model_dump(exclude={"timestamp"}),
        quality=quality.value, source=source.value,
        timestamp=payload.timestamp or utcnow(),
    )
    if not measurement.technician:
        measurement.technician = user.email
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    return measurement
