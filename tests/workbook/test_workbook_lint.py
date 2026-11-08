"""Static Excel-compatibility lint. Excel is not available in the build environment; this is the only check of Excel-specific limits."""
import pytest
from openpyxl import Workbook

from ohmetry_dc.cli import EXIT_FAIL, EXIT_OK, main
from ohmetry_dc.validation.workbook_lint import LintReport, lint_directory, lint_workbook, to_markdown


def _wb(tmp_path, cells, name="t.xlsx", sheets=("A",)):
    wb = Workbook()
    wb.active.title = sheets[0]
    for s in sheets[1:]:
        wb.create_sheet(s)
    for ref, v in cells.items():
        wb[sheets[0]][ref] = v
    p = tmp_path / name
    wb.save(p)
    return p


def _codes(path):
    r = LintReport()
    lint_workbook(path, r)
    return {e.code for e in r.errors}


def test_clean_formulas_pass(tmp_path):
    assert _codes(_wb(tmp_path, {"A1": 1, "A2": '=IF(AND(A1>0,LEN(TRIM("x"))>0),SQRT(A1),"n")', "A3": "=SUM(A1:A2)+B!A1"}, sheets=("A", "B"))) == set()


def test_a_text_literal_over_255_characters_is_flagged(tmp_path):
    assert "TEXT_LITERAL_TOO_LONG" in _codes(_wb(tmp_path, {"A1": '=IF(1=1,"' + "x" * 256 + '","y")'}))
    assert "TEXT_LITERAL_TOO_LONG" not in _codes(_wb(tmp_path, {"A1": '=IF(1=1,"' + "x" * 255 + '","y")'}))


def test_functions_newer_than_excel_2016_and_unknown_functions_are_flagged(tmp_path):
    assert "FUNCTION_NEEDS_NEWER_EXCEL" in _codes(_wb(tmp_path, {"A1": "=XLOOKUP(1,B1:B2,C1:C2)", "A2": '=TEXTJOIN(",",TRUE,B1:B2)'}))
    assert "FUNCTION_NOT_ALLOWLISTED" in _codes(_wb(tmp_path, {"A1": "=FOOBAR(1)"}))


def test_missing_sheet_external_link_error_literal_and_unbalanced_brackets_are_flagged(tmp_path):
    got = _codes(_wb(tmp_path, {"A1": "=Nope!A1", "A2": "='C:\\x\\[book.xlsx]S'!A1", "A3": "=#REF!+1", "A4": "=IF(1=1,2", "A5": '=IF(1=1,"a)'}))
    assert {"MISSING_SHEET", "EXTERNAL_LINK", "ERROR_LITERAL", "UNBALANCED_PARENTHESES", "UNBALANCED_QUOTES"} <= got


def test_over_deep_nesting_and_long_validation_lists_are_flagged(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "=" + "IF(1," * 70 + "1" + ",0)" * 70
    from openpyxl.worksheet.datavalidation import DataValidation
    dv = DataValidation(type="list", formula1='"' + ",".join(["item"] * 80) + '"')
    ws.add_data_validation(dv)
    dv.add("B1")
    p = tmp_path / "d.xlsx"
    wb.save(p)
    assert {"NESTING_TOO_DEEP", "VALIDATION_LIST_TOO_LONG"} <= _codes(p)


def test_numeric_constants_in_formulas_are_listed_for_the_reviewer_but_are_not_errors(tmp_path):
    r = LintReport()
    lint_workbook(_wb(tmp_path, {"A1": "=A2*0.95+7+1", "A2": 3}), r)
    assert r.errors == [] and r.constants["t.xlsx"] == {"0.95", "7"}


def test_report_states_that_excel_was_not_used(tmp_path):
    md = to_markdown(lint_directory(tmp_path), "stamp")
    assert "Microsoft Excel was not available" in md and "not a substitute for opening the workbooks in Excel" in md


def test_cli_fails_on_a_finding_and_on_an_empty_directory(tmp_path):
    out = tmp_path / "out"
    assert main(["lint-workbooks", "--workbooks", str(tmp_path / "none"), "--output", str(out)]) == EXIT_FAIL
    d = tmp_path / "wbs"
    d.mkdir()
    _wb(d, {"A1": "=FOOBAR(1)"})
    assert main(["lint-workbooks", "--workbooks", str(d), "--output", str(out)]) == EXIT_FAIL
    (d / "t.xlsx").unlink()
    _wb(d, {"A1": "=SUM(1,2)"})
    assert main(["lint-workbooks", "--workbooks", str(d), "--output", str(out)]) == EXIT_OK and "No finding" in (out / "WORKBOOK_LINT.md").read_text()


def test_every_shipped_workbook_passes_the_lint(root, tmp_path):
    out = tmp_path / "wb"
    assert main(["--config", str(root / "config" / "project_config.yaml"), "--loads", str(root / "config" / "load_schedule.yaml"), "generate-workbooks", "--workbooks", str(out)]) == EXIT_OK
    rep = lint_directory(out)
    assert rep.workbooks == 20 and rep.formulas > 1000 and [(e.workbook, e.cell, e.code) for e in rep.errors] == []
