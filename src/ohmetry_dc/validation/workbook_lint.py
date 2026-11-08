"""Static lint of the generated workbooks for Microsoft Excel compatibility.

WHY THIS EXISTS. Microsoft Excel was NOT available when this package was built. The workbook tests recalculate with LibreOffice only. LibreOffice accepts things that
Excel rejects (a text literal over 255 characters inside a formula, a function Excel 2016 lacks, an external link). This lint reads every formula and flags those.
It is NOT a substitute for opening the workbooks in Excel: it cannot show that Excel and LibreOffice give the same numbers, and a clean lint does not mean the formulas are right.

Errors are things Excel would reject or mis-evaluate. Notes list the numeric constants typed into formulas, for a reviewer auditing R34 (no hard-coded critical values).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

# Functions available in Excel 2007 and later (no _xlfn prefix needed). Anything else is flagged for a person to look at.
ALLOWED = {"ABS", "ACOS", "AND", "ASIN", "ATAN", "ATAN2", "AVERAGE", "CEILING", "COS", "COUNT", "COUNTA", "COUNTIF", "COUNTIFS", "EXP", "FLOOR", "IF", "IFERROR", "INDEX", "INT", "ISBLANK", "ISNUMBER", "ISTEXT",
           "LEFT", "LEN", "LN", "LOG", "LOG10", "MATCH", "MAX", "MIN", "MOD", "N", "NOT", "OR", "PI", "POWER", "RIGHT", "ROUND", "ROUNDDOWN", "ROUNDUP", "SIN", "SQRT", "SUBSTITUTE", "SUM", "SUMIF", "SUMIFS",
           "SUMPRODUCT", "SUMSQ", "TAN", "TEXT", "TRIM", "UPPER", "VLOOKUP", "HLOOKUP", "AVERAGEIF"}
POST_2016 = {"IFS", "SWITCH", "MAXIFS", "MINIFS", "CONCAT", "TEXTJOIN", "XLOOKUP", "XMATCH", "FILTER", "SORT", "UNIQUE", "SEQUENCE", "LET", "LAMBDA", "RANDARRAY", "TEXTSPLIT", "VSTACK", "HSTACK"}
MAX_LITERAL, MAX_FORMULA, MAX_DEPTH = 255, 8192, 64
SAFE_CONSTANTS = {"0", "1", "2", "3", "100", "1000", "1000000", "20", "0.000000001", "0.000001", "0.0001"}      # counting, unit conversion and tolerances, not engineering values


@dataclass
class Finding:
    workbook: str
    sheet: str
    cell: str
    code: str
    message: str


@dataclass
class LintReport:
    workbooks: int = 0
    formulas: int = 0
    errors: list[Finding] = field(default_factory=list)
    constants: dict[str, set[str]] = field(default_factory=dict)       # workbook -> numeric constants typed into formulas (for the reviewer)
    functions: set[str] = field(default_factory=set)


def _strip_strings(f: str) -> tuple[str, list[str]]:
    lits = [m.group(1).replace('""', '"') for m in re.finditer(r'"((?:[^"]|"")*)"', f)]
    return re.sub(r'"(?:[^"]|"")*"', '""', f), lits


def _depth(f: str) -> int:
    d = m = 0
    for ch in f:
        if ch == "(":
            d += 1
            m = max(m, d)
        elif ch == ")":
            d -= 1
    return m


def lint_workbook(path: Path, report: LintReport) -> None:
    wb = load_workbook(path)
    name = path.name
    sheets = {s.title for s in wb.worksheets}
    report.workbooks += 1
    consts: set[str] = set()
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                report.formulas += 1
                add = lambda code, msg: report.errors.append(Finding(name, ws.title, c.coordinate, code, msg))
                body, lits = _strip_strings(v)
                if len(v) > MAX_FORMULA:
                    add("FORMULA_TOO_LONG", f"{len(v)} characters (Excel limit {MAX_FORMULA})")
                for lit in lits:
                    if len(lit) > MAX_LITERAL:
                        add("TEXT_LITERAL_TOO_LONG", f"a text literal of {len(lit)} characters inside a formula (Excel limit {MAX_LITERAL}); put the text in a cell and refer to it")
                if v.count('"') % 2:
                    add("UNBALANCED_QUOTES", "odd number of quotation marks")
                if body.count("(") != body.count(")"):
                    add("UNBALANCED_PARENTHESES", "parentheses do not balance")
                if _depth(body) > MAX_DEPTH:
                    add("NESTING_TOO_DEEP", f"nesting depth {_depth(body)} (Excel limit {MAX_DEPTH})")
                for fn in re.findall(r"([A-Za-z_][A-Za-z0-9_\.]*)\(", body):
                    u = fn.upper()
                    report.functions.add(u)
                    if u in POST_2016:
                        add("FUNCTION_NEEDS_NEWER_EXCEL", f"{u} is not in Excel 2016 or earlier")
                    elif u not in ALLOWED:
                        add("FUNCTION_NOT_ALLOWLISTED", f"{u} is not on the allowlist of Excel 2007+ functions; check it exists in Excel")
                if re.search(r"#(REF|NAME|VALUE|DIV/0|N/A)!?", body):
                    add("ERROR_LITERAL", "an error value is written into the formula")
                if re.search(r"\[[^\]]+\]|\.xls[xmb]?'?!", body):
                    add("EXTERNAL_LINK", "the formula refers to another workbook")
                for m in re.finditer(r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_\.]*))!", body):
                    ref = m.group(1) or m.group(2)
                    if ref not in sheets:
                        add("MISSING_SHEET", f"refers to sheet '{ref}', which does not exist")
                no_refs = re.sub(r"\$?[A-Z]{1,3}\$?\d+", "", re.sub(r"(?:'[^']+'|[A-Za-z_][A-Za-z0-9_\.]*)!", "", body))
                consts |= {k for k in re.findall(r"(?<![A-Za-z_\.])\d+\.?\d*(?:[eE][+-]?\d+)?", no_refs) if k not in SAFE_CONSTANTS}
        for dv in ws.data_validations.dataValidation:
            f1 = dv.formula1 or ""
            if dv.type == "list" and f1.startswith('"') and len(f1) - 2 > MAX_LITERAL:
                report.errors.append(Finding(name, ws.title, str(dv.sqref), "VALIDATION_LIST_TOO_LONG", f"a list of {len(f1) - 2} characters (Excel limit {MAX_LITERAL})"))
    report.constants[name] = consts


def lint_directory(directory: Path) -> LintReport:
    report = LintReport()
    for p in sorted(Path(directory).glob("*.xlsx")):
        lint_workbook(p, report)
    return report


def to_markdown(report: LintReport, generated: str) -> str:
    L = ["# Workbook static lint (Excel compatibility)", "", f"Generated {generated}. {report.workbooks} workbooks, {report.formulas:,} formulas, {len(report.functions)} distinct functions.", "",
         "**Microsoft Excel was not available when this package was built.** The workbook tests recalculate with LibreOffice only. This lint is a static read of the formulas for things Excel rejects "
         "(text literals over 255 characters, functions newer than Excel 2016, external links, unbalanced brackets, references to missing sheets). **It is not a substitute for opening the workbooks in Excel** "
         "and a clean result does not show that the formulas are right or that Excel and LibreOffice agree.", ""]
    if report.errors:
        L += [f"## {len(report.errors)} finding(s)", "", "| Workbook | Sheet | Cell | Code | Message |", "|---|---|---|---|---|"] + [f"| {e.workbook} | {e.sheet} | {e.cell} | {e.code} | {e.message} |" for e in report.errors]
    else:
        L += ["## Result", "", "No finding. Every formula uses only allowlisted Excel 2007+ functions and stays within the Excel limits checked here."]
    L += ["", "## Constants typed into formulas (for the reviewer's formula audit)", "",
          "Numbers other than counting, unit-conversion and tolerance values that appear inside formulas. Each should be a standard equation constant or an input cell reference; check each against its source.", "",
          "| Workbook | Constants |", "|---|---|"] + [f"| {k} | {', '.join(sorted(v, key=lambda x: float(x))) or '-'} |" for k, v in sorted(report.constants.items())]
    L += ["", "Functions used: " + ", ".join(sorted(report.functions)) + "."]
    return "\n".join(L) + "\n"
