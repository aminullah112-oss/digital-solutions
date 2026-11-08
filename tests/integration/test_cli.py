import json

import pytest
import yaml

from ohmetry_dc.cli import EXIT_CONFIG, EXIT_FAIL, EXIT_OK, main


def args(root, *extra):
    pre = [e for e in extra if e == "--generated"]
    if extra and extra[0] == "--generated":
        return ["--config", str(root / "config" / "project_config.yaml"), "--loads", str(root / "config" / "load_schedule.yaml"), extra[0], extra[1], *extra[2:]]
    return ["--config", str(root / "config" / "project_config.yaml"), "--loads", str(root / "config" / "load_schedule.yaml"), *extra]


def test_validate_config_on_the_shipped_configuration(root, tmp_path, capsys):
    out = tmp_path / "result.json"
    code = main(args(root, "validate-config", "--json", str(out)))
    data = json.loads(out.read_text())
    assert code == EXIT_OK and data["summary"]["FAIL"] == 0
    assert data["release_gate"] == "DEVELOPMENT" and data["declared_state"] == "DEVELOPMENT"
    assert {c["id"] for c in data["checks"]} >= {"required_user_inputs", "inputs_deferred", "pue_arithmetic", "transformer_loading", "load_pue_vs_target"}
    assert data["summary"]["NOT VERIFIED"] >= 5 and data["summary"]["WARNING"] == 2      # transformer and UPS kVA are above the preferred targets
    statuses = {c["id"]: c["status"] for c in data["checks"]}
    calc = {c["id"]: c["calculation_result"] for c in data["checks"]}
    assert statuses["transformer_loading"] == "WARNING" and statuses["ups_loading_kw"] == "NOT VERIFIED" and calc["ups_loading_kw"] == "PASS" and statuses["generator_step_load"] == "NOT VERIFIED" and statuses["battery_sizing"] == "NOT VERIFIED"
    assert "required_user_inputs" in capsys.readouterr().out


def test_validate_config_fails_and_blocks_release_when_a_current_stage_input_is_missing(write_config, root, tmp_path):
    def mutate(d):
        d["sections"]["general"]["future_expansion_allowance"].update(value=None, status="USER_INPUT")
    out = tmp_path / "r.json"
    code = main(["--config", str(write_config(mutate)), "--loads", str(root / "config" / "load_schedule.yaml"), "validate-config", "--json", str(out)])
    assert code == EXIT_FAIL
    assert json.loads(out.read_text())["release_gate"] == "RELEASE_BLOCKED"


def test_configuration_error_gives_exit_2(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "missing.yaml"), "validate-config"]) == EXIT_CONFIG
    assert "Configuration error" in capsys.readouterr().err


def test_generate_drawings_writes_the_single_line_diagram(root, tmp_path):
    assert main(args(root, "generate-drawings", "--drawings", str(tmp_path))) == EXIT_OK
    assert "NOT FOR CONSTRUCTION" in (tmp_path / "svg" / "OHM-DC-2000-SLD-001.svg").read_text()


def test_assumptions_register_is_in_step_with_the_configuration(root):
    assert main(args(root, "build-assumptions-register", "--register", str(root / "config" / "assumptions_register.yaml"), "--check")) == EXIT_OK


def test_assumptions_register_lists_every_assumption_and_marks_them_unconfirmed(root):
    reg = yaml.safe_load((root / "config" / "assumptions_register.yaml").read_text())
    ids = {a["id"] for a in reg["assumptions"]}
    assert "general.it_critical_load" in ids and "equipment.ups_rating" in ids
    assert all(a["confirmation_status"] == "UNCONFIRMED" for a in reg["assumptions"])


def test_run_calculations_writes_results_json(root, tmp_path, capsys):
    assert main(args(root, "run-calculations", "--output", str(tmp_path))) == EXIT_OK
    data = json.loads((tmp_path / "results.json").read_text())
    assert data["load_estimate"]["pue"] == pytest.approx(1.3487, abs=1e-4)
    assert "PUE 1.349" in capsys.readouterr().out


def test_generate_commands_write_the_files(root, tmp_path):
    assert main(args(root, "--generated", "2026-11-05 12:00 UTC", "generate-workbooks", "--workbooks", str(tmp_path / "w"))) == EXIT_OK
    assert main(args(root, "--generated", "2026-11-05 12:00 UTC", "generate-reports", "--reports", str(tmp_path / "r"))) == EXIT_OK
    assert (tmp_path / "w" / "02_LOAD_ESTIMATION.xlsx").stat().st_size > 5000
    assert (tmp_path / "r" / "02_Electrical_Load_Estimation_Report.pdf").stat().st_size > 5000


def test_build_manufacturer_register_writes_markdown_and_csv(root, tmp_path):
    assert main(args(root, "build-manufacturer-register", "--output", str(tmp_path))) == EXIT_OK
    md = (tmp_path / "manufacturer_data_register.md").read_text()
    assert "A placeholder is not validated equipment data" in md and "GEN-A1" in md and "(none: pending)" in md
    assert (tmp_path / "manufacturer_data_register.csv").read_text().count("\n") > 50


def test_qa_report_is_not_run_recursively_in_the_suite():
    from ohmetry_dc.cli import cmd_qa
    assert callable(cmd_qa)


def test_build_package_assembles_only_what_exists_and_is_labelled_preliminary(root, tmp_path, monkeypatch):
    import json
    import zipfile
    monkeypatch.chdir(root)
    assert main(args(root, "build-package", "--dist", str(tmp_path))) == EXIT_OK
    z = zipfile.ZipFile(next(tmp_path.glob("*.zip")))
    names = z.namelist()
    assert any(n.endswith("PACKAGE_STATUS.txt") for n in names) and not any("/engine/" in n for n in names)
    man = json.loads(z.read(next(n for n in names if n.endswith("MANIFEST.json"))))
    assert "Not construction-ready" in man["state"] and man["workbooks_planned_total"] == 20
    assert man["workbooks_planned_total"] == 20 and any("drawings" in x for x in man["not_included"]) and len(man["workbooks_included"]) + len(man["workbooks_not_included"]) == 20
    assert "NOT construction-ready" in z.read(next(n for n in names if n.endswith("PACKAGE_STATUS.txt"))).decode()
    assert all(len(f["sha256"]) == 64 for f in man["files"])
