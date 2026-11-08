import hashlib
import subprocess

import pytest

from ohmetry_dc.calculations import estimate_loads
from ohmetry_dc.config import load_config
from ohmetry_dc.reporting import build_load_report
from ohmetry_dc.validation import run_all_checks

from conftest import STAMP, needs_pdftotext


def make(root, tmp_path, name="r.pdf", mutate_cfg=None):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml") if mutate_cfg is None else mutate_cfg
    est = estimate_loads(cfg)
    return cfg, est, build_load_report(cfg, est, run_all_checks(cfg), tmp_path / name, STAMP)


def text(path):
    out = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True).stdout
    return " ".join(out.split())          # a phrase can wrap across lines or pages; compare on whitespace-normalised text


@needs_pdftotext
def test_report_contains_the_required_sections(root, tmp_path):
    _, _, path = make(root, tmp_path)
    t = text(path)
    for heading in ("Executive summary", "Purpose and scope", "Design basis", "Input data and sources", "Assumptions", "Calculation methodology", "Results", "Design checks and status",
                    "Limitations", "Outstanding information", "Required engineering review", "Revision history"):
        assert heading in t, heading


@needs_pdftotext
def test_report_shows_the_project_values_status_and_limitations(root, tmp_path):
    cfg, est, path = make(root, tmp_path)
    t = text(path)
    assert cfg.project.code in t and f"{est.facility_kw:,.1f} kW" in t and f"{est.pue:.3f}" in t
    assert "NOT VERIFIED" in t and "PASS" in t
    assert "NOT FOR CONSTRUCTION" in t.upper() and "not an engineering approval" in t
    assert "design-point power ratio" in t.lower() or "design-point pue" in t.lower()
    assert "None" not in t and "nan" not in t.lower().split()


@needs_pdftotext
def test_report_does_not_imply_a_completed_specialist_study(root, tmp_path):
    t = text(make(root, tmp_path)[2]).lower()
    assert "does not size transformers" in t and "short-circuit" in t
    for claim in ("code-compliant." , "approved for"):
        assert claim not in t.replace("not code-compliant", "")


def test_report_is_reproducible(root, tmp_path):
    a = make(root, tmp_path, "a.pdf")[2].read_bytes()
    b = make(root, tmp_path, "b.pdf")[2].read_bytes()
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
