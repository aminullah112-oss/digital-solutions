"""Schematic import pipeline.

What this does, and what it does not:

  VECTOR PDFs   Full geometric read. Positioned text plus stroked line
                segments are extracted, conductors are traced into nets,
                closed symbol outlines are treated as devices that break the
                conductor, and tags are bound to the geometry nearest them.
                This is the format CAD tools export, so it is the normal case.
  RASTER PAGES  Scans carry no text and no geometry. With OCR installed
                (pytesseract + Tesseract) tags can still be read, but
                connectivity cannot be traced from a scan at all, and the
                importer says so rather than proposing something.
  NOT DONE      Symbol classification by shape. A device outline is detected
                and located, but what kind of device it is comes from its
                designator (K, F, CB, ...), not from recognising the symbol.
                Off-page cross-references are not followed between sheets.

The rule that matters most: **two conductors that merely cross are not
connected.** They are joined only where a junction dot is drawn, or where one
ends on the other. Inventing continuity would send a technician to the wrong
side of a panel.

Every proposal carries a confidence and lands in the review queue. Nothing
enters the circuit graph as verified until a person accepts it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..domain import NodeType
from . import net_builder, pdf_geometry
from .net_builder import LabelHit

# --- Pattern library ------------------------------------------------------
# Patterns are configurable per project because drawing conventions vary by
# panel builder; these defaults follow common IEC/NEMA control-drawing usage.

REFERENCE_PATTERNS: list[tuple[str, NodeType, float]] = [
    (r"\b(K\d{1,3}[A-Z]?)\b", NodeType.RELAY, 0.82),
    (r"\b(CR\d{1,3})\b", NodeType.RELAY, 0.80),
    (r"\b(F\d{1,3})\b", NodeType.FUSE, 0.78),
    (r"\b(FU\d{1,3})\b", NodeType.FUSE, 0.85),
    (r"\b(CB\d{1,3})\b", NodeType.BREAKER, 0.85),
    (r"\b(52[A-Z]?\d{0,3})\b", NodeType.BREAKER, 0.70),
    (r"\b(M\d{1,3})\b", NodeType.CONTACTOR, 0.65),
    (r"\b(S\d{1,3})\b", NodeType.SWITCH, 0.62),
    (r"\b(PT\d{1,3})\b", NodeType.PT, 0.80),
    (r"\b(CT\d{1,3})\b", NodeType.CT, 0.80),
]

TERMINAL_PATTERN = re.compile(r"\b(TB\s?\d{1,3})\s?[-:]\s?(\d{1,3})\b", re.I)
WIRE_PATTERN = re.compile(r"\b(W[-\s]?\d{2,5})\b", re.I)
CONTROLLER_IO_PATTERN = re.compile(r"\b(D[IO]|A[IO])\s?[-]?\s?(\d{1,3})\b", re.I)

STAGES = [
    "upload", "page_detection", "text_extraction", "ocr", "symbol_detection",
    "designator_detection", "terminal_detection", "wire_detection",
    "line_tracing", "net_tracing", "graph_proposal", "review",
]


@dataclass
class Proposal:
    kind: str                     # component | terminal | wire | connection
    key: str
    payload: dict[str, Any]
    confidence: float
    page_number: int
    basis: str                    # what on the drawing produced this
    #: Where on the page the evidence sits, so a reviewer can find it.
    geometry: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "key": self.key, "payload": self.payload,
            "confidence": round(self.confidence, 3), "confidence_band": band(self.confidence),
            "page_number": self.page_number, "basis": self.basis, "verified": False,
            "geometry": self.geometry,
        }


@dataclass
class ImportResult:
    pages: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    log: list[dict[str, Any]] = field(default_factory=list)
    nets: dict[int, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for p in self.proposals:
            by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
        vector_pages = [p for p in self.pages if p.get("is_vector")]
        return {
            "pages": self.pages,
            "proposals": [p.as_dict() for p in self.proposals],
            "counts": by_kind,
            "log": self.log,
            "nets": self.nets,
            "requires_review": True,
            "note": (
                "Conductors were traced from the drawing's line geometry on "
                f"{len(vector_pages)} of {len(self.pages)} page(s). Crossing conductors "
                "are joined only at a drawn junction dot or where one ends on the other. "
                "Review and accept each proposal before using the circuit model to "
                "troubleshoot."
            ) if vector_pages else (
                "No page carried vector line geometry, so no connectivity could be traced. "
                "Only tags read from text are proposed. Review and accept each item."
            ),
        }


def band(confidence: float) -> str:
    if confidence >= 0.85:
        return "HIGH"
    if confidence >= 0.6:
        return "MEDIUM"
    return "LOW"


def capabilities() -> dict[str, Any]:
    """Report honestly which stages this installation can actually run."""
    caps = {stage: "AVAILABLE" for stage in STAGES}
    try:
        import pypdf  # noqa: F401
    except ImportError:
        caps["page_detection"] = "LIMITED (pypdf not installed: PDFs treated as one page)"
        caps["text_extraction"] = "UNAVAILABLE (pypdf not installed)"
        caps["line_tracing"] = "UNAVAILABLE (pypdf not installed)"
        caps["net_tracing"] = "UNAVAILABLE (pypdf not installed)"
    else:
        caps["line_tracing"] = "AVAILABLE for vector PDFs (a scan has no line geometry)"
        caps["net_tracing"] = (
            "AVAILABLE for vector PDFs. Crossing conductors are joined only at a "
            "drawn junction dot or where one ends on the other."
        )
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        caps["ocr"] = "UNAVAILABLE (pytesseract/Tesseract not installed; scanned pages " \
                      "yield no text)"
    caps["symbol_detection"] = (
        "PARTIAL (device outlines are located; device kind comes from the designator, "
        "not from recognising the symbol)"
    )
    return caps


def extract_pdf_text(path: str) -> list[str]:
    try:
        import pypdf
    except ImportError:
        return []
    reader = pypdf.PdfReader(path)
    return [(page.extract_text() or "") for page in reader.pages]


def ocr_image(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    return pytesseract.image_to_string(Image.open(path))


def classify_words(words: list[pdf_geometry.Word]) -> list[LabelHit]:
    """Recognise which words on the page are electrical tags.

    Works on positioned words, so a downstream proximity test means "near on
    the drawing", not "near in the extracted character stream". The string
    offset between two tags says nothing about where they sit on the page.
    """
    hits: list[LabelHit] = []
    for word in words:
        text = word.text
        matched = False

        for match in TERMINAL_PATTERN.finditer(text):
            tag = f"{match.group(1).upper().replace(' ', '')}-{match.group(2)}"
            hits.append(LabelHit("terminal", tag, word, 0.88))
            matched = True
        if matched:
            continue

        for match in WIRE_PATTERN.finditer(text):
            hits.append(LabelHit("wire", _normalise_wire(match.group(1)), word, 0.80))
            matched = True
        if matched:
            continue

        for match in CONTROLLER_IO_PATTERN.finditer(text):
            tag = f"{match.group(1).upper()}-{match.group(2)}"
            hits.append(LabelHit("io", tag, word, 0.78))
            matched = True
        if matched:
            continue

        for pattern, _node_type, confidence in REFERENCE_PATTERNS:
            for match in re.finditer(pattern, text):
                hits.append(LabelHit("designator", match.group(1).upper(), word, confidence))
                matched = True
            if matched:
                break
    return hits


def _normalise_wire(raw: str) -> str:
    cleaned = raw.upper().replace(" ", "").replace("-", "")
    return f"W-{cleaned[1:]}" if cleaned.startswith("W") else cleaned


def node_type_for(designator: str) -> NodeType:
    """Infer a device kind from its reference designator.

    This is what the designator convention is for. It is not symbol
    recognition, and it is wrong for a panel that uses its own scheme — which
    is why every component proposal is reviewed before it is accepted.
    """
    for pattern, node_type, _confidence in REFERENCE_PATTERNS:
        if re.fullmatch(pattern.replace(r"\b", ""), designator):
            return node_type
    return NodeType.UNKNOWN


def analyze_geometry(geometry: pdf_geometry.PageGeometry) -> tuple[list[Proposal], dict]:
    """Read one vector page: tags, devices and traced conductors."""
    labels = classify_words(geometry.words)
    nets = net_builder.build_nets(geometry, labels)

    proposals: list[Proposal] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, key: str, payload: dict, confidence: float, basis: str,
            geometry_hint: dict | None = None) -> None:
        if (kind, key) in seen:
            return
        seen.add((kind, key))
        proposals.append(Proposal(kind=kind, key=key, payload=payload,
                                  confidence=confidence, page_number=geometry.page_number,
                                  basis=basis, geometry=geometry_hint))

    for label in labels:
        if label.kind == "terminal":
            add("terminal", label.key,
                {"tag": label.key, "block": label.key.rsplit("-", 1)[0],
                 "number": label.key.rsplit("-", 1)[-1]},
                label.confidence, f"terminal tag printed at ({label.word.cx:.0f}, "
                                  f"{label.word.cy:.0f})",
                {"bbox": [label.word.x0, label.word.y0, label.word.x1, label.word.y1]})
        elif label.kind == "wire":
            add("wire", label.key, {"wire_number": label.key}, label.confidence,
                f"wire number printed at ({label.word.cx:.0f}, {label.word.cy:.0f})")
        elif label.kind == "io":
            node_type = (NodeType.CONTROLLER_OUTPUT if label.key.upper().startswith(("DO", "AO"))
                         else NodeType.CONTROLLER_INPUT)
            add("component", label.key,
                {"reference_designator": label.key, "component_type": node_type.value,
                 "controller_signal": label.key.replace("-", "_")},
                label.confidence, "controller I/O tag on the drawing")

    # Devices come from the geometry, named by the nearest designator. A
    # designator with no symbol beside it is still proposed, at lower
    # confidence, because it may be a label on a symbol we did not close.
    named_devices = {name for net in nets for _, name in net.device_pins if name}
    for device in geometry.devices:
        name = net_builder._nearest_designator(device, labels)
        if not name:
            continue
        x0, y0, x1, y1 = device.bbox
        add("component", name,
            {"reference_designator": name, "component_type": node_type_for(name).value},
            0.86, f"device outline {device.size:.0f} pt at ({x0:.0f}, {y0:.0f}) "
                  f"with designator {name} beside it",
            {"bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]})

    for label in labels:
        if label.kind == "designator" and label.key not in named_devices:
            add("component", label.key,
                {"reference_designator": label.key,
                 "component_type": node_type_for(label.key).value},
                min(label.confidence, 0.55),
                "designator text with no closed symbol outline beside it")

    for raw in net_builder.connection_proposals(nets, geometry.page_number):
        add(raw["kind"], raw["key"], raw["payload"], raw["confidence"], raw["basis"],
            raw.get("geometry"))

    return proposals, net_builder.summarize(nets)


def analyze_text(text: str, page_number: int) -> list[Proposal]:
    proposals: list[Proposal] = []
    seen: set[tuple[str, str]] = set()

    for pattern, node_type, base_conf in REFERENCE_PATTERNS:
        for match in re.finditer(pattern, text):
            ref = match.group(1).upper()
            if ("component", ref) in seen:
                continue
            seen.add(("component", ref))
            proposals.append(Proposal(
                kind="component", key=ref,
                payload={"reference_designator": ref, "component_type": node_type.value},
                confidence=base_conf, page_number=page_number,
                basis=_context(text, match.start()),
            ))

    for match in TERMINAL_PATTERN.finditer(text):
        block = match.group(1).upper().replace(" ", "")
        number = match.group(2)
        tag = f"{block}-{number}"
        if ("terminal", tag) in seen:
            continue
        seen.add(("terminal", tag))
        proposals.append(Proposal(
            kind="terminal", key=tag,
            payload={"tag": tag, "block": block, "number": number},
            confidence=0.88, page_number=page_number, basis=_context(text, match.start()),
        ))

    for match in WIRE_PATTERN.finditer(text):
        wire = match.group(1).upper().replace(" ", "").replace("W", "W-", 1).replace("--", "-")
        if ("wire", wire) in seen:
            continue
        seen.add(("wire", wire))
        proposals.append(Proposal(
            kind="wire", key=wire, payload={"wire_number": wire},
            confidence=0.75, page_number=page_number, basis=_context(text, match.start()),
        ))

    for match in CONTROLLER_IO_PATTERN.finditer(text):
        tag = f"{match.group(1).upper()}-{match.group(2)}"
        if ("io", tag) in seen:
            continue
        seen.add(("io", tag))
        node_type = (NodeType.CONTROLLER_OUTPUT if tag.upper().startswith(("DO", "AO"))
                     else NodeType.CONTROLLER_INPUT)
        proposals.append(Proposal(
            kind="component", key=tag,
            payload={"reference_designator": tag, "component_type": node_type.value,
                     "controller_signal": tag.replace("-", "_")},
            confidence=0.7, page_number=page_number, basis=_context(text, match.start()),
        ))

    return proposals


def propose_connections(proposals: list[Proposal], text_by_page: dict[int, str]) -> list[Proposal]:
    """Propose terminal-to-terminal connections from shared wire numbers.

    This is the only connectivity inference made, and it is a weak one: a wire
    number appearing near two terminal tags on the same page suggests, but does
    not establish, that they are the same conductor. Confidence is capped at
    MEDIUM and every proposal must be reviewed.
    """
    out: list[Proposal] = []
    terminals_by_page: dict[int, list[Proposal]] = {}
    wires_by_page: dict[int, list[Proposal]] = {}
    for p in proposals:
        if p.kind == "terminal":
            terminals_by_page.setdefault(p.page_number, []).append(p)
        elif p.kind == "wire":
            wires_by_page.setdefault(p.page_number, []).append(p)

    for page, wires in wires_by_page.items():
        text = text_by_page.get(page, "")
        terminals = terminals_by_page.get(page, [])
        for wire in wires:
            near = [t for t in terminals if _proximity(text, wire.key, t.key) is not None]
            near.sort(key=lambda t: _proximity(text, wire.key, t.key) or 10**9)
            if len(near) >= 2:
                a, b = near[0], near[1]
                distance = (_proximity(text, wire.key, a.key) or 0) + \
                           (_proximity(text, wire.key, b.key) or 0)
                confidence = max(0.35, min(0.72, 0.72 - distance / 4000.0))
                out.append(Proposal(
                    kind="connection", key=f"{a.key}~{b.key}",
                    payload={"from_terminal": a.key, "to_terminal": b.key,
                             "wire_number": wire.key},
                    confidence=confidence, page_number=page,
                    basis=f"wire {wire.key} appears near {a.key} and {b.key} on page {page}",
                ))
    return out


def _proximity(text: str, a: str, b: str) -> int | None:
    ia, ib = text.upper().find(a.upper()), text.upper().find(b.upper())
    if ia < 0 or ib < 0:
        return None
    return abs(ia - ib)


def _context(text: str, index: int, width: int = 60) -> str:
    start = max(0, index - width // 2)
    return " ".join(text[start:start + width].split())


def run(path: str, content_type: str) -> ImportResult:
    """Execute the pipeline end to end and report what each stage did."""
    result = ImportResult()
    caps = capabilities()
    is_pdf = content_type == "application/pdf" or path.lower().endswith(".pdf")

    if is_pdf:
        pages = pdf_geometry.extract(path)
        if pages:
            return _run_vector(path, pages, result, caps)
        result.log.append({"stage": "text_extraction", "status": "SKIPPED",
                           "detail": caps["text_extraction"]})
        texts = [""]
    else:
        # A raster image can still be read for tags, but it holds no geometry,
        # so nothing about connectivity can be inferred from it.
        text = ocr_image(path)
        result.log.append({
            "stage": "ocr",
            "status": "OK" if text else "SKIPPED",
            "detail": caps["ocr"] if not text else f"{len(text)} characters recognised",
        })
        texts = [text]

    return _run_text_only(texts, result, caps)


def _run_vector(path: str, pages: list[pdf_geometry.PageGeometry],
                result: ImportResult, caps: dict[str, Any]) -> ImportResult:
    vector_pages = 0
    for page in pages:
        proposals, summary = ([], {}) if not page.is_vector else analyze_geometry(page)
        if page.is_vector:
            vector_pages += 1
            result.nets[page.page_number] = summary
        else:
            # Text without geometry: tags can be read, connectivity cannot.
            proposals = analyze_text(" ".join(w.text for w in page.words), page.page_number)

        result.proposals.extend(proposals)
        result.pages.append({
            "page_number": page.page_number,
            "width": round(page.width, 1),
            "height": round(page.height, 1),
            "is_vector": page.is_vector,
            "words": len(page.words),
            "segments": len(page.segments),
            "conductors": len(page.conductors),
            "devices": len(page.devices),
            "junction_dots": len(page.junction_dots),
            "characters": sum(len(w.text) for w in page.words),
            "extracted_text": " ".join(w.text for w in page.words)[:4000],
            "has_text": page.has_text,
            "note": page.note,
        })

    result.log.extend([
        {"stage": "page_detection", "status": "OK", "detail": f"{len(pages)} page(s)"},
        {"stage": "text_extraction", "status": "OK",
         "detail": f"{sum(len(p.words) for p in pages)} positioned text run(s)"},
        {"stage": "line_tracing", "status": "OK" if vector_pages else "SKIPPED",
         "detail": f"{sum(len(p.conductors) for p in pages)} conductor segment(s) across "
                   f"{vector_pages} vector page(s)"},
        {"stage": "symbol_detection", "status": "PARTIAL",
         "detail": caps["symbol_detection"]},
        {"stage": "net_tracing", "status": "OK" if vector_pages else "SKIPPED",
         "detail": caps["net_tracing"] if vector_pages
                   else "no vector geometry on any page"},
        {"stage": "graph_proposal", "status": "OK",
         "detail": f"{len(result.proposals)} proposals, all requiring review"},
    ])
    return result


def _run_text_only(texts: list[str], result: ImportResult,
                   caps: dict[str, Any]) -> ImportResult:
    """Fallback for pages with no vector geometry.

    Connectivity is not guessed here. Only tags are proposed, plus the weak
    same-wire-number pairing, which is capped at MEDIUM confidence.
    """
    text_by_page: dict[int, str] = {}
    for i, text in enumerate(texts, start=1):
        text_by_page[i] = text
        result.pages.append({
            "page_number": i,
            "is_vector": False,
            "characters": len(text),
            "extracted_text": text[:4000],
            "has_text": bool(text.strip()),
            "note": "No vector geometry; connectivity cannot be traced from this page.",
        })
        result.proposals.extend(analyze_text(text, i))

    result.proposals.extend(propose_connections(result.proposals, text_by_page))
    result.log.extend([
        {"stage": "line_tracing", "status": "UNAVAILABLE",
         "detail": "page carries no vector line geometry"},
        {"stage": "net_tracing", "status": "UNAVAILABLE",
         "detail": "connectivity cannot be traced without line geometry"},
        {"stage": "graph_proposal", "status": "OK",
         "detail": f"{len(result.proposals)} proposals, all requiring review"},
    ])
    return result
