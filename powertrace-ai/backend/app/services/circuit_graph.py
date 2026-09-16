"""Circuit graph: construction, traversal and tracing.

The graph is the schematic's meaning, separated from its drawing.  Traversal
is direction-aware: POWERED_BY / FEEDS / RETURNS_TO describe energy flow,
CONTROLLED_BY / SIGNAL_TO describe command flow, and CONNECTED_TO is
undirected continuity.  Tracing upstream from a terminal therefore walks back
toward the source rather than wandering across the whole drawing.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import MEDIUM_VOLTAGE_THRESHOLD_V, MV_SAFETY_NOTICE, EdgeType, NodeType
from ..models import CircuitEdge, CircuitNode, Component, Terminal, Wire

#: Edge types whose direction means "power/signal flows from -> to".
DIRECTED = {
    EdgeType.FEEDS, EdgeType.SIGNAL_TO, EdgeType.CONTROLLED_BY,
    EdgeType.POWERED_BY, EdgeType.RETURNS_TO,
}
#: For POWERED_BY and CONTROLLED_BY the arrow points at the source, so flow is
#: the reverse of the stored direction.
REVERSED_FLOW = {EdgeType.POWERED_BY, EdgeType.CONTROLLED_BY}


@dataclass
class GraphEdge:
    id: int
    from_key: str
    to_key: str
    edge_type: EdgeType
    label: str = ""
    wire_number: str = ""
    confidence: float = 1.0
    verified: bool = False

    def flow(self) -> tuple[str, str]:
        if self.edge_type in REVERSED_FLOW:
            return self.to_key, self.from_key
        return self.from_key, self.to_key


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    _down: dict[str, list[GraphEdge]] = field(default_factory=lambda: defaultdict(list))
    _up: dict[str, list[GraphEdge]] = field(default_factory=lambda: defaultdict(list))
    _any: dict[str, list[GraphEdge]] = field(default_factory=lambda: defaultdict(list))

    def index(self) -> "Graph":
        self._down.clear(); self._up.clear(); self._any.clear()
        for e in self.edges:
            src, dst = e.flow()
            self._any[src].append(e)
            self._any[dst].append(e)
            if e.edge_type in DIRECTED:
                self._down[src].append(e)
                self._up[dst].append(e)
            else:
                self._down[src].append(e); self._down[dst].append(e)
                self._up[src].append(e); self._up[dst].append(e)
        return self

    def neighbours(self, key: str, direction: str) -> list[tuple[str, GraphEdge]]:
        table = {"down": self._down, "up": self._up}.get(direction, self._any)
        out: list[tuple[str, GraphEdge]] = []
        for e in table[key]:
            src, dst = e.flow()
            other = dst if src == key else src
            if other != key:
                out.append((other, e))
        return out


def load_graph(db: Session, project_id: int) -> Graph:
    nodes = db.scalars(select(CircuitNode).where(CircuitNode.project_id == project_id)).all()
    edges = db.scalars(select(CircuitEdge).where(CircuitEdge.project_id == project_id)).all()
    wires = {w.id: w for w in db.scalars(select(Wire).where(Wire.project_id == project_id))}
    components = {
        c.id: c for c in db.scalars(select(Component).where(Component.project_id == project_id))
    }
    terminals = {
        t.id: t for t in db.scalars(select(Terminal).where(Terminal.project_id == project_id))
    }

    by_id = {n.id: n for n in nodes}
    graph = Graph()
    for n in nodes:
        graph.nodes[n.key] = node_payload(n, components.get(n.component_id),
                                          terminals.get(n.terminal_id), wires.get(n.wire_id))
    for e in edges:
        src, dst = by_id.get(e.from_node_id), by_id.get(e.to_node_id)
        if not src or not dst:
            continue
        graph.edges.append(GraphEdge(
            id=e.id, from_key=src.key, to_key=dst.key, edge_type=EdgeType(e.edge_type),
            label=e.label, wire_number=wires[e.wire_id].wire_number if e.wire_id in wires else "",
            confidence=e.confidence, verified=e.verified,
        ))
    return graph.index()


def node_payload(
    n: CircuitNode, component: Component | None = None,
    terminal: Terminal | None = None, wire: Wire | None = None,
) -> dict[str, Any]:
    nominal = n.nominal_voltage_v
    payload: dict[str, Any] = {
        "id": n.id,
        "key": n.key,
        "label": n.label or n.key,
        "node_type": str(n.node_type),
        "component_id": n.component_id,
        "terminal_id": n.terminal_id,
        "wire_id": n.wire_id,
        "controller_id": n.controller_id,
        "controller_signal": n.controller_signal,
        "schematic_page_id": n.schematic_page_id,
        "nominal_voltage_v": nominal,
        "x": n.x, "y": n.y,
        "confidence": n.confidence,
        "verified": n.verified,
        "attributes": n.attributes or {},
        "medium_voltage": bool(nominal and nominal >= MEDIUM_VOLTAGE_THRESHOLD_V),
    }
    if payload["medium_voltage"]:
        payload["safety_notice"] = MV_SAFETY_NOTICE
    if component:
        payload["component"] = {
            "reference_designator": component.reference_designator,
            "component_type": str(component.component_type),
            "description": component.description,
            "rating": component.rating,
            "location": component.location,
            "part_number": component.part_number,
        }
    if terminal:
        payload["terminal"] = {
            "tag": terminal.tag, "block": terminal.block, "number": terminal.number,
            "description": terminal.description,
            "expected_voltage_v": terminal.expected_voltage_v,
            "expected_reference": terminal.expected_reference,
            "expected_tolerance_pct": terminal.expected_tolerance_pct,
            "expected_signal_type": terminal.expected_signal_type,
        }
    if wire:
        payload["wire"] = {
            "wire_number": wire.wire_number, "color": wire.color, "gauge": wire.gauge,
        }
    return payload


def trace(
    graph: Graph, start_key: str, *, direction: str = "both", max_depth: int = 12,
) -> dict[str, Any]:
    """Breadth-first trace from a node.

    Returns the visited nodes with their depth, the edges walked, and the
    ordered paths — the path list is what the Circuit Explorer renders as
    "EMCP DO-07 -> W105 -> TB23-14 -> K12 -> ...".
    """
    if start_key not in graph.nodes:
        raise KeyError(start_key)

    visited: dict[str, int] = {start_key: 0}
    parents: dict[str, tuple[str, GraphEdge] | None] = {start_key: None}
    walked: list[GraphEdge] = []
    order: list[str] = [start_key]
    queue: deque[str] = deque([start_key])

    while queue:
        key = queue.popleft()
        depth = visited[key]
        if depth >= max_depth:
            continue
        for other, edge in graph.neighbours(key, direction):
            if other in visited:
                continue
            visited[other] = depth + 1
            parents[other] = (key, edge)
            walked.append(edge)
            order.append(other)
            queue.append(other)

    leaves = [k for k in visited if not _has_children(graph, k, direction, visited)]
    paths = [_path_to(parents, leaf) for leaf in leaves if leaf != start_key]
    return {
        "start": start_key,
        "direction": direction,
        "max_depth": max_depth,
        "nodes": [{**graph.nodes[k], "depth": visited[k]} for k in order],
        "edges": [_edge_payload(e) for e in walked],
        "paths": paths,
        "truncated": any(d >= max_depth for d in visited.values()),
    }


def _has_children(graph: Graph, key: str, direction: str, visited: dict[str, int]) -> bool:
    return any(other not in visited or visited[other] > visited[key]
               for other, _ in graph.neighbours(key, direction))


def _path_to(parents: dict[str, tuple[str, GraphEdge] | None], leaf: str) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    cursor: str | None = leaf
    while cursor is not None:
        parent = parents.get(cursor)
        if parent is None:
            chain.append({"key": cursor, "via": None})
            break
        prev, edge = parent
        chain.append({"key": cursor, "via": _edge_payload(edge)})
        cursor = prev
    return list(reversed(chain))


def _edge_payload(e: GraphEdge) -> dict[str, Any]:
    return {
        "id": e.id, "from": e.from_key, "to": e.to_key, "edge_type": e.edge_type.value,
        "label": e.label, "wire_number": e.wire_number,
        "confidence": e.confidence, "verified": e.verified,
    }


def highlight_circuit(graph: Graph, start_key: str, *, max_depth: int = 16) -> dict[str, Any]:
    """The full galvanically-connected circuit around a node: everything
    reachable through continuity plus the source and return ends."""
    up = trace(graph, start_key, direction="up", max_depth=max_depth)
    down = trace(graph, start_key, direction="down", max_depth=max_depth)
    keys = {n["key"] for n in up["nodes"]} | {n["key"] for n in down["nodes"]}
    edge_ids = {e["id"] for e in up["edges"]} | {e["id"] for e in down["edges"]}
    sources = [k for k in keys if graph.nodes[k]["node_type"] in
               (NodeType.SOURCE.value, NodeType.BUS.value)]
    grounds = [k for k in keys if graph.nodes[k]["node_type"] == NodeType.GROUND.value]
    return {
        "start": start_key,
        "node_keys": sorted(keys),
        "edge_ids": sorted(edge_ids),
        "nodes": [graph.nodes[k] for k in sorted(keys)],
        "upstream": up,
        "downstream": down,
        "sources": sources,
        "returns": grounds,
        "medium_voltage": any(graph.nodes[k].get("medium_voltage") for k in keys),
    }


def shortest_path(graph: Graph, from_key: str, to_key: str) -> list[str] | None:
    if from_key not in graph.nodes or to_key not in graph.nodes:
        return None
    prev: dict[str, str | None] = {from_key: None}
    queue = deque([from_key])
    while queue:
        key = queue.popleft()
        if key == to_key:
            break
        for other, _ in graph.neighbours(key, "both"):
            if other not in prev:
                prev[other] = key
                queue.append(other)
    if to_key not in prev:
        return None
    out: list[str] = []
    cursor: str | None = to_key
    while cursor is not None:
        out.append(cursor)
        cursor = prev[cursor]
    return list(reversed(out))


def nodes_by_controller_signal(graph: Graph, signal: str) -> list[dict[str, Any]]:
    want = signal.replace("-", "_").upper()
    return [n for n in graph.nodes.values()
            if n.get("controller_signal", "").replace("-", "_").upper() == want]


def find(graph: Graph, query: str) -> list[dict[str, Any]]:
    """Loose search across keys, labels, designators, terminals and wires."""
    q = query.strip().lower()
    if not q:
        return []
    hits: list[tuple[int, dict[str, Any]]] = []
    for node in graph.nodes.values():
        haystack: Iterable[str] = filter(None, [
            node["key"], node["label"], node.get("controller_signal", ""),
            (node.get("component") or {}).get("reference_designator", ""),
            (node.get("terminal") or {}).get("tag", ""),
            (node.get("wire") or {}).get("wire_number", ""),
        ])
        for text in haystack:
            low = text.lower()
            if low == q:
                hits.append((0, node)); break
            if low.startswith(q):
                hits.append((1, node)); break
            if q in low:
                hits.append((2, node)); break
    hits.sort(key=lambda pair: (pair[0], pair[1]["key"]))
    return [n for _, n in hits]
