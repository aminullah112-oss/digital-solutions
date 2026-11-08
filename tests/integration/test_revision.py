import shutil

import pytest
import yaml

from ohmetry_dc.cli import EXIT_OK, main
from ohmetry_dc.config import load_config
from ohmetry_dc.reporting import append_revision_log, compare, compare_markdown

from conftest import set_value


def cfg(path, root):
    return load_config(path, root / "config" / "load_schedule.yaml")


def test_no_change_means_no_equipment_sizing_change(root):
    base = cfg(root / "config" / "project_config.yaml", root)
    d = compare(base, base)
    assert d["parameters"] == {} and d["sizing"] == {} and d["equipment_sizing_changed"] is False


def test_new_demand_figures_are_traced_to_the_sizing_changes(root, write_config):
    old = cfg(root / "config" / "project_config.yaml", root)
    new = cfg(write_config(lambda d: set_value(d, "demand_data", "it_critical_load_kw", 2600)), root)
    d = compare(old, new)
    assert d["equipment_sizing_changed"] and "demand_data.it_critical_load_kw" in d["parameters"]
    assert d["parameters"]["demand_data.it_critical_load_kw"] == (2000, 2600)
    assert d["load"]["it_kw"] == (2000.0, 2600.0)
    assert set(d["sizing"]) >= {"transformer", "ups_kw", "ups_kva"}
    assert d["sizing"]["ups_kw"]["status"] == ("PASS", "FAIL")          # 2,600 kW on a 2,500 kW UPS is 104 %, above the 100 % maximum
    md = compare_markdown(d, "A1", "A2")
    assert "Equipment sizing changes" in md and "demand_data.it_critical_load_kw" in md


def test_revision_log_entry_is_appended_and_marked_not_reviewed(root, write_config, tmp_path):
    old = cfg(root / "config" / "project_config.yaml", root)
    new = cfg(write_config(lambda d: set_value(d, "demand_data", "it_critical_load_kw", 2600)), root)
    log = tmp_path / "revisions.yaml"
    shutil.copy(root / "config" / "design_basis_revisions.yaml", log)
    before = len(yaml.safe_load(log.read_text())["revisions"])
    append_revision_log(log, "A2", "New demand figures", compare(old, new), date="2026-11-20")
    data = yaml.safe_load(log.read_text())["revisions"]
    assert len(data) == before + 1 and data[-1]["revision"] == "A2" and data[-1]["review_status"] == "NOT REVIEWED" and data[-1]["reviewer"] is None
    assert "ups_kw" in data[-1]["equipment_sizing_changes"]


def test_cli_revision_impact_records_the_change(root, write_config, tmp_path, capsys):
    log = tmp_path / "revisions.yaml"
    shutil.copy(root / "config" / "design_basis_revisions.yaml", log)
    new_path = write_config(lambda d: set_value(d, "demand_data", "it_critical_load_kw", 2600))
    code = main(["--config", str(new_path), "--loads", str(root / "config" / "load_schedule.yaml"), "revision-impact", "--previous-config", str(root / "config" / "project_config.yaml"),
                 "--record", "Test change", "--log", str(log)])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "Equipment sizing changes" in out and "Recorded in" in out
    assert yaml.safe_load(log.read_text())["revisions"][-1]["description"] == "Test change"


def test_shipped_revision_log_starts_with_unreviewed_entries(root):
    revs = yaml.safe_load((root / "config" / "design_basis_revisions.yaml").read_text())["revisions"]
    assert [r["revision"] for r in revs][:2] == ["A0", "A1"] and all(r["review_status"] == "NOT REVIEWED" for r in revs)


def test_sizing_summary_states_it_is_preliminary_and_lists_outstanding_data(root, tmp_path):
    assert main(["--config", str(root / "config" / "project_config.yaml"), "--loads", str(root / "config" / "load_schedule.yaml"), "sizing-summary", "--output", str(tmp_path)]) == EXIT_OK
    text = (tmp_path / "stage3_sizing_summary.md").read_text()
    for must in ("PRELIMINARY", "Not construction-ready", "Outstanding manufacturer data", "generators.max_step_load_pct", "not an IEC acceptance limit", "TX-PATH-OUT", "GEN-UNIT-OUT",
                 "UPS: kVA", "Battery (interface only)", "is not used to justify continuous loading"):
        assert must in text, must
    assert "construction-ready." not in text.replace("Not construction-ready", "")
