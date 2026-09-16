from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import (
    CircuitEdge, CircuitNode, Component, Controller, Project, ProtocolConfiguration, Terminal,
    Wire,
)
from ...schemas import ProjectIn, ProjectOut
from ...security import current_user, requires

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), _=Depends(current_user)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.name)))


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectIn, db: Session = Depends(get_db),
                   _=Depends(requires("manage_projects"))) -> Project:
    if db.scalars(select(Project).where(Project.name == payload.name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "a project with that name exists")
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), _=Depends(current_user)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectIn, db: Session = Depends(get_db),
                   _=Depends(requires("manage_projects"))) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    for key, value in payload.model_dump().items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db),
                   _=Depends(requires("manage_projects"))) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    db.delete(project)
    db.commit()


@router.post("/{project_id}/duplicate", response_model=ProjectOut,
             status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: int, name: str, db: Session = Depends(get_db),
                      _=Depends(requires("manage_projects"))) -> Project:
    """Copy configuration to a new project for an identical panel.

    Configuration is copied: controllers, circuit model, components, terminals,
    wires. History is not — measurements, alarms and diagnostic sessions belong
    to the panel they were taken on, and copying them into a new panel would
    put another machine's readings in front of a technician.
    """
    source = db.get(Project, project_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if db.scalars(select(Project).where(Project.name == name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "a project with that name exists")

    clone = Project(
        name=name, site=source.site, panel=source.panel,
        description=f"Duplicated from {source.name}. Configuration only; no history copied.",
        is_demo=source.is_demo, nominal_voltage_v=source.nominal_voltage_v,
        nominal_frequency_hz=source.nominal_frequency_hz,
        control_voltage_v=source.control_voltage_v,
    )
    db.add(clone)
    db.flush()

    controller_map: dict[int, int] = {}
    for c in db.scalars(select(Controller).where(Controller.project_id == project_id)):
        new_c = Controller(
            project_id=clone.id, name=c.name, manufacturer=c.manufacturer, model=c.model,
            controller_type=c.controller_type, description=c.description, enabled=False,
            is_simulated=c.is_simulated, register_map_id=c.register_map_id,
        )
        db.add(new_c)
        db.flush()
        controller_map[c.id] = new_c.id
        if c.protocol_config:
            db.add(ProtocolConfiguration(
                controller_id=new_c.id, protocol=c.protocol_config.protocol,
                host=None,  # network details are panel-specific; forced re-entry
                port=c.protocol_config.port, unit_id=c.protocol_config.unit_id,
                poll_interval_ms=c.protocol_config.poll_interval_ms,
                timeout_s=c.protocol_config.timeout_s, retries=c.protocol_config.retries,
                options=dict(c.protocol_config.options or {}),
            ))

    component_map: dict[int, int] = {}
    for comp in db.scalars(select(Component).where(Component.project_id == project_id)):
        new = Component(
            project_id=clone.id, reference_designator=comp.reference_designator,
            component_type=comp.component_type, description=comp.description,
            manufacturer=comp.manufacturer, part_number=comp.part_number, rating=comp.rating,
            location=comp.location, confidence=comp.confidence, verified=comp.verified,
            attributes=dict(comp.attributes or {}),
        )
        db.add(new)
        db.flush()
        component_map[comp.id] = new.id

    terminal_map: dict[int, int] = {}
    for t in db.scalars(select(Terminal).where(Terminal.project_id == project_id)):
        new = Terminal(
            project_id=clone.id, component_id=component_map.get(t.component_id),
            tag=t.tag, block=t.block, number=t.number, description=t.description,
            expected_voltage_v=t.expected_voltage_v, expected_reference=t.expected_reference,
            expected_tolerance_pct=t.expected_tolerance_pct,
            expected_signal_type=t.expected_signal_type,
            confidence=t.confidence, verified=t.verified,
        )
        db.add(new)
        db.flush()
        terminal_map[t.id] = new.id

    wire_map: dict[int, int] = {}
    for w in db.scalars(select(Wire).where(Wire.project_id == project_id)):
        new = Wire(project_id=clone.id, wire_number=w.wire_number, color=w.color,
                   gauge=w.gauge, description=w.description, confidence=w.confidence,
                   verified=w.verified)
        db.add(new)
        db.flush()
        wire_map[w.id] = new.id

    node_map: dict[int, int] = {}
    for n in db.scalars(select(CircuitNode).where(CircuitNode.project_id == project_id)):
        new = CircuitNode(
            project_id=clone.id, key=n.key, label=n.label, node_type=n.node_type,
            component_id=component_map.get(n.component_id),
            terminal_id=terminal_map.get(n.terminal_id), wire_id=wire_map.get(n.wire_id),
            controller_id=controller_map.get(n.controller_id),
            controller_signal=n.controller_signal, nominal_voltage_v=n.nominal_voltage_v,
            x=n.x, y=n.y, confidence=n.confidence, verified=n.verified,
            attributes=dict(n.attributes or {}),
        )
        db.add(new)
        db.flush()
        node_map[n.id] = new.id

    for e in db.scalars(select(CircuitEdge).where(CircuitEdge.project_id == project_id)):
        db.add(CircuitEdge(
            project_id=clone.id, from_node_id=node_map[e.from_node_id],
            to_node_id=node_map[e.to_node_id], edge_type=e.edge_type,
            wire_id=wire_map.get(e.wire_id), label=e.label, confidence=e.confidence,
            verified=e.verified, notes=e.notes,
        ))

    db.commit()
    db.refresh(clone)
    return clone
