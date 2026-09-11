"""Stage 2 entry point (kept as-is for continuity/bisectability).

Builds the same baseline U-channel bracket as before, now via the
parametrized model in bracket_model.py (Stage 3). Same dimensions, same
sanity checks, same outputs -- this script's job is just to prove the
Stage 3 refactor didn't change Stage 2's result.

Run with:
    /opt/miniconda3/envs/freecad/bin/freecadcmd scripts/build_bracket.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_sheetmetal_to_path, output_dir

add_sheetmetal_to_path()

from bracket_model import build_bracket

# Stage 2's baseline dimensions.
PLATE_LENGTH = 100.0
PLATE_WIDTH = 60.0
THICKNESS = 2.0
FLANGE_LENGTH = 30.0
BEND_ANGLE = 90.0
BEND_RADIUS = 2.0
K_FACTOR = 0.38
HOLE_DIA = 6.0
HOLE_X = 30.0
HOLE_Y = 15.0


def main():
    result = build_bracket(
        plate_length=PLATE_LENGTH,
        plate_width=PLATE_WIDTH,
        thickness=THICKNESS,
        flange_length=FLANGE_LENGTH,
        bend_angle=BEND_ANGLE,
        bend_radius=BEND_RADIUS,
        k_factor=K_FACTOR,
        hole_dia=HOLE_DIA,
        hole_x=HOLE_X,
        hole_y=HOLE_Y,
        doc_name="Bracket",
        export_dir=output_dir(),
        export_prefix="bracket",
    )

    if not result["ok"]:
        raise RuntimeError(f"Build failed: {result['error']}")

    m = result["metrics"]
    print(f"Folded bbox: {m['folded_bbox']}, volume={m['folded_volume']} mm^3")
    print(f"STEP export OK: {m['step_path']}")
    print(f"Flat pattern: {m['flat_length']} x {m['flat_width']} mm")
    print(
        f"Flat length sanity check: measured={m['flat_length']}, "
        f"expected={m['expected_flat_length']}, diff={m['flat_length_diff']} mm"
    )
    print(f"Flat width sanity check: diff from plate width={m['flat_width_diff']} mm")
    if m["flat_length_diff"] > 0.5:
        raise RuntimeError(f"Flat length off by {m['flat_length_diff']} mm -- not dimensionally sane")
    if m["flat_width_diff"] > 0.01:
        raise RuntimeError(f"Flat width off by {m['flat_width_diff']} mm -- not dimensionally sane")
    print(f"DXF export OK: {m['dxf_path']}")
    print("STAGE 2 BUILD PASSED")


main()
