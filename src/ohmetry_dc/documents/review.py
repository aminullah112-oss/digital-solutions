"""Everything for the independent engineering review: the consolidated outstanding items, the reviewer checklist and guide, the findings log and the review package."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from ohmetry_dc import __version__
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models.attestation import is_complete
from ohmetry_dc.reporting.manufacturer_register import build_rows, load_register_meta
from ohmetry_dc.validation import run_all_checks

from . import docx_tools as dx

REVIEW_BANNER = "FOR INDEPENDENT ENGINEERING REVIEW. THE PACKAGE IS PRELIMINARY. IT IS NOT CONSTRUCTION-READY AND NOT VERIFIED. NOTHING IN IT HAS BEEN APPROVED."


# ------------------------------------------------------------------ outstanding items
def outstanding_items(root: Path, cfg: ProjectConfig) -> list[dict]:
    items: list[dict] = []

    def add(source, cat, item, action, status="OPEN", prio="Medium"):
        items.append({"id": f"OV-{len(items) + 1:03d}", "source": source, "category": cat, "item": item, "action_or_evidence": action, "status": status, "priority": prio})

    # 1. review log
    log = (root / "ENGINEERING_REVIEW_LOG.md").read_text(encoding="utf-8").splitlines()
    for line in log:
        if line.startswith("| ER-"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 8 and not cells[7].upper().startswith("CLOSED"):
                add(f"Review log {cells[0]}", cells[1], cells[2][:300], cells[5][:300], cells[7], cells[3])
    # 2. checks that are not a clean pass
    for c in run_all_checks(cfg):
        if c.verification_status == "N/A" and c.status.value == "PASS":
            continue
        if c.status.value != "PASS":
            add(f"Check {c.id}", "Engineering check", f"{c.title}: overall {c.status.value} (calculation {c.calculation_status}, result {c.calculation_result}, inputs {c.input_status})", c.next_action or "Supply the missing or unverified inputs", c.status.value, "High" if c.status.value in ("FAIL", "WARNING") else "Medium")
    # 3. manufacturer / site data
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    for r in build_rows(cfg, meta):
        if r.data_state != "VERIFIED":
            add(f"Register {r.parameter}", f"{r.category} data", f"{r.name}: {r.data_class}", f"{r.required_datasheet.split(':')[0]}. {r.verification_action}", r.data_state, "High" if r.data_state == "PENDING" else "Medium")
    # 4. standards
    reg = yaml.safe_load((root / "config" / "standards_register.yaml").read_text())
    for s in reg["standards"]:
        if s["applicability_status"] != "VERIFIED":
            add(f"Standards register {s['id']}", "Standard", f"{s['reference']}: edition and applicability not verified", "Verify the current edition, amendments, scope and applicability for the project", "NOT_VERIFIED", "Medium")
    add("Standards register", "Standard", "Local codes, utility and authority requirements are not stated", "Project team to add them", "OPEN", "High")
    # 5. exceptions
    for ex in cfg.exceptions:
        if not is_complete(ex.model_dump()):
            add(f"Exception {ex.id}", "Design-target exception", f"{ex.check_id}: {ex.status} up to {ex.accepted_ceiling_pct:g} %. Verification: {ex.verification_action}", ex.verification_action, "PENDING INDEPENDENT VERIFICATION", "High")
    # 6. assumptions
    for pid, p in cfg.parameters.items():
        if p.status.value == "ASSUMPTION":
            add(f"Assumption {pid}", "Assumption", f"{p.name} = {p.value} {p.unit}".strip(), "Confirm or replace with project data", "UNCONFIRMED", "Low" if not p.requires_manufacturer_verification else "Medium")
    # 7. fixed review items
    for cat, item, action, prio in [
        ("Independent review", "No calculation, workbook, drawing or document has been independently reviewed", "Complete this review and record findings in the findings log", "High"),
        ("Engine", "The Python engine and its tests have not been code-reviewed by anyone other than the author", "Review the engine against the methodology documents; rerun the test suite", "High"),
        ("Workbooks", "Workbook formulas have been tested against Python in LibreOffice only, not audited by a person", "Formula audit of every workbook; open in Microsoft Excel and confirm results", "High"),
        ("Methodology", "Standard-based methods (IEC 60909, IEEE 80, IEC 62305-2 area, adiabatic equation) are implemented from general knowledge, not checked against the current standards", "Check each equation, constant and its applicability against the current edition", "High"),
        ("Design basis", "400/230 V at 60 Hz is an owner decision, flagged as unusual, and not verified", "Confirm the voltage system with the utility and the project", "Medium"),
        ("Specifications", "The ten specification templates have not been reviewed for technical content", "Review requirements, standards lists, test lists and placeholders", "Medium"),
        ("Training", "The twelve training modules and the question bank have not been reviewed for technical accuracy", "Review explanations, formulas, worked examples and answers", "Medium"),
        ("Licence", "The commercial licence is a draft without legal review", "Legal professional to review and adapt before any sale (outside the engineering review)", "Medium"),
        ("Drawing", "The single-line diagram is a concept drawing generated from the configuration", "Review the architecture shown; decide path independence, transfer scheme and tag convention", "Medium"),
        ("Scope", "No cooling, fire protection, structural, lightning, IT distribution or controls design is included", "State the scope boundary in any project use", "Low")]:
        add("Package", cat, item, action, "OPEN", prio)
    return items


def outstanding_markdown(items: list[dict], cfg: ProjectConfig, stamp: str) -> str:
    L = [f"# Outstanding verification items", "", f"**Package revision {cfg.project.revision}. Generated {stamp}. {len(items)} items.**", "", f"> {REVIEW_BANNER}", "",
         "Consolidated from the engineering review log, the engineering checks, the manufacturer-data register, the standards register, the design-target exceptions, the assumptions register and the known review gaps. Regenerated by `generate-documents`.", ""]
    cats: dict[str, int] = {}
    for i in items:
        cats[i["source"].split(" ")[0]] = cats.get(i["source"].split(" ")[0], 0) + 1
    L += ["## Summary by source", ""] + [f"- {k}: {v}" for k, v in sorted(cats.items())] + [""]
    L += ["## Items", "", "| Id | Source | Category | Item | Action or evidence needed | Status | Priority |", "|---|---|---|---|---|---|---|"]
    for i in items:
        L.append("| " + " | ".join(str(i[k]).replace("|", "/").replace("\n", " ") for k in ("id", "source", "category", "item", "action_or_evidence", "status", "priority")) + " |")
    return "\n".join(L) + "\n"


def outstanding_csv(items: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "source", "category", "item", "action_or_evidence", "status", "priority"])
    w.writeheader()
    w.writerows(items)
    return buf.getvalue()


# ------------------------------------------------------------------ checklist
CHECKLIST: list[tuple[str, list[tuple[str, str]]]] = [
    ("A. Scope, independence and conduct of the review", [
        ("Confirm you are independent of the authors and have no stake in the package.", "Reviewer declaration"),
        ("Confirm the scope: educational and preliminary reference package, not a project design. Note anything claimed beyond that.", "CUSTOMER_README sections 1, 13 to 16"),
        ("Confirm nothing is labelled approved, verified or construction-ready.", "All documents; run the search listed in REVIEW_GUIDE"),
        ("Reproduce the package from the review package: install, run the test suite, regenerate the deliverables (REVIEW_GUIDE, REPRODUCE).", "REVIEW_GUIDE")]),
    ("B. Design basis", [
        ("Check each design-basis parameter, unit and source; confirm the data status is honest (preliminary vs placeholder vs reference).", "01_MASTER_DESIGN_BASIS.xlsx, config/project_config.yaml"),
        ("Check the voltage and frequency basis (400/230 V, 60 Hz is flagged as unusual); decide whether it is acceptable for the reference project.", "ER-001, lv_voltage_frequency check"),
        ("Check the redundancy concept (2N paths, 2N UPS, N+1 generators) is internally consistent and what 'credible contingency' means here.", "03_POWER_ARCHITECTURE, config redundancy section"),
        ("Check the loading policy (transformer 90/100 %, UPS 80/100 %, generator 80/100 %) is applied to the derated rating and no overload is used.", "docs/calculation_methodology/power_system_sizing.md"),
        ("Check the design-target exception EX-001 is recorded correctly and never converts a WARNING to PASS.", "config/design_exceptions.yaml, validation/exceptions.py")]),
    ("C. Load estimate and PUE", [
        ("Check P and Q are added separately and S = sqrt(P^2+Q^2); check the UPS loss formula and distribution loss treatment.", "docs/.../load_estimation.md, calculations/load.py, 02_LOAD_ESTIMATION"),
        ("Check the load schedule items, demand and power factors are reasonable for the reference project.", "config/load_schedule.yaml"),
        ("Confirm the PUE is a design-point power ratio and not described as annual anywhere.", "02, 18, training module 02"),
        ("Check the A/B allocation and the path-out scenarios.", "AB_ALLOCATION sheet, calculations/load.py")]),
    ("D. Equipment sizing", [
        ("Transformer: loading against the derated rating, contingency case, required rating for the target; confirm 3,150 kVA result.", "04_TRANSFORMER_SIZING, calculations/sizing.py"),
        ("Generators: PRP basis stated as assumed; kW and kVA both checked; N+1 and the double-contingency treatment; step loads reported NOT VERIFIED.", "05_GENERATOR_SIZING, ER-010, ER-012"),
        ("UPS: kW and kVA both checked; 2N logic; kVA governs at 0.95 power factor.", "06_UPS_SIZING, ER-009"),
        ("Battery: energy only; confirm no battery selection is implied.", "07_BATTERY_SIZING"),
        ("Derating: 1.00 placeholders are shown as placeholders everywhere and their effect is stated.", "ER-011, derating_factors check"),
        ("Check the size lists and suggested sizes are labelled illustrative.", "config size lists")]),
    ("E. Distribution", [
        ("Design current bases for each feeder; busbar and busduct required current (about 4,136 A on path-out).", "08, 11, 12, 13; calculations/distribution.py"),
        ("Conductor resistance constants and the three-phase voltage drop formula; reactance placeholders and their effect.", "docs/.../distribution.md, 09_VOLTAGE_DROP"),
        ("Confirm tabulated ratings, busduct and switchgear ratings are never assumed and read NOT VERIFIED.", "08, 11, 12, 13"),
        ("Check the cable selections are labelled illustrative and path B is assumed identical.", "config/distribution.yaml")]),
    ("F. Short-circuit, protection and earthing", [
        ("Check the IEC 60909 equations (utility, K_T, K_G, peak factor, thermal factor) against the standard; check the transformer-limited bound.", "calculations/short_circuit.py, docs/.../short_circuit_and_earthing.md"),
        ("Confirm no utility, generator or site value is invented; cases that lack data read NOT CALCULATED.", "10_SHORT_CIRCUIT, ER-019, ER-024"),
        ("Check the adiabatic cable withstand constant and its flagged status.", "08_CABLE_SIZING"),
        ("Check the IEEE 80 grid resistance and tolerable voltage equations against the standard; confirm the screening wording.", "calculations/earthing.py, 15_EARTHING_BONDING"),
        ("Confirm protection coordination, arc-flash and lightning compliance are never claimed.", "14, 16 workbooks")]),
    ("G. Status model and data override", [
        ("Confirm a calculation on unverified inputs can never reach overall PASS; confirm a preliminary WARNING or FAIL is kept.", "validation/verification.py, docs/.../status_model.md"),
        ("Confirm every engineering check depends on the right inputs (the CHECK_INPUTS map).", "validation/verification.py"),
        ("Import: confirm missing source, missing datasheet revision, unknown parameter, unsupported unit and implausible value reject the whole file; confirm unit conversion.", "reporting/data_import.py"),
        ("Confirm the master design basis is never edited by an import and the history is append-only.", "config/loader.py, manufacturer_data_overrides.yaml"),
        ("Confirm MANUFACTURER_VERIFIED is reachable only through an import plus a recorded reviewer.", "models/data_status.py, cli record-verification")]),
    ("H. Workbooks", [
        ("Audit formulas in each workbook: no hard-coded critical values, correct references, correct units.", "workbooks/ (all 20)"),
        ("Enter a datasheet value without a source: confirm it is rejected. Enter with a source: confirm the calculation updates and the status becomes SUPPLIED. Add a reviewer: confirm VERIFIED.", "INPUTS sheets"),
        ("Confirm the overall status can only be PASS when the calculation passes and all inputs are verified (try it).", "RESULTS sheets"),
        ("Open in Microsoft Excel (the tests recalculated with LibreOffice only) and confirm results agree.", "All workbooks"),
        ("Check the five input-register workbooks (14, 16, 17, 18, 19) do not produce a result without data and do not claim compliance.", "14, 16, 17, 18, 19")]),
    ("I. Python engine", [
        ("Review the code against the methodology documents; check units, boundary conditions and error handling.", "engine/src/ohmetry_dc"),
        ("Run the full test suite and confirm all tests pass; read the tests for the engineering-critical formulas (hand calculations).", "engine/tests, QA_RESULTS.md"),
        ("Check for hidden defaults: where an input is missing the engine must report it, not substitute a value.", "calculations/*.py"),
        ("Check configuration validation: required inputs, stage gating, value_ref resolution.", "config/loader.py, models/")]),
    ("J. Reports, drawings and registers", [
        ("Read the load estimation report; confirm statements, limitations and the agreement with the workbook.", "reports/"),
        ("Review the single-line diagram: architecture, tags, no unverified value shown as fact; decide path independence and transfer scheme.", "drawings/"),
        ("Check the assumptions register, standards register (all NOT_VERIFIED) and manufacturer-data register for completeness.", "07_registers"),
        ("Verify the outstanding items list is complete; add anything missing.", "OUTSTANDING_VERIFICATION_ITEMS")]),
    ("K. Specifications and training", [
        ("Review each specification template: standards named correctly, requirements sound, test lists complete, placeholders clear, no invented numbers.", "08_specifications"),
        ("Review the training modules, worked examples, exercise answers and question bank for technical accuracy and fair wording.", "09_training"),
        ("Confirm the certificate states it is not accredited.", "Completion_Certificate_Template")]),
    ("L. Documentation and commercial", [
        ("Check the customer README is accurate against the package and states limitations honestly.", "CUSTOMER_README"),
        ("Note that the licence draft is outside this review: it needs a legal professional.", "LICENCE_COMMERCIAL"),
        ("Check the master index and manifest: every file has an id, revision and hash; cross-references are right.", "MASTER_INDEX, MANIFEST.json")]),
]

SIGNOFF = [("Reviewer name and organisation", ""), ("Qualification and registration (if any)", ""), ("Independence declaration", "I have no interest in the package or its sale and was not involved in producing it. [ ] Confirmed"), ("Scope reviewed", ""),
           ("Date of review", ""), ("Overall conclusion (reviewer's own words)", ""), ("Signature", "")]


def checklist_markdown(cfg: ProjectConfig, stamp: str) -> str:
    L = [f"# Independent reviewer checklist: {cfg.project.name}", "", f"**Document {cfg.project.code}-DOC-03  Issue P1. Package revision {cfg.project.revision}. Generated {stamp}.**", "", f"> {REVIEW_BANNER}", "",
         "Mark each item PASS, FAIL, N/A or QUERY and record findings in REVIEW_FINDINGS_LOG.xlsx with the item reference. The checklist does not limit the review.", ""]
    n = 0
    for sec, items in CHECKLIST:
        L += [f"## {sec}", "", "| Ref | Check | Where | Result | Notes |", "|---|---|---|---|---|"]
        for text, where in items:
            n += 1
            L.append(f"| R{n:02d} | {text} | {where} |  |  |")
        L.append("")
    L += ["## Sign-off", "", "| Field | Entry |", "|---|---|"] + [f"| {a} | {b} |" for a, b in SIGNOFF] + [""]
    return "\n".join(L)


def checklist_docx(cfg: ProjectConfig, path: Path, stamp: str) -> Path:
    d = dx.new_document("Independent reviewer checklist", f"{cfg.project.code}-DOC-03", "P1", "For review", f"OHMETRY {cfg.project.code}: independent reviewer checklist")
    dx.title(d, "Independent reviewer checklist", f"{cfg.project.name}. Package revision {cfg.project.revision}. Generated {stamp}.")
    dx.banner(d, REVIEW_BANNER)
    d.add_paragraph("Mark each item PASS, FAIL, N/A or QUERY and record findings in REVIEW_FINDINGS_LOG.xlsx with the item reference. The checklist does not limit the review.")
    n = 0
    for sec, items in CHECKLIST:
        d.add_heading(sec, 2)
        rows = []
        for text, where in items:
            n += 1
            rows.append([f"R{n:02d}", text, where, "", ""])
        dx.table(d, ["Ref", "Check", "Where", "Result", "Notes"], rows)
    d.add_heading("Sign-off", 2)
    dx.table(d, ["Field", "Entry"], [[a, b] for a, b in SIGNOFF])
    d.save(path)
    return path


def guide_markdown(cfg: ProjectConfig, stamp: str, n_files: int) -> str:
    c = cfg.project
    return f"""# Independent review guide: {c.name}

**Document {c.code}-DOC-04  Issue P1. Package revision {c.revision}. Generated {stamp}.**

> {REVIEW_BANNER}

## 1. What you are reviewing
The Ohmetry {c.name} ({c.code}): a preliminary educational and reference package for a 2 MW data centre electrical design. It contains a design basis, a Python calculation engine, twenty Excel workbooks, a report, a single-line diagram, ten specification templates, a twelve-module training suite, registers and documents. It is not a project design and makes no claim to be construction-ready or verified.

## 2. What the package claims, and what it does not
- It claims: transparent calculations; every input labelled with its data status; no calculation on unverified inputs reaches an overall PASS; missing data is reported, not substituted.
- It does not claim: that any rating is manufacturer-confirmed, that any result is verified, compliance with any standard or code, readiness for construction, or any approval by a regulator, utility, client or professional engineer.

## 3. What is in this review package
`00_START_HERE` (this guide, the checklist, the findings log, the outstanding items, the master index), `01_design_basis`, `02_calculation_methodology`, `03_workbooks`, `04_engine` (a complete runnable replica of the repository: source, tests, configuration and every generated deliverable; the other numbered folders are reading copies of parts of it), `05_reports`, `06_drawings`, `07_registers`, `08_specifications`, `09_training`, `10_customer_documents`, `11_qa`. A SHA-256 manifest (MANIFEST.json) covers every file.

## 4. Reproducing the package
1. Unzip the review package. Python 3.11 or later and LibreOffice are needed (LibreOffice is used by the workbook tests).
2. In `04_engine` (the repository root): install the dependencies in `requirements.txt` (pydantic, PyYAML, openpyxl, reportlab, python-docx, pytest).
3. Run `PYTHONPATH=src python -m pytest -q`. All tests should pass. Note any that do not.
4. Run `PYTHONPATH=src python -m ohmetry_dc validate-config` and compare with `11_qa/QA_RESULTS.md` and the CHECK_STATUS sheet of workbook 01.
5. Run `generate-workbooks`, `generate-reports`, `generate-drawings`, `generate-training`, `generate-documents` and compare the outputs with the supplied files (timestamps will differ).

## 5. Suggested order of review
Design basis, then the methodology documents, then the engine code for each calculation, then the workbooks against the engine, then registers, drawing, specifications, training and customer documents. Use the checklist; it does not limit your review.

## 6. Quick checks
- Search all documents for the words approved, verified, compliant and construction: every use should be a negation or a status label.
- In any workbook, enter a value in the blue datasheet column without a source: it must be rejected.
- Change `equipment.transformer_rating` in `config/project_config.yaml`, rerun, and confirm the workbook, report, drawing and training examples follow.

## 7. Recording findings
Use REVIEW_FINDINGS_LOG.xlsx (the columns match the engineering review log). Give each finding a severity (Critical, High, Medium, Low, Observation), the evidence (file, sheet, cell or line) and the corrective action you expect. Do not edit the package files; send findings back so changes are made and re-tested by the author.

## 8. Out of scope
Legal review of the licence, commercial terms, and the website. Those need a different professional.

## 9. Known gaps you should expect
See OUTSTANDING_VERIFICATION_ITEMS.md. The biggest: no independent review has happened yet; manufacturer, utility and site data are not supplied; the standards editions are NOT_VERIFIED; the workbooks were tested only in LibreOffice.
"""


def findings_workbook(path: Path, stamp: str) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "FINDINGS"
    ws["A1"].value, ws["A1"].font = "Independent review: findings log", Font(name="Arial", size=14, bold=True)
    ws["A2"].value = f"Generated {stamp}. {REVIEW_BANNER}"
    heads = ["Finding id", "Checklist ref", "Module / file", "Finding", "Severity", "Evidence (file, sheet, cell, line)", "Corrective action expected", "Reviewer", "Date", "Author response", "Status", "Closure evidence"]
    widths = [10, 10, 28, 60, 12, 40, 44, 16, 12, 44, 14, 36]
    for i, (h, w) in enumerate(zip(heads, widths), 1):
        c = ws.cell(4, i, h)
        c.font, c.fill = Font(name="Arial", bold=True, color="FFFFFF"), PatternFill("solid", fgColor="0E171E")
        ws.column_dimensions[chr(64 + i)].width = w
    sev = DataValidation(type="list", formula1='"Critical,High,Medium,Low,Observation"', allow_blank=True)
    stat = DataValidation(type="list", formula1='"OPEN,ACCEPTED,FIXED,REJECTED,CLOSED"', allow_blank=True)
    ws.add_data_validation(sev)
    ws.add_data_validation(stat)
    sev.add("E5:E200")
    stat.add("K5:K200")
    for r in range(5, 201):
        ws[f"A{r}"].value = f"RF-{r - 4:03d}"
        for col in "BCDEFGHIJKL":
            ws[f"{col}{r}"].fill = PatternFill("solid", fgColor="DCEBFF")
    ws.freeze_panes = "A5"
    wb.save(path)
    return path


# ------------------------------------------------------------------ the review package
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_review_package(root: Path, out_dir: Path, cfg: ProjectConfig, stamp: str) -> tuple[Path, dict]:
    code, rev = cfg.project.code, cfg.project.revision
    files: list[tuple[Path, str]] = []

    def add(p: Path, dest: str):
        if p.is_file() and p.name != ".gitkeep" and "__pycache__" not in p.parts and p.suffix != ".pyc":
            files.append((p, dest))

    rel = root / "docs" / "release"
    for n in ("REVIEW_GUIDE.md", "REVIEWER_CHECKLIST.md", "REVIEWER_CHECKLIST.docx", "REVIEWER_CHECKLIST.pdf", "REVIEW_FINDINGS_LOG.xlsx", "MASTER_INDEX.md", "MASTER_INDEX.csv"):
        add(rel / n, f"00_START_HERE/{n}")
    for n in ("OUTSTANDING_VERIFICATION_ITEMS.md", "OUTSTANDING_VERIFICATION_ITEMS.csv"):
        add(root / "output" / n, f"00_START_HERE/{n}")
    for n in ("project_config.yaml", "load_schedule.yaml", "distribution.yaml", "design_exceptions.yaml", "design_basis_revisions.yaml"):
        add(root / "config" / n, f"01_design_basis/{n}")
    for p in sorted((root / "docs" / "design_basis").glob("*.md")):
        add(p, f"01_design_basis/{p.name}")
    for sub in ("calculation_methodology", "user_guide", "engineering_review"):
        for p in sorted((root / "docs" / sub).glob("*.md")):
            add(p, f"02_calculation_methodology/{sub}/{p.name}")
    for p in sorted((root / "workbooks" / "generated").glob("*.xlsx")):
        add(p, f"03_workbooks/{p.name}")
    skip_dirs = {".git", "dist", "__pycache__", ".pytest_cache", ".venv"}
    for p in sorted(root.rglob("*")):                       # 04_engine is a complete, runnable replica of the repository, so the tests can be rerun as they are
        rel_parts = p.relative_to(root).parts
        if p.is_file() and not (set(rel_parts) & skip_dirs) and not any(x.endswith(".egg-info") for x in rel_parts):
            add(p, f"04_engine/{p.relative_to(root)}")
    for p in sorted((root / "reports" / "generated").glob("*.pdf")):
        add(p, f"05_reports/{p.name}")
    for p in sorted((root / "drawings").rglob("*")):
        if p.is_file() and p.parent.name in ("svg", "pdf"):
            add(p, f"06_drawings/{p.name}")
    for n in ("assumptions_register.yaml", "standards_register.yaml", "manufacturer_data_register.yaml", "manufacturer_data_overrides.yaml", "document_revisions.yaml"):
        add(root / "config" / n, f"07_registers/{n}")
    for n in ("manufacturer_data_register.md", "manufacturer_data_register.csv", "manufacturer_data_import_template.csv"):
        add(root / "output" / n, f"07_registers/{n}")
    add(root / "ENGINEERING_REVIEW_LOG.md", "07_registers/ENGINEERING_REVIEW_LOG.md")
    add(root / "DEVELOPMENT_STATUS.md", "07_registers/DEVELOPMENT_STATUS.md")
    add(root / "RELEASE_CHECKLIST.md", "07_registers/RELEASE_CHECKLIST.md")
    for p in sorted((root / "specifications").rglob("*")):
        add(p, f"08_specifications/{p.relative_to(root / 'specifications')}")
    for p in sorted((root / "training").rglob("*")):
        add(p, f"09_training/{p.relative_to(root / 'training')}")
    for n in ("CUSTOMER_README.md", "CUSTOMER_README.docx", "CUSTOMER_README.pdf", "LICENCE_COMMERCIAL.md", "LICENCE_COMMERCIAL.docx", "LICENCE_COMMERCIAL.pdf"):
        add(rel / n, f"10_customer_documents/{n}")
    add(root / "output" / "QA_RESULTS.md", "11_qa/QA_RESULTS.md")

    manifest = {"package": f"{code} independent review package", "revision": rev, "package_version": __version__, "generated": stamp, "state": REVIEW_BANNER,
                "files": [{"path": z, "sha256": _sha(p), "bytes": p.stat().st_size} for p, z in files]}
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"{code}_{rev}_REVIEW_PACKAGE.zip"
    top = f"{code}-REVIEW"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p, dest in files:
            z.write(p, f"{top}/{dest}")
        z.writestr(f"{top}/00_START_HERE/MANIFEST.json", json.dumps(manifest, indent=2))
    return zpath, manifest
