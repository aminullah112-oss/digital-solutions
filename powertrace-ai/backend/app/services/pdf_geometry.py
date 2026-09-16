"""Geometry extraction from vector PDF schematics.

Schematics exported from AutoCAD Electrical, EPLAN, SEE Electrical and similar
tools are vector PDFs: the wires are real line segments with coordinates and
the tags are real text with coordinates. That is the difference between
guessing at a drawing and reading it.

This module pulls two things out of a page:

  * positioned words  — every text run with its bounding box
  * stroked segments  — every straight line the drawing paints

Fills are skipped, except that small filled blobs are kept separately as
candidate junction dots. Symbol bodies, hatching and title-block shading are
fills and would otherwise swamp the wire geometry.

A scanned drawing has none of this. It is raster, so it yields no segments and
no text, and the importer says so rather than pretending.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

# Segments shorter than this are almost always symbol detail (arrowheads,
# contact ticks, hatching), not wire runs.
MIN_SEGMENT_LENGTH_PT = 2.0
# A filled path with a bounding box under this size is a candidate junction dot.
MAX_JUNCTION_DOT_PT = 6.0
# Tolerance for treating a line as exactly horizontal or vertical.
ORTHOGONAL_TOLERANCE_PT = 0.35
# A closed outline at least this large is a device symbol; anything smaller is
# a terminal or junction marker drawn on the conductor.
DEVICE_MIN_SIZE_PT = 10.0


Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply(m1: Matrix, m2: Matrix) -> Matrix:
    """m1 applied first, then m2 — PDF's own concatenation order."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


@dataclass
class Word:
    """A text run with its position on the page (PDF coordinates)."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    def distance_to_point(self, x: float, y: float) -> float:
        dx = max(self.x0 - x, 0.0, x - self.x1)
        dy = max(self.y0 - y, 0.0, y - self.y1)
        return math.hypot(dx, dy)

    def as_dict(self) -> dict[str, Any]:
        return {"text": self.text, "x0": self.x0, "y0": self.y0,
                "x1": self.x1, "y1": self.y1}


@dataclass
class Segment:
    """A stroked straight line in page coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float
    #: Which drawn subpath produced this segment.
    shape_id: int = -1
    #: True when that subpath closed on itself. A closed shape is a symbol
    #: outline (a coil, a fuse body, a terminal marker), not a conductor.
    closed: bool = False

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def orientation(self) -> str:
        if abs(self.y1 - self.y0) <= ORTHOGONAL_TOLERANCE_PT:
            return "H"
        if abs(self.x1 - self.x0) <= ORTHOGONAL_TOLERANCE_PT:
            return "V"
        return "D"

    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return ((self.x0, self.y0), (self.x1, self.y1))

    def projected_distance(self, px: float, py: float) -> float | None:
        """Perpendicular distance, or None when the point does not sit beside
        the segment's body.

        The distinction matters for labels. A wire number is written alongside
        the run it names; a tag that is merely near a segment's end is usually
        naming something else. Requiring the projection to land on the body
        stops a label being claimed by a conductor that happens to cross near
        it.
        """
        dx, dy = self.x1 - self.x0, self.y1 - self.y0
        denom = dx * dx + dy * dy
        if denom == 0.0:
            return None
        t = ((px - self.x0) * dx + (py - self.y0) * dy) / denom
        if t < -0.02 or t > 1.02:
            return None
        return math.hypot(px - (self.x0 + t * dx), py - (self.y0 + t * dy))

    def distance_to_point(self, px: float, py: float) -> float:
        """Perpendicular distance to the segment, clamped to its extent."""
        dx, dy = self.x1 - self.x0, self.y1 - self.y0
        denom = dx * dx + dy * dy
        if denom == 0.0:
            return math.hypot(px - self.x0, py - self.y0)
        t = max(0.0, min(1.0, ((px - self.x0) * dx + (py - self.y0) * dy) / denom))
        return math.hypot(px - (self.x0 + t * dx), py - (self.y0 + t * dy))

    def as_dict(self) -> dict[str, Any]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1,
                "orientation": self.orientation, "shape_id": self.shape_id,
                "closed": self.closed}


@dataclass
class Shape:
    """A closed stroked outline: a device symbol or a terminal marker.

    Size is the discriminator. A coil, fuse body or controller block is drawn
    at symbol scale; a terminal or junction marker is a few points across.
    Getting this wrong matters: a device breaks the conductor, a terminal
    marker does not.
    """

    id: int
    segments: list["Segment"]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [v for s in self.segments for v in (s.x0, s.x1)]
        ys = [v for s in self.segments for v in (s.y0, s.y1)]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def size(self) -> float:
        x0, y0, x1, y1 = self.bbox
        return max(x1 - x0, y1 - y0)

    @property
    def is_device(self) -> bool:
        return self.size >= DEVICE_MIN_SIZE_PT

    def distance_to_point(self, x: float, y: float) -> float:
        return min(s.distance_to_point(x, y) for s in self.segments)

    def as_dict(self) -> dict[str, Any]:
        x0, y0, x1, y1 = self.bbox
        return {"id": self.id, "bbox": [round(x0, 1), round(y0, 1),
                                        round(x1, 1), round(y1, 1)],
                "size": round(self.size, 1), "is_device": self.is_device}


@dataclass
class JunctionDot:
    x: float
    y: float
    size: float


@dataclass
class PageGeometry:
    page_number: int
    width: float
    height: float
    words: list[Word] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    shapes: list[Shape] = field(default_factory=list)
    junction_dots: list[JunctionDot] = field(default_factory=list)
    #: Why this page yielded nothing, when it yielded nothing.
    note: str = ""

    @property
    def is_vector(self) -> bool:
        return bool(self.segments)

    @property
    def conductors(self) -> list[Segment]:
        """Segments that are wire runs, not symbol outlines."""
        device_shapes = {s.id for s in self.shapes if s.is_device}
        return [s for s in self.segments if s.shape_id not in device_shapes]

    @property
    def devices(self) -> list[Shape]:
        return [s for s in self.shapes if s.is_device]

    @property
    def has_text(self) -> bool:
        return bool(self.words)


class _PathInterpreter:
    """Minimal PDF content-stream interpreter for path construction.

    It tracks the CTM through q/Q/cm, builds paths from m/l/re/h (curves are
    reduced to their endpoints), and emits segments only for paths that are
    actually stroked. That stroke filter is what keeps symbol fills and title
    block shading out of the wire geometry.
    """

    def __init__(self, next_shape_id: int = 0) -> None:
        self.segments: list[Segment] = []
        self.shapes: list[Shape] = []
        self.dots: list[JunctionDot] = []
        self._ctm: Matrix = IDENTITY
        self._stack: list[Matrix] = []
        self._current: list[tuple[float, float]] = []
        self._subpaths: list[tuple[list[tuple[float, float]], bool]] = []
        self._start: tuple[float, float] | None = None
        self._explicitly_closed = False
        self._next_shape_id = next_shape_id

    # --- path building ----------------------------------------------------
    def _flush_subpath(self) -> None:
        if len(self._current) >= 2:
            first, last = self._current[0], self._current[-1]
            closed = self._explicitly_closed or (
                len(self._current) >= 4
                and math.hypot(first[0] - last[0], first[1] - last[1]) <= 0.6
            )
            self._subpaths.append((self._current, closed))
        self._current = []
        self._explicitly_closed = False

    def _moveto(self, x: float, y: float) -> None:
        self._flush_subpath()
        point = apply(self._ctm, x, y)
        self._current = [point]
        self._start = point

    def _lineto(self, x: float, y: float) -> None:
        if not self._current:
            self._current = [apply(self._ctm, x, y)]
            return
        self._current.append(apply(self._ctm, x, y))

    def _rect(self, x: float, y: float, w: float, h: float) -> None:
        self._flush_subpath()
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        self._subpaths.append(([apply(self._ctm, cx, cy) for cx, cy in corners], True))

    def _close(self) -> None:
        if self._current and self._start:
            self._current.append(self._start)
            self._explicitly_closed = True

    def _emit_stroked(self) -> None:
        self._flush_subpath()
        for points, closed in self._subpaths:
            shape_id = self._next_shape_id
            self._next_shape_id += 1
            members: list[Segment] = []
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                segment = Segment(x0, y0, x1, y1, shape_id=shape_id, closed=closed)
                if segment.length >= MIN_SEGMENT_LENGTH_PT:
                    members.append(segment)
            if not members:
                continue
            self.segments.extend(members)
            if closed:
                self.shapes.append(Shape(id=shape_id, segments=members))
        self._reset_path()

    def _emit_filled(self) -> None:
        """Keep only small filled blobs, as candidate junction dots."""
        self._flush_subpath()
        for points, _closed in self._subpaths:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if 0 < w <= MAX_JUNCTION_DOT_PT and 0 < h <= MAX_JUNCTION_DOT_PT:
                self.dots.append(JunctionDot(
                    x=(min(xs) + max(xs)) / 2.0, y=(min(ys) + max(ys)) / 2.0,
                    size=max(w, h),
                ))
        self._reset_path()

    def _reset_path(self) -> None:
        self._current = []
        self._subpaths = []
        self._start = None
        self._explicitly_closed = False

    # --- dispatch ---------------------------------------------------------
    def run(self, operations: Iterable[tuple[list[Any], bytes]], base: Matrix = IDENTITY) -> None:
        self._ctm = base
        for operands, operator in operations:
            try:
                self._apply(operands, operator)
            except (TypeError, ValueError, IndexError):
                # A malformed operand should skip one operator, not abandon the
                # page. Real-world CAD exports contain surprises.
                continue

    def _apply(self, operands: list[Any], operator: bytes) -> None:
        op = operator.decode("latin-1") if isinstance(operator, bytes) else str(operator)
        nums = [float(v) for v in operands if _is_number(v)]

        if op == "q":
            self._stack.append(self._ctm)
        elif op == "Q":
            if self._stack:
                self._ctm = self._stack.pop()
        elif op == "cm" and len(nums) >= 6:
            self._ctm = multiply(tuple(nums[:6]), self._ctm)  # type: ignore[arg-type]
        elif op == "m" and len(nums) >= 2:
            self._moveto(nums[0], nums[1])
        elif op == "l" and len(nums) >= 2:
            self._lineto(nums[0], nums[1])
        elif op == "re" and len(nums) >= 4:
            self._rect(nums[0], nums[1], nums[2], nums[3])
        elif op in ("c", "v", "y") and len(nums) >= 2:
            # Curves are reduced to their endpoint. Wires in a schematic are
            # straight; a curve is a symbol detail or a line-hop arc, and
            # approximating it keeps the path connected without inventing a
            # run of geometry that is not there.
            self._lineto(nums[-2], nums[-1])
        elif op == "h":
            self._close()
        elif op in ("S", "s", "B", "B*", "b", "b*"):
            if op in ("s", "b", "b*"):
                self._close()
            self._emit_stroked()
        elif op in ("f", "F", "f*"):
            self._emit_filled()
        elif op == "n":
            self._reset_path()


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def extract(path: str) -> list[PageGeometry]:
    """Read every page's words and stroked segments.

    Returns an empty list if pypdf is not installed — the caller reports that
    as a missing capability rather than as an empty drawing.
    """
    try:
        from pypdf import PdfReader
        from pypdf.generic import ContentStream
    except ImportError:
        return []

    reader = PdfReader(path)
    pages: list[PageGeometry] = []

    for index, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        width = float(box.width)
        height = float(box.height)
        geometry = PageGeometry(page_number=index, width=width, height=height)

        # --- text with positions -----------------------------------------
        words: list[Word] = []

        def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
            cleaned = text.strip()
            if not cleaned:
                return
            try:
                matrix = multiply(tuple(tm), tuple(cm))  # type: ignore[arg-type]
                x, y = matrix[4], matrix[5]
                size = float(font_size or 0) or 8.0
                scale = abs(matrix[3]) or 1.0
            except (TypeError, ValueError):
                return
            height_pt = size * scale
            # Character width is approximated; exact advance widths need the
            # font metrics and buy nothing here, since every downstream use is
            # a proximity test against a bounding box.
            width_pt = 0.55 * height_pt * len(cleaned)
            words.append(Word(cleaned, x, y, x + width_pt, y + height_pt))

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:  # noqa: BLE001 - a bad font must not lose the page
            pass
        geometry.words = words

        # --- stroked geometry --------------------------------------------
        interpreter = _PathInterpreter()
        try:
            contents = page.get_contents()
            if contents is not None:
                stream = ContentStream(contents, reader)
                interpreter.run(stream.operations)
            _run_form_xobjects(page, reader, interpreter, ContentStream)
        except Exception as exc:  # noqa: BLE001
            geometry.note = f"path extraction failed: {exc}"

        geometry.segments = interpreter.segments
        geometry.shapes = interpreter.shapes
        geometry.junction_dots = interpreter.dots

        if not geometry.segments and not geometry.words:
            geometry.note = geometry.note or (
                "Page contains no extractable text or vector geometry. It is most "
                "likely a scan; connectivity cannot be read from it."
            )
        elif not geometry.segments:
            geometry.note = geometry.note or (
                "Page has text but no vector line geometry, so wire runs cannot be "
                "traced from it."
            )
        pages.append(geometry)

    return pages


def _run_form_xobjects(page: Any, reader: Any, interpreter: _PathInterpreter,
                       content_stream_cls: Any, depth: int = 0) -> None:
    """CAD exporters commonly wrap the drawing body in a Form XObject.

    One level of recursion covers the usual case; deeper nesting is rare and
    is not worth the risk of a cycle.
    """
    if depth > 1:
        return
    try:
        resources = page.get("/Resources")
        xobjects = resources.get("/XObject") if resources else None
        if not xobjects:
            return
        for name in list(xobjects.keys()):
            xobject = xobjects[name].get_object()
            if xobject.get("/Subtype") != "/Form":
                continue
            matrix = xobject.get("/Matrix")
            base: Matrix = tuple(float(v) for v in matrix) if matrix else IDENTITY  # type: ignore
            stream = content_stream_cls(xobject, reader)
            nested = _PathInterpreter(next_shape_id=interpreter._next_shape_id + 1000)
            nested.run(stream.operations, base=base)
            interpreter.segments.extend(nested.segments)
            interpreter.shapes.extend(nested.shapes)
            interpreter.dots.extend(nested.dots)
            interpreter._next_shape_id = nested._next_shape_id
    except Exception:  # noqa: BLE001 - xobject handling is best-effort
        return


def capabilities() -> dict[str, str]:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return {
            "geometry": "UNAVAILABLE",
            "detail": "pypdf is not installed; no PDF text or geometry can be read.",
        }
    return {
        "geometry": "AVAILABLE",
        "detail": (
            "Vector PDFs yield positioned text and stroked line segments. Scanned "
            "(raster) PDFs yield neither."
        ),
    }
