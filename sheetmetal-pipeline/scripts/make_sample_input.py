"""Generate input/parts_sample.xlsx -- a template/demo workbook for run_batch.py.

Six rows: three valid (varying material/gauge/size), and three deliberately
bad ones demonstrating the distinct failure modes run_batch.py has to
survive: a manufacturability-rule violation (BR-004: bend radius too tight
for the gauge), a bad cell value (BR-005: non-numeric thickness), and an
unknown material the K-factor table has no data for (BR-006).

Run with plain python3 (or freecadcmd) -- only needs openpyxl:
    /opt/miniconda3/envs/freecad/bin/python scripts/make_sample_input.py
"""

import os

import openpyxl

PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(PIPELINE_ROOT, "input", "parts_sample.xlsx")

HEADERS = [
    "JobID", "Material", "PlateLength", "PlateWidth", "Thickness", "FlangeLength",
    "BendAngle", "BendRadius", "HoleDia", "HoleX", "HoleY",
]

ROWS = [
    # Baseline, matches Stage 2/3's known-good part. mild_steel at 2mm looks
    # up to K=0.38 -- same value Stages 2-4 had hardcoded, so this is a
    # direct continuity check on the lookup table.
    ["BR-001", "mild_steel", 100.0, 60.0, 2.0, 30.0, 90.0, 2.0, 6.0, 30.0, 15.0],
    # Smaller, thinner-gauge aluminum variant -- still clears both manufacturability checks.
    ["BR-002", "aluminum_5052", 80.0, 50.0, 1.0, 15.0, 90.0, 1.2, 5.0, 25.0, 12.0],
    # Larger, thicker-gauge stainless variant -- bend radius == thickness (right at the minimum ratio).
    ["BR-003", "stainless_304", 150.0, 80.0, 4.0, 40.0, 90.0, 4.0, 8.0, 50.0, 25.0],
    # Deliberately bad: bend_radius (1mm) is far below thickness (5mm) --
    # caught by validate_params's manufacturability check, not the geometry engine.
    ["BR-004", "mild_steel", 120.0, 70.0, 5.0, 35.0, 90.0, 1.0, 6.0, 35.0, 17.0],
    # Deliberately bad: non-numeric thickness -- caught by run_batch's require_float.
    ["BR-005", "mild_steel", 100.0, 60.0, "N/A", 30.0, 90.0, 2.0, 6.0, 30.0, 15.0],
    # Deliberately bad: material with no entry in the K-factor table --
    # caught by kfactor_lookup.lookup_k_factor's KeyError.
    ["BR-006", "unobtainium", 100.0, 60.0, 2.0, 30.0, 90.0, 2.0, 6.0, 30.0, 15.0],
]


def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Parts"
    ws.append(HEADERS)
    for row in ROWS:
        ws.append(row)
    wb.save(OUT_PATH)
    print(f"Wrote {OUT_PATH} ({len(ROWS)} rows)")


main()
