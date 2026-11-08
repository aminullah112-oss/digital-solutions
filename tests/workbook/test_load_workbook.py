import openpyxl
import pytest

from ohmetry_dc.calculations import estimate_loads
from ohmetry_dc.config import load_config
from ohmetry_dc.excel import REQUIRED_SHEETS, build_load_workbook
from ohmetry_dc.validation import run_all_checks

from conftest import STAMP, needs_soffice, recalc, set_value


@pytest.fixture
def built(root, tmp_path):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    est = estimate_loads(cfg)
    path = build_load_workbook(cfg, est, run_all_checks(cfg), tmp_path / "w" / "02_LOAD_ESTIMATION.xlsx", STAMP)
    return cfg, est, path


def test_required_sheets_exist_and_open(built):
    _, _, path = built
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == REQUIRED_SHEETS


def test_key_formulas_exist_and_nothing_critical_is_hard_coded(built):
    _, est, path = built
    wb = openpyxl.load_workbook(path)
    calc = wb["CALCULATIONS"]
    assert calc["B9"].value == "=B5*(100/B8-1)"
    assert calc["B20"].value == "=B16/B5"
    assert str(calc["B8"].value).startswith("=PROJECT_INPUTS!")       # efficiency is read from the inputs, not typed in
    ls = wb["LOAD_SCHEDULE"]
    assert ls["F5"].value == "=D5*E5" and ls["I5"].value == "=F5*H5"
    assert ls["E5"].value == "=PROJECT_INPUTS!$C$5"                   # the IT rating is linked to the design basis
    assert wb["RESULTS"]["C9"].value == "=CALCULATIONS!B16"


def test_every_input_has_a_unit_and_status_and_generation_stamp_is_recorded(built):
    _, _, path = built
    wb = openpyxl.load_workbook(path)
    pin = wb["PROJECT_INPUTS"]
    for row in range(5, 12):
        assert pin.cell(row, 4).value and pin.cell(row, 5).value
    assert STAMP in wb["README"]["B5"].value and "PRELIMINARY" in wb["README"]["B8"].value or "PRELIMINARY" in wb["README"]["B11"].value
    readme = " ".join(str(c.value) for row in wb["README"].iter_rows() for c in row if c.value)
    assert "Not for construction" in readme and "independent engineering review" in readme


@needs_soffice
def test_excel_agrees_with_python_and_has_no_errors(built, tmp_path):
    cfg, est, path = built
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)
    res = wb["RESULTS"]
    expected = {5: est.it_demand_kw, 6: est.items_demand_kw, 7: est.ups_loss.kw, 8: est.distribution_loss.kw, 9: est.facility_kw, 10: est.facility_kvar,
                11: est.facility_kva, 12: est.power_factor, 13: est.pue, 14: est.design_demand_kw, 15: est.path_a.kw, 16: est.path_b.kw}
    for row, want in expected.items():
        assert res.cell(row, 3).value == pytest.approx(want, rel=1e-9), res.cell(row, 1).value
        assert res.cell(row, 7).value == "PASS"
    for ws in wb.worksheets:
        for r in ws.iter_rows():
            for c in r:
                assert not (isinstance(c.value, str) and c.value.startswith("#") and c.value[1:2].isupper()), f"{ws.title}!{c.coordinate} {c.value}"
    assert [wb["DESIGN_CHECKS"].cell(r, 2).value for r in range(5, 10)] == ["PASS"] * 5


@needs_soffice
def test_editing_an_input_in_excel_makes_the_python_comparison_fail(built, tmp_path):
    """The comparison must notice a change: a workbook edited away from the generated Python values is flagged, not hidden."""
    _, _, path = built
    wb = openpyxl.load_workbook(path)
    wb["LOAD_SCHEDULE"]["H6"].value = 0.5          # chiller demand factor
    edited = tmp_path / "edited.xlsx"
    wb.save(edited)
    rc = openpyxl.load_workbook(recalc(edited, tmp_path / "rc2"), data_only=True)
    statuses = [rc["RESULTS"].cell(r, 7).value for r in range(5, 17)]
    assert "FAIL" in statuses and rc["RESULTS"]["G5"].value == "PASS"      # IT demand is unchanged, facility demand is not


def test_sheet_protection_has_no_unlock_phrase(built):
    _, _, path = built
    wb = openpyxl.load_workbook(path)
    for name in ("CALCULATIONS", "AB_ALLOCATION", "DESIGN_CHECKS", "RESULTS"):
        assert wb[name].protection.sheet and not wb[name].protection.hashValue
    assert not wb["LOAD_SCHEDULE"].protection.sheet


def test_workbook_content_is_reproducible(root, tmp_path):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    est, checks = estimate_loads(cfg), run_all_checks(cfg)
    a = openpyxl.load_workbook(build_load_workbook(cfg, est, checks, tmp_path / "a.xlsx", STAMP))
    b = openpyxl.load_workbook(build_load_workbook(cfg, est, checks, tmp_path / "b.xlsx", STAMP))
    for ws in a.worksheets:
        assert [[c.value for c in r] for r in ws.iter_rows()] == [[c.value for c in r] for r in b[ws.title].iter_rows()]
