"""Generate input/parts_sample.xlsx -- a template/demo workbook for run_batch.py.

Five rows: three valid (varying gauge/size), and two deliberately bad ones
demonstrating the two distinct failure modes run_batch.py has to survive:
a manufacturability-rule violation (BR-004: bend radius too tight for the
gauge) and a bad cell value (BR-005: non-numeric thickness).

Run with plain python3 (or freecadcmd) -- only needs openpyxl:
    /opt/miniconda3/envs/freecad/bin/python scripts/make_sample_input.py
"""

import os

import openpyxl

PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(PIPELINE_ROOT, "input", "parts_sample.xlsx")

HEADERS = [
    "JobID", "PlateLength", "PlateWidth", "Thickness", "FlangeLength",
    "BendAngle", "BendRadius", "KFactor", "HoleDia", "HoleX", "HoleY",
]

ROWS = [
    # Baseline, matches Stage 2/3's known-good part.
    ["BR-001", 100.0, 60.0, 2.0, 30.0, 90.0, 2.0, 0.38, 6.0, 30.0, 15.0],
    # Smaller, thinner-gauge variant -- still clears both manufacturability checks.
    ["BR-002", 80.0, 50.0, 1.0, 15.0, 90.0, 1.2, 0.38, 5.0, 25.0, 12.0],
    # Larger, thicker-gauge variant -- bend radius == thickness (right at the minimum ratio).
    ["BR-003", 150.0, 80.0, 4.0, 40.0, 90.0, 4.0, 0.40, 8.0, 50.0, 25.0],
    # Deliberately bad: bend_radius (1mm) is far below thickness (5mm) --
    # caught by validate_params's manufacturability check, not the geometry engine.
    ["BR-004", 120.0, 70.0, 5.0, 35.0, 90.0, 1.0, 0.38, 6.0, 35.0, 17.0],
    # Deliberately bad: non-numeric thickness -- caught by run_batch's require_float.
    ["BR-005", 100.0, 60.0, "N/A", 30.0, 90.0, 2.0, 0.38, 6.0, 30.0, 15.0],
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
