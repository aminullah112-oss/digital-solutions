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


# ---- revision A6, item 9: the reviewer name is an attestation, recorded with organisation, date, evidence and scope
def _supplied_copy(root, tmp_path):
    """A temporary copy of config/ with one manufacturer value imported, so there is a supplied value to attest."""
    import shutil
    cfgdir = tmp_path / "config"
    shutil.copytree(root / "config", cfgdir)
    csvf = tmp_path / "in.csv"
    csvf.write_text("parameter,value,unit,source,datasheet_revision,datasheet_reference\ngenerators.max_step_load_pct,60,%,Example Gensets GX-2000 data sheet,B,Table 4\n")
    base = ["--config", str(cfgdir / "project_config.yaml"), "--loads", str(cfgdir / "load_schedule.yaml")]
    assert main([*base, "import-manufacturer-data", "--file", str(csvf), "--register", str(cfgdir / "manufacturer_data_register.yaml"), "--output", str(tmp_path / "out")]) == EXIT_OK
    return cfgdir, base


def _verify(base, cfgdir, **kw):
    a = {"by": "A. Reviewer", "org": "Example Engineering Ltd", "evidence": "GX-2000 data sheet rev B, table 4", "scope": "value and unit against the data sheet; not the design", "date": "2026-11-01"}
    a.update(kw)
    cmd = ["record-verification", "--parameter", "generators.max_step_load_pct", "--register", str(cfgdir / "manufacturer_data_register.yaml")]
    for k, v in a.items():
        if v is not None:
            cmd += [f"--{k}", v]
    return main([*base, *cmd])


def test_verification_needs_name_organisation_date_evidence_and_scope(root, tmp_path, capsys):
    cfgdir, base = _supplied_copy(root, tmp_path)
    with pytest.raises(SystemExit):                                  # organisation, evidence and scope are required arguments
        main([*base, "record-verification", "--parameter", "generators.max_step_load_pct", "--by", "A. Reviewer"])
    capsys.readouterr()
    assert _verify(base, cfgdir, date="not-a-date") == EXIT_FAIL and "not an ISO date" in capsys.readouterr().out
    assert _verify(base, cfgdir, date="2999-01-01") == EXIT_FAIL and "in the future" in capsys.readouterr().out
    assert _verify(base, cfgdir, org="  ") == EXIT_FAIL and "organisation" in capsys.readouterr().out
    assert yaml.safe_load((cfgdir / "verification_log.yaml").read_text())["records"] == []           # nothing was recorded by a rejected attempt


def test_a_complete_attestation_is_recorded_in_the_register_and_an_append_only_log_and_says_it_is_not_authenticated(root, tmp_path, capsys):
    cfgdir, base = _supplied_copy(root, tmp_path)
    assert _verify(base, cfgdir) == EXIT_OK
    out = capsys.readouterr().out
    assert "self-declared attestation" in out and "not an authenticated identity" in out
    e = next(x for x in yaml.safe_load((cfgdir / "manufacturer_data_register.yaml").read_text())["entries"] if x["parameter"] == "generators.max_step_load_pct")
    assert (e["verified_by"], e["verified_org"], e["verification_date"], e["evidence_ref"]) == ("A. Reviewer", "Example Engineering Ltd", "2026-11-01", "GX-2000 data sheet rev B, table 4") and "not the design" in e["verification_scope"]
    assert _verify(base, cfgdir, by="B. Second Reviewer", date="2026-11-02") == EXIT_OK
    log = yaml.safe_load((cfgdir / "verification_log.yaml").read_text())["records"]
    assert [r["verified_by"] for r in log] == ["A. Reviewer", "B. Second Reviewer"] and all("recorded" in r for r in log)    # history is kept, not overwritten


def test_verifying_a_placeholder_is_refused_even_with_a_complete_record(root, tmp_path, capsys):
    import shutil
    cfgdir = tmp_path / "config"
    shutil.copytree(root / "config", cfgdir)
    base = ["--config", str(cfgdir / "project_config.yaml"), "--loads", str(cfgdir / "load_schedule.yaml")]
    code = _verify(base, cfgdir)
    assert code == EXIT_FAIL and "placeholder" in capsys.readouterr().out


# ---- revision A6, item 12: the release gate
def test_regenerate_all_runs_every_step_in_order_documents_twice_around_qa_and_stops_on_failure(monkeypatch, capsys):
    import ohmetry_dc.cli as cli
    calls = []
    real = cli.main

    def fake(argv):
        if argv[:1] == ["--config"] and argv[4:5] != ["regenerate-all"]:
            i = argv.index("--loads") + 2
            i += 2 if argv[i:i + 1] == ["--generated"] else 0
            calls.append(argv[i:])
            return 0 if argv[i] != "generate-reports" or not FAIL["on"] else 1
        return real(argv)
    FAIL = {"on": False}
    monkeypatch.setattr(cli, "main", fake)
    assert real(["--generated", "2026-11-08 00:00 UTC", "regenerate-all", "--dist", "d"]) == 0
    names = [c[0] for c in calls]
    assert names == ["build-assumptions-register", "validate-config", "run-calculations", "sizing-summary", "build-manufacturer-register", "generate-workbooks", "lint-workbooks", "generate-reports", "generate-drawings",
                     "generate-training", "generate-documents", "qa-report", "generate-documents", "build-review-package", "build-package"]
    assert calls[-2] == ["build-review-package", "--dist", "d"]
    calls.clear()
    assert real(["regenerate-all", "--skip-qa"]) == 0 and "qa-report" not in [c[0] for c in calls]
    calls.clear()
    FAIL["on"] = True
    assert real(["regenerate-all", "--skip-qa"]) == 1 and [c[0] for c in calls][-1] == "generate-reports" and "regenerate-all stopped" in capsys.readouterr().out
