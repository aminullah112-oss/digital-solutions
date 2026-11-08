"""Changing the IT load in the master configuration updates every downstream result, workbook and report."""
import json
import subprocess

import openpyxl
import pytest

from ohmetry_dc.cli import EXIT_OK, main

from conftest import STAMP, needs_pdftotext, needs_soffice, recalc, set_value


def run(root, cfg_path, out):
    base = ["--config", str(cfg_path), "--loads", str(root / "config" / "load_schedule.yaml")]
    assert main(base + ["run-calculations", "--output", str(out / "o")]) == EXIT_OK
    assert main(base + ["--generated", STAMP, "generate-workbooks", "--workbooks", str(out / "w")]) == EXIT_OK
    assert main(base + ["--generated", STAMP, "generate-reports", "--reports", str(out / "r")]) == EXIT_OK
    return json.loads((out / "o" / "results.json").read_text())


@needs_soffice
@needs_pdftotext
def test_it_load_change_propagates_to_results_workbook_and_report(root, write_config, tmp_path):
    shipped = run(root, root / "config" / "project_config.yaml", tmp_path / "base")
    changed = run(root, write_config(lambda d: set_value(d, "general", "it_critical_load", 3000)), tmp_path / "changed")
    b, c = shipped["load_estimate"], changed["load_estimate"]
    assert c["it_demand_kw"] == pytest.approx(3000) and c["facility_kw"] > b["facility_kw"] and c["ups_loss"]["kw"] > b["ups_loss"]["kw"]
    assert c["path_a"]["kw"] > b["path_a"]["kw"]
    # the workbook, recalculated by a separate engine, shows the same new numbers and still agrees with Python
    wb = openpyxl.load_workbook(recalc(tmp_path / "changed" / "w" / "02_LOAD_ESTIMATION.xlsx", tmp_path / "changed" / "rc"), data_only=True)
    assert wb["RESULTS"]["C9"].value == pytest.approx(c["facility_kw"], rel=1e-9) and wb["PROJECT_INPUTS"]["C5"].value == 3000
    assert [wb["RESULTS"].cell(r, 7).value for r in range(5, 17)] == ["PASS"] * 12
    # the report shows them too
    txt = subprocess.run(["pdftotext", "-layout", str(tmp_path / "changed" / "r" / "02_Electrical_Load_Estimation_Report.pdf"), "-"], check=True, capture_output=True, text=True).stdout
    assert f"{c['facility_kw']:,.1f} kW" in txt and f"{b['facility_kw']:,.1f} kW" not in txt
    # the stated initial estimate is NOT adjusted: the inconsistency is reported instead
    ids = {x["id"]: x["status"] for x in changed["checks"]}
    assert ids["pue_arithmetic"] == "FAIL" and ids["load_demand_vs_initial_estimate"] == "WARNING"
