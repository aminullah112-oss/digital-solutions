import openpyxl
import pytest

from ohmetry_dc.calculations import assess_distribution, assess_short_circuit, estimate_loads, size_power_system
from ohmetry_dc.config import load_config
from ohmetry_dc.excel import CABLE_FILE, SC_FILE, SIZING_KINDS, build_cable_workbook, build_short_circuit_workbook, build_sizing_workbook
from ohmetry_dc.validation import run_all_checks

from conftest import ATTESTATION, STAMP, needs_soffice, recalc, supply_sc


def _cfg(root, write_config=None, mutate=None):
    if write_config is None:
        return load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    return load_config(write_config(mutate), root / "config" / "load_schedule.yaml")


def _sizing(cfg, kind, tmp_path):
    est = estimate_loads(cfg)
    return build_sizing_workbook(cfg, kind, size_power_system(cfg, est), run_all_checks(cfg), tmp_path / "w" / SIZING_KINDS[kind][0], STAMP)


def _col_find(ws, text, col=1):
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, col).value == text:
            return r
    raise KeyError(text)


def _errors(wb):
    return [(ws.title, c.coordinate, c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str) and (c.value.startswith("#") or c.value.startswith("Err:"))]


def test_workbooks_have_the_standard_sheets_and_input_columns(root, tmp_path):
    cfg = _cfg(root)
    for kind in SIZING_KINDS:
        wb = openpyxl.load_workbook(_sizing(cfg, kind, tmp_path))
        assert wb.sheetnames == ["README", "INPUTS", "CALCULATIONS", "RESULTS"] + (["OPTIONS"] if kind in ("transformer", "ups") else []) + ["REVISION_LOG"]
        hdr = [c.value for c in wb["INPUTS"][5]]
        assert "Preliminary value (retained)" in hdr and "Datasheet / confirmed value (enter here)" in hdr and "Input status" in hdr and "Reviewer attestation: name; organisation; date (YYYY-MM-DD); evidence reference; scope (self-declared, not authenticated)" in hdr
        readme = " ".join(str(c.value) for row in wb["README"].iter_rows() for c in row if c.value)
        assert "Not for construction" in readme and "never read PASS overall" in readme


def test_no_critical_value_is_hard_coded_in_the_calculations(root, tmp_path):
    wb = openpyxl.load_workbook(_sizing(_cfg(root), "transformer", tmp_path))
    calc = wb["CALCULATIONS"]
    assert calc["B5"].value.startswith("=INPUTS!") and "INPUTS!" in calc["E8"].value and "INPUTS!" in calc["L8"].value


@needs_soffice
@pytest.mark.parametrize("kind", ["transformer", "generator", "ups"])
def test_sizing_workbooks_agree_with_python_and_never_pass_on_preliminary_inputs(root, tmp_path, kind):
    cfg = _cfg(root)
    wb = openpyxl.load_workbook(recalc(_sizing(cfg, kind, tmp_path), tmp_path / "rc"), data_only=True)
    assert not _errors(wb)
    res = wb["RESULTS"]
    n = 0
    for r in range(1, res.max_row + 1):
        if str(res.cell(r, 4).value).startswith(("MATCH", "DIFFERENT")):
            assert res.cell(r, 4).value == "MATCH", (res.cell(r, 1).value, res.cell(r, 2).value, res.cell(r, 3).value)
            n += 1
    assert n >= 4 * len(SIZING_KINDS[kind][2])
    overall = [res.cell(r, 2).value for r in range(1, res.max_row + 1) if res.cell(r, 1).value == "OVERALL DESIGN STATUS"]
    assert overall and "PASS" not in overall                      # preliminary inputs: no overall PASS
    assert all(res.cell(r, 2).value == "UNVERIFIED_PLACEHOLDER" for r in range(1, res.max_row + 1) if str(res.cell(r, 1).value).startswith("Input-data status"))


@needs_soffice
def test_datasheet_values_update_the_calculation_and_need_a_source(root, tmp_path):
    cfg = _cfg(root)
    path = _sizing(cfg, "transformer", tmp_path)
    wb = openpyxl.load_workbook(path)
    ws = wb["INPUTS"]
    r = _col_find(ws, "rating_kVA")
    ws[f"E{r}"] = 4000                                           # a datasheet rating, but no source yet
    wb.save(path)
    out = openpyxl.load_workbook(recalc(path, tmp_path / "rc1"), data_only=True)
    i = out["INPUTS"]
    assert i[f"F{r}"].value == 3150 and i[f"J{r}"].value == "REJECTED: SOURCE MISSING"           # rejected without a source: the preliminary value stays
    assert out["RESULTS"]["B13"].value == "MISSING"                                                  # and the input status of the whole check says so
    wb = openpyxl.load_workbook(path)
    wb["INPUTS"][f"H{r}"] = "Transformer data sheet TX-4000, rev B"
    wb.save(path)
    out = openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)
    assert out["INPUTS"][f"F{r}"].value == 4000 and out["INPUTS"][f"J{r}"].value == "MANUFACTURER_SUPPLIED"
    assert out["INPUTS"][f"G{r}"].value == "Transformer data sheet TX-4000, rev B"
    res = out["RESULTS"]
    assert res["B5"].value == pytest.approx(2865.59525 / 4000 * 100, rel=1e-6)                      # loading recalculated with the datasheet rating
    assert res["B12"].value == "PASS" and res["B15"].value == "NOT VERIFIED"                       # a passing calculation, still not verified: other inputs are placeholders


@needs_soffice
def test_overall_pass_needs_every_input_verified_by_a_reviewer(root, tmp_path):
    cfg = _cfg(root)
    path = _sizing(cfg, "ups", tmp_path)
    wb = openpyxl.load_workbook(path)
    ws = wb["INPUTS"]
    for r in range(6, ws.max_row + 1):
        if ws[f"A{r}"].value:
            ws[f"E{r}"] = ws[f"D{r}"].value                       # restate each value from a (hypothetical) data sheet
            ws[f"H{r}"] = "Hypothetical data sheet, rev A (test)"
            ws[f"I{r}"] = ATTESTATION
    wb.save(path)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["RESULTS"]
    r = _col_find(res, "OVERALL DESIGN STATUS")
    assert res.cell(r, 2).value == "PASS"                         # kW block: 80.0 % against an 80 % target
    r2 = _col_find(res, "Engineering verification status")
    assert res.cell(r2, 2).value == "VERIFIED"
    wb = openpyxl.load_workbook(path)                             # remove one reviewer: the pass disappears
    wb["INPUTS"]["I8"] = None
    wb.save(path)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["RESULTS"]
    assert res.cell(_col_find(res, "OVERALL DESIGN STATUS"), 2).value == "NOT VERIFIED"


@needs_soffice
def test_short_circuit_workbook_agrees_with_python_when_inputs_are_supplied(root, write_config, tmp_path):
    cfg = _cfg(root, write_config, supply_sc)
    py = assess_short_circuit(cfg)
    path = build_short_circuit_workbook(cfg, run_all_checks(cfg), tmp_path / "w" / SC_FILE, STAMP)
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)
    assert not _errors(wb)
    res = wb["RESULTS"]
    got = {res.cell(r, 1).value: res.cell(r, 2).value for r in range(4, 11)}
    u = next(c for c in py.lv_cases if c.name.startswith("Utility and one"))
    g = next(c for c in py.lv_cases if c.name.endswith("generators") and not c.name.startswith("Utility"))
    assert got["MV bus, utility Ik'' (kA)"] == pytest.approx(py.mv_case.ik_ka, rel=1e-9)
    assert got["LV: utility and one transformer Ik'' (kA)"] == pytest.approx(u.ik_ka, rel=1e-9)
    assert got["LV: generators Ik'' (kA)"] == pytest.approx(g.ik_ka, rel=1e-9)
    assert got["LV design level (kA)"] == pytest.approx(py.design_lv.ik_ka, rel=1e-9)
    assert got["LV design peak (kA)"] == pytest.approx(py.design_lv.ip_ka, rel=1e-9) and got["LV design thermal equivalent (kA)"] == pytest.approx(py.design_lv.ith_ka, rel=1e-9)
    for r in range(4, 11):
        assert res.cell(r, 4).value == "MATCH"
    st = res.cell(_col_find(res, "OVERALL DESIGN STATUS"), 2).value
    assert st == "NOT VERIFIED"                                    # calculated, but the inputs are test values, not verified data


@needs_soffice
def test_short_circuit_workbook_shows_not_calculated_for_pending_data_and_judges_ratings_when_entered(root, tmp_path):
    cfg = _cfg(root)
    path = build_short_circuit_workbook(cfg, run_all_checks(cfg), tmp_path / "w" / SC_FILE, STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["RESULTS"]
    assert res["B4"].value == "NOT CALCULATED" and res["B5"].value == pytest.approx(82.637, rel=1e-4)       # only the transformer-limited bound is available
    wb = openpyxl.load_workbook(path)
    ws = wb["INPUTS"]
    for key, val in (("utility_mva", 500), ("utility_xr", 10), ("tx_xr", 8), ("gen_xd", 14), ("gen_xr", 20), ("rating_LV-MSB-A", 50), ("rating_MV-SWG-A", 40)):
        r = _col_find(ws, key)
        ws[f"E{r}"] = val
        ws[f"H{r}"] = "Test document, rev A"
    wb.save(path)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["RESULTS"]
    assert res["B4"].value == pytest.approx(20.92, rel=1e-3)
    rows = {res.cell(r, 1).value: (res.cell(r, 4).value, res.cell(r, 5).value) for r in range(20, 30) if res.cell(r, 1).value}
    assert rows["LV-MSB-A switchboard"][0] == "FAIL" and rows["LV-MSB-A switchboard"][1] == "FAIL"        # 50 kA rating against about 74 kA
    assert rows["MV-SWG-A switchgear"][0] == "PASS" and rows["MV-SWG-A switchgear"][1] == "NOT VERIFIED"   # passes arithmetically, unreviewed inputs


@needs_soffice
def test_cable_workbook_agrees_with_python(root, tmp_path):
    cfg = _cfg(root)
    est = estimate_loads(cfg)
    dist = assess_distribution(cfg, est, size_power_system(cfg, est))
    path = build_cable_workbook(cfg, run_all_checks(cfg), tmp_path / "w" / CABLE_FILE, STAMP)
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)
    assert not _errors(wb)
    res = wb["RESULTS"]
    for k, c in enumerate(dist.cables):
        r = 5 + k
        assert res.cell(r, 1).value == c.tag and res.cell(r, 4).value == "MATCH" and res.cell(r, 7).value == "MATCH"
        assert res.cell(r, 2).value == pytest.approx(c.voltage_drop_pct, rel=1e-9)
        assert res.cell(r, 10).value == "NOT VERIFIED"           # no tabulated rating: never assumed
    calc = wb["CALCULATIONS"]
    assert calc["I5"].value == "NOT VERIFIED" and calc["K5"].value == "NOT VERIFIED"


@needs_soffice
def test_cable_workbook_judges_ampacity_and_thermal_withstand_when_data_is_entered(root, tmp_path):
    cfg = _cfg(root)
    path = build_cable_workbook(cfg, run_all_checks(cfg), tmp_path / "w" / CABLE_FILE, STAMP)
    wb = openpyxl.load_workbook(path)
    ws = wb["INPUTS"]
    for key, val in (("CAB-GEN-A.tab", 400), ("ith_lv", 75), ("CAB-MV-A.tab", 300), ("ith_mv", 20)):
        r = _col_find(ws, key)
        ws[f"E{r}"] = val
        ws[f"H{r}"] = "Test cable data sheet, rev A"
    wb.save(path)
    calc = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["CALCULATIONS"]
    assert calc["H6"].value == pytest.approx(481.125 / 400 * 100, rel=1e-4) and calc["I6"].value == "FAIL"       # 120 % of the table value
    assert calc["J6"].value == pytest.approx(75 * 1000 / 6 * 0.5 ** 0.5 / 143, rel=1e-6) and calc["K6"].value == "PASS"
    assert calc["I5"].value == "PASS" and calc["L5"].value == "NOT VERIFIED"


# ---- 07, 11, 12, 13, 15
from ohmetry_dc.excel import OTHER_FILES, build_battery_workbook, build_earthing_workbook, build_rating_workbook      # noqa: E402


def _enter(path, values, source="Test data sheet, rev A"):
    wb = openpyxl.load_workbook(path)
    ws = wb["INPUTS"]
    for key, val in values.items():
        r = _col_find(ws, key)
        ws[f"E{r}"] = val
        ws[f"H{r}"] = source
    wb.save(path)


@needs_soffice
@pytest.mark.parametrize("kind", ["lv", "mv", "busduct"])
def test_rating_workbooks_agree_with_python_and_are_not_verified_without_data(root, tmp_path, kind):
    cfg = _cfg(root)
    path = build_rating_workbook(cfg, kind, tmp_path / "w" / OTHER_FILES[kind], STAMP)
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)
    assert not _errors(wb)
    res = wb["RESULTS"]
    assert res["D5"].value == "MATCH" and res["F5"].value == "NOT VERIFIED" and res["E5"].value == "MISSING"
    assert wb["CALCULATIONS"]["E5"].value == "NOT CALCULATED"        # the required fault level is not available from the shipped data


@needs_soffice
def test_lv_switchboard_is_judged_when_ratings_and_evidence_are_entered(root, tmp_path):
    cfg = _cfg(root)
    path = build_rating_workbook(cfg, "lv", tmp_path / "w" / OTHER_FILES["lv"], STAMP)
    _enter(path, {"req_ik": 74, "LV-MSB-A.rated": 5000, "LV-MSB-A.sc": 65, "LV-MSB-A.form_of_separation": "Form 3b", "LV-MSB-A.ip_rating": "IP31", "LV-MSB-A.verification_evidence": "Type-test report TEST-1"})
    calc = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["CALCULATIONS"]
    assert calc["C5"].value == pytest.approx(4136.13 / 5000 * 100, rel=1e-4) and calc["D5"].value == "PASS"
    assert calc["F5"].value == "FAIL" and calc["G5"].value == 1 and calc["J5"].value == "FAIL"         # 65 kA rating against 74 kA


@needs_soffice
def test_busduct_voltage_drop_is_calculated_only_with_manufacturer_impedance(root, tmp_path):
    cfg = _cfg(root)
    path = build_rating_workbook(cfg, "busduct", tmp_path / "w" / OTHER_FILES["busduct"], STAMP)
    assert openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["CALCULATIONS"]["H5"].value == "NOT CALCULATED"
    _enter(path, {"BD-TX-A.R": 0.02, "BD-TX-A.X": 0.03})
    calc = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["CALCULATIONS"]
    import math
    want = math.sqrt(3) * 4136.13047 * 15 * (0.02 / 1000 * 0.94 + 0.03 / 1000 * math.sqrt(1 - 0.94 ** 2)) / 400 * 100
    assert calc["H5"].value == pytest.approx(want, rel=1e-5) and calc["I5"].value == "PASS"


@needs_soffice
def test_earthing_workbook_agrees_with_python_and_screens_when_inputs_are_entered(root, write_config, tmp_path):
    cfg = _cfg(root)
    path = build_earthing_workbook(cfg, run_all_checks(cfg), tmp_path / "w" / OTHER_FILES["earthing"], STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["RESULTS"]
    assert res["B4"].value == "NOT CALCULATED" and res["B13"].value == "NOT VERIFIED"
    _enter(path, {"rho": 100, "area": 2500, "length": 1200, "depth": 0.5, "ig": 0.5, "ts": 0.5, "rho_s": 3000, "hs": 0.1})
    out = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["RESULTS"]
    from ohmetry_dc.calculations.earthing import grid_resistance, surface_layer_factor, tolerable_touch_v
    assert out["B4"].value == pytest.approx(grid_resistance(100, 2500, 1200, 0.5), rel=1e-9)
    assert out["B5"].value == pytest.approx(0.5 * 1000 * grid_resistance(100, 2500, 1200, 0.5), rel=1e-9)
    assert out["B6"].value == pytest.approx(tolerable_touch_v(3000, surface_layer_factor(100, 3000, 0.1), 0.5), rel=1e-9)
    assert out["B11"].value == "PASS" and out["B13"].value == "NOT VERIFIED"           # screening passes; the inputs are unreviewed


@needs_soffice
def test_battery_workbook_gives_the_energy_and_never_selects_a_battery(root, tmp_path):
    cfg = _cfg(root)
    path = build_battery_workbook(cfg, tmp_path / "w" / OTHER_FILES["battery"], STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["RESULTS"]
    assert res["B4"].value == pytest.approx(2000 * 10 / 60) and res["D4"].value == "MATCH" and res["B5"].value == "NOT CALCULATED"
    _enter(path, {"eta": 96, "eol": 0.8, "temp": 0.95, "margin": 1.1})
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["RESULTS"]
    assert res["B5"].value == pytest.approx(333.3333 / 0.96 / (0.8 * 0.95) * 1.1, rel=1e-5)
    assert "NOT VERIFIED" in res["B8"].value


# ---- 01, 03, 09, 20
from ohmetry_dc.excel import ARCH_FILES, build_architecture_workbook, build_basis_workbook, build_equipment_schedule, build_voltage_drop_workbook      # noqa: E402


@needs_soffice
def test_architecture_workbook_agrees_with_python_and_transfers_ups_load_with_one_ups_per_path(root, tmp_path):
    cfg = _cfg(root)
    path = build_architecture_workbook(cfg, tmp_path / "w" / ARCH_FILES["arch"], STAMP)
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)
    assert not _errors(wb)
    res, calc = wb["RESULTS"], wb["CALCULATIONS"]
    assert [res.cell(r, 4).value for r in (4, 5, 6)] == ["MATCH"] * 3
    assert calc["F6"].value == pytest.approx(90.97, abs=0.01) and calc["J9"].value == "PASS"
    assert calc["G8"].value == pytest.approx(80.0)                 # one UPS out: its critical load moves to the other path's UPS
    assert [calc.cell(r, 2).value for r in range(13, 19)] == ["PASS"] * 6
    assert res["B10"].value == "NOT VERIFIED"                      # preliminary inputs


@needs_soffice
def test_architecture_workbook_fails_a_path_that_cannot_carry_the_load(root, tmp_path):
    cfg = _cfg(root)
    path = build_architecture_workbook(cfg, tmp_path / "w" / ARCH_FILES["arch"], STAMP)
    _enter(path, {"tx_kva": 2500})
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)
    assert wb["CALCULATIONS"]["J6"].value == "FAIL" and wb["RESULTS"]["B10"].value == "FAIL"
    assert wb["CALCULATIONS"]["B16"].value == "FAIL"               # a transformer can no longer carry the whole load alone


@needs_soffice
def test_voltage_drop_workbook_matches_python_and_handles_single_phase_and_starting_cases(root, tmp_path):
    cfg = _cfg(root)
    est = estimate_loads(cfg)
    dist = assess_distribution(cfg, est, size_power_system(cfg, est))
    path = build_voltage_drop_workbook(cfg, tmp_path / "w" / ARCH_FILES["vdrop"], STAMP)
    ws = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["CASES"]
    for k, c in enumerate(dist.cables):
        assert ws.cell(5 + k, 12).value == pytest.approx(c.voltage_drop_pct, rel=1e-9)
    assert ws.cell(10, 11).value == "NOT CALCULATED" and ws.cell(10, 13).value == "NOT VERIFIED"
    wb = openpyxl.load_workbook(path)
    c = wb["CASES"]
    for col, v in zip("CDEFGHIJN", (1, 100, 50, 0.5, 0.1, 0.9, 230, 1, "Test motor data sheet")):
        c[f"{col}10"] = v
    wb.save(path)
    ws = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["CASES"]
    import math
    want = 2 * 100 * 50 * (0.5 / 1000 * 0.9 + 0.1 / 1000 * math.sqrt(1 - 0.81))
    assert ws["K10"].value == pytest.approx(want, rel=1e-9) and ws["M10"].value == "FAIL"        # 2.15 % against a 1 % limit
    assert ws["L10"].value == pytest.approx(want / 230 * 100, rel=1e-9)


@needs_soffice
def test_equipment_schedule_never_reads_verified_without_a_datasheet_and_reviewer(root, tmp_path):
    cfg = _cfg(root)
    path = build_equipment_schedule(cfg, tmp_path / "w" / ARCH_FILES["equip"], STAMP)
    ws = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["SCHEDULE"]
    tags = [ws.cell(r, 1).value for r in range(5, ws.max_row + 1) if ws.cell(r, 1).value]
    assert {"TX-A1", "TX-B1", "GEN-A1", "GEN-B3", "UPS-A1", "BAT-B1", "LV-MSB-A", "MV-SWG-B", "ACB-GEN-A", "CAB-MECH-A"} <= set(tags)
    assert all(str(ws.cell(5 + i, 15).value).startswith("NOT VERIFIED") for i in range(len(tags)))
    wb = openpyxl.load_workbook(path)
    s = wb["SCHEDULE"]
    for col, v in zip("JKLM", ("Test Maker", "TM-1", "DS-1", "A")):
        s[f"{col}5"] = v
    wb.save(path)
    ws = openpyxl.load_workbook(recalc(path, tmp_path / "rc1"), data_only=True)["SCHEDULE"]
    assert ws["O5"].value == "DATA ENTERED: REVIEW REQUIRED"
    wb = openpyxl.load_workbook(path)
    wb["SCHEDULE"]["N5"] = ATTESTATION
    wb.save(path)
    assert openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["SCHEDULE"]["O5"].value == "DATASHEET REVIEWED (attested, not authenticated)"


def test_basis_workbook_lists_every_parameter_with_its_status_and_empty_approval_fields(root, tmp_path):
    cfg = _cfg(root)
    wb = openpyxl.load_workbook(build_basis_workbook(cfg, run_all_checks(cfg), tmp_path / ARCH_FILES["basis"], STAMP))
    assert wb.sheetnames == ["README", "PARAMETERS", "DESIGN_CRITERIA", "ASSUMPTIONS_EXCLUSIONS", "STANDARDS", "CHECK_STATUS", "REVISION_APPROVAL"]
    par = wb["PARAMETERS"]
    assert par.max_row - 4 == len(cfg.parameters)
    assert {par.cell(r, 5).value for r in range(5, par.max_row + 1)} >= {"MISSING", "UNVERIFIED_PLACEHOLDER", "PRELIMINARY_ASSUMPTION", "REFERENCE_DATA"}
    assert all(wb["REVISION_APPROVAL"][f"B{r}"].value is None for r in range(9, 15))
    assert wb["STANDARDS"].max_row >= 20 and all(wb["STANDARDS"].cell(r, 5).value == "NOT_VERIFIED" for r in range(4, 22))


# ---- 14, 16, 17, 18, 19
from ohmetry_dc.excel import (STUDY_FILES, build_energy_workbook, build_fuel_workbook, build_lightning_workbook, build_power_quality_workbook, build_protection_workbook)      # noqa: E402


def _set(path, sheet, cells):
    wb = openpyxl.load_workbook(path)
    for ref, v in cells.items():
        wb[sheet][ref] = v
    wb.save(path)


@needs_soffice
def test_protection_workbook_never_reports_a_coordination_pass(root, tmp_path):
    cfg = _cfg(root)
    path = build_protection_workbook(cfg, tmp_path / "w" / STUDY_FILES["protection"], STAMP)
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)
    assert not _errors(wb)
    assert wb["DEVICE_SCHEDULE"]["L5"].value == "NOT VERIFIED" and wb["SELECTIVITY"]["B14"].value == "NOT VERIFIED"
    _set(path, "DEVICE_SCHEDULE", {"E6": 74, "G6": 100, "J6": "Breaker data sheet, rev A", "I6": "TCC-123", "K6": ATTESTATION})
    _set(path, "SELECTIVITY", {"C5": "TCC-1", "D5": "TCC-2", "E5": "Study S-1", "G5": "SELECTIVE", "C6": "TCC-2", "D6": "TCC-3", "E6": "Study S-1", "C7": "TCC-4", "D7": "TCC-3", "E7": "Study S-1"})
    wb = openpyxl.load_workbook(recalc(path, tmp_path / "rc1"), data_only=True)
    assert wb["DEVICE_SCHEDULE"]["L6"].value == "PASS" and wb["DEVICE_SCHEDULE"]["M6"].value == "RATING VERIFIED (coordination separate)"
    assert wb["SELECTIVITY"]["B14"].value == "EVIDENCE ENTERED: REVIEW REQUIRED"          # never PASS
    _set(path, "DEVICE_SCHEDULE", {"G6": 50})
    assert openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["DEVICE_SCHEDULE"]["L6"].value == "FAIL"


@needs_soffice
def test_lightning_workbook_calculates_collection_area_and_never_claims_compliance(root, tmp_path):
    import math
    cfg = _cfg(root)
    path = build_lightning_workbook(cfg, tmp_path / "w" / STUDY_FILES["lightning"], STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["RESULTS"]
    assert res["B3"].value == "NOT CALCULATED" and res["B9"].value.startswith("NOT VERIFIED")
    ws = openpyxl.load_workbook(path)["INPUTS"]
    rows = {ws.cell(r, 1).value: r for r in range(6, 20) if ws.cell(r, 1).value}
    _set(path, "INPUTS", {**{f"E{rows[k]}": v for k, v in (("L", 100), ("W", 60), ("H", 15), ("Ng", 2), ("Cd", 1))}, **{f"H{rows[k]}": "Site data, rev A" for k in ("L", "W", "H", "Ng", "Cd")}})
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc1"), data_only=True)["RESULTS"]
    ad = 100 * 60 + 2 * 45 * 160 + math.pi * 45 ** 2
    assert res["B3"].value == pytest.approx(ad, rel=1e-9) and res["B4"].value == pytest.approx(2 * ad * 1e-6, rel=1e-9)
    assert res["B9"].value.startswith("NOT VERIFIED")                                      # no risk assessment reference yet


@needs_soffice
def test_power_quality_workbook_calculates_from_measurements_and_needs_limits_and_instrument(root, tmp_path):
    cfg = _cfg(root)
    path = build_power_quality_workbook(cfg, tmp_path / "w" / STUDY_FILES["pq"], STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["RESULTS"]
    assert res["B4"].value == "NOT CALCULATED" and res["D4"].value == "NOT CALCULATED"
    ws = openpyxl.load_workbook(path)["INPUTS"]
    rows = {ws.cell(r, 1).value: r for r in range(6, 25) if ws.cell(r, 1).value}
    vals = {"vab": 400, "vbc": 404, "vca": 396, "v1": 230, "f": 60.1, "vuf_limit": 2, "thd_limit": 5, "freq_limit": 0.5}
    _set(path, "INPUTS", {**{f"E{rows[k]}": v for k, v in vals.items()}, **{f"H{rows[k]}": "Meter report M-1, rev A" for k in vals}})
    _set(path, "HARMONICS", {"B7": 8, "B9": 6})        # 5th and 7th
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc1"), data_only=True)["RESULTS"]
    assert res["B4"].value == pytest.approx(1.0) and res["B5"].value == pytest.approx(10 / 230 * 100, rel=1e-9) and res["B6"].value == pytest.approx(0.1 / 60 * 100, rel=1e-9)
    assert all(str(res[f"D{r}"].value).startswith("NOT VERIFIED") for r in (4, 5, 6))      # no instrument named, inputs unreviewed: no PASS
    _set(path, "INPUTS", {f"E{rows['thd_limit']}": 4})
    assert openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["RESULTS"]["D5"].value == "FAIL"      # 4.35 % against 4 %


@needs_soffice
def test_energy_workbook_agrees_with_the_python_design_point_pue(root, tmp_path):
    cfg = _cfg(root)
    est = estimate_loads(cfg)
    path = build_energy_workbook(cfg, tmp_path / "w" / STUDY_FILES["energy"], STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["RESULTS"]
    assert res["B10"].value == pytest.approx(est.pue, rel=1e-9) and res["E10"].value == "MATCH"
    assert res["B4"].value == pytest.approx(est.it_demand_kw * 8760, rel=1e-9) and res["B14"].value.startswith("NOT VERIFIED")
    assert res["B12"].value == "NOT CALCULATED"


@needs_soffice
def test_fuel_workbook_estimates_nothing_without_the_manufacturer_curve(root, tmp_path):
    cfg = _cfg(root)
    path = build_fuel_workbook(cfg, tmp_path / "w" / STUDY_FILES["fuel"], STAMP)
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc0"), data_only=True)["RESULTS"]
    assert res["B3"].value == "NOT CALCULATED" and res["B6"].value == "NOT CALCULATED" and res["B9"].value.startswith("NOT VERIFIED")
    ws = openpyxl.load_workbook(path)["INPUTS"]
    rows = {ws.cell(r, 1).value: r for r in range(6, 30) if ws.cell(r, 1).value}
    vals = {"x1": 25, "x2": 50, "x3": 75, "x4": 100, "y1": 20, "y2": 35, "y3": 50, "y4": 70, "tank": 20000, "reserve": 10}
    _set(path, "INPUTS", {**{f"E{rows[k]}": v for k, v in vals.items()}, **{f"H{rows[k]}": "Fuel curve, test, rev A" for k in vals}})
    res = openpyxl.load_workbook(recalc(path, tmp_path / "rc1"), data_only=True)["RESULTS"]
    load = openpyxl.load_workbook(path)["INPUTS"][f"D{rows['load_pct']}"].value                 # 83.98 %: the combined contingency, two engines running
    run = openpyxl.load_workbook(path)["INPUTS"][f"D{rows['running']}"].value
    per = next(y0 + (y1 - y0) * (load - x0) / (x1 - x0) for (x0, y0), (x1, y1) in zip([(25, 20), (50, 35), (75, 50)], [(50, 35), (75, 50), (100, 70)]) if x0 < load <= x1)
    assert run == 2 and load == pytest.approx(83.98, abs=0.01)
    assert res["B3"].value == pytest.approx(per, rel=1e-9) and res["B4"].value == pytest.approx(run * per, rel=1e-9)
    assert res["B6"].value == pytest.approx(18000 / (run * per), rel=1e-9) and res["B9"].value.startswith("NOT VERIFIED")
    _set(path, "INPUTS", {f"E{rows['load_pct']}": 110, f"H{rows['load_pct']}": "Test"})
    assert openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["RESULTS"]["B3"].value == "OUTSIDE CURVE"


def test_architecture_workbook_lists_every_concept_function_as_not_designed_and_does_not_claim_utility_independence(root, tmp_path):
    from openpyxl import load_workbook
    from ohmetry_dc.models.architecture import ARCHITECTURE_FUNCTIONS
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    path = build_architecture_workbook(cfg, tmp_path / "w" / ARCH_FILES["arch"], STAMP)
    ws = load_workbook(path)["FUNCTIONS"]
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=5, max_col=6) if r[0].value]
    assert [r[0] for r in rows] == [a.id for a in ARCHITECTURE_FUNCTIONS]
    independence = next(r for r in rows if "Independence of utility" in r[1])
    assert independence[4] == "NOT CLAIMED"
    assert all(r[4] != "VERIFIED" for r in rows)


@needs_soffice
def test_a_bare_reviewer_name_in_a_workbook_is_rejected_as_an_incomplete_attestation(root, tmp_path):
    cfg = _cfg(root)
    path = _sizing(cfg, "ups", tmp_path)
    wb = openpyxl.load_workbook(path)
    ws = wb["INPUTS"]
    r = next(r for r in range(6, ws.max_row + 1) if ws[f"A{r}"].value)
    ws[f"E{r}"], ws[f"H{r}"], ws[f"I{r}"] = ws[f"D{r}"].value, "Hypothetical data sheet, rev A (test)", "Test reviewer"
    wb.save(path)
    got = openpyxl.load_workbook(recalc(path, tmp_path / "rc"), data_only=True)["INPUTS"]
    assert got[f"J{r}"].value == "REJECTED: ATTESTATION INCOMPLETE"
    wb = openpyxl.load_workbook(path)
    wb["INPUTS"][f"I{r}"] = ATTESTATION
    wb.save(path)
    assert openpyxl.load_workbook(recalc(path, tmp_path / "rc2"), data_only=True)["INPUTS"][f"J{r}"].value.endswith("_VERIFIED")


@needs_soffice
def test_options_sheets_recalculate_to_the_python_values_and_follow_a_changed_option_rating(root, tmp_path):
    from ohmetry_dc.calculations import estimate_loads, size_power_system
    from ohmetry_dc.calculations.options import equipment_options
    cfg = _cfg(root)
    opts = equipment_options(cfg, size_power_system(cfg, estimate_loads(cfg)))
    for kind, want in (("transformer", [("kVA", 90.97, "WARNING"), ("kVA", 71.64, "PASS")]), ("ups", [("kW", 80.0, "PASS"), ("kW", 66.67, "PASS"), ("kVA", 84.21, "WARNING"), ("kVA", 70.18, "PASS")])):
        path = _sizing(cfg, kind, tmp_path)
        ws = openpyxl.load_workbook(recalc(path, tmp_path / f"rc_{kind}"), data_only=True)["OPTIONS"]
        assert not _errors(openpyxl.load_workbook(recalc(path, tmp_path / f"rc2_{kind}"), data_only=True))
        got = [(ws[f"A{r}"].value, round(ws[f"D{r}"].value, 2), ws[f"E{r}"].value, ws[f"G{r}"].value) for r in range(5, 5 + len(want))]
        assert [(m, v, s) for m, v, s, _ in got] == want and all(g[3] == "MATCH" for g in got), got
    path = _sizing(cfg, "transformer", tmp_path)                                    # overwrite the option rating: the loading follows
    wb = openpyxl.load_workbook(path)
    wb["OPTIONS"]["C6"] = 3600
    wb.save(path)
    ws = openpyxl.load_workbook(recalc(path, tmp_path / "rc3"), data_only=True)["OPTIONS"]
    assert ws["D6"].value == pytest.approx(2865.595 / 3600 * 100, rel=1e-4) and ws["G6"].value.startswith("DIFFERENT")
