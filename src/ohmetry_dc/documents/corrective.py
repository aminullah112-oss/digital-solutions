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


def live_statuses(cfg: ProjectConfig) -> list[str]:
    """The loading status of each key number where it has one (calculation result against the target and limit; not an engineering verification)."""
    from ohmetry_dc.calculations import estimate_loads, size_power_system
    from ohmetry_dc.calculations.sizing import classify

    sz = size_power_system(cfg, estimate_loads(cfg))
    sc_by = lambda blk, i: next(s for s in blk.scenarios if s.id == i)
    tx = sc_by(sz.transformer, "TX-PATH-OUT")
    return ["-", "-", "-", "-", tx.status.value, classify(tx.load / 4000, sz.transformer.policy).value, sc_by(sz.ups_kw, "UPS-PATH-OUT").status.value, sc_by(sz.ups_kva, "UPS-PATH-OUT").status.value,
            sc_by(sz.generator, "GEN-PATH-OUT-UNIT-OUT").status.value, sc_by(sz.generator_kw, "GEN-PATH-OUT-UNIT-OUT").status.value, "-", "-", "-"]


def key_number_rows(cfg: ProjectConfig) -> list[list[str]]:
    rows = []
    for (label, reviewed, tol), got, st in zip(REVIEWED_A5, live_values(cfg), live_statuses(cfg)):
        nd = next(v for k, v in DECIMALS.items() if label.startswith(k))
        rows.append([label, f"{reviewed:,.{nd}f}", f"{got:,.{nd}f}", "MATCH" if abs(got - reviewed) <= tol else "DIFFERENT", st])
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
    dict(no=1, title="Generator N+1 (combined contingency)",
         asked="Judge one utility path out plus one generator out (about 71.4 % kVA and 84.0 % kW: WARNING against the 80 % kW target, under the 100 % hard limit); document the redundancy philosophy (N+1 engine-out basis); flag that the engineer must select and document the contingency basis; do not convert the WARNING to PASS.",
         done=["The combined case is judged (`redundancy.double_contingency_credible` is true, source: the A5 review). Generator kVA 71.36 % of 4,000 kVA (under the 80 % target); kW 83.98 % of 3,200 kW: WARNING, never converted to PASS. Loss of a path only gives 47.6 % kVA / 56.0 % kW.",
               "New check `generator_contingency_basis` (NOT VERIFIED): states the basis used, shows the loading under each candidate basis, and says in capitals that the engineer must select and document it. New parameter `redundancy.generator_contingency_basis` records the assumption. The methodology document and the sizing summary state the philosophy.",
               "Note on the reviewed table: it lists the 71.36 % kVA row as WARNING; against the 80 % kVA target it reads PASS, and the WARNING is on kW. The item text says the same (WARNING against the 80 % kW target)."],
         evidence=["tests/unit/test_options_sensitivity.py", "tests/unit/test_sizing.py", "check generator_contingency_basis", "ER-035"],
         still=["No engineer has selected or documented the contingency basis, the outage duration, fuel autonomy or load-shedding assumptions it implies.", "The PRP rating basis and 1,600 kW engine rating are still assumptions."]),
    dict(no=2, title="Transformer: EX-001 and the 3,150 / 4,000 kVA options",
         asked="Reconcile design exception EX-001 with the 91.0 % kVA loading on 3,150 kVA; keep the 90 % target / 100 % limit (WARNING); show 3,150 kVA and 4,000 kVA side by side so the engineer can select.",
         done=["The exact loading is 90.97 % (shown as 91.0 %). EX-001's ceiling is 91.0 %: the check now states the exact value, the 0.03 percentage point margin and that any small increase voids the exception (at +10 % IT the loading is 98 % and EX-001 does not cover it). Target 90 % and limit 100 % unchanged; the result stays WARNING.",
               "3,150 kVA (90.97 %, WARNING) and an illustrative 4,000 kVA (71.64 %, PASS) are shown side by side in the check `equipment_options`, workbook 04 sheet OPTIONS (live formulas, option rating editable) and the sizing summary. The 4,000 kVA option raises the transformer-limited figure to 104.9 kA at the same impedance, above the 100 kA practical limit, and the full-load LV current to 5,774 A: the table flags both. Nothing is selected."],
         evidence=["tests/unit/test_options_sensitivity.py (4 tests)", "tests/workbook/test_calc_workbooks.py (OPTIONS sheets)", "ER-008, ER-036"],
         still=["The 4,000 kVA option assumes the same impedance percentage and derating, which a real unit would not have to share.", "Transformer selection, impedance and the fault-level consequence are for the engineer, from manufacturer data."]),
    dict(no=3, title="UPS: separate kW and kVA, 3,000 kVA option",
         asked="Separate kW and kVA checks; kVA 84.2 % at 2,500 kVA is a WARNING; keep kW at 80.0 % (PASS); include an illustrative 3,000 kVA option in the sizing table.",
         done=["kW (80.0 %, PASS) and kVA (84.2 %, WARNING) remain separate checks (`ups_loading_kw`, `ups_loading_kva`). The 3,000 kVA option (kW scaled by the same ratio) reads 66.7 % kW and 70.2 % kVA (PASS) in the options table, workbook 06 sheet OPTIONS and the sizing summary."],
         evidence=["tests/unit/test_options_sensitivity.py", "workbook 06_UPS_SIZING sheet OPTIONS", "ER-009, ER-036"],
         still=["Real UPS kW and kVA ratings and the output power factor are manufacturer data; the 3,000 kVA option is illustrative."]),
    dict(no=4, title="Load model review and sensitivity",
         asked="Review cooling load (chiller and pump redundancy, CRAH), the A/B split, UPS and distribution losses; add a sensitivity table (+/-10 % IT load, PUE range); do not force a PUE target.",
         done=["Review recorded (sizing summary, methodology document, ER-037): chillers 4 installed / 3 running (N+1), pumps 6 / 4, CRAH 20 all counted as running with spares not stated; the 50 / 50 path split is an assumption and 3 running chillers cannot split evenly (worst path 240 kW against 180 kW in the model); UPS efficiency (flat 96 %) and distribution loss (flat 1 %) are assumptions.",
               "Sensitivity table: IT load -10 / 0 / +10 % with the cooling plant held as scheduled and scaled with the load, plus UPS efficiency +/-2 points and doubled distribution losses. PUE ranges from 1.322 to 1.382. At +10 % IT the transformer reads 98.0 to 99.9 % and EX-001 does not cover it. Workbook 02 sheet SENSITIVITY (a Python snapshot, labelled as such).",
               "PUE is documented and tested as an output: the check `load_pue_vs_target` no longer suggests retuning inputs, and the sensitivity code varies copies of the configuration, never the configuration itself."],
         evidence=["tests/unit/test_options_sensitivity.py (5 tests)", "calculations/sensitivity.py", "docs/calculation_methodology/power_system_sizing.md", "ER-005, ER-037"],
         still=["CRAH redundancy, the real UPS efficiency curve, the A/B allocation by whole units and mechanical behaviour after a path loss need design decisions and manufacturer data.", "The sensitivity table is a snapshot, not live formulas, and its cases are the package's own choices."]),
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

def _short(items):
    return "; ".join(items)


def markdown(cfg: ProjectConfig, root: Path, stamp: str) -> str:
    kn = key_number_rows(cfg)
    now = summary_now(cfg)
    L = [f"# Corrective action report: {cfg.project.name}", "", f"**Document {cfg.project.code}-DOC-07  Issue {ISSUE}. Package revision {cfg.project.revision}. Generated {stamp}. Package version {__version__}.**", "", f"> {BANNER}", "",
         "This report answers items 5 to 12 of the independent review of revision A5. **Implemented is not verified:** every change below is NOT REVIEWED until an independent engineer says otherwise.", "",
         "## 1. What changed and what did not", "", "Revision A6 changes how results are labelled, drawn and documented, and applies items 1 to 4 of the review. **No load, demand or rating input changed.** One judgement setting changed: the generator combined contingency (one utility path out and one engine out) is now judged, so the generator verification, the suggested generator size and the check summary change (one new WARNING, on generator kW). The table in section 3 shows the reviewed A5 values reproduce.", "",
         "## 2. Items 1 to 4", "", "The text of items 1 to 4 was supplied by the project owner on 2026-11-08 and is answered in the same way as items 5 to 12 below (items 1 to 4 first).", "", "## 3. Key numbers: reviewed at A5, computed now", "", "| Item | Reviewed at A5 | Computed now | Agreement | Status now |", "|---|---|---|---|---|"] + [f"| {' | '.join(r)} |" for r in kn] + [
         "", f"Agreement: {'ALL MATCH' if all(r[3] == 'MATCH' for r in kn) else 'DIFFERENCE FOUND: investigate before release'}. The transformer-limited figure is the utility contribution through one transformer only; it is not the bus fault level.", "",
         "## 4. Check summary", "", "| Status | A5 | A6 |", "|---|---|---|"] + [f"| {k} | {A5_SUMMARY[k]} | {now[k]} |" for k in A5_SUMMARY] + [
         "", "WARNING rose from 2 to 3 because the generator kW check now judges the combined contingency (84.0 % of 3,200 kW, above the 80 % target, below the 100 % limit). NOT VERIFIED rose because checks were added (`cable_derating_basis`, `generator_contingency_basis`, `equipment_options`) and two scope checks read NOT APPLICABLE. Nothing was upgraded and no WARNING was converted to a PASS.", "",
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
    d.add_paragraph("Revision A6 changes how results are labelled, drawn and documented, and applies items 1 to 4 of the review. No load, demand or rating input changed. One judgement setting changed: the generator combined contingency is now judged, so the generator verification, the suggested generator size and the check summary change (one new WARNING, on generator kW).")
    d.add_heading("2. Items 1 to 4", 2)
    d.add_paragraph("The text of items 1 to 4 was supplied by the project owner on 2026-11-08 and is answered in the same way as items 5 to 12 (items 1 to 4 first).")
    d.add_heading("3. Key numbers: reviewed at A5, computed now", 2)
    dx.table(d, ["Item", "Reviewed at A5", "Computed now", "Agreement", "Status now"], key_number_rows(cfg))
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
