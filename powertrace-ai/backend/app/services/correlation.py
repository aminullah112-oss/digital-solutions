"""Event correlation.

Builds a single ordered timeline from controller I/O transitions, alarms and
physical measurements so cause and effect can be read off directly:

  14:32:01  DO-07 OFF -> ON          CONTROLLER
  14:32:02  K12 coil 24.1 V          MEASURED
  14:32:03  TB23-14 0.2 V            MEASURED
  14:32:04  breaker feedback ON? no  CONTROLLER

Ordering across sources is only as good as their clocks; the clock skew
between a controller and the measurement gateway is reported rather than
quietly assumed to be zero.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alarm, CircuitNode, Event, Measurement, MeasurementChannel


def timeline(
    db: Session, project_id: int, *, since: datetime, until: datetime | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    until = until or datetime.max.replace(tzinfo=since.tzinfo)
    rows: list[dict[str, Any]] = []

    for e in db.scalars(
        select(Event).where(Event.project_id == project_id,
                            Event.timestamp >= since, Event.timestamp <= until)
        .order_by(Event.timestamp).limit(limit)
    ):
        rows.append({
            "timestamp": e.timestamp.isoformat(), "category": e.category, "code": e.code,
            "message": e.message, "severity": str(e.severity), "source": e.source,
            "quality": e.quality, "value": e.value, "unit": e.unit,
            "controller_id": e.controller_id, "circuit_node_id": e.circuit_node_id,
        })

    for a in db.scalars(
        select(Alarm).where(Alarm.project_id == project_id,
                            Alarm.raised_at >= since, Alarm.raised_at <= until)
        .order_by(Alarm.raised_at).limit(limit)
    ):
        rows.append({
            "timestamp": a.raised_at.isoformat(), "category": "ALARM", "code": a.code,
            "message": a.description or "(no imported definition for this code)",
            "severity": str(a.severity), "source": a.source, "quality": "GOOD",
            "controller_id": a.controller_id,
        })

    nodes = {n.id: n for n in db.scalars(select(CircuitNode)
                                        .where(CircuitNode.project_id == project_id))}
    channels = {c.id: c for c in db.scalars(select(MeasurementChannel))}
    for m in db.scalars(
        select(Measurement).where(Measurement.project_id == project_id,
                                  Measurement.timestamp >= since, Measurement.timestamp <= until)
        .order_by(Measurement.timestamp).limit(limit)
    ):
        node = nodes.get(m.circuit_node_id) if m.circuit_node_id else None
        channel = channels.get(m.channel_id) if m.channel_id else None
        rows.append({
            "timestamp": m.timestamp.isoformat(), "category": "MEASUREMENT",
            "code": node.key if node else (channel.channel_tag if channel else "measurement"),
            "message": f"{node.label if node else 'point'} = {m.value} {m.unit}",
            "severity": "INFO", "source": m.source, "quality": m.quality,
            "value": m.value, "unit": m.unit, "circuit_node_id": m.circuit_node_id,
        })

    rows.sort(key=lambda r: r["timestamp"])
    return rows[:limit]


def correlate_around(
    db: Session, project_id: int, anchor: datetime, *, window_s: float = 30.0,
) -> dict[str, Any]:
    """Timeline around an anchor event, with per-source clock notes."""
    rows = timeline(
        db, project_id,
        since=anchor - timedelta(seconds=window_s),
        until=anchor + timedelta(seconds=window_s),
    )
    sources = sorted({r["source"] for r in rows})
    return {
        "anchor": anchor.isoformat(),
        "window_s": window_s,
        "events": rows,
        "sources": sources,
        "clock_note": (
            "Timestamps come from different clocks (controller, gateway, server). "
            "Sub-second ordering between sources is not reliable unless the devices "
            "are time-synchronised."
        ) if len(sources) > 1 else "",
    }
