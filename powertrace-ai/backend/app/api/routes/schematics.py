from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...domain import NodeType
from ...models import (
    CircuitEdge, CircuitNode, Component, Connection, Project, Schematic, SchematicPage, Terminal,
    Wire,
)
from ...domain import EdgeType
from ...security import current_user, requires
from ...services import schematic_import

router = APIRouter(prefix="/api/schematics", tags=["schematics"])

STORAGE = Path("storage/schematics")
ALLOWED = {"application/pdf", "image/png", "image/jpeg", "image/svg+xml"}


@router.get("/capabilities")
def capabilities(_=Depends(current_user)) -> dict:
    """What the import pipeline can and cannot do in this installation."""
    return {
        "stages": schematic_import.capabilities(),
        "accepted_types": sorted(ALLOWED),
        "note": (
            "Connectivity drawn only as lines is not extracted. Every proposal must be "
            "reviewed before the circuit model is used for troubleshooting."
        ),
    }


@router.get("")
def list_schematics(project_id: int | None = None, db: Session = Depends(get_db),
                    _=Depends(current_user)) -> list[dict]:
    stmt = select(Schematic).order_by(Schematic.name)
    if project_id:
        stmt = stmt.where(Schematic.project_id == project_id)
    return [{
        "id": s.id, "project_id": s.project_id, "name": s.name,
        "drawing_number": s.drawing_number, "revision": s.revision,
        "original_filename": s.original_filename, "content_type": s.content_type,
        "page_count": s.page_count, "import_status": s.import_status,
        "created_at": s.created_at,
    } for s in db.scalars(stmt)]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload(file: UploadFile, project_id: int = Form(...), name: str = Form(""),
                 drawing_number: str = Form(""), revision: str = Form(""),
                 db: Session = Depends(get_db),
                 _=Depends(requires("edit_schematic"))) -> dict:
    if db.get(Project, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if file.content_type not in ALLOWED:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            f"accepted types: {', '.join(sorted(ALLOWED))}")

    STORAGE.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "drawing").suffix
    stored = STORAGE / f"{uuid.uuid4().hex}{suffix}"
    with stored.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    schematic = Schematic(
        project_id=project_id, name=name or (file.filename or "Drawing"),
        drawing_number=drawing_number, revision=revision,
        original_filename=file.filename or "", content_type=file.content_type or "",
        storage_path=str(stored), import_status="ANALYZING",
    )
    db.add(schematic)
    db.flush()

    result = schematic_import.run(str(stored), file.content_type or "")
    for page in result.pages:
        db.add(SchematicPage(
            schematic_id=schematic.id, page_number=page["page_number"],
            width=page.get("width"), height=page.get("height"),
            extracted_text=[page["extracted_text"]] if page["extracted_text"] else [],
        ))
    schematic.page_count = len(result.pages)
    schematic.import_status = "AWAITING_REVIEW"
    schematic.import_log = result.log
    db.commit()

    payload = result.as_dict()
    payload["schematic_id"] = schematic.id
    return payload


@router.get("/{schematic_id}")
def get_schematic(schematic_id: int, db: Session = Depends(get_db),
                  _=Depends(current_user)) -> dict:
    schematic = db.get(Schematic, schematic_id)
    if schematic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "schematic not found")
    return {
        "id": schematic.id, "project_id": schematic.project_id, "name": schematic.name,
        "drawing_number": schematic.drawing_number, "revision": schematic.revision,
        "original_filename": schematic.original_filename,
        "content_type": schematic.content_type, "page_count": schematic.page_count,
        "import_status": schematic.import_status, "import_log": schematic.import_log,
        "pages": [{"id": p.id, "page_number": p.page_number, "title": p.title,
                   "has_text": bool(p.extracted_text)} for p in schematic.pages],
        "original_url": f"/api/schematics/{schematic.id}/original",
    }


@router.get("/{schematic_id}/original")
def original(schematic_id: int, db: Session = Depends(get_db),
             _=Depends(current_user)) -> FileResponse:
    """The uploaded drawing, unmodified.

    The original is always the authority. The interactive circuit is a derived
    model, and a technician has to be able to check it against the drawing.
    """
    schematic = db.get(Schematic, schematic_id)
    if schematic is None or not schematic.storage_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "schematic file not found")
    path = Path(schematic.storage_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stored file missing")
    return FileResponse(path, media_type=schematic.content_type or "application/octet-stream",
                        filename=schematic.original_filename or path.name)


@router.post("/{schematic_id}/accept")
def accept_proposals(schematic_id: int, proposals: list[dict],
                     db: Session = Depends(get_db),
                     _=Depends(requires("edit_schematic"))) -> dict:
    """Commit reviewed proposals into the circuit model.

    Only what is sent here is committed, and everything committed is marked
    verified with the reviewer's acceptance behind it.
    """
    schematic = db.get(Schematic, schematic_id)
    if schematic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "schematic not found")
    project_id = schematic.project_id
    created = {"components": 0, "terminals": 0, "wires": 0, "nodes": 0,
               "connections": 0, "nets": 0}

    terminals: dict[str, Terminal] = {}
    # Nets are committed after everything else so their attachments already
    # exist as nodes.
    net_proposals = [p for p in proposals if p.get("kind") == "net"]
    proposals = [p for p in proposals if p.get("kind") != "net"]
    for proposal in proposals:
        kind = proposal.get("kind")
        payload = proposal.get("payload", {})
        if kind == "component":
            ref = payload.get("reference_designator")
            if not ref or db.scalars(select(Component).where(
                    Component.project_id == project_id,
                    Component.reference_designator == ref)).first():
                continue
            component = Component(
                project_id=project_id, reference_designator=ref,
                component_type=NodeType(payload.get("component_type", "UNKNOWN")),
                description=proposal.get("basis", ""), confidence=1.0, verified=True,
            )
            db.add(component)
            db.flush()
            created["components"] += 1
            _ensure_node(db, project_id, ref, component.component_type,
                         component_id=component.id,
                         controller_signal=payload.get("controller_signal", ""),
                         position=_layout_from(db, schematic_id, proposal))
            created["nodes"] += 1
        elif kind == "terminal":
            tag = payload.get("tag")
            existing = db.scalars(select(Terminal).where(
                Terminal.project_id == project_id, Terminal.tag == tag)).first()
            if existing:
                terminals[tag] = existing
                continue
            terminal = Terminal(
                project_id=project_id, tag=tag, block=payload.get("block", ""),
                number=payload.get("number", ""), description=proposal.get("basis", ""),
                confidence=1.0, verified=True,
            )
            db.add(terminal)
            db.flush()
            terminals[tag] = terminal
            created["terminals"] += 1
            _ensure_node(db, project_id, tag.replace("-", "_"), NodeType.TERMINAL,
                         terminal_id=terminal.id, label=tag,
                         position=_layout_from(db, schematic_id, proposal))
            created["nodes"] += 1
        elif kind == "wire":
            number = payload.get("wire_number")
            if not number or db.scalars(select(Wire).where(
                    Wire.project_id == project_id, Wire.wire_number == number)).first():
                continue
            db.add(Wire(project_id=project_id, wire_number=number, confidence=1.0,
                        verified=True))
            created["wires"] += 1
        elif kind == "connection":
            a = payload.get("from_terminal")
            b = payload.get("to_terminal")
            t_a = terminals.get(a) or db.scalars(select(Terminal).where(
                Terminal.project_id == project_id, Terminal.tag == a)).first()
            t_b = terminals.get(b) or db.scalars(select(Terminal).where(
                Terminal.project_id == project_id, Terminal.tag == b)).first()
            if not (t_a and t_b):
                continue
            wire = db.scalars(select(Wire).where(
                Wire.project_id == project_id,
                Wire.wire_number == payload.get("wire_number"))).first()
            db.add(Connection(project_id=project_id, wire_id=wire.id if wire else None,
                              from_terminal_id=t_a.id, to_terminal_id=t_b.id,
                              confidence=1.0, verified=True,
                              notes=proposal.get("basis", "")))
            node_a = _ensure_node(db, project_id, a.replace("-", "_"), NodeType.TERMINAL,
                                  terminal_id=t_a.id, label=a)
            node_b = _ensure_node(db, project_id, b.replace("-", "_"), NodeType.TERMINAL,
                                  terminal_id=t_b.id, label=b)
            db.add(CircuitEdge(project_id=project_id, from_node_id=node_a.id,
                               to_node_id=node_b.id, wire_id=wire.id if wire else None,
                               label=payload.get("wire_number", ""), confidence=1.0,
                               verified=True))
            created["connections"] += 1

    # --- traced conductors -------------------------------------------------
    # A net becomes a WIRE node with an edge to everything that lands on it.
    # Modelling the conductor as its own node keeps a device (a fuse, a coil)
    # as a node between two conductors instead of dissolving it into a wire,
    # which is what makes a trace stop at the component that broke.
    for proposal in net_proposals:
        payload = proposal.get("payload", {})
        wire_number = payload.get("wire_number")
        net_key = (wire_number or proposal.get("key") or "").replace("-", "_").upper()
        if not net_key:
            continue

        wire_row = None
        if wire_number:
            wire_row = db.scalars(select(Wire).where(
                Wire.project_id == project_id, Wire.wire_number == wire_number)).first()
            if wire_row is None:
                wire_row = Wire(project_id=project_id, wire_number=wire_number,
                                description=proposal.get("basis", ""),
                                confidence=1.0, verified=True)
                db.add(wire_row)
                db.flush()
                created["wires"] += 1

        net_node = _ensure_node(db, project_id, net_key, NodeType.WIRE,
                                label=wire_number or net_key,
                                position=_layout_from(db, schematic_id, proposal))
        if wire_row is not None and net_node.wire_id is None:
            net_node.wire_id = wire_row.id
        net_node.schematic_page_id = net_node.schematic_page_id or _page_id(
            db, schematic_id, proposal.get("page_number"))
        created["nets"] += 1

        for attachment in payload.get("attachments", []):
            key = (attachment.get("key") or "").strip()
            if not key:
                continue
            if attachment.get("kind") == "terminal":
                terminal_row = terminals.get(key) or db.scalars(select(Terminal).where(
                    Terminal.project_id == project_id, Terminal.tag == key)).first()
                if terminal_row is None:
                    terminal_row = Terminal(project_id=project_id, tag=key,
                                            description=proposal.get("basis", "")[:200],
                                            confidence=1.0, verified=True)
                    db.add(terminal_row)
                    db.flush()
                    terminals[key] = terminal_row
                    created["terminals"] += 1
                node = _ensure_node(db, project_id, key.replace("-", "_"), NodeType.TERMINAL,
                                    terminal_id=terminal_row.id, label=key)
            else:
                component_row = db.scalars(select(Component).where(
                    Component.project_id == project_id,
                    Component.reference_designator == key)).first()
                node_type = schematic_import.node_type_for(key)
                if component_row is None:
                    component_row = Component(
                        project_id=project_id, reference_designator=key,
                        component_type=node_type, description=proposal.get("basis", "")[:200],
                        confidence=1.0, verified=True)
                    db.add(component_row)
                    db.flush()
                    created["components"] += 1
                node = _ensure_node(db, project_id, key.replace("-", "_"), node_type,
                                    component_id=component_row.id, label=key,
                                    controller_signal=key.replace("-", "_")
                                    if node_type in (NodeType.CONTROLLER_INPUT,
                                                     NodeType.CONTROLLER_OUTPUT) else "")

            existing = db.scalars(select(CircuitEdge).where(
                CircuitEdge.project_id == project_id,
                CircuitEdge.from_node_id == net_node.id,
                CircuitEdge.to_node_id == node.id)).first()
            if existing is None:
                db.add(CircuitEdge(
                    project_id=project_id, from_node_id=net_node.id, to_node_id=node.id,
                    edge_type=EdgeType.CONNECTED_TO,
                    wire_id=wire_row.id if wire_row else None,
                    label=wire_number or "", confidence=1.0, verified=True,
                    notes=proposal.get("basis", "")[:500],
                ))
                created["connections"] += 1

    schematic.import_status = "REVIEWED"
    db.commit()
    return {"schematic_id": schematic_id, "created": created}


def _page_id(db: Session, schematic_id: int, page_number: int | None) -> int | None:
    if not page_number:
        return None
    page = db.scalars(select(SchematicPage).where(
        SchematicPage.schematic_id == schematic_id,
        SchematicPage.page_number == page_number)).first()
    return page.id if page else None


#: Drawing points to canvas pixels. Schematics are drawn with generous spacing
#: at 1 pt per unit; the interactive nodes are larger than the symbols they
#: stand for, so the layout needs room.
LAYOUT_SCALE = 1.6


def _layout_from(db: Session, schematic_id: int, proposal: dict) -> tuple[float, float] | None:
    """Place an imported node where it sits on the drawing.

    A graph laid out like the page it came from is navigable; the same graph
    with everything at the origin is not. PDF coordinates run bottom-up, the
    canvas runs top-down, so y is flipped against the page height.
    """
    bbox = (proposal.get("geometry") or {}).get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    page = db.scalars(select(SchematicPage).where(
        SchematicPage.schematic_id == schematic_id,
        SchematicPage.page_number == proposal.get("page_number"))).first()
    height = (page.height if page and page.height else None) or max(bbox[1], bbox[3])
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    return (round(cx * LAYOUT_SCALE, 1), round((height - cy) * LAYOUT_SCALE, 1))


def _ensure_node(db: Session, project_id: int, key: str, node_type, *,
                 component_id: int | None = None, terminal_id: int | None = None,
                 label: str = "", controller_signal: str = "",
                 position: tuple[float, float] | None = None) -> CircuitNode:
    node = db.scalars(select(CircuitNode).where(
        CircuitNode.project_id == project_id, CircuitNode.key == key)).first()
    if node:
        # An existing node keeps its position: a hand-placed node should not be
        # shoved around by a later import.
        if position and node.x is None and node.y is None:
            node.x, node.y = position
        return node
    node = CircuitNode(project_id=project_id, key=key, label=label or key,
                       node_type=node_type, component_id=component_id,
                       terminal_id=terminal_id, controller_signal=controller_signal,
                       x=position[0] if position else None,
                       y=position[1] if position else None,
                       confidence=1.0, verified=True)
    db.add(node)
    db.flush()
    return node
