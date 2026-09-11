"""Stage 1 smoke test.

Confirms the whole headless toolchain is wired correctly, before any real
part geometry is attempted:

  freecadcmd -> FreeCAD core -> SheetMetal workbench (SMBaseBend) -> STEP export

Builds a trivial flat sheet-metal plate (a closed rectangular sketch turned
into a single sheet-metal wall) and exports it as STEP. No flanges, holes,
or unfolding yet -- that starts in Stage 2.

Run with:
    /opt/miniconda3/envs/freecad/bin/freecadcmd scripts/smoke_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_sheetmetal_to_path, output_dir

add_sheetmetal_to_path()

import FreeCAD
import Part

import SheetMetalBaseCmd

# Trivial placeholder geometry: a 40mm x 40mm square, 2mm thick.
PLATE_SIZE = 40.0
THICKNESS = 2.0


def build_plate_sketch(doc):
    sketch = doc.addObject("Sketcher::SketchObject", "PlateSketch")
    half = PLATE_SIZE / 2.0
    p1 = FreeCAD.Vector(-half, -half, 0)
    p2 = FreeCAD.Vector(half, -half, 0)
    p3 = FreeCAD.Vector(half, half, 0)
    p4 = FreeCAD.Vector(-half, half, 0)
    sketch.addGeometry(
        [
            Part.LineSegment(p1, p2),
            Part.LineSegment(p2, p3),
            Part.LineSegment(p3, p4),
            Part.LineSegment(p4, p1),
        ],
        False,
    )
    doc.recompute()
    return sketch


def main():
    doc = FreeCAD.newDocument("SmokeTest")
    sketch = build_plate_sketch(doc)

    base = doc.addObject("Part::FeaturePython", "BaseWall")
    SheetMetalBaseCmd.SMBaseBend(base, sketch)
    base.Thickness = THICKNESS
    doc.recompute()

    if base.Shape is None or base.Shape.isNull():
        raise RuntimeError("SheetMetal base wall produced an empty/null shape")

    bbox = base.Shape.BoundBox
    print(
        f"Base wall shape OK. BoundBox: "
        f"{bbox.XLength:.2f} x {bbox.YLength:.2f} x {bbox.ZLength:.2f} mm, "
        f"volume={base.Shape.Volume:.2f} mm^3"
    )

    expected_footprint = PLATE_SIZE * PLATE_SIZE
    expected_volume = expected_footprint * THICKNESS
    tolerance = 0.05  # 5%
    if abs(base.Shape.Volume - expected_volume) > expected_volume * tolerance:
        raise RuntimeError(
            f"Sanity check failed: volume {base.Shape.Volume:.2f} mm^3 is not "
            f"within {tolerance:.0%} of expected {expected_volume:.2f} mm^3"
        )
    print(f"Volume sanity check passed (expected ~{expected_volume:.2f} mm^3).")

    out_dir = output_dir()
    step_path = os.path.join(out_dir, "smoke_test.step")
    Part.export([base], step_path)

    if not os.path.isfile(step_path) or os.path.getsize(step_path) == 0:
        raise RuntimeError(f"STEP export failed or produced an empty file: {step_path}")
    print(f"STEP export OK: {step_path} ({os.path.getsize(step_path)} bytes)")

    FreeCAD.closeDocument(doc.Name)
    print("SMOKE TEST PASSED")


# NOTE: freecadcmd sets __name__ to the script's basename (e.g. "smoke_test"),
# not "__main__", when the script is passed as a command-line file argument.
# `if __name__ == "__main__":` never fires under freecadcmd -- call directly.
main()
