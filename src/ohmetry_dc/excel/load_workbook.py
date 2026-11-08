"""02_LOAD_ESTIMATION.xlsx: the load estimate as a working Excel calculation.

The Python model is the authoritative source. The workbook carries the same calculation as formulas so a reader can follow and change it,
and the RESULTS sheet compares every Excel result with the Python value that was generated with the file. A disagreement shows as FAIL.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.worksheet.datavalidation import DataValidation

from ohmetry_dc import __version__
from ohmetry_dc.calculations import LoadEstimate
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.validation import CheckResult

REQUIRED_SHEETS = ["README", "PROJECT_INPUTS", "LOAD_SCHEDULE", "CALCULATIONS", "AB_ALLOCATION", "DESIGN_CHECKS", "RESULTS", "SENSITIVITY", "REVISION_LOG"]

F = "Arial"
INK = "0E171E"
base = Font(name=F, size=10)
bold = Font(name=F, size=10, bold=True)
blue = Font(name=F, size=10, color="0000FF")
title = Font(name=F, size=16, bold=True, color=INK)
note = Font(name=F, size=9, color="666666")
head = Font(name=F, size=10, bold=True, color="FFFFFF")
FILL_HEAD = PatternFill("solid", fgColor=INK)
FILL_RESULT = PatternFill("solid", fgColor="E3F4E3")   # green: calculated results
FILL_ASSUME = PatternFill("solid", fgColor="FFF9DB")   # yellow: assumptions
FILL_REF = PatternFill("solid", fgColor="EDEFF1")      # grey: reference data
thin = Side(style="thin", color="C9D2DA")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
STATUS_FILLS = {"PASS": "CDEBD3", "WARNING": "FFE9A8", "FAIL": "F8C9C4", "NOT VERIFIED": "E4DCF2", "NOT APPLICABLE": "DDDDDD"}

INPUT_IDS = ["general.it_critical_load", "general.target_pue", "general.estimated_facility_demand", "general.design_power_factor",
             "general.future_expansion_allowance", "equipment.ups_efficiency", "losses.distribution_loss_fraction"]


def _put(ws, ref, value, font=base, fill=None, fmt=None, align=None, border=BOX):
    c = ws[ref]
    c.value = value
    c.font = font
    if fill:
        c.fill = fill
    if fmt:
        c.number_format = fmt
    if align:
        c.alignment = align
    if border:
        c.border = border
    return c


def _header(ws, row, labels, widths):
    for i, (h, w) in enumerate(zip(labels, widths), 1):
        c = ws.cell(row, i, h)
        c.font, c.fill, c.alignment, c.border = head, FILL_HEAD, CENTER, BOX
        ws.column_dimensions[chr(64 + i)].width = w


def _status_formatting(ws, rng):
    for text, color in STATUS_FILLS.items():
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{text}"'], fill=PatternFill("solid", bgColor=color, fgColor=color)))


def _page(ws):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = INK


def build_load_workbook(cfg: ProjectConfig, est: LoadEstimate, checks: list[CheckResult], path: str | Path, generated_utc: str | None = None) -> Path:
    generated_utc = generated_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wb = Workbook()
    try:
        fixed = dt.datetime.strptime(generated_utc.replace(" UTC", ""), "%Y-%m-%d %H:%M")
    except ValueError:
        fixed = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    wb.properties.creator = "Ohmetry"
    wb.properties.created = fixed
    wb.properties.modified = fixed
    wb.properties.title = f"{cfg.project.code} load estimation"
    ws0 = wb.active
    ws0.title = "README"
    pin, ls, calc, ab, dc, res, sens, rev = (wb.create_sheet(n) for n in REQUIRED_SHEETS[1:])
    for ws in wb.worksheets:
        _page(ws)

    # ---- README
    ws0.column_dimensions["A"].width = 3
    ws0.column_dimensions["B"].width = 110
    ws0["B2"].value = "Load estimation: " + cfg.project.name
    ws0["B2"].font = title
    lines = [
        ("Workbook", f"02_LOAD_ESTIMATION.xlsx. Project {cfg.project.code}, revision {cfg.project.revision}. Package version {__version__}. Generated {generated_utc}."),
        ("Status", f"Release state: {cfg.project.release_state.value}. PRELIMINARY. Educational and preliminary engineering reference only."),
        ("Not for construction", "Every input is an illustrative assumption for the sample project, chosen for ideal conditions. Nothing here is manufacturer data, a measured value, an approved design selection, or a statement of code compliance. Any real design needs project data and review by suitably qualified engineers."),
        ("What it does", "Itemised demand load, UPS and distribution losses, facility load and design-point PUE, and the A/B path allocation. Real and reactive power are added separately; apparent power is the square root of the sum of squares."),
        ("How to use", "Change the blue inputs on PROJECT_INPUTS and LOAD_SCHEDULE. Read CALCULATIONS, AB_ALLOCATION and RESULTS. Check that every status on RESULTS and DESIGN_CHECKS is understood."),
        ("Python agreement", "The Python model in the package is the authoritative calculation. The RESULTS sheet compares each Excel result with the Python value that was generated with this file. After you change inputs, those Python values are out of date and the comparison will show FAIL. Re-run the package to refresh them."),
        ("Colour code", "Blue font: inputs. Black font: formulas. Green fill: calculated results. Yellow fill: assumptions. Grey fill: reference data. Status cells: PASS green, WARNING yellow, FAIL red, NOT VERIFIED purple, NOT APPLICABLE grey."),
        ("Limitations", "PUE here is a design-point power ratio, not an annual energy PUE. All load transfers to the surviving path in the path-out scenarios, which ignores load shedding and equipment limits. UPS losses assume all IT load is on the UPS at the stated efficiency. Distribution losses use a single percentage. Power factors of losses use the design assumption."),
        ("Review", "The design basis, assumptions and results require independent engineering review before any use beyond education."),
    ]
    r = 4
    for h, t in lines:
        ws0[f"B{r}"].value, ws0[f"B{r}"].font = h, bold
        ws0[f"B{r+1}"].value, ws0[f"B{r+1}"].font, ws0[f"B{r+1}"].alignment = t, base, WRAP
        ws0.row_dimensions[r + 1].height = 15 * (1 + len(t) // 105)
        r += 3
    ws0[f"B{r}"].value = "Sheets: " + ", ".join(REQUIRED_SHEETS)
    ws0[f"B{r}"].font = note

    # ---- PROJECT_INPUTS
    _header(pin, 4, ["Parameter id", "Name", "Value", "Unit", "Status", "Source"], [38, 42, 12, 8, 18, 70])
    pin["A1"].value, pin["A1"].font = "Project inputs (read from the master configuration)", title
    in_row: dict[str, int] = {}
    for i, pid in enumerate(INPUT_IDS):
        p = cfg.get(pid)
        row = 5 + i
        in_row[pid] = row
        _put(pin, f"A{row}", pid)
        _put(pin, f"B{row}", p.name, align=WRAP)
        c = _put(pin, f"C{row}", p.value, blue, FILL_ASSUME if p.status.value == "ASSUMPTION" else None, "General")
        c.protection = Protection(locked=False)
        _put(pin, f"D{row}", p.unit)
        _put(pin, f"E{row}", p.status.value)
        _put(pin, f"F{row}", p.source, align=WRAP)
    dv = DataValidation(type="decimal", operator="greaterThan", formula1="0", allow_blank=False, showErrorMessage=True, error="Enter a number above zero.")
    pin.add_data_validation(dv)
    for pid in ("general.it_critical_load", "general.target_pue", "general.design_power_factor", "equipment.ups_efficiency"):
        dv.add(f"C{in_row[pid]}")
    pin.freeze_panes = "A5"
    I = lambda pid: f"PROJECT_INPUTS!$C${in_row[pid]}"

    # ---- LOAD_SCHEDULE
    ls["A1"].value, ls["A1"].font = "Load schedule (illustrative assumptions)", title
    _header(ls, 4, ["ID", "Category", "Description", "Qty", "Unit rating (kW)", "Connected (kW)", "PF", "Demand factor", "Demand (kW)", "Demand (kvar)", "Demand (kVA)",
                    "Path A fraction", "Path A (kW)", "Path A (kvar)", "Status", "Source"], [8, 20, 44, 7, 12, 12, 7, 10, 12, 12, 12, 10, 12, 12, 13, 50])
    first = 5
    for i, it in enumerate(est.items):
        row = first + i
        cfg_item = cfg.load_items[i]
        _put(ls, f"A{row}", it.id)
        _put(ls, f"B{row}", it.category)
        _put(ls, f"C{row}", it.description, align=WRAP)
        c = _put(ls, f"D{row}", it.quantity, blue, FILL_ASSUME, "0.##")
        c.protection = Protection(locked=False)
        if cfg_item.rating_from == "general.it_critical_load":
            _put(ls, f"E{row}", f"={I('general.it_critical_load')}", base, None, "#,##0.0")
        else:
            c = _put(ls, f"E{row}", it.unit_rating_kw, blue, FILL_ASSUME, "#,##0.0")
            c.protection = Protection(locked=False)
        _put(ls, f"F{row}", f"=D{row}*E{row}", base, FILL_RESULT, "#,##0.0")
        for col, val, fmt in (("G", it.power_factor, "0.00"), ("H", it.demand_factor, "0.00"), ("L", it.path_a_fraction, "0.00")):
            c = _put(ls, f"{col}{row}", val, blue, FILL_ASSUME, fmt)
            c.protection = Protection(locked=False)
        _put(ls, f"I{row}", f"=F{row}*H{row}", base, FILL_RESULT, "#,##0.0")
        _put(ls, f"J{row}", f"=I{row}*TAN(ACOS(G{row}))", base, FILL_RESULT, "#,##0.0")
        _put(ls, f"K{row}", f"=SQRT(I{row}^2+J{row}^2)", base, FILL_RESULT, "#,##0.0")
        _put(ls, f"M{row}", f"=I{row}*L{row}", base, FILL_RESULT, "#,##0.0")
        _put(ls, f"N{row}", f"=J{row}*L{row}", base, FILL_RESULT, "#,##0.0")
        _put(ls, f"O{row}", cfg_item.status.value)
        _put(ls, f"P{row}", cfg_item.source, align=WRAP)
    last = first + len(est.items) - 1
    tot = last + 1
    _put(ls, f"C{tot}", "Total", bold)
    for col in "FIJMN":
        _put(ls, f"{col}{tot}", f"=SUM({col}{first}:{col}{last})", bold, FILL_RESULT, "#,##0.0")
    _put(ls, f"K{tot}", f"=SQRT(I{tot}^2+J{tot}^2)", bold, FILL_RESULT, "#,##0.0")
    pdv = DataValidation(type="decimal", operator="between", formula1="0.01", formula2="1", showErrorMessage=True, error="Enter a value above 0 and at most 1.")
    ls.add_data_validation(pdv)
    pdv.add(f"G{first}:H{last}")
    fdv = DataValidation(type="decimal", operator="between", formula1="0", formula2="1", showErrorMessage=True, error="Enter a fraction between 0 and 1.")
    ls.add_data_validation(fdv)
    fdv.add(f"L{first}:L{last}")
    ls.freeze_panes = "D5"
    ls.auto_filter.ref = f"A4:P{last}"
    ls[f"A{tot+2}"].value = "Total apparent power is from the total kW and kvar, not the sum of the kVA column. Categories: it_critical, mechanical_cooling, lighting_small_power, auxiliary."
    ls[f"A{tot+2}"].font = note
    LSR = lambda col: f"LOAD_SCHEDULE!${col}${first}:${col}${last}"

    # ---- CALCULATIONS
    calc["A1"].value, calc["A1"].font = "Calculations", title
    _header(calc, 4, ["Quantity", "Value", "Unit", "Formula / note"], [48, 16, 8, 90])
    rows = [
        (5, "IT critical demand", f'=SUMIF({LSR("B")},"it_critical",{LSR("I")})', "kW", "Sum of demand kW for category it_critical", "#,##0.00"),
        (6, "All load items, demand", f"=LOAD_SCHEDULE!I{tot}", "kW", "Sum of demand kW of every item", "#,##0.00"),
        (7, "All load items, reactive demand", f"=LOAD_SCHEDULE!J{tot}", "kvar", "Sum of demand kvar of every item", "#,##0.00"),
        (8, "UPS efficiency", f"={I('equipment.ups_efficiency')}", "%", "Assumption, not manufacturer data", "0.00"),
        (9, "UPS losses", "=B5*(100/B8-1)", "kW", "IT demand x (1/efficiency - 1)", "#,##0.00"),
        (10, "Design power factor", f"={I('general.design_power_factor')}", "-", "Applied to losses", "0.000"),
        (11, "tan(phi) for losses", "=TAN(ACOS(B10))", "-", "tan(acos(power factor))", "0.000000"),
        (12, "UPS losses, reactive", "=B9*B11", "kvar", "", "#,##0.00"),
        (13, "Distribution losses", f"={I('losses.distribution_loss_fraction')}", "%", "Assumption: percentage of the load supplied", "0.00"),
        (14, "Distribution losses", "=B13/100*(B6+B9)", "kW", "Percentage x (load items + UPS losses)", "#,##0.00"),
        (15, "Distribution losses, reactive", "=B14*B11", "kvar", "", "#,##0.00"),
        (16, "Facility demand", "=B6+B9+B14", "kW", "Load items + UPS losses + distribution losses", "#,##0.00"),
        (17, "Facility reactive demand", "=B7+B12+B15", "kvar", "", "#,##0.00"),
        (18, "Facility apparent demand", "=SQRT(B16^2+B17^2)", "kVA", "sqrt(P^2 + Q^2)", "#,##0.00"),
        (19, "Facility power factor", "=B16/B18", "-", "kW / kVA", "0.0000"),
        (20, "Design-point PUE", "=B16/B5", "-", "Facility kW / IT kW. A design-point power ratio, not an annual energy PUE", "0.0000"),
        (21, "Growth allowance", f"={I('general.future_expansion_allowance')}", "%", "Assumption", "0.00"),
        (22, "Design demand including growth", "=B16*(1+B21/100)", "kW", "", "#,##0.00"),
        (23, "Design apparent demand including growth", "=B18*(1+B21/100)", "kVA", "", "#,##0.00"),
    ]
    for r, label, f, unit, nt, fmt in rows:
        _put(calc, f"A{r}", label)
        _put(calc, f"B{r}", f, bold, FILL_RESULT, fmt)
        _put(calc, f"C{r}", unit)
        _put(calc, f"D{r}", nt, note, align=WRAP)
    calc.freeze_panes = "A5"

    # ---- AB_ALLOCATION
    ab["A1"].value, ab["A1"].font = "A/B path allocation", title
    _header(ab, 4, ["Quantity", "Value", "Unit", "Formula / note"], [48, 16, 8, 90])
    abrows = [
        (5, "Path A share of the IT load", f'=SUMIF({LSR("B")},"it_critical",{LSR("M")})/CALCULATIONS!B5', "-", "UPS losses are allocated by this share", "0.0000"),
        (6, "Path A subtotal", f"=LOAD_SCHEDULE!M{tot}+CALCULATIONS!B9*B5", "kW", "Path A items + its share of UPS losses", "#,##0.00"),
        (7, "Path A subtotal, reactive", f"=LOAD_SCHEDULE!N{tot}+CALCULATIONS!B12*B5", "kvar", "", "#,##0.00"),
        (8, "Path A distribution losses", "=CALCULATIONS!B13/100*B6", "kW", "Percentage of the path's own load", "#,##0.00"),
        (9, "Path A load", "=B6+B8", "kW", "", "#,##0.00"),
        (10, "Path A load, reactive", "=B7+B8*CALCULATIONS!B11", "kvar", "", "#,##0.00"),
        (11, "Path A apparent load", "=SQRT(B9^2+B10^2)", "kVA", "", "#,##0.00"),
        (12, "Path B load", "=CALCULATIONS!B16-B9", "kW", "Facility load minus path A", "#,##0.00"),
        (13, "Path B load, reactive", "=CALCULATIONS!B17-B10", "kvar", "", "#,##0.00"),
        (14, "Path B apparent load", "=SQRT(B12^2+B13^2)", "kVA", "", "#,##0.00"),
        (17, "Path out: surviving path carries all, load", "=CALCULATIONS!B16", "kW", "Conservative: all load transfers to the surviving path", "#,##0.00"),
        (18, "Path out: surviving path carries all, reactive", "=CALCULATIONS!B17", "kvar", "", "#,##0.00"),
        (19, "Path out: surviving path carries all, apparent", "=CALCULATIONS!B18", "kVA", "Needed to size each path for a 2N concept (Stage 3)", "#,##0.00"),
    ]
    for r, label, f, unit, nt, fmt in abrows:
        _put(ab, f"A{r}", label)
        _put(ab, f"B{r}", f, bold, FILL_RESULT, fmt)
        _put(ab, f"C{r}", unit)
        _put(ab, f"D{r}", nt, note, align=WRAP)
    ab["A16"].value, ab["A16"].font = "Scenarios", bold

    # ---- RESULTS (Excel against Python)
    res["A1"].value, res["A1"].font = "Results: Excel formula against the Python model", title
    _header(res, 4, ["Quantity", "Unit", "Excel (formula)", "Python (generated)", "Difference", "Tolerance (relative)", "Status"], [44, 8, 18, 18, 14, 18, 14])
    pairs = [
        ("IT demand", "kW", "=CALCULATIONS!B5", est.it_demand_kw), ("All load items, demand", "kW", "=CALCULATIONS!B6", est.items_demand_kw),
        ("UPS losses", "kW", "=CALCULATIONS!B9", est.ups_loss.kw), ("Distribution losses", "kW", "=CALCULATIONS!B14", est.distribution_loss.kw),
        ("Facility demand", "kW", "=CALCULATIONS!B16", est.facility_kw), ("Facility reactive demand", "kvar", "=CALCULATIONS!B17", est.facility_kvar),
        ("Facility apparent demand", "kVA", "=CALCULATIONS!B18", est.facility_kva), ("Facility power factor", "-", "=CALCULATIONS!B19", est.power_factor),
        ("Design-point PUE", "-", "=CALCULATIONS!B20", est.pue), ("Design demand including growth", "kW", "=CALCULATIONS!B22", est.design_demand_kw),
        ("Path A load", "kW", "=AB_ALLOCATION!B9", est.path_a.kw), ("Path B load", "kW", "=AB_ALLOCATION!B12", est.path_b.kw),
    ]
    for i, (label, unit, f, pyv) in enumerate(pairs):
        r = 5 + i
        _put(res, f"A{r}", label)
        _put(res, f"B{r}", unit)
        _put(res, f"C{r}", f, bold, FILL_RESULT, "#,##0.0000")
        _put(res, f"D{r}", pyv, base, FILL_REF, "#,##0.0000")
        _put(res, f"E{r}", f"=C{r}-D{r}", base, None, "0.0E+00")
        _put(res, f"F{r}", 1e-6, base, FILL_REF, "0.0E+00")
        _put(res, f"G{r}", f'=IF(ABS(E{r})<=F{r}*MAX(1,ABS(D{r})),"PASS","FAIL")', bold, None, None, CENTER)
    rend = 4 + len(pairs)
    _status_formatting(res, f"G5:G{rend}")
    res.freeze_panes = "A5"

    # ---- DESIGN_CHECKS
    dc["A1"].value, dc["A1"].font = "Design checks", title
    _header(dc, 4, ["Check", "Excel status", "Python status", "Detail (Python)"], [58, 16, 16, 110])
    tgt, init = I("general.target_pue"), I("general.estimated_facility_demand")
    py = {c.id: c for c in checks}
    xl = [
        ("Design-point PUE against the target", "load_pue_vs_target", f'=IF(CALCULATIONS!B20<={tgt},"PASS","WARNING")'),
        ("Load model against the initial facility demand estimate", "load_demand_vs_initial_estimate", f'=IF(ABS(CALCULATIONS!B16/{init}-1)<=0.02,"PASS","WARNING")'),
        ("Facility power factor against the design assumption", "load_pf_vs_design", f'=IF(ABS(CALCULATIONS!B19-{I("general.design_power_factor")})<=0.02,"PASS","WARNING")'),
        ("A/B path allocation adds up to the facility load", "load_path_allocation_consistent", '=IF(ABS(AB_ALLOCATION!B9+AB_ALLOCATION!B12-CALCULATIONS!B16)<=0.000001,"PASS","FAIL")'),
        ("IT load in the schedule matches the design basis", "load_it_matches_design_basis", f'=IF(ABS(SUMIF({LSR("B")},"it_critical",{LSR("F")})-{I("general.it_critical_load")})<=0.000001,"PASS","FAIL")'),
    ]
    for i, (label, cid, f) in enumerate(xl):
        r = 5 + i
        _put(dc, f"A{r}", label, align=WRAP)
        _put(dc, f"B{r}", f, bold, None, None, CENTER)
        _put(dc, f"C{r}", py[cid].status.value if cid in py else "NOT VERIFIED", base, FILL_REF, None, CENTER)
        _put(dc, f"D{r}", py[cid].detail if cid in py else "", note, align=WRAP)
        dc.row_dimensions[r].height = 30
    dend = 4 + len(xl)
    r = dend + 2
    dc[f"A{r}"].value, dc[f"A{r}"].font = "Other Python checks (not recalculated in Excel)", bold
    other = [c for c in checks if c.id not in {x[1] for x in xl}]
    for j, c in enumerate(other):
        rr = r + 1 + j
        _put(dc, f"A{rr}", c.title, align=WRAP)
        _put(dc, f"B{rr}", "", None)
        _put(dc, f"C{rr}", c.status.value, base, FILL_REF, None, CENTER)
        _put(dc, f"D{rr}", c.detail, note, align=WRAP)
        dc.row_dimensions[rr].height = 30
    _status_formatting(dc, f"B5:C{r + len(other)}")
    dc.freeze_panes = "A5"
    dc[f"A{r + len(other) + 2}"].value = "A PASS is a software check against the stated assumptions. It is not an engineering approval."
    dc[f"A{r + len(other) + 2}"].font = note

    # ---- SENSITIVITY: computed by the Python engine at generation. A snapshot, NOT live formulas.
    from ohmetry_dc.calculations.sensitivity import discrete_allocation_review, it_load_cases, loss_cases, pue_range

    sens["A1"].value, sens["A1"].font = "Sensitivity of the load model (computed by the Python engine at generation: a snapshot, not live formulas)", title
    sens["A2"].value, sens["A2"].font = "Illustrative variations chosen by the package, not forecasts. PUE is an OUTPUT of the load model: no input was adjusted to reach a target, and the design-basis target is context only.", note
    _header(sens, 4, ["Case", "IT (kW)", "Facility (kW)", "Facility (kVA)", "PUE", "Transformer path-out %", "Transformer status", "UPS kW %", "UPS kVA %", "UPS status", "Generators kVA % (combined)", "Generators kW % (combined)", "Generators status"],
            [52, 10, 13, 13, 8, 14, 16, 10, 10, 12, 16, 16, 16])
    cases = it_load_cases(cfg) + loss_cases(cfg)
    for k, c in enumerate(cases):
        rr = 5 + k
        for col, v, fmt in (("A", c.label, None), ("B", c.it_kw, "#,##0"), ("C", c.facility_kw, "#,##0.0"), ("D", c.facility_kva, "#,##0.0"), ("E", c.pue, "0.000"), ("F", c.transformer_pct, "0.0"), ("G", c.transformer_status + (" (EX-001 covers)" if c.exception_covers else " (EX-001 does NOT cover)" if c.exception_covers is False else ""), None),
                            ("H", c.ups_kw_pct, "0.0"), ("I", c.ups_kva_pct, "0.0"), ("J", c.ups_status, None), ("K", c.gen_kva_pct, "0.0"), ("L", c.gen_kw_pct, "0.0"), ("M", c.gen_status, None)):
            _put(sens, f"{col}{rr}", v, base, None, fmt)
    rr = 5 + len(cases) + 1
    lo, hi = pue_range(cases)
    sens[f"A{rr}"].value, sens[f"A{rr}"].font = f"PUE across all cases: {lo:.3f} to {hi:.3f}", bold
    rr += 2
    _header(sens, rr, ["Mechanical item (whole-unit allocation)", "Installed", "Running", "kW per unit", "Model worst path (kW)", "Whole-unit worst path (kW)", "Note"], [52, 10, 13, 13, 8, 14, 60])
    for j, a in enumerate(discrete_allocation_review(cfg)):
        for col, v in zip("ABCDEFG", (a.item, a.installed, a.running, a.unit_kw, a.model_per_path_kw, a.discrete_worst_path_kw, a.note)):
            _put(sens, f"{col}{rr + 1 + j}", v, base, None, None)

    # ---- REVISION_LOG
    rev["A1"].value, rev["A1"].font = "Revision log", title
    _header(rev, 4, ["Revision", "Date", "Description", "Author", "Reviewer", "Status"], [10, 14, 80, 14, 14, 26])
    _put(rev, "A5", cfg.project.revision)
    _put(rev, "B5", generated_utc[:10])
    _put(rev, "C5", "First generated load estimate (Stage 2). Illustrative assumptions for the sample project.", align=WRAP)
    _put(rev, "D5", "Ohmetry")
    _put(rev, "E5", "not assigned")
    _put(rev, "F5", "PRELIMINARY, not reviewed")

    # Sheet protection with no unlock phrase: the calculation sheets cannot be edited by accident, and anyone can remove the protection.
    for ws in (calc, ab, dc, res):
        ws.protection.sheet = True
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
