"""Terminal status model.

A terminal carries four independent facts, and they are never collapsed:

  expected    engineering expectation (drawing / design)
  controller  what a controller signal associated with this point reports
  measured    what an instrument actually read on the terminal
  status      the comparison of expected against measured, only

`status` is driven by measurement alone.  If nothing has been measured, the
status is NOT_MEASURED and the overlay is gray — regardless of what the
controller is reporting.  That rule is the whole point of the model.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import (
    MEDIUM_VOLTAGE_THRESHOLD_V, MV_SAFETY_NOTICE, ComparisonResult, DataSource, Quality,
)
from ..models import CircuitNode, Measurement, Terminal
from .expected_actual import Expectation, compare
from .value_store import store

#: Overlay colours are semantic and always accompanied by a text status.
OVERLAY = {
    ComparisonResult.NORMAL: ("GREEN", "NORMAL"),
    ComparisonResult.MARGINAL: ("YELLOW", "MARGINAL"),
    ComparisonResult.ABNORMAL: ("RED", "FAULT"),
    ComparisonResult.NOT_MEASURED: ("GRAY", "NOT MEASURED"),
    ComparisonResult.NO_EXPECTATION: ("GRAY", "NO EXPECTATION"),
}


def latest_measurement(db: Session, *, node_id: int | None, terminal_id: int | None):
    stmt = select(Measurement).order_by(Measurement.timestamp.desc()).limit(1)
    if node_id is not None:
        stmt = stmt.where(Measurement.circuit_node_id == node_id)
    elif terminal_id is not None:
        stmt = stmt.where(Measurement.terminal_id == terminal_id)
    else:
        return None
    return db.scalars(stmt).first()


def controller_state_for(node: CircuitNode) -> dict[str, Any] | None:
    """The controller's own report for a node, if one is associated.

    Returned under its own key with source CONTROLLER so the UI cannot render
    it in a measurement slot.
    """
    if not node.controller_id or not node.controller_signal:
        return None
    env = store.get(node.controller_id, node.controller_signal)
    if env is None:
        return {
            "signal": node.controller_signal,
            "value": None,
            "quality": Quality.UNKNOWN.value,
            "source": DataSource.CONTROLLER.value,
            "note": "No live value for this signal.",
        }
    return {
        "signal": node.controller_signal,
        "value": env.get("value"),
        "unit": env.get("unit"),
        "timestamp": env.get("timestamp"),
        "age_s": env.get("age_s"),
        "quality": env.get("quality"),
        "source": env.get("source"),
        "source_detail": env.get("source_detail"),
        "note": (
            "Controller-reported state. This is not a measurement of voltage "
            "at this point."
        ),
    }


def terminal_status(db: Session, node: CircuitNode, terminal: Terminal | None) -> dict[str, Any]:
    expectation = None
    if terminal and terminal.expected_voltage_v is not None:
        expectation = Expectation(
            value=terminal.expected_voltage_v,
            unit="V",
            tolerance_pct=terminal.expected_tolerance_pct,
            signal_type=terminal.expected_signal_type,
            reference=terminal.expected_reference,
            basis="Terminal expectation from schematic review",
        )

    measurement = latest_measurement(
        db, node_id=node.id, terminal_id=terminal.id if terminal else None
    )
    comparison = compare(
        expectation,
        measurement.value if measurement else None,
        measured_unit=measurement.unit if measurement else "V",
        measured_quality=Quality(measurement.quality) if measurement else Quality.UNKNOWN,
        measured_source=DataSource(measurement.source) if measurement else DataSource.UNKNOWN,
        measured_at=measurement.timestamp.isoformat() if measurement else None,
    )
    colour, label = OVERLAY[comparison.result]

    nominal = node.nominal_voltage_v
    payload: dict[str, Any] = {
        "node_key": node.key,
        "terminal_tag": terminal.tag if terminal else None,
        "expected": comparison.expected,
        "measured": comparison.actual,
        "controller": controller_state_for(node),
        "comparison": comparison.as_dict(),
        "status": label,
        "overlay_color": colour,
        "reason": comparison.reason,
    }
    if measurement:
        payload["measured"] = {
            **(payload["measured"] or {}),
            "method": measurement.method,
            "instrument": measurement.instrument,
            "technician": measurement.technician,
        }
    if nominal and nominal >= MEDIUM_VOLTAGE_THRESHOLD_V:
        payload["medium_voltage"] = True
        payload["safety_notice"] = MV_SAFETY_NOTICE
    return payload
