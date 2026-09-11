"""Stage 2: one hardcoded part, full pipeline.

Target part family (placeholder, pending real job specs): a U-channel
bracket -- flat base plate with an edge flange bent up from each of the two
short ends (90 deg), plus a 4-hole bolt pattern in the base. Referred to as
"L-bracket with two edge flanges" in the original brief; built here as a
symmetric U-channel since a literal L-bracket only has one bend and the
brief calls for two.

Pipeline: sketch -> base wall -> edge flange x2 -> hole cuts
          -> STEP export (folded) -> unfold -> DXF export (flat pattern)

All dimensions are hardcoded constants below (Stage 3 turns these into
function arguments). Run with:

    /opt/miniconda3/envs/freecad/bin/freecadcmd scripts/build_bracket.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_sheetmetal_to_path, output_dir

add_sheetmetal_to_path()

import FreeCAD
import Part

import SheetMetalBaseCmd
import SheetMetalCmd
import SheetMetalUnfoldCmd
import importDXF

# ---------------------------------------------------------------------------
# Hardcoded part dimensions (placeholder values -- no real job specs yet).
# ---------------------------------------------------------------------------
PLATE_LENGTH = 100.0  # X, base plate length (the direction the flanges bend up from)
PLATE_WIDTH = 60.0    # Y, base plate width (also the flange width)
THICKNESS = 2.0       # sheet gauge
FLANGE_LENGTH = 30.0  # leg length of each edge flange, measured from the bend tangent line
BEND_ANGLE = 90.0     # degrees
BEND_RADIUS = 2.0     # inner bend radius
K_FACTOR = 0.38       # ANSI K-factor -- matches the SheetMetal workbench's own worked example
HOLE_DIA = 6.0        # bolt hole diameter (M6 clearance)
HOLE_X = 30.0         # hole X offset from plate center
HOLE_Y = 15.0         # hole Y offset from plate center


def find_edge(shape, predicate, description):
    """Return the FreeCAD sub-element name ("EdgeN") of the one edge in
    `shape` matching `predicate(edge) -> bool`. Fails loudly (instead of
    silently picking a wrong edge) if the match isn't exactly one."""
    matches = [i for i, e in enumerate(shape.Edges, start=1) if predicate(e)]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one edge for '{description}', found {len(matches)}"
        )
    return f"Edge{matches[0]}"


def find_face(shape, predicate, description):
    """Same as find_edge, but for faces, picking the largest-area match
    when the predicate matches more than one (e.g. several small planar
    faces at the same Z after holes are cut)."""
    matches = [(i, f) for i, f in enumerate(shape.Faces, start=1) if predicate(f)]
    if not matches:
        raise RuntimeError(f"Expected at least one face for '{description}', found 0")
    idx, _ = max(matches, key=lambda pair: pair[1].Area)
    return f"Face{idx}"


def build_plate_sketch(doc):
    sketch = doc.addObject("Sketcher::SketchObject", "PlateSketch")
    hl, hw = PLATE_LENGTH / 2.0, PLATE_WIDTH / 2.0
    p1 = FreeCAD.Vector(-hl, -hw, 0)
    p2 = FreeCAD.Vector(hl, -hw, 0)
    p3 = FreeCAD.Vector(hl, hw, 0)
    p4 = FreeCAD.Vector(-hl, hw, 0)
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


def build_base_wall(doc, sketch):
    base = doc.addObject("Part::FeaturePython", "BaseWall")
    SheetMetalBaseCmd.SMBaseBend(base, sketch)
    base.Thickness = THICKNESS
    doc.recompute()
    return base


def add_edge_flange(doc, name, base_obj, edge_name):
    flange = doc.addObject("Part::FeaturePython", name)
    SheetMetalCmd.SMBendWall(flange, base_obj, [edge_name])
    flange.length = FLANGE_LENGTH
    flange.angle = BEND_ANGLE
    flange.radius = BEND_RADIUS
    flange.kfactor = K_FACTOR
    doc.recompute()
    if flange.Shape is None or flange.Shape.isNull():
        raise RuntimeError(f"{name}: SheetMetal produced an empty/null shape")
    return flange


def add_hole_pattern(doc, base_obj):
    cylinders = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            center = FreeCAD.Vector(sx * HOLE_X, sy * HOLE_Y, -1.0)
            cylinders.append(Part.makeCylinder(HOLE_DIA / 2.0, THICKNESS + 2.0, center, FreeCAD.Vector(0, 0, 1)))
    hole_tool = doc.addObject("Part::Feature", "HoleTool")
    hole_tool.Shape = cylinders[0].multiFuse(cylinders[1:])

    cut = doc.addObject("Part::Cut", "HolePattern")
    cut.Base = base_obj
    cut.Tool = hole_tool
    doc.recompute()
    if cut.Shape is None or cut.Shape.isNull():
        raise RuntimeError("Hole cut produced an empty/null shape")
    return cut


def unfold_part(doc, folded_obj):
    face_name = find_face(
        folded_obj.Shape,
        lambda f: f.Surface.TypeId == "Part::GeomPlane" and abs(f.CenterOfMass.z) < 1e-3,
        "base plate bottom face (unfold reference)",
    )
    unfold = doc.addObject("Part::FeaturePython", "Unfold")
    SheetMetalUnfoldCmd.SMUnfold(unfold, folded_obj, [face_name])
    unfold.KFactor = K_FACTOR
    unfold.KFactorStandard = "ansi"
    unfold.GenerateSketch = True
    # KNOWN HEADLESS BUG (FreeCAD SheetMetal, checked at v0.7.x / networkx-based
    # unfolder): when GenerateSketch=True and ShowBendAngles=True (its default),
    # SheetMetalNewUnfolder.getUnfoldSketches() unconditionally does
    # `bend_labels_doc_obj.ViewObject.PointSize = 0` to size the bend-angle-label
    # points. ViewObject is always None under freecadcmd (no GUI), so this raises
    # AttributeError and the unfold silently fails (empty UnfoldSketches / caught
    # exception logged as a warning by FreeCAD, not a Python traceback we can
    # catch). Disabling ShowBendAngles skips that code path entirely and does
    # NOT affect the flat-pattern geometry itself (outline, bend lines, holes) --
    # it only suppresses in-sketch bend-angle text annotations.
    unfold.ShowBendAngles = False
    doc.recompute()

    if not unfold.UnfoldSketches:
        raise RuntimeError("Unfold produced no sketch -- see headless GenerateSketch note above")
    sketches = [doc.getObject(n) for n in unfold.UnfoldSketches]
    return unfold, sketches


def expected_flat_length():
    """Cross-check formula, independent of FreeCAD's own unfolder, taken
    directly from the SheetMetal workbench's own documented worked example
    (tools/calc-unfold.py in shaise/FreeCAD_SheetMetal):

        t = K * thickness
        BA = 2*pi*(r + t) * (angle / 360)   # bend allowance (arc length)

    With LengthSpec="Leg" (this script's default -- the "length" property is
    the straight flat leg beyond the bend tangent line), the total flattened
    length is the base length plus, for each bend, its bend allowance arc
    plus its leg length -- confirmed against FreeCAD's own unfold output to
    6 decimal places during development of this script.
    """
    t = K_FACTOR * THICKNESS
    ba_per_bend = 2 * math.pi * (BEND_RADIUS + t) * (BEND_ANGLE / 360.0)
    return PLATE_LENGTH + 2 * (FLANGE_LENGTH + ba_per_bend)


def main():
    doc = FreeCAD.newDocument("Bracket")

    sketch = build_plate_sketch(doc)
    base = build_base_wall(doc, sketch)
    print(f"Base wall OK: {base.Shape.BoundBox}")

    edge1 = find_edge(
        base.Shape,
        lambda e: len(e.Vertexes) == 2
        and all(abs(v.Point.x - PLATE_LENGTH / 2.0) < 1e-4 for v in e.Vertexes)
        and all(abs(v.Point.z - THICKNESS) < 1e-4 for v in e.Vertexes),
        "base plate +X short edge (top face)",
    )
    flange1 = add_edge_flange(doc, "Flange1", base, edge1)
    print(f"Flange1 OK: {flange1.Shape.BoundBox}")

    edge2 = find_edge(
        flange1.Shape,
        lambda e: len(e.Vertexes) == 2
        and all(abs(v.Point.x + PLATE_LENGTH / 2.0) < 1e-4 for v in e.Vertexes)
        and all(abs(v.Point.z - THICKNESS) < 1e-4 for v in e.Vertexes),
        "base plate -X short edge (top face, carried through Flange1)",
    )
    flange2 = add_edge_flange(doc, "Flange2", flange1, edge2)
    print(f"Flange2 OK: {flange2.Shape.BoundBox}")

    folded = add_hole_pattern(doc, flange2)
    print(f"Hole pattern OK: {folded.Shape.BoundBox}, volume={folded.Shape.Volume:.2f} mm^3")

    out_dir = output_dir()
    step_path = os.path.join(out_dir, "bracket_folded.step")
    Part.export([folded], step_path)
    if not os.path.isfile(step_path) or os.path.getsize(step_path) == 0:
        raise RuntimeError(f"STEP export failed: {step_path}")
    print(f"STEP export OK: {step_path} ({os.path.getsize(step_path)} bytes)")

    unfold, sketches = unfold_part(doc, folded)
    flat_bbox = unfold.Shape.BoundBox
    print(
        f"Unfold OK. Flat bbox: {flat_bbox.XLength:.3f} x {flat_bbox.YLength:.3f} mm "
        f"(width should equal plate width {PLATE_WIDTH} mm unchanged, since bends run along Y)"
    )

    if abs(flat_bbox.YLength - PLATE_WIDTH) > 0.01:
        raise RuntimeError(
            f"Sanity check failed: flat pattern width {flat_bbox.YLength:.3f} mm "
            f"should be unchanged from plate width {PLATE_WIDTH} mm (bends run along Y, "
            f"not across it)"
        )

    expected_len = expected_flat_length()
    tolerance = 0.5  # mm -- generous given this cross-checks a different code path
    diff = abs(flat_bbox.XLength - expected_len)
    print(
        f"Flat length sanity check: measured={flat_bbox.XLength:.3f} mm, "
        f"expected(base + 2*(leg + bend_allowance))={expected_len:.3f} mm, "
        f"diff={diff:.3f} mm"
    )
    if diff > tolerance:
        raise RuntimeError(
            f"Sanity check failed: flat length off by {diff:.3f} mm "
            f"(tolerance {tolerance} mm) -- flat pattern is not dimensionally sane"
        )
    print("Flat length sanity check passed.")

    dxf_path = os.path.join(out_dir, "bracket_flat.dxf")
    importDXF.export(sketches, dxf_path)
    if not os.path.isfile(dxf_path) or os.path.getsize(dxf_path) == 0:
        raise RuntimeError(f"DXF export failed: {dxf_path}")
    print(f"DXF export OK: {dxf_path} ({os.path.getsize(dxf_path)} bytes)")

    FreeCAD.closeDocument(doc.Name)
    print("STAGE 2 BUILD PASSED")


main()
