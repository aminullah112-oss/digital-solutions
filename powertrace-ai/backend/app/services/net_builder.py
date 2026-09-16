"""Build electrical nets from extracted page geometry.

This is the step that turns a picture into connectivity, and it is where a
schematic reader earns or loses trust. The rules it follows are the drawing
conventions, not convenient approximations:

  * Two segments sharing an endpoint are the same conductor.
  * An endpoint landing on another segment's interior is a T-junction, and is
    the same conductor.
  * **Two segments whose interiors cross are NOT connected.** Wires cross on
    schematics constantly without being joined. Connecting them would
    manufacture continuity that does not exist, which in a fault-finding tool
    means sending a technician to the wrong side of a panel.
  * A crossing is only joined when a junction dot is drawn on it — which is
    exactly what the dot means.

Everything produced here is a proposal with a confidence, and every proposal
records the geometry that produced it so a reviewer can check it against the
drawing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .pdf_geometry import PageGeometry, Segment, Shape, Word

#: Endpoints within this distance are the same point. CAD exports are exact,
#: but rounding through the PDF coordinate system leaves sub-point gaps.
JOIN_TOLERANCE_PT = 1.5
#: A junction dot within this distance of a segment sits on it.
DOT_TOLERANCE_PT = 3.0
#: A conductor endpoint this close to a device outline is landing on its pin.
PIN_TOLERANCE_PT = 3.0
#: How far a label can sit from a conductor and still belong to it. Wire
#: numbers are written tight against the wire; component designators are not.
WIRE_LABEL_MAX_PT = 16.0
TERMINAL_LABEL_MAX_PT = 20.0
DESIGNATOR_MAX_PT = 26.0
#: Spatial grid cell. Large enough that a segment touches few cells, small
#: enough that a cell holds few segments.
GRID_PT = 24.0


@dataclass
class LabelHit:
    """A word on the page that was recognised as an electrical tag."""

    kind: str   # wire | terminal | designator | io
    key: str
    word: Word
    confidence: float


@dataclass
class Net:
    """A set of segments that form one electrical conductor on this page."""

    id: int
    segments: list[Segment]
    wire_numbers: list[tuple[str, float]] = field(default_factory=list)
    terminals: list[tuple[str, float]] = field(default_factory=list)
    components: list[tuple[str, float]] = field(default_factory=list)
    #: Device symbols this conductor lands on, as (shape_id, designator).
    device_pins: list[tuple[int, str]] = field(default_factory=list)
    junction_dots: int = 0
    joins: dict[str, int] = field(default_factory=dict)

    @property
    def total_length(self) -> float:
        return sum(s.length for s in self.segments)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [v for s in self.segments for v in (s.x0, s.x1)]
        ys = [v for s in self.segments for v in (s.y0, s.y1)]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def wire_number(self) -> str | None:
        return self.wire_numbers[0][0] if self.wire_numbers else None

    @property
    def conflicting_wire_numbers(self) -> list[str]:
        """More than one wire number on a single traced conductor.

        Either the drawing renumbers at a junction — common and harmless — or
        the tracer joined two conductors that are not actually one. Worth a
        reviewer's eye either way, so it is surfaced rather than resolved by
        picking the nearest and moving on.
        """
        return [k for k, _ in self.wire_numbers] if len(self.wire_numbers) > 1 else []

    def as_dict(self) -> dict[str, Any]:
        x0, y0, x1, y1 = self.bbox
        return {
            "id": self.id,
            "wire_number": self.wire_number,
            "wire_candidates": [{"key": k, "distance": round(d, 2)}
                                for k, d in self.wire_numbers],
            "conflicting_wire_numbers": self.conflicting_wire_numbers,
            "terminals": [{"key": k, "distance": round(d, 2)} for k, d in self.terminals],
            "components": [{"key": k, "distance": round(d, 2)} for k, d in self.components],
            "device_pins": [{"shape_id": sid, "designator": name}
                            for sid, name in self.device_pins],
            "segment_count": len(self.segments),
            "total_length": round(self.total_length, 1),
            "junction_dots": self.junction_dots,
            "joins": self.joins,
            "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
        }


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, index: int) -> int:
        while self._parent[index] != index:
            self._parent[index] = self._parent[self._parent[index]]
            index = self._parent[index]
        return index

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1
        return True


class _SegmentGrid:
    """Spatial index so joining is near-linear instead of quadratic.

    A drawing page routinely carries a few thousand segments; an all-pairs
    comparison is tens of millions of distance computations per page.
    """

    def __init__(self, segments: list[Segment], cell: float = GRID_PT) -> None:
        self.cell = cell
        self._buckets: dict[tuple[int, int], list[int]] = {}
        for index, segment in enumerate(segments):
            for key in self._cells_for(segment):
                self._buckets.setdefault(key, []).append(index)

    def _cells_for(self, segment: Segment) -> Iterable[tuple[int, int]]:
        x0, x1 = sorted((segment.x0, segment.x1))
        y0, y1 = sorted((segment.y0, segment.y1))
        for cx in range(int(x0 // self.cell), int(x1 // self.cell) + 1):
            for cy in range(int(y0 // self.cell), int(y1 // self.cell) + 1):
                yield (cx, cy)

    def near_point(self, x: float, y: float) -> set[int]:
        cx, cy = int(x // self.cell), int(y // self.cell)
        found: set[int] = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                found.update(self._buckets.get((cx + dx, cy + dy), ()))
        return found


def build_nets(geometry: PageGeometry, labels: list[LabelHit]) -> list[Net]:
    # Only conductors take part in net tracing. A closed device outline is a
    # two-terminal component sitting in the run, not a length of wire; tracing
    # through it would merge the conductors on either side of a coil or fuse
    # into one net and hide the very break a technician is looking for.
    segments = geometry.conductors
    if not segments:
        return []

    union = _UnionFind(len(segments))
    grid = _SegmentGrid(segments)
    joins = {"shared_endpoint": 0, "t_junction": 0, "junction_dot": 0}

    # --- shared endpoints and T-junctions ---------------------------------
    for index, segment in enumerate(segments):
        for px, py in segment.endpoints():
            for other_index in grid.near_point(px, py):
                if other_index == index:
                    continue
                other = segments[other_index]
                # Shared endpoint.
                if any(math.hypot(px - ox, py - oy) <= JOIN_TOLERANCE_PT
                       for ox, oy in other.endpoints()):
                    if union.union(index, other_index):
                        joins["shared_endpoint"] += 1
                    continue
                # T-junction: this endpoint lands on the other's interior.
                if other.distance_to_point(px, py) <= JOIN_TOLERANCE_PT:
                    if union.union(index, other_index):
                        joins["t_junction"] += 1

    # --- junction dots ----------------------------------------------------
    # A dot is the drawing's explicit statement that the conductors meeting
    # here are joined. It is the only thing that connects a plain crossing.
    dot_counts: dict[int, int] = {}
    for dot in geometry.junction_dots:
        touching = [
            i for i in grid.near_point(dot.x, dot.y)
            if segments[i].distance_to_point(dot.x, dot.y) <= DOT_TOLERANCE_PT
        ]
        if len(touching) < 2:
            continue
        first = touching[0]
        for other in touching[1:]:
            if union.union(first, other):
                joins["junction_dot"] += 1
        dot_counts[union.find(first)] = dot_counts.get(union.find(first), 0) + 1

    # --- materialize nets -------------------------------------------------
    grouped: dict[int, list[Segment]] = {}
    for index, segment in enumerate(segments):
        grouped.setdefault(union.find(index), []).append(segment)

    nets = [
        Net(id=i, segments=members, junction_dots=dot_counts.get(root, 0), joins=dict(joins))
        for i, (root, members) in enumerate(sorted(grouped.items()), start=1)
    ]

    _attach_labels(nets, labels)
    _attach_devices(nets, geometry.devices, labels)
    return nets


def _attach_devices(nets: list[Net], devices: list[Shape],
                    labels: list[LabelHit]) -> None:
    """Bind each device symbol to the conductors landing on its pins.

    The device's designator is the nearest designator label to its outline —
    schematics print it beside the symbol, not beside the wire.
    """
    for device in devices:
        designator = _nearest_designator(device, labels)
        for net in nets:
            touches = any(
                device.distance_to_point(px, py) <= PIN_TOLERANCE_PT
                for segment in net.segments
                for px, py in segment.endpoints()
            )
            if touches:
                net.device_pins.append((device.id, designator))


def _nearest_designator(device: Shape, labels: list[LabelHit]) -> str:
    x0, y0, x1, y1 = device.bbox
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    best: tuple[float, str] | None = None
    for label in labels:
        if label.kind not in ("designator", "io"):
            continue
        distance = min(
            device.distance_to_point(label.word.cx, label.word.cy),
            math.hypot(label.word.cx - cx, label.word.cy - cy),
        )
        if distance <= DESIGNATOR_MAX_PT and (best is None or distance < best[0]):
            best = (distance, label.key)
    return best[1] if best else ""


def _attach_labels(nets: list[Net], labels: list[LabelHit]) -> None:
    """Assign each recognised tag to the nearest net it can plausibly belong to."""
    limits = {
        "wire": WIRE_LABEL_MAX_PT,
        "terminal": TERMINAL_LABEL_MAX_PT,
        "io": TERMINAL_LABEL_MAX_PT,
        "designator": DESIGNATOR_MAX_PT,
    }

    for label in labels:
        limit = limits.get(label.kind, DESIGNATOR_MAX_PT)
        # Measure from the text's anchor — the one position the PDF states
        # exactly. The bounding box width is approximated from the font size,
        # so measuring from its centre would let a wide label drift onto a
        # conductor that merely crosses beneath it.
        ax, ay = label.word.x0, label.word.y0
        best: tuple[float, Net] | None = None
        for net in nets:
            distances = [d for d in (s.projected_distance(ax, ay) for s in net.segments)
                         if d is not None]
            if not distances:
                continue
            distance = min(distances)
            if distance <= limit and (best is None or distance < best[0]):
                best = (distance, net)
        if best is None:
            continue
        distance, net = best
        if label.kind == "wire":
            net.wire_numbers.append((label.key, distance))
        elif label.kind in ("terminal", "io"):
            net.terminals.append((label.key, distance))
        else:
            net.components.append((label.key, distance))

    for net in nets:
        net.wire_numbers.sort(key=lambda pair: pair[1])
        net.terminals.sort(key=lambda pair: pair[1])
        net.components.sort(key=lambda pair: pair[1])


def net_confidence(net: Net) -> float:
    """How much the geometry supports this net's identity.

    Driven by what the drawing actually shows: a labelled conductor that lands
    on two named endpoints is strong; an unlabelled fragment with one endpoint
    is weak, whatever its length.
    """
    score = 0.30
    if net.wire_numbers:
        # A wire number printed within a few points of the conductor is the
        # strongest single piece of evidence on the page.
        score += 0.30 * max(0.0, 1.0 - net.wire_numbers[0][1] / WIRE_LABEL_MAX_PT)
    endpoints = len(net.terminals) + len([1 for _, n in net.device_pins if n])
    if endpoints >= 2:
        score += 0.25
    elif endpoints == 1:
        score += 0.10
    if net.junction_dots:
        score += 0.05
    if net.conflicting_wire_numbers:
        score -= 0.15
    if len(net.segments) == 1 and not net.wire_numbers and endpoints == 0:
        # A lone unlabelled stroke is as likely to be a symbol detail or a
        # border rule as a conductor.
        score -= 0.20
    return max(0.05, min(0.95, score))


def connection_proposals(nets: list[Net], page_number: int) -> list[dict[str, Any]]:
    """Emit one proposal per traced conductor.

    A net becomes a WIRE node with an edge to everything that lands on it —
    terminals and device pins alike. That is exactly what the conductor is,
    and it keeps a device (a fuse, a coil) as a node between two conductors
    rather than dissolving it into a wire.
    """
    proposals: list[dict[str, Any]] = []
    for net in nets:
        attachments = [{"kind": "terminal", "key": key} for key, _ in net.terminals]
        attachments += [{"kind": "component", "key": name}
                        for _, name in net.device_pins if name]
        # A conductor with fewer than two things on it tells us nothing about
        # connectivity; it is a stub, a border rule or a symbol detail.
        if len(attachments) < 2:
            continue
        wire = net.wire_number
        x0, y0, x1, y1 = net.bbox
        proposals.append({
            "kind": "net",
            "key": wire or f"NET-{page_number}-{net.id}",
            "payload": {
                "wire_number": wire,
                "net_id": net.id,
                "attachments": attachments,
                "conflicting_wire_numbers": net.conflicting_wire_numbers,
            },
            "confidence": net_confidence(net),
            "page_number": page_number,
            "basis": (
                f"traced conductor: {len(net.segments)} segment(s), "
                f"{round(net.total_length)} pt, "
                + (f"labelled {wire}" if wire else "no wire number found")
                + f"; {net.junction_dots} junction dot(s); lands on "
                + ", ".join(a["key"] for a in attachments)
                + (f". NOTE: this conductor carries more than one wire number "
                   f"({', '.join(net.conflicting_wire_numbers)}) — confirm it is "
                   f"really one conductor."
                   if net.conflicting_wire_numbers else "")
            ),
            "geometry": {"bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]},
        })
    return proposals


def summarize(nets: list[Net]) -> dict[str, Any]:
    labelled = [n for n in nets if n.wire_numbers]
    connected = [n for n in nets if len(n.terminals) + len(n.device_pins) >= 2]
    return {
        "nets": len(nets),
        "labelled_nets": len(labelled),
        "nets_with_two_endpoints": len(connected),
        "orphan_fragments": len([n for n in nets
                                 if len(n.segments) == 1 and not n.wire_numbers
                                 and not n.terminals]),
        "nets_with_conflicting_numbers": len([n for n in nets
                                              if n.conflicting_wire_numbers]),
        "note": (
            "Crossing conductors are only joined where a junction dot is drawn. "
            "Two wires that merely cross on the page are left unconnected, which "
            "is what the drawing means."
        ),
    }
