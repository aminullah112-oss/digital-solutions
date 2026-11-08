"""Shared building blocks for the calculation workbooks: input rows with a preliminary value, a manufacturer-confirmed value cell, the source,
a reviewer cell and a live input status, plus the four-status block (calculation, inputs, verification, overall design).

Rules the formulas enforce, matching the Python engine:
  - a datasheet value in column E is used only if a source (column H) is given; without a source the status shows REJECTED and the preliminary value stays in force
  - a value stays MANUFACTURER_SUPPLIED until a reviewer name is entered in column I; only then does it read MANUFACTURER_VERIFIED
  - an overall PASS needs a passing calculation AND every input verified or an accepted project decision or reference value
"""
from __future__ import annotations

import datetime as dt

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Protection
from openpyxl.worksheet.datavalidation import DataValidation

from ohmetry_dc import __version__
from ohmetry_dc.excel.load_workbook import (BOX, CENTER, FILL_ASSUME, FILL_HEAD, FILL_REF, FILL_RESULT, INK, WRAP, _header, _page, _put, _status_formatting, base, blue, bold, head, note, title)
from openpyxl.styles import PatternFill

FILL_INPUT = PatternFill("solid", fgColor="DCEBFF")      # blue: cell the customer edits
INPUT_HEADERS = ["Key", "Parameter", "Unit", "Preliminary value (retained)", "Datasheet / confirmed value (enter here)", "Effective value used", "Source of the effective value",
                 "Datasheet source and revision (REQUIRED with a value in E)", "Reviewer attestation: name; organisation; date (YYYY-MM-DD); evidence reference; scope (self-declared, not authenticated)", "Input status", "Preliminary status", "Note"]
INPUT_WIDTHS = [20, 40, 9, 16, 18, 14, 44, 34, 24, 26, 24, 44]
STATUS_COLORS = {"PASS": "CDEBD3", "WARNING": "FFE9A8", "FAIL": "F8C9C4", "NOT VERIFIED": "E4DCF2", "NOT CALCULATED": "E4DCF2", "MISSING": "F8C9C4", "VERIFIED": "CDEBD3",
                 "UNVERIFIED_PLACEHOLDER": "FFE9A8", "PRELIMINARY_ASSUMPTION": "FFF3C4", "MANUFACTURER_SUPPLIED": "DCEBFF", "SITE_DATA_SUPPLIED": "DCEBFF", "CALCULATED": "E3F4E3"}


def new_workbook(cfg, stamp: str, title_text: str) -> tuple[Workbook, dt.datetime]:
    try:
        fixed = dt.datetime.strptime(stamp.replace(" UTC", ""), "%Y-%m-%d %H:%M")
    except ValueError:
        fixed = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    wb = Workbook()
    wb.properties.creator = "Ohmetry"
    wb.properties.created = fixed
    wb.properties.modified = fixed
    wb.properties.title = f"{cfg.project.code} {title_text}"
    return wb, fixed


def colour_statuses(ws, rng: str) -> None:
    for text, color in STATUS_COLORS.items():
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{text}"'], fill=PatternFill("solid", bgColor=color, fgColor=color)))


class Inputs:
    """The INPUTS sheet: one row per input."""

    def __init__(self, ws, heading: str, intro: str, first_row: int = 6):
        self.ws, self.first, self.row, self.rows, self.text_rows = ws, first_row, first_row, {}, set()
        ws["A1"].value, ws["A1"].font = heading, title
        ws["A2"].value, ws["A2"].font = intro, note
        ws["A3"].value = ("Blue cells are yours to edit. Enter a datasheet value in column E AND its source in column H. Without a source the value is rejected and the preliminary value stays in force. "
                          "A reviewer name in column I marks the value as checked against the source.")
        ws["A3"].font = bold
        _header(ws, first_row - 1, INPUT_HEADERS, INPUT_WIDTHS)
        ws.row_dimensions[first_row - 1].height = 54

    def add(self, key, label, unit, prelim, prelim_status, source, supplied="MANUFACTURER", note_text="", fmt="General", fixed=False, text=False):
        """prelim: the retained preliminary value (None for pending). supplied: MANUFACTURER or SITE_DATA, the label a supplied value earns.
        fixed=True is for reference constants and project policy: shown in column D only, no datasheet column needed."""
        ws, r = self.ws, self.row
        self.rows[key] = r
        if text:
            self.text_rows.add(r)
        _put(ws, f"A{r}", key, note)
        _put(ws, f"B{r}", label, base, align=WRAP)
        _put(ws, f"C{r}", unit)
        _put(ws, f"D{r}", prelim, base, FILL_ASSUME if prelim is not None else None, fmt)
        e = _put(ws, f"E{r}", None, blue, FILL_INPUT, fmt)
        e.protection = Protection(locked=False)
        _put(ws, f"F{r}", f'=IF(AND(E{r}<>"",H{r}<>""),E{r},IF(D{r}="","",D{r}))', bold, FILL_RESULT, fmt)
        _put(ws, f"G{r}", f'=IF(AND(E{r}<>"",H{r}<>""),H{r},{_q(source)})', base, align=WRAP)
        h = _put(ws, f"H{r}", None, blue, FILL_INPUT, align=WRAP)
        h.protection = Protection(locked=False)
        i = _put(ws, f"I{r}", None, blue, FILL_INPUT)
        i.protection = Protection(locked=False)
        _put(ws, f"J{r}", (f'=IF(AND(E{r}<>"",H{r}=""),"REJECTED: SOURCE MISSING",IF(F{r}="","MISSING",IF(AND(E{r}<>"",H{r}<>""),IF(I{r}="","{supplied}_SUPPLIED",IF({attested(f"I{r}")},"{supplied}_VERIFIED","REJECTED: ATTESTATION INCOMPLETE")),K{r})))'), bold, align=CENTER)
        _put(ws, f"K{r}", prelim_status if prelim is not None else "MISSING")
        _put(ws, f"L{r}", note_text, note, align=WRAP)
        self.row += 1
        return r

    @property
    def last(self) -> int:
        return self.row - 1

    def eff(self, key) -> str:
        return f"INPUTS!$F${self.rows[key]}"

    def status_range(self, keys: list[str] | None = None) -> str:
        if keys is None:
            return f"INPUTS!$J${self.first}:$J${self.last}"
        rs = sorted(self.rows[k] for k in keys)
        return f"INPUTS!$J${rs[0]}:$J${rs[-1]}" if rs == list(range(rs[0], rs[-1] + 1)) else ",".join(f"INPUTS!$J${r}" for r in rs)

    def finish(self):
        ws = self.ws
        dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True, showErrorMessage=True, error="Enter a number (in the unit shown) or leave blank.")
        ws.add_data_validation(dv)
        for r in range(self.first, self.last + 1):
            if r not in self.text_rows:
                dv.add(f"E{r}")
        colour_statuses(ws, f"J{self.first}:K{self.last}")
        ws.freeze_panes = f"C{self.first}"


def attested(ref: str) -> str:
    """Excel test that a reviewer cell holds a full attestation: name; organisation; date; evidence reference; scope (four semicolons, no empty text).
    It cannot authenticate the person: it only refuses an entry that lacks the record."""
    return f'AND(LEN(TRIM({ref}))>=20,LEN({ref})-LEN(SUBSTITUTE({ref},";",""))>=4)'


def _q(text: str) -> str:
    return '"' + str(text).replace('"', '""') + '"'


def agg_status(rng_cells: str) -> str:
    """Worst input status over a range or a comma list of cells (a formula fragment)."""
    cnt = lambda pat: f'COUNTIF({rng_cells},"{pat}")' if "," not in rng_cells else "+".join(f'COUNTIF({c},"{pat}")' for c in rng_cells.split(","))
    return (f'IF({cnt("MISSING")}+{cnt("REJECTED*")}>0,"MISSING",IF({cnt("UNVERIFIED_PLACEHOLDER")}>0,"UNVERIFIED_PLACEHOLDER",IF({cnt("PRELIMINARY_ASSUMPTION")}>0,"PRELIMINARY_ASSUMPTION",'
            f'IF({cnt("*_SUPPLIED")}>0,"MANUFACTURER_SUPPLIED","VERIFIED_OR_ACCEPTED"))))')


def status_block(ws, top: int, label: str, required_refs: list[str], result_expr: str, rng_cells: str, col: str = "B") -> dict:
    """Write the four statuses and the overall design status. Returns the cell references.

    Row top: heading. Then calculation status, calculation result, input status, engineering verification status, overall design status.
    result_expr must evaluate to PASS, WARNING or FAIL when the calculation ran.
    """
    A, B = "A", col
    _put(ws, f"{A}{top}", label, bold)
    cnt = ",".join(required_refs)
    rows = {"calc": top + 1, "result": top + 2, "inputs": top + 3, "verif": top + 4, "overall": top + 5}
    labels = {"calc": "Calculation status (did the arithmetic run on complete inputs)", "result": "Calculation result (against the criterion; preliminary if inputs are)",
              "inputs": "Input-data status (worst input)", "verif": "Engineering verification status", "overall": "OVERALL DESIGN STATUS"}
    for k, r in rows.items():
        _put(ws, f"{A}{r}", labels[k], bold if k == "overall" else base, align=WRAP)
    c, res, inp, ver, ov = (f"{B}{rows[k]}" for k in ("calc", "result", "inputs", "verif", "overall"))
    _put(ws, c, f'=IF(COUNT({cnt})<{len(required_refs)},"NOT CALCULATED","CALCULATED")', bold, align=CENTER)
    _put(ws, res, f'=IF({c}="NOT CALCULATED","N/A",{result_expr})', bold, align=CENTER)
    _put(ws, inp, f"={agg_status(rng_cells)}", bold, align=CENTER)
    _put(ws, ver, f'=IF(AND({res}="PASS",{inp}="VERIFIED_OR_ACCEPTED"),"VERIFIED","NOT VERIFIED")', bold, align=CENTER)
    _put(ws, ov, f'=IF({c}="NOT CALCULATED","NOT VERIFIED",IF({res}="FAIL","FAIL",IF({res}="WARNING","WARNING",IF({ver}="VERIFIED","PASS","NOT VERIFIED"))))', bold, align=CENTER)
    colour_statuses(ws, f"{B}{top + 1}:{B}{top + 5}")
    return {"calc": c, "result": res, "inputs": inp, "verif": ver, "overall": ov}


def readme(ws, heading: str, file: str, cfg, stamp: str, what: str, limits: str, sheets: list[str]) -> None:
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 110
    ws["B2"].value, ws["B2"].font = heading, title
    rows = [("Workbook", f"{file}. Project {cfg.project.code}, revision {cfg.project.revision}. Package version {__version__}. Generated {stamp}."),
            ("Status", f"Release state: {cfg.project.release_state.value}. PRELIMINARY. Educational and preliminary engineering reference only. Not for construction."),
            ("What it does", what),
            ("How to use it with datasheet values", "On INPUTS, type the datasheet value in column E (same unit as column C) and the datasheet source and revision in column H. Every calculation updates. "
             "The value is used only when a source is present. A reviewer name in column I records that the value was checked against its source."),
            ("Four separate statuses", "RESULTS shows, separately: the calculation status (did the arithmetic run), the calculation result (PASS, WARNING or FAIL against the criterion), the input-data status "
             "(PRELIMINARY_ASSUMPTION, UNVERIFIED_PLACEHOLDER, MANUFACTURER_SUPPLIED, ...) and the overall design status. A calculation on preliminary inputs can never read PASS overall: "
             "it reads NOT VERIFIED, with the calculation result shown beside it."),
            ("Colour code", "Blue fill: cells you edit. Yellow fill: retained preliminary values. Green fill: calculated results. Purple status: NOT VERIFIED."),
            ("Limitations", limits),
            ("Review", "A passing calculation is not a verified design. The inputs, results and design need independent engineering review before any use beyond education.")]
    r = 4
    for h, t in rows:
        ws[f"B{r}"].value, ws[f"B{r}"].font = h, bold
        ws[f"B{r+1}"].value, ws[f"B{r+1}"].font, ws[f"B{r+1}"].alignment = t, base, WRAP
        ws.row_dimensions[r + 1].height = 15 * (1 + len(t) // 105)
        r += 3
    ws[f"B{r}"].value, ws[f"B{r}"].font = "Sheets: " + ", ".join(sheets), note


def revision_sheet(ws, cfg, stamp: str, file: str) -> None:
    ws["A1"].value, ws["A1"].font = "Revision log", title
    _header(ws, 3, ["Date", "Revision", "Package version", "Change"], [22, 12, 16, 90])
    for i, v in enumerate([stamp, cfg.project.revision, __version__, f"{file} generated from the master configuration. Customer edits to INPUTS are recorded by the customer."]):
        _put(ws, f"{'ABCD'[i]}4", v, base, align=WRAP)
