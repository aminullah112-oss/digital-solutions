import copy
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-11-05 12:00 UTC"

needs_soffice = pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is needed to recalculate workbooks")
needs_pdftotext = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext is needed to read the PDF")


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def raw_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "project_config.yaml").read_text())


@pytest.fixture
def write_config(tmp_path):
    """Write a modified copy of the project config and return its path."""
    def _write(mutate):
        data = copy.deepcopy(yaml.safe_load((ROOT / "config" / "project_config.yaml").read_text()))
        mutate(data)
        p = tmp_path / "project_config.yaml"
        p.write_text(yaml.safe_dump(data, sort_keys=False))
        for name in ("design_exceptions.yaml", "distribution.yaml", "manufacturer_data_register.yaml"):     # files the loader and checks find beside the project config
            shutil.copy(ROOT / "config" / name, tmp_path / name)
        return p
    return _write


@pytest.fixture
def write_loads(tmp_path):
    """Write a modified copy of the load schedule and return its path."""
    def _write(mutate):
        data = copy.deepcopy(yaml.safe_load((ROOT / "config" / "load_schedule.yaml").read_text()))
        mutate(data)
        p = tmp_path / "load_schedule.yaml"
        p.write_text(yaml.safe_dump(data, sort_keys=False))
        return p
    return _write


def set_value(data: dict, section: str, key: str, value):
    """Set a parameter's value, following a value_ref to the demand-data parameter that holds the number."""
    p = data["sections"][section][key]
    if "value_ref" in p:
        sec, k = p["value_ref"].split(".", 1)
        data["sections"][sec][k]["value"] = value
    else:
        p["value"] = value


def recalc(path: Path, outdir: Path) -> Path:
    """Recalculate a workbook with LibreOffice and return the recalculated copy."""
    outdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(outdir), str(path)], check=True, capture_output=True, timeout=180)
    return outdir / path.name


def reference_model(items, ups_eff_pct=96.0, dist_pct=1.0, design_pf=0.95, growth_pct=0.0):
    """An independent hand-written version of the load model, used only to check the package. items: (quantity, kW, pf, df, category)."""
    import math
    t = lambda pf: math.tan(math.acos(pf))
    kw = [q * r * df for q, r, pf, df, c in items]
    kvar = [q * r * df * t(pf) for q, r, pf, df, c in items]
    it = sum(k for k, (q, r, pf, df, c) in zip(kw, items) if c == "it_critical")
    ups = it * (100 / ups_eff_pct - 1)
    dist = dist_pct / 100 * (sum(kw) + ups)
    p = sum(kw) + ups + dist
    qv = sum(kvar) + (ups + dist) * t(design_pf)
    return {"it": it, "ups": ups, "dist": dist, "kw": p, "kvar": qv, "kva": math.hypot(p, qv), "pf": p / math.hypot(p, qv), "pue": p / it, "design_kw": p * (1 + growth_pct / 100)}


DEFAULT_ITEMS = [(1, 2000, 0.95, 1.00, "it_critical"), (4, 120, 0.90, 0.75, "m"), (20, 6, 0.95, 1.00, "m"), (6, 15, 0.85, 0.67, "m"), (1, 15, 0.90, 0.80, "l"), (1, 20, 0.90, 0.50, "l"), (1, 25, 0.90, 1.00, "a")]


# TEST INPUTS ONLY. The shipped configuration holds none of these (they are pending utility, manufacturer and site data). Tests supply them to exercise the
# calculations against independent hand calculations. They are not project data and not reference data.
SC_TEST_INPUTS = {("short_circuit", "utility_fault_level_mva"): 500, ("short_circuit", "utility_x_r_ratio"): 10, ("short_circuit", "transformer_x_r_ratio"): 8,
                  ("short_circuit", "generator_subtransient_reactance_pct"): 14, ("short_circuit", "generator_x_r_ratio"): 20, ("equipment", "transformer_impedance"): 6,
                  ("earthing", "soil_resistivity"): 100, ("earthing_study", "grid_area_m2"): 2500, ("earthing_study", "grid_conductor_length_m"): 1200, ("earthing_study", "grid_burial_depth_m"): 0.5}


def supply_sc(d: dict) -> None:
    for (sec, key), v in SC_TEST_INPUTS.items():
        set_value(d, sec, key, v)


ATTESTATION = "A. Reviewer; Example Engineering Ltd; 2026-11-01; Data sheet DS-1 rev A; value and unit against the data sheet (test)"


def attest(entry: dict, name: str = "A. Reviewer") -> dict:
    """Fill a register entry with a complete (test) verification record."""
    entry.update(verified_by=name, verified_org="Example Engineering Ltd", verification_date="2026-11-01", evidence_ref="Data sheet DS-1 rev A", verification_scope="value and unit against the data sheet (test)")
    return entry
