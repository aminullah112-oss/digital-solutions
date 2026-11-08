"""The values reviewed at revision A5 must still reproduce at A6 (corrective actions 5 to 12 change labels, drawings and documents, not numbers)."""
import re

from ohmetry_dc.config import load_config
from ohmetry_dc.documents import corrective


def _cfg(root):
    return load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")


def test_every_reviewed_a5_number_reproduces(root):
    rows = corrective.key_number_rows(_cfg(root))
    assert len(rows) == 13 and [r for r in rows if r[3] != "MATCH"] == []
    st = {r[0]: r[4] for r in rows}
    assert st["Transformer 3,150 kVA, path out (% of derated kVA)"] == "WARNING" and st["Transformer 4,000 kVA, same load (% kVA, arithmetic only)"] == "PASS" and st["UPS, path out (% kW)"] == "PASS" and st["UPS, path out (% kVA)"] == "WARNING"
    assert st["Generators, path out and one unit out (% of 4,000 kVA)"] == "PASS" and st["Generators, path out and one unit out (% of 3,200 kW)"] == "WARNING"


def test_reviewed_values_are_the_ones_given_for_a5(root):
    want = {"Facility total (kW)": 2697.3, "Facility total (kVA)": 2865.6, "PUE (design point)": 1.349, "Transformer 3,150 kVA, path out (% of derated kVA)": 90.97, "UPS, path out (% kW)": 80.0, "UPS, path out (% kVA)": 84.2,
            "Generators, path out and one unit out (% of 4,000 kVA)": 71.36, "Generators, path out and one unit out (% of 3,200 kW)": 83.98, "LV busduct required current (A)": 4136.0, "Transformer full-load LV current (A)": 4547.0}
    got = {label: reviewed for label, reviewed, _ in corrective.REVIEWED_A5}
    assert all(got[k] == v for k, v in want.items())


def test_the_check_summary_has_no_fail_and_no_check_was_upgraded_since_a5(root):
    now = corrective.summary_now(_cfg(root))
    assert now["FAIL"] == 0 and now["WARNING"] == corrective.A5_SUMMARY["WARNING"] + 1 and now["PASS"] == corrective.A5_SUMMARY["PASS"]
    assert now["NOT VERIFIED"] >= corrective.A5_SUMMARY["NOT VERIFIED"]


def test_the_report_says_items_1_to_4_are_not_covered_and_that_implemented_is_not_verified(root, tmp_path):
    md = corrective.markdown(_cfg(root), root, "stamp")
    assert "Item 1. Generator N+1" in md and "Item 4. Load model review and sensitivity" in md and "NOT covered" not in md and "Implemented is not verified" in md and "ALL MATCH" in md and "NOT REVIEWED" in md
    for line in md.splitlines():                                   # every use of "approved" is a negation or a status label
        if "approved" in line.lower():
            assert re.search(r"\b(not|no|nothing|never)\b", line.lower()) or "Independent reviewer | not assigned" in line, line
