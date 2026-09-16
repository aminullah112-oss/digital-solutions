from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...domain import MV_SAFETY_NOTICE
from ...models import CircuitNode, Terminal
from ...schemas import CircuitNodeIn
from ...security import current_user, requires
from ...services import circuit_graph as cg
from ...services.diagnostics import node_statuses
from ...services.terminal_status import terminal_status

router = APIRouter(prefix="/api/circuits", tags=["circuits"])


@router.get("/{project_id}")
def get_circuit(project_id: int, include_status: bool = True, db: Session = Depends(get_db),
                _=Depends(current_user)) -> dict:
    graph = cg.load_graph(db, project_id)
    payload = {
        "project_id": project_id,
        "nodes": list(graph.nodes.values()),
        "edges": [cg._edge_payload(e) for e in graph.edges],
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "unverified_nodes": [n["key"] for n in graph.nodes.values() if not n["verified"]],
        "unverified_edges": [e.id for e in graph.edges if not e.verified],
    }
    if include_status:
        payload["status"] = node_statuses(db, project_id)
    return payload


@router.get("/{project_id}/node/{node_key}")
def get_node(project_id: int, node_key: str, db: Session = Depends(get_db),
             _=Depends(current_user)) -> dict:
    node = db.scalars(select(CircuitNode).where(CircuitNode.project_id == project_id,
                                                CircuitNode.key == node_key)).first()
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"node {node_key} not found")
    terminal = db.get(Terminal, node.terminal_id) if node.terminal_id else None
    graph = cg.load_graph(db, project_id)
    payload = cg.node_payload(node, None, terminal, None)
    payload.update({
        "status": terminal_status(db, node, terminal),
        "neighbours": {
            "upstream": [k for k, _ in graph.neighbours(node_key, "up")],
            "downstream": [k for k, _ in graph.neighbours(node_key, "down")],
            "connected": [k for k, _ in graph.neighbours(node_key, "both")],
        },
    })
    return payload


@router.get("/{project_id}/trace/{node_key}")
def trace(project_id: int, node_key: str,
          direction: str = Query("both", pattern="^(up|down|both)$"),
          max_depth: int = Query(12, ge=1, le=40),
          db: Session = Depends(get_db), _=Depends(current_user)) -> dict:
    graph = cg.load_graph(db, project_id)
    try:
        result = cg.trace(graph, node_key, direction=direction, max_depth=max_depth)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"node {node_key} not found") from None
    result["status"] = node_statuses(db, project_id, [n["key"] for n in result["nodes"]])
    if any(n.get("medium_voltage") for n in result["nodes"]):
        result["safety_notice"] = MV_SAFETY_NOTICE
    return result


@router.get("/{project_id}/highlight/{node_key}")
def highlight(project_id: int, node_key: str, db: Session = Depends(get_db),
              _=Depends(current_user)) -> dict:
    graph = cg.load_graph(db, project_id)
    if node_key not in graph.nodes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"node {node_key} not found")
    result = cg.highlight_circuit(graph, node_key)
    result["status"] = node_statuses(db, project_id, result["node_keys"])
    if result["medium_voltage"]:
        result["safety_notice"] = MV_SAFETY_NOTICE
    return result


@router.get("/{project_id}/search")
def search_circuit(project_id: int, q: str, db: Session = Depends(get_db),
                   _=Depends(current_user)) -> dict:
    graph = cg.load_graph(db, project_id)
    matches = cg.find(graph, q)
    if not matches:
        matches = cg.nodes_by_controller_signal(graph, q)
    return {"query": q, "results": matches[:50], "count": len(matches)}


@router.get("/{project_id}/path")
def path(project_id: int, from_key: str, to_key: str, db: Session = Depends(get_db),
         _=Depends(current_user)) -> dict:
    graph = cg.load_graph(db, project_id)
    keys = cg.shortest_path(graph, from_key, to_key)
    return {
        "from": from_key, "to": to_key, "found": keys is not None,
        "path": [graph.nodes[k] for k in (keys or [])],
    }


@router.post("/nodes", status_code=status.HTTP_201_CREATED)
def create_node(payload: CircuitNodeIn, db: Session = Depends(get_db),
                _=Depends(requires("edit_schematic"))) -> dict:
    existing = db.scalars(select(CircuitNode).where(
        CircuitNode.project_id == payload.project_id, CircuitNode.key == payload.key)).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "a node with that key exists")
    node = CircuitNode(**payload.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    return cg.node_payload(node)


@router.post("/nodes/{node_id}/verify")
def verify_node(node_id: int, db: Session = Depends(get_db),
                _=Depends(requires("edit_schematic"))) -> dict:
    node = db.get(CircuitNode, node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "node not found")
    node.verified = True
    node.confidence = 1.0
    db.commit()
    return {"id": node.id, "key": node.key, "verified": True}
