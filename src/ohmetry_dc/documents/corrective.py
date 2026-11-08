"""Corrective action report for revision A6 (the response to items 5 to 12 of the A5 independent review), as Markdown, DOCX and PDF.

The numbers in it are computed from the engine at generation time and compared with the values reviewed at A5. Implemented is not verified: every item here is
NOT REVIEWED until an independent reviewer says otherwise.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from ohmetry_dc import __version__
from ohmetry_dc.documents import ISSUE
from ohmetry_dc.models import ProjectConfig

from . import docx_tools as dx

BANNER = "FOR INDEPENDENT ENGINEERING REVIEW. THE PACKAGE IS PRELIMINARY. IT IS NOT CONSTRUCTION-READY AND NOT VERIFIED. NOTHING IN IT HAS BEEN APPROVED."

# The values reviewed at revision A5 (the fidelity gate). (label, reviewed value as text, tolerance for the comparison)
REVIEWED_A5 = [
    ("IT load (kW)", 2000.0, 0.05), ("Facility total (kW)", 2697.3, 0.05), ("Facility total (kVA)", 2865.6, 0.05), ("PUE (design point)", 1.349, 0.0005),
    ("Transformer 3,150 kVA, path out (% of derated kVA)", 90.97, 0.005), ("Transformer 4,000 kVA, same load (% kVA, arithmetic only)", 71.64, 0.005),
    ("UPS, path out (% kW)", 80.0, 0.05), ("UPS, path out (% kVA)", 84.2, 0.05),
    ("Generators, path out and one unit out (% of 4,000 kVA)", 71.36, 0.005), ("Generators, path out and one unit out (% of 3,200 kW)", 83.98, 0.005),
    ("Transformer-limited LV figure (kA; utility contribution through one transformer only)", 82.64, 0.005), ("Transformer full-load LV current (A)", 4547.0, 0.5), ("LV busduct required current (A)", 4136.0, 0.5),
]
DECIMALS = {'IT load (kW)': 0, 'Facility total (kW)': 1, 'Facility total (kVA)': 1, 'PUE (design point)': 3, 'Transformer 3,150': 2, 'Transformer 4,000': 2, 'UPS, path out (% kW)': 1, 'UPS, path out (% kVA)': 1, 'Generators, path out and one unit out (% of 4,000': 2, 'Generators, path out and one unit out (% of 3,200': 2, 'Transformer-limited': 2, 'Transformer full-load': 0, 'LV busduct': 0}
A5_SUMMARY = {"PASS": 9, "WARNING": 2, "FAIL": 0, "NOT VERIFIED": 25, "NOT APPLICABLE": 0}


def live_values(cfg: ProjectConfig) -> list[float]:
    from ohmetry_dc.calculations import assess_distribution, estimate_loads, size_power_system
    from ohmetry_dc.calculations.short_circuit import assess_short_circuit

    est = estimate_loads(cfg)
    sz = size_power_system(cfg, est)
    sc = assess_short_circuit(cfg)
    bound = next(c for c in sc.lv_cases if c.name.startswith("Transformer-limited"))
    sc_by = lambda blk, i: next(s for s in blk.scenarios if s.id == i)
    tx = sc_by(sz.transformer, "TX-PATH-OUT")
    dist = assess_distribution(cfg, est, sz)
    i_full = cfg.value("equipment.transformer_rating") * 1000 / (math.sqrt(3) * cfg.value("electrical_system.lv_line_voltage"))
    return [est.it_demand_kw, est.facility_kw, est.facility_kva, est.pue, tx.loading * 100, tx.load / 4000 * 100, sc_by(sz.ups_kw, "UPS-PATH-OUT").loading * 100, sc_by(sz.ups_kva, "UPS-PATH-OUT").loading * 100,
            sc_by(sz.generator, "GEN-PATH-OUT-UNIT-OUT").loading * 100, sc_by(sz.generator_kw, "GEN-PATH-OUT-UNIT-OUT").loading * 100, bound.ik_ka, i_full, dist.busducts[0].required_rating_a]


def key_number_rows(cfg: ProjectConfig) -> list[list[str]]:
    rows = []
    for (label, reviewed, tol), got in zip(REVIEWED_A5, live_values(cfg)):
        nd = next(v for k, v in DECIMALS.items() if label.startswith(k))
        rows.append([label, f"{reviewed:,.{nd}f}", f"{got:,.{nd}f}", "MATCH" if abs(got - reviewed) <= tol else "DIFFERENT"])
    return rows


def key_numbers_match(cfg: ProjectConfig) -> bool:
    return all(r[3] == "MATCH" for r in key_number_rows(cfg))


def _qa_line(root: Path) -> str:
    p = root / "output" / "QA_RESULTS.md"
    if p.exists():
        m = re.search(r"\*\*(\d+) passed, (\d+) failed, (\d+) skipped\.\*\*", p.read_text(encoding="utf-8"))
        run = re.search(r"Run (.+?)\. Package", p.read_text(encoding="utf-8"))
        if m:
            return f"{m.group(1)} passed, {m.group(2)} failed, {m.group(3)} skipped ({run.group(1) if run else 'time not recorded'}; output/QA_RESULTS.md)"
    return "not recorded: run qa-report"


def summary_now(cfg: ProjectConfig) -> dict[str, int]:
    from ohmetry_dc.validation import run_all_checks

    out = {k: 0 for k in A5_SUMMARY}
    for r in run_all_checks(cfg):
        out[r.status.value] += 1
    return out


ITEMS = [
    dict(no=5, title="Single-line diagram and architecture",
         asked="Utility A/B independence not claimed; generator transfer and interlocking; paralleling and synchronising; PMS and load sharing; load shedding; UPS static and maintenance bypass; battery isolation and protection; protection and measurement boundaries.",
         done=["SLD-001 redrawn at A6: a breaker per generator (GCB) onto a generator bus; a dashed interlock between ACB-TX and ACB-GEN; a PMS box (synchronising, load sharing, load shedding); UPS static bypass (STS) and maintenance bypass (MBB); a battery isolator (BAT-ISO); the utility point-of-connection boundary and the UPS vendor-scope boundary. Every one is labelled concept or not designed.",
               "The IT load is one dual-corded load fed from both IT distribution boards, replacing two boxes each labelled 2,000 kW (which could be read as 4 MW).",
               "Independence of utility A and B is stated as NOT claimed on the drawing, in the workbook and in the register.",
               "`models/architecture.py` lists twelve functions with status and what is needed; workbook 03 has a FUNCTIONS sheet; the sizing methodology document has a section on them."],
         evidence=["tests/drawing/test_single_line.py (5 new tests)", "tests/workbook/test_calc_workbooks.py (FUNCTIONS sheet)", "drawings/svg/OHM-DC-2000-SLD-001.svg", "ER-028"],
         still=["None of the twelve functions is designed. No transfer scheme, synchronising method, PMS, bypass arrangement or battery protection exists.", "Protection and measurement are not drawn at all (no relays, CTs, VTs or metering).", "Utility independence needs the utility's written confirmation."]),
    dict(no=6, title="Distribution and cables",
         asked="Parallel arrangement; grouping factors (never 1.00 as verified); installation method; ambient derating; conductor temperature; current sharing; busduct rating; voltage drop.",
         done=["A derating factor counts as verified only when the entry names its source (`derating_evidence`). A 1.00 is a placeholder. Required ratings for every cable, busduct and switchgear item are labelled MINIMUMS while any factor is a placeholder.",
               "A grouping factor of 1.00 with parallel runs is called out (CAB-GEN-A: 6 runs).", "Installation method, parallel arrangement and current-sharing allowance are recorded; unsupplied ones are listed as missing data and no allowance is invented.",
               "New check `cable_derating_basis`; workbook 08 splits the derating into grouping, ambient and installation placeholders and takes a sharing allowance; busduct and switchgear workbooks label their factor a placeholder.",
               "Voltage drop is stated as per segment, operating current only, not cumulative, excluding starting. Conductor temperature is stated as used for resistance only."],
         evidence=["tests/unit/test_checks.py (7 new tests)", "check cable_derating_basis", "docs/calculation_methodology/distribution.md", "ER-029"],
         still=["No cable table, grouping, ambient or installation factor, parallel layout or sharing allowance is supplied, so every required rating is a minimum.", "Busduct and switchgear ratings and impedances are manufacturer data and absent."]),
    dict(no=7, title="Short-circuit and protection",
         asked="Keep NOT CALCULATED where data is absent; never select ratings from an invented fault level; keep arc-flash out of scope.",
         done=["The 82.6 kA figure is reworded everywhere: it limits only the utility contribution through one transformer. It excludes generators and motors, so it is not the bus fault level and not a design value. (The earlier wording called it an upper bound valid for any utility fault level and the check said 'LV bus calculated': both overstated it.)",
               "Tests show no required rating, withstand, cable section or breaking capacity is derived from it.", "Check `arc_flash_scope` records arc-flash as OUT OF SCOPE (IEEE 1584 named, not applied)."],
         evidence=["tests/unit/test_stage5.py (4 new tests)", "docs/calculation_methodology/short_circuit_and_earthing.md", "ER-024 (corrected), ER-030"],
         still=["The design fault level is NOT CALCULATED: utility fault level and X/R, transformer X/R and generator reactance and X/R are not supplied.", "No protection coordination, minimum fault current, device settings or arc-flash study."]),
    dict(no=8, title="Earthing and lightning",
         asked="Preliminary screening only; distinguish GPR screening from a full mesh and step study; no IEC 62305 compliance claim.",
         done=["The earthing check states, in every state, that it is PRELIMINARY SCREENING ONLY and not a mesh and step voltage study or an earthing design; the NOT CALCULATED message says so too.", "Check `lightning_scope` records lightning as OUT OF SCOPE with compliance NOT claimed."],
         evidence=["tests/unit/test_stage5.py (2 new tests)", "ER-031"],
         still=["Soil survey, grid design, earth-fault current and clearing time are not supplied, so grid resistance and GPR are NOT CALCULATED for the project.", "No lightning risk assessment."]),
    dict(no=9, title="Data verification",
         asked="The reviewer name is an attestation, not authenticated; record name, organisation, date, evidence reference and scope.",
         done=["`models/attestation.py`: a value reads verified only when all five fields are present, the date is ISO and not in the future. A bare name is reported as an incomplete record and is not treated as verified.", "`record-verification` requires all five, rejects incomplete or invalid records and placeholders, and appends every record to `config/verification_log.yaml`.",
               "Design exceptions use the same rule. Workbook reviewer cells need `name; organisation; date; evidence; scope` or read REJECTED: ATTESTATION INCOMPLETE.", "The register, CLI output and documents say the name is a self-declared attestation and not authenticated."],
         evidence=["tests/integration/test_cli.py (3 new tests)", "tests/unit/test_stage4.py (3 new tests)", "tests/workbook/test_calc_workbooks.py (1 new test)", "docs/calculation_methodology/status_model.md", "ER-032"],
         still=["Identity, credentials and independence are still not checked by anything. A workbook cell is a text pattern, not a signature."]),
    dict(no=10, title="Standards and specifications",
         asked="Review the standards register (no invented clause numbers); expand the specifications with vendor data schedules, compliance schedules, FAT, SAT and commissioning.",
         done=["Register reconciled: 33 entries (was 18). Every standard named in a specification is now in it (tested). Each entry has `relevant_modules` and `package_use`, including where a standard is named only to say compliance is not claimed or the topic is out of scope. No edition or clause is given.",
               "Specifications now carry a vendor data schedule, a compliance schedule (per standard and per requirement), FAT, SAT, commissioning with integrated systems testing, and a submittals table. Acceptance criteria are left to the project."],
         evidence=["tests/documents/test_documents.py (6 new tests)", "config/standards_register.yaml", "specifications/", "ER-033"],
         still=["Titles and relevance of the 33 standards are from the authors' general knowledge and have not been checked against the standards; editions and applicability are all NOT_VERIFIED.", "Local codes, utility and authority requirements are not stated."]),
    dict(no=11, title="Document control and QA",
         asked="Revision A6; remove or regenerate the stale Stage 3 sizing summary; reconcile the ER log; note that Excel was unavailable (LibreOffice only plus static lint).",
         done=["Revision A6 in the configuration, the revision log (no load, demand or sizing change) and every generated document at issue P2.", "The Stage 3 sizing summary (A2) and results.json (A1) are regenerated; a test fails if any generated file carries another revision.",
               "ER log reconciled: ER-016, ER-018, ER-024, ER-025, ER-027 amended; ER-028 to ER-034 added; a test checks the IDs, columns, references and closure evidence.", "Two defects found while reconciling and fixed: the register check reported 0 placeholders (the real split is 59 missing, 24 placeholders); distribution tags GEN-SWG-A, CRIT-DIST-A, MCC-A differed from the drawing (GENBUS-A, IT-DIST-A, MECH-A).",
               "Excel limitation stated in the customer README, review guide, checklist, outstanding items, QA results and ER-027. `lint-workbooks` statically checks all 20 workbooks for Excel limits (text literal length, post-2016 functions, external links, brackets, missing sheets) and lists typed-in constants for the formula audit."],
         evidence=["tests/package/test_repository_files.py (5 new tests)", "tests/workbook/test_workbook_lint.py (9 tests)", "output/WORKBOOK_LINT.md", "ER-034"],
         still=["The workbooks have never been opened in Microsoft Excel. The lint cannot show Excel and LibreOffice agree.", "The lint found no problem; that does not mean the formulas are right (R34 is still a person's job)."]),
    dict(no=12, title="Release gate",
         asked="Regenerate the full package, manifest, master index, outstanding items register, corrective-action report, revised reviewer checklist and review package.",
         done=["`regenerate-all` rebuilds everything in one deterministic sequence: assumptions and manufacturer registers, results, sizing summary, workbooks and lint, report, drawing, training, documents (index, outstanding items, checklist with new section M, guide, findings log), QA results, review package and customer package.", "This report, the revised checklist (section M, R-numbers continue from the A5 checklist so existing findings references still resolve) and the review package are part of that run."],
         evidence=["dist/OHM-DC-2000_A6_REVIEW_PACKAGE.zip (MANIFEST.json with hashes)", "docs/release/MASTER_INDEX.md", "output/OUTSTANDING_VERIFICATION_ITEMS.md"],
         still=["The release state stays DEVELOPMENT. Nothing is pushed or approved by this work."]),
]

ITEMS_1_TO_4 = ("Items 1 to 4 of the A5 review are NOT covered by this report. They were implemented in an earlier working session whose repository was lost before it was ever pushed, and their text was not in the handover. "
                "This package was rebuilt from the A5 review package, so it is the A5 state plus corrective actions 5 to 12. Until the text of items 1 to 4 is supplied and checked, do not assume they are present. "
                "Signals in the handover suggest the reviewed values included a judged path-out-plus-one-unit generator case and a third WARNING; the engine currently reports that case as informational and still shows 2 WARNINGs. This is an inference, not a fact.")


def _short(items):
    return "; ".join(items)


def markdown(cfg: ProjectConfig, root: Path, stamp: str) -> str:
    kn = key_number_rows(cfg)
    now = summary_now(cfg)
    L = [f"# Corrective action report: {cfg.project.name}", "", f"**Document {cfg.project.code}-DOC-07  Issue {ISSUE}. Package revision {cfg.project.revision}. Generated {stamp}. Package version {__version__}.**", "", f"> {BANNER}", "",
         "This report answers items 5 to 12 of the independent review of revision A5. **Implemented is not verified:** every change below is NOT REVIEWED until an independent engineer says otherwise.", "",
         "## 1. What changed and what did not", "", "Revision A6 changes how results are labelled, drawn and documented. **No load, demand, rating or sizing value changed**: the revision log records no equipment sizing change, and the table in section 3 shows the reviewed A5 values reproduce.", "",
         "## 2. Items 1 to 4", "", ITEMS_1_TO_4, "", "## 3. Key numbers: reviewed at A5, computed now", "", "| Item | Reviewed at A5 | Computed now | Agreement |", "|---|---|---|---|"] + [f"| {' | '.join(r)} |" for r in kn] + [
         "", f"Agreement: {'ALL MATCH' if all(r[3] == 'MATCH' for r in kn) else 'DIFFERENCE FOUND: investigate before release'}. The transformer-limited figure is the utility contribution through one transformer only; it is not the bus fault level.", "",
         "## 4. Check summary", "", "| Status | A5 | A6 |", "|---|---|---|"] + [f"| {k} | {A5_SUMMARY[k]} | {now[k]} |" for k in A5_SUMMARY] + [
         "", "The NOT VERIFIED count rose because new checks were added (`cable_derating_basis`; arc-flash and lightning scope are NOT APPLICABLE). No check changed status and nothing was upgraded.", "",
         f"Tests: {_qa_line(root)}.", ""]
    for it in ITEMS:
        L += [f"## Item {it['no']}. {it['title']}", "", f"**Asked:** {it['asked']}", "", "**Done:**", ""] + [f"- {d}" for d in it["done"]] + ["", f"**Evidence:** {_short(it['evidence'])}.", "", "**Still open:**", ""] + [f"- {s}" for s in it["still"]] + [""]
    L += ["## Limits of this report", "", "- Microsoft Excel was not available: the workbooks have never been opened in Excel.", "- The tests show the code does what it was written to do. They do not show the engineering is right.",
          "- Nothing here has been independently reviewed, approved, or checked against the standards named.", "", "## Sign-off", "", "| Field | Entry |", "|---|---|", "| Independent reviewer | not assigned |", "| Review date | not assigned |", "| Release state | DEVELOPMENT |", ""]
    return "\n".join(L)


def docx(cfg: ProjectConfig, root: Path, path: Path, stamp: str) -> Path:
    d = dx.new_document("Corrective action report", f"{cfg.project.code}-DOC-07", ISSUE, "For review", f"OHMETRY {cfg.project.code}: corrective action report")
    dx.title(d, "Corrective action report", f"{cfg.project.name}. Package revision {cfg.project.revision}. Generated {stamp}.")
    dx.banner(d, BANNER)
    d.add_paragraph("This report answers items 5 to 12 of the independent review of revision A5. Implemented is not verified: every change below is NOT REVIEWED until an independent engineer says otherwise.")
    d.add_heading("1. What changed and what did not", 2)
    d.add_paragraph("Revision A6 changes how results are labelled, drawn and documented. No load, demand, rating or sizing value changed.")
    d.add_heading("2. Items 1 to 4", 2)
    d.add_paragraph(ITEMS_1_TO_4)
    d.add_heading("3. Key numbers: reviewed at A5, computed now", 2)
    dx.table(d, ["Item", "Reviewed at A5", "Computed now", "Agreement"], key_number_rows(cfg))
    d.add_heading("4. Check summary", 2)
    now = summary_now(cfg)
    dx.table(d, ["Status", "A5", "A6"], [[k, str(A5_SUMMARY[k]), str(now[k])] for k in A5_SUMMARY])
    d.add_paragraph(f"Tests: {_qa_line(root)}.")
    for it in ITEMS:
        d.add_heading(f"Item {it['no']}. {it['title']}", 2)
        d.add_paragraph("Asked: " + it["asked"])
        d.add_paragraph("Done:")
        dx.bullets(d, [x.replace("`", "") for x in it["done"]])
        d.add_paragraph("Evidence: " + _short(it["evidence"]) + ".")
        d.add_paragraph("Still open:")
        dx.bullets(d, [x.replace("`", "") for x in it["still"]])
    d.add_heading("Limits of this report", 2)
    dx.bullets(d, ["Microsoft Excel was not available: the workbooks have never been opened in Excel.", "The tests show the code does what it was written to do. They do not show the engineering is right.", "Nothing here has been independently reviewed, approved, or checked against the standards named."])
    d.save(path)
    return path
