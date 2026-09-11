"""Parametrized U-channel bracket model (Stage 3).

Same geometry as Stage 2 (base plate, edge flange on each short end, 4-hole
bolt pattern, unfold to flat pattern), but every dimension that Stage 2
hardcoded is now a function argument. Used by both build_bracket.py (single
hardcoded-equivalent run, kept for continuity with Stage 2) and
test_matrix.py (Stage 3's edge-case sweep).

Every geometry-building step raises on failure (null shape, invalid shape,
or an exception from FreeCAD/OCCT itself) rather than silently continuing
with bad geometry -- callers are expected to catch and log, not to assume
success.
"""

import math
import os

import FreeCAD
import Part

import SheetMetalBaseCmd
import SheetMetalCmd
import SheetMetalUnfoldCmd
import importDXF


def find_edge(shape, predicate, description):
    matches = [i for i, e in enumerate(shape.Edges, start=1) if predicate(e)]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one edge for '{description}', found {len(matches)}"
        )
    return f"Edge{matches[0]}"


def find_face(shape, predicate, description):
    matches = [(i, f) for i, f in enumerate(shape.Faces, start=1) if predicate(f)]
    if not matches:
        raise RuntimeError(f"Expected at least one face for '{description}', found 0")
    idx, _ = max(matches, key=lambda pair: pair[1].Area)
    return f"Face{idx}"


def check_shape(obj, name):
    """Raise if obj.Shape is missing, null, or topologically invalid."""
    shape = obj.Shape
    if shape is None or shape.isNull():
        raise RuntimeError(f"{name}: empty/null shape")
    if not shape.isValid():
        raise RuntimeError(f"{name}: shape failed OCCT validity check (isValid() == False)")


def build_plate_sketch(doc, plate_length, plate_width):
    sketch = doc.addObject("Sketcher::SketchObject", "PlateSketch")
    hl, hw = plate_length / 2.0, plate_width / 2.0
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


def build_base_wall(doc, sketch, thickness):
    base = doc.addObject("Part::FeaturePython", "BaseWall")
    SheetMetalBaseCmd.SMBaseBend(base, sketch)
    base.Thickness = thickness
    doc.recompute()
    check_shape(base, "BaseWall")
    return base


def add_edge_flange(doc, name, base_obj, edge_name, flange_length, bend_angle, bend_radius, k_factor):
    flange = doc.addObject("Part::FeaturePython", name)
    SheetMetalCmd.SMBendWall(flange, base_obj, [edge_name])
    flange.length = flange_length
    flange.angle = bend_angle
    flange.radius = bend_radius
    flange.kfactor = k_factor
    doc.recompute()
    check_shape(flange, name)
    return flange


def add_hole_pattern(doc, base_obj, thickness, hole_dia, hole_x, hole_y):
    cylinders = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            center = FreeCAD.Vector(sx * hole_x, sy * hole_y, -1.0)
            cylinders.append(Part.makeCylinder(hole_dia / 2.0, thickness + 2.0, center, FreeCAD.Vector(0, 0, 1)))
    hole_tool = doc.addObject("Part::Feature", "HoleTool")
    hole_tool.Shape = cylinders[0].multiFuse(cylinders[1:])

    cut = doc.addObject("Part::Cut", "HolePattern")
    cut.Base = base_obj
    cut.Tool = hole_tool
    doc.recompute()
    check_shape(cut, "HolePattern")
    return cut


def unfold_part(doc, folded_obj, k_factor):
    face_name = find_face(
        folded_obj.Shape,
        lambda f: f.Surface.TypeId == "Part::GeomPlane" and abs(f.CenterOfMass.z) < 1e-3,
        "base plate bottom face (unfold reference)",
    )
    unfold = doc.addObject("Part::FeaturePython", "Unfold")
    SheetMetalUnfoldCmd.SMUnfold(unfold, folded_obj, [face_name])
    unfold.KFactor = k_factor
    unfold.KFactorStandard = "ansi"
    unfold.GenerateSketch = True
    # See README / build_bracket.py: headless-only crash in the SheetMetal
    # workbench's bend-angle-label code, worked around by disabling it.
    unfold.ShowBendAngles = False
    doc.recompute()
    check_shape(unfold, "Unfold")

    if not unfold.UnfoldSketches:
        raise RuntimeError("Unfold produced no sketch")
    sketches = [doc.getObject(n) for n in unfold.UnfoldSketches]
    return unfold, sketches


def expected_flat_length(plate_length, thickness, flange_length, bend_angle, bend_radius, k_factor):
    """Same cross-check formula as Stage 2 -- see build_bracket.py for the
    derivation and the validation against FreeCAD's own unfold output."""
    t = k_factor * thickness
    ba_per_bend = 2 * math.pi * (bend_radius + t) * (bend_angle / 360.0)
    return plate_length + 2 * (flange_length + ba_per_bend)


def build_bracket(
    plate_length,
    plate_width,
    thickness,
    flange_length,
    bend_angle,
    bend_radius,
    k_factor,
    hole_dia,
    hole_x,
    hole_y,
    doc_name="Bracket",
    export_dir=None,
    export_prefix="bracket",
):
    """Build the full parametrized bracket and unfold it.

    Returns a dict with:
      ok: bool
      metrics: dict of measured values (present even on partial failure,
                for whatever steps completed)
      error: str or None
    On success, if export_dir is given, also writes
    "{export_prefix}_folded.step" and "{export_prefix}_flat.dxf" there.

    Always closes its FreeCAD document before returning, success or failure.
    """
    metrics = {}
    doc = FreeCAD.newDocument(doc_name)
    try:
        sketch = build_plate_sketch(doc, plate_length, plate_width)
        base = build_base_wall(doc, sketch, thickness)

        edge1 = find_edge(
            base.Shape,
            lambda e: len(e.Vertexes) == 2
            and all(abs(v.Point.x - plate_length / 2.0) < 1e-4 for v in e.Vertexes)
            and all(abs(v.Point.z - thickness) < 1e-4 for v in e.Vertexes),
            "base plate +X short edge (top face)",
        )
        flange1 = add_edge_flange(doc, "Flange1", base, edge1, flange_length, bend_angle, bend_radius, k_factor)

        edge2 = find_edge(
            flange1.Shape,
            lambda e: len(e.Vertexes) == 2
            and all(abs(v.Point.x + plate_length / 2.0) < 1e-4 for v in e.Vertexes)
            and all(abs(v.Point.z - thickness) < 1e-4 for v in e.Vertexes),
            "base plate -X short edge (top face, carried through Flange1)",
        )
        flange2 = add_edge_flange(doc, "Flange2", flange1, edge2, flange_length, bend_angle, bend_radius, k_factor)

        folded = add_hole_pattern(doc, flange2, thickness, hole_dia, hole_x, hole_y)
        metrics["folded_bbox"] = tuple(round(v, 3) for v in (
            folded.Shape.BoundBox.XLength, folded.Shape.BoundBox.YLength, folded.Shape.BoundBox.ZLength
        ))
        metrics["folded_volume"] = round(folded.Shape.Volume, 3)

        if export_dir:
            step_path = os.path.join(export_dir, f"{export_prefix}_folded.step")
            Part.export([folded], step_path)
            metrics["step_path"] = step_path

        unfold, sketches = unfold_part(doc, folded, k_factor)
        flat_bbox = unfold.Shape.BoundBox
        metrics["flat_length"] = round(flat_bbox.XLength, 3)
        metrics["flat_width"] = round(flat_bbox.YLength, 3)

        expected_len = expected_flat_length(plate_length, thickness, flange_length, bend_angle, bend_radius, k_factor)
        metrics["expected_flat_length"] = round(expected_len, 3)
        metrics["flat_length_diff"] = round(abs(flat_bbox.XLength - expected_len), 3)
        metrics["flat_width_diff"] = round(abs(flat_bbox.YLength - plate_width), 3)

        if export_dir:
            dxf_path = os.path.join(export_dir, f"{export_prefix}_flat.dxf")
            importDXF.export(sketches, dxf_path)
            metrics["dxf_path"] = dxf_path

        return {"ok": True, "metrics": metrics, "error": None}

    except Exception as exc:  # noqa: BLE001 -- deliberately broad: log every failure mode, never crash the sweep
        return {"ok": False, "metrics": metrics, "error": f"{type(exc).__name__}: {exc}"}

    finally:
        FreeCAD.closeDocument(doc.Name)
