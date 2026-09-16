"""Schematic import pipeline.

What this actually does, and what it does not:

  IMPLEMENTED   page detection, embedded-text extraction, pattern recognition
                of reference designators, terminal tags and wire numbers, and
                proposal of connections where the same wire number appears at
                two terminals.
  OPTIONAL      OCR of scanned pages (requires pytesseract + Tesseract).
  NOT DONE      symbol recognition and line/vector tracing. Proposing a
                connection from a drawn line needs vector geometry work that
                is not implemented, and guessing at it would put fabricated
                connectivity into a diagnostic tool.

Every proposal carries a confidence and lands in the review queue. Nothing
enters the circuit graph as verified until a person accepts it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..domain import NodeType

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
    "line_tracing", "graph_proposal", "review",
]


@dataclass
class Proposal:
    kind: str                     # component | terminal | wire | connection
    key: str
    payload: dict[str, Any]
    confidence: float
    page_number: int
    basis: str                    # what text actually produced this

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "key": self.key, "payload": self.payload,
            "confidence": round(self.confidence, 3), "confidence_band": band(self.confidence),
            "page_number": self.page_number, "basis": self.basis, "verified": False,
        }


@dataclass
class ImportResult:
    pages: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    log: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for p in self.proposals:
            by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
        return {
            "pages": self.pages,
            "proposals": [p.as_dict() for p in self.proposals],
            "counts": by_kind,
            "log": self.log,
            "requires_review": True,
            "note": (
                "These are proposals read from the drawing's text. Connectivity that is "
                "only drawn as a line is not extracted. Review and accept each item before "
                "using the circuit model for troubleshooting."
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
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        caps["ocr"] = "UNAVAILABLE (pytesseract/Tesseract not installed; scanned pages " \
                      "yield no text)"
    caps["symbol_detection"] = "NOT IMPLEMENTED (symbols are not recognised)"
    caps["line_tracing"] = "NOT IMPLEMENTED (drawn connections are not extracted)"
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

    if content_type == "application/pdf" or path.lower().endswith(".pdf"):
        texts = extract_pdf_text(path)
        if not texts:
            result.log.append({"stage": "text_extraction", "status": "SKIPPED",
                               "detail": caps["text_extraction"]})
            texts = [""]
        else:
            result.log.append({"stage": "text_extraction", "status": "OK",
                               "detail": f"{len(texts)} page(s) of embedded text"})
    else:
        text = ocr_image(path)
        result.log.append({
            "stage": "ocr",
            "status": "OK" if text else "SKIPPED",
            "detail": caps["ocr"] if not text else f"{len(text)} characters recognised",
        })
        texts = [text]

    text_by_page: dict[int, str] = {}
    for i, text in enumerate(texts, start=1):
        text_by_page[i] = text
        result.pages.append({
            "page_number": i,
            "characters": len(text),
            "extracted_text": text[:4000],
            "has_text": bool(text.strip()),
        })
        result.proposals.extend(analyze_text(text, i))

    result.proposals.extend(propose_connections(result.proposals, text_by_page))

    result.log.extend([
        {"stage": "symbol_detection", "status": "NOT_IMPLEMENTED",
         "detail": caps["symbol_detection"]},
        {"stage": "line_tracing", "status": "NOT_IMPLEMENTED", "detail": caps["line_tracing"]},
        {"stage": "graph_proposal", "status": "OK",
         "detail": f"{len(result.proposals)} proposals, all requiring review"},
    ])
    return result
