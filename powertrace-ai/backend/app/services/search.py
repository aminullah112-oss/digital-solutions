"""Global search across projects, controllers, circuit objects and sessions."""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import (
    Alarm, CircuitNode, Component, Controller, DiagnosticSession, Project, Schematic, Terminal,
    Wire,
)


def search(db: Session, query: str, *, project_id: int | None = None,
           limit: int = 40) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    like = f"%{q}%"
    results: list[dict[str, Any]] = []

    def scoped(stmt, model):
        return stmt.where(model.project_id == project_id) if project_id else stmt

    for p in db.scalars(select(Project).where(
            or_(Project.name.ilike(like), Project.site.ilike(like), Project.panel.ilike(like)))
            .limit(limit)):
        results.append({"type": "project", "id": p.id, "project_id": p.id, "title": p.name,
                        "subtitle": f"{p.site} {p.panel}".strip(), "route": f"/projects/{p.id}"})

    for c in db.scalars(scoped(select(Controller).where(
            or_(Controller.name.ilike(like), Controller.model.ilike(like),
                Controller.manufacturer.ilike(like))), Controller).limit(limit)):
        results.append({"type": "controller", "id": c.id, "project_id": c.project_id,
                        "title": c.name, "subtitle": f"{c.manufacturer} {c.model}".strip(),
                        "status": str(c.connection_state), "route": f"/controllers/{c.id}"})

    for comp in db.scalars(scoped(select(Component).where(
            or_(Component.reference_designator.ilike(like), Component.description.ilike(like))),
            Component).limit(limit)):
        results.append({"type": "component", "id": comp.id, "project_id": comp.project_id,
                        "title": comp.reference_designator,
                        "subtitle": f"{comp.component_type} {comp.description}".strip(),
                        "route": f"/circuit?select={comp.reference_designator}"})

    for t in db.scalars(scoped(select(Terminal).where(
            or_(Terminal.tag.ilike(like), Terminal.description.ilike(like))),
            Terminal).limit(limit)):
        results.append({"type": "terminal", "id": t.id, "project_id": t.project_id,
                        "title": t.tag, "subtitle": t.description,
                        "route": f"/circuit?select={t.tag}"})

    for w in db.scalars(scoped(select(Wire).where(Wire.wire_number.ilike(like)), Wire)
                        .limit(limit)):
        results.append({"type": "wire", "id": w.id, "project_id": w.project_id,
                        "title": w.wire_number, "subtitle": w.description,
                        "route": f"/circuit?select={w.wire_number}"})

    for n in db.scalars(scoped(select(CircuitNode).where(
            or_(CircuitNode.key.ilike(like), CircuitNode.label.ilike(like),
                CircuitNode.controller_signal.ilike(like))), CircuitNode).limit(limit)):
        results.append({"type": "circuit_node", "id": n.id, "project_id": n.project_id,
                        "title": n.key, "subtitle": f"{n.node_type} {n.label}".strip(),
                        "route": f"/circuit?select={n.key}"})

    for s in db.scalars(scoped(select(Schematic).where(
            or_(Schematic.name.ilike(like), Schematic.drawing_number.ilike(like))),
            Schematic).limit(limit)):
        results.append({"type": "schematic", "id": s.id, "project_id": s.project_id,
                        "title": s.name, "subtitle": s.drawing_number,
                        "route": f"/schematics/{s.id}"})

    for a in db.scalars(scoped(select(Alarm).where(
            or_(Alarm.code.ilike(like), Alarm.description.ilike(like))), Alarm).limit(limit)):
        results.append({"type": "alarm", "id": a.id, "project_id": a.project_id,
                        "title": a.code, "subtitle": a.description,
                        "status": str(a.severity), "route": "/alarms"})

    for d in db.scalars(scoped(select(DiagnosticSession).where(
            or_(DiagnosticSession.title.ilike(like), DiagnosticSession.symptom.ilike(like))),
            DiagnosticSession).limit(limit)):
        results.append({"type": "diagnostic_session", "id": d.id, "project_id": d.project_id,
                        "title": f"Session #{d.id}: {d.title}", "subtitle": d.status,
                        "route": f"/diagnostics/{d.id}"})

    exact = [r for r in results if r["title"].lower() == q.lower()]
    rest = [r for r in results if r not in exact]
    return (exact + rest)[:limit]
