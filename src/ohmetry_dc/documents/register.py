"""The document register and master index. Every deliverable gets an id, a revision (the package revision), an issue (P1, P2, ...), a status and cross-references.

The register is built by scanning the real files, so it cannot list a document that does not exist or miss one that does. A file that matches no rule is reported.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import yaml

from ohmetry_dc.models import ProjectConfig

PREFIX = "OHM-DC-2000"
WB_TITLES = {1: "Master design basis", 2: "Load estimation", 3: "Power architecture", 4: "Transformer sizing", 5: "Generator sizing", 6: "UPS sizing", 7: "Battery sizing (interface)", 8: "Cable sizing", 9: "Voltage drop",
             10: "Short-circuit levels", 11: "LV switchgear", 12: "MV switchgear", 13: "Busduct sizing", 14: "Protection coordination (register)", 15: "Earthing and bonding (screening)", 16: "Lightning protection (register)",
             17: "Power quality (register)", 18: "Energy efficiency", 19: "Generator fuel (register)", 20: "Master equipment schedule"}
SPEC_TITLES = {1: "Power transformers", 2: "Standby generator sets", 3: "UPS systems", 4: "UPS batteries", 5: "MV switchgear", 6: "LV switchgear and assemblies", 7: "Power cables", 8: "Busduct", 9: "Protection and coordination", 10: "Earthing, bonding and lightning interface"}
TRN_TITLES = {1: "Introduction to data centre electrical design", 2: "IT load, facility load and PUE", 3: "Architecture, A/B paths and redundancy", 4: "MV distribution and transformer sizing", 5: "Generator sizing and transients",
              6: "UPS architecture and battery sizing", 7: "LV distribution and switchgear", 8: "Cable sizing, ampacity and voltage drop", 9: "Short-circuit and protection coordination", 10: "Earthing, lightning and power quality",
              11: "Single-line diagrams, schedules and reports", 12: "Commissioning, FAT, SAT and IST"}
MET_FOR_WB = {2: ["load_estimation"], 4: ["power_system_sizing"], 5: ["power_system_sizing"], 6: ["power_system_sizing"], 7: ["power_system_sizing"], 3: ["power_system_sizing"], 8: ["distribution"], 9: ["distribution"], 11: ["distribution"],
              12: ["distribution"], 13: ["distribution"], 10: ["short_circuit_and_earthing"], 14: ["short_circuit_and_earthing"], 15: ["short_circuit_and_earthing"], 18: ["load_estimation"]}
SPEC_WB = {1: [4, 10], 2: [5, 19], 3: [6, 7], 4: [7], 5: [12, 10], 6: [11, 10], 7: [8, 9], 8: [13], 9: [14], 10: [15, 16]}
TRN_WB = {1: [1, 2], 2: [2, 18], 3: [3], 4: [4], 5: [5, 19], 6: [6, 7], 7: [11, 12, 13], 8: [8, 9], 9: [10, 14], 10: [15, 16, 17], 11: [20, 1], 12: []}


def _issue(root: Path) -> tuple[str, dict]:
    p = root / "config" / "document_revisions.yaml"
    d = yaml.safe_load(p.read_text()) if p.exists() else {}
    return (d or {}).get("default_issue", "P1"), (d or {}).get("overrides") or {}


def _scan(root: Path) -> list[tuple[str, str, str, str, str]]:
    """(repo-relative path, id suffix, title, type, status)."""
    out: list[tuple[str, str, str, str, str]] = []
    PRE = "PRELIMINARY: NOT VERIFIED"

    def add(path: Path, suffix: str, title: str, typ: str, status: str):
        out.append((str(path.relative_to(root)), suffix, title, typ, status))

    for p in sorted((root / "workbooks" / "generated").glob("*.xlsx")):
        n = int(p.name[:2])
        add(p, f"WB-{n:02d}", f"Workbook {p.stem}: {WB_TITLES.get(n, p.stem)}", "Workbook", PRE)
    for p in sorted((root / "reports" / "generated").glob("*.pdf")):
        add(p, "RPT-02", "Electrical load estimation report", "Report", PRE)
    for p in sorted((root / "drawings").rglob("OHM-DC-2000-SLD-001.*")):
        add(p, "DRW-001", "Preliminary single-line diagram", "Drawing", "PRELIMINARY CONCEPT: NOT FOR CONSTRUCTION")
    for p in sorted((root / "specifications").rglob("*")):
        m = re.search(r"SPEC-(\d\d)_", p.name)
        if p.is_file() and m:
            n = int(m.group(1))
            add(p, f"SPEC-{n:02d}", f"Specification template: {SPEC_TITLES.get(n, '')}", "Specification template", "DRAFT TEMPLATE")
    for sub, prefix, typ in (("calculation_methodology", "MET", "Methodology"), ("user_guide", "GUIDE", "User guide"), ("design_basis", "BASIS", "Design basis"), ("engineering_review", "ERV", "Engineering review note")):
        for i, p in enumerate(sorted((root / "docs" / sub).glob("*.md")), 1):
            add(p, f"{prefix}-{i:02d}", f"{typ}: {p.stem.replace('_', ' ')}", typ, "WORKING DOCUMENT")
    for p in sorted((root / "training" / "modules").rglob("*")):
        m = re.match(r"(\d\d)_", p.name)
        if p.is_file() and m:
            n = int(m.group(1))
            add(p, f"TRN-{n:02d}", f"Training module {n:02d}: {TRN_TITLES[n]}", "Training", "PRELIMINARY: NOT INDEPENDENTLY REVIEWED")
    for sub, sfx, title in (("exercises", "TRN-13", "Training exercise workbook"), ("assessments", "TRN-14", "Training assessment question bank"), ("answer_keys", "TRN-15", "Training answer key")):
        for p in sorted((root / "training" / sub).glob("*")):
            add(p, sfx, title, "Training", "PRELIMINARY: NOT INDEPENDENTLY REVIEWED")
    for p in sorted((root / "training").glob("Completion_Certificate_Template.*")):
        add(p, "TRN-16", "Completion certificate template", "Training", "TEMPLATE: not accredited")
    reg = {"assumptions_register.yaml": ("REG-01", "Assumptions register"), "standards_register.yaml": ("REG-02", "Standards register (all NOT_VERIFIED)"), "manufacturer_data_register.yaml": ("REG-03", "Manufacturer-data register"),
           "manufacturer_data_overrides.yaml": ("REG-04", "Supplied-data overrides and history"), "design_exceptions.yaml": ("REG-05", "Accepted design-target exceptions"), "design_basis_revisions.yaml": ("REG-06", "Design basis revision log"),
           "document_revisions.yaml": ("REG-08", "Document revision convention and history")}
    for name, (sfx, title) in reg.items():
        if (root / "config" / name).exists():
            add(root / "config" / name, sfx, title, "Register", "WORKING RECORD")
    for p in sorted((root / "output").glob("manufacturer_data_*")):
        add(p, "REG-03", "Manufacturer-data register (generated view / import template)", "Register", "WORKING RECORD")
    for p in sorted((root / "output").glob("OUTSTANDING_VERIFICATION_ITEMS.*")):
        add(p, "REG-07", "Outstanding verification items", "Register", "WORKING RECORD")
    if (root / "output" / "WORKBOOK_LINT.md").exists():
        add(root / "output" / "WORKBOOK_LINT.md", "LOG-05", "Workbook static lint (Excel compatibility)", "Log", "WORKING RECORD")
    if (root / "config" / "verification_log.yaml").exists():
        add(root / "config" / "verification_log.yaml", "REG-09", "Verification attestation log (append-only; names self-declared, not authenticated)", "Register", "WORKING RECORD")
    if (root / "output" / "QA_RESULTS.md").exists():
        add(root / "output" / "QA_RESULTS.md", "LOG-04", "QA test results", "Log", "WORKING RECORD")
    for name, sfx, title in (("ENGINEERING_REVIEW_LOG.md", "LOG-01", "Engineering review log"), ("DEVELOPMENT_STATUS.md", "LOG-02", "Development status"), ("RELEASE_CHECKLIST.md", "LOG-03", "Release checklist"),
                             ("README.md", "DOC-05", "Engineer's README (repository)"), ("LICENSE", "DOC-06", "Repository licence placeholder")):
        if (root / name).exists():
            add(root / name, sfx, title, "Log" if sfx.startswith("LOG") else "Document", "WORKING RECORD")
    for p in sorted((root / "docs" / "release").glob("*")):
        m = {"CUSTOMER_README": ("DOC-01", "Customer README", "PRELIMINARY: NOT VERIFIED"), "LICENCE_COMMERCIAL": ("DOC-02", "Commercial licence (draft, not legally reviewed)", "DRAFT: NOT LEGALLY REVIEWED"),
             "MASTER_INDEX": ("DOC-00", "Master index", "WORKING RECORD"), "CORRECTIVE_ACTION_REPORT": ("DOC-07", "Corrective action report (revision A6)", "FOR REVIEW"), "REVIEWER_CHECKLIST": ("DOC-03", "Independent reviewer checklist", "FOR REVIEW"), "REVIEW_GUIDE": ("DOC-04", "Independent review guide", "FOR REVIEW")}.get(p.stem)
        if p.is_file() and m:
            add(p, m[0], m[1], "Document", m[2])
    return out


def build_register(root: Path, cfg: ProjectConfig) -> list[dict]:
    default_issue, overrides = _issue(root)
    rows = []
    for path, sfx, title, typ, status in _scan(root):
        did = f"{PREFIX}-{sfx}"
        rows.append({"id": did, "title": title, "type": typ, "path": path, "revision": cfg.project.revision, "issue": overrides.get(did, default_issue), "status": status, "related": []})
    by_sfx = {}
    for r in rows:
        by_sfx.setdefault(r["id"], []).append(r)

    def link(a: str, b: str):
        for ra in by_sfx.get(f"{PREFIX}-{a}", []):
            if f"{PREFIX}-{b}" not in ra["related"]:
                ra["related"].append(f"{PREFIX}-{b}")
        for rb in by_sfx.get(f"{PREFIX}-{b}", []):
            if f"{PREFIX}-{a}" not in rb["related"]:
                rb["related"].append(f"{PREFIX}-{a}")

    met = {}
    for r in rows:
        if r["type"] == "Methodology":
            met[Path(r["path"]).stem] = r["id"].replace(f"{PREFIX}-", "")
    for n, names in MET_FOR_WB.items():
        for nm in names:
            if nm in met:
                link(f"WB-{n:02d}", met[nm])
    for n, wbs in SPEC_WB.items():
        for w in wbs:
            link(f"SPEC-{n:02d}", f"WB-{w:02d}")
    for n, wbs in TRN_WB.items():
        for w in wbs:
            link(f"TRN-{n:02d}", f"WB-{w:02d}")
    for w in (3, 20):
        link("DRW-001", f"WB-{w:02d}")
    link("DRW-001", "SPEC-05")
    link("RPT-02", "WB-02")
    for w in range(1, 21):
        link(f"WB-{w:02d}", "REG-03")
    link("REG-03", "REG-04")
    link("DOC-01", "DOC-02")
    link("DOC-01", "DOC-00")
    link("DOC-03", "DOC-04")
    link("DOC-03", "REG-07")
    link("LOG-01", "REG-07")
    for r in rows:
        r["related"] = sorted(r["related"])
    return rows


def unregistered(root: Path, files: list[str]) -> list[str]:
    known = {p for p, *_ in _scan(root)}
    return [f for f in files if f not in known]


def index_markdown(rows: list[dict], cfg: ProjectConfig, stamp: str) -> str:
    L = [f"# Master index: {cfg.project.name}", "", f"**Document {PREFIX}-DOC-00. Package revision {cfg.project.revision}. Generated {stamp}.**", "",
         "> PRELIMINARY EDUCATIONAL AND REFERENCE PACKAGE. NOT CONSTRUCTION-READY. NOT VERIFIED. No document below carries an approved issue.", "",
         "## Revision convention", "", "- **Revision** is the package (design basis) revision. It changes when the master configuration changes.", "- **Issue** (P1, P2, ...) is the document's own preliminary issue. It changes when the document is reissued. Neither is an approval.",
         "- **Related** lists the documents that must be read with this one (the workbook for a specification, the methodology for a workbook, and so on).", "- The machine-readable register is `MASTER_INDEX.csv`; the package manifest (`MANIFEST.json`) carries the same ids, revisions and a SHA-256 hash per file.", ""]
    ids = {}
    for r in rows:
        ids.setdefault(r["id"], r)
    for typ in ("Document", "Workbook", "Report", "Drawing", "Specification template", "Methodology", "User guide", "Design basis", "Engineering review note", "Training", "Register", "Log"):
        sel = [r for r in ids.values() if r["type"] == typ]
        if not sel:
            continue
        L += [f"## {typ}s" if not typ.endswith("s") else f"## {typ}", "", "| Id | Title | Rev | Issue | Status | File | Related |", "|---|---|---|---|---|---|---|"]
        for r in sorted(sel, key=lambda x: x["id"]):
            files = [x["path"] for x in rows if x["id"] == r["id"]]
            L.append(f"| {r['id'].replace(PREFIX + '-', '')} | {r['title']} | {r['revision']} | {r['issue']} | {r['status']} | {'<br>'.join(files)} | {', '.join(x.replace(PREFIX + '-', '') for x in r['related'])} |")
        L.append("")
    return "\n".join(L)


def index_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "type", "revision", "issue", "status", "path", "related"])
    for r in rows:
        w.writerow([r["id"], r["title"], r["type"], r["revision"], r["issue"], r["status"], r["path"], ";".join(r["related"])])
    return buf.getvalue()
