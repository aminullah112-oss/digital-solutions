# Excel → Sheet-Metal → DXF Pipeline

Generates 3D sheet-metal parts and flat-pattern DXFs from Excel input, using
FreeCAD's open-source SheetMetal workbench, run headless via `freecadcmd`.
No SolidWorks dependency in this phase.

Target part family (Stage 2+, placeholder pending real specs): an L-bracket
with two edge flanges and a bolt hole pattern, reasonable placeholder
dimensions until real job specs are supplied.

Built in stages; each stage is committed only after its confirmation test
passes, so the git history stays bisectable.

## Stage 1 — Environment (done)

**What's installed and how**

Ubuntu 24.04 ("noble") ships no `freecad` package at all — it's absent from
main/universe/backports/security in this release (confirmed by inspecting
the raw apt package indices, not just `apt-cache search` coming up empty).
snapd/flatpak/AppImage were also not viable in this container (no snapd
daemon, GitHub Releases assets blocked by this environment's network
policy). So FreeCAD comes from **conda-forge** instead:

- Miniconda installed to `/opt/miniconda3`
- Conda env `freecad` with **FreeCAD 1.0.0** (conda-forge) — chosen over the
  newer 1.1.x builds available on conda-forge for a longer track record with
  third-party workbenches
- [shaise/FreeCAD_SheetMetal](https://github.com/shaise/FreeCAD_SheetMetal)
  (actively maintained, explicit FreeCAD 0.21/1.x compatibility notes in its
  changelog) cloned into FreeCAD's user Mod directory
  (`~/.local/share/FreeCAD/Mod/SheetMetal`)

Reproduce with:

```bash
./setup_env.sh
```

This is idempotent — safe to re-run, skips steps already done. Override
`FREECAD_VERSION`, `CONDA_PREFIX_DIR`, or `SHEETMETAL_REPO` env vars if
needed.

**Verified**

- `freecadcmd --version` → `FreeCAD 1.0.0 Revision: 39109 (Git)`, runs fully
  headless (no X server / display needed)
- `import SheetMetalCmd` succeeds once the workbench directory is added to
  `sys.path` (see `scripts/common.py::add_sheetmetal_to_path` — FreeCAD's
  normal Mod-directory auto-loading only runs for the GUI via each
  workbench's `InitGui.py`; `freecadcmd` never loads GUI workbenches, so
  headless scripts add the path themselves)

**Gotcha worth flagging for every later stage:** `freecadcmd some_script.py`
sets that script's `__name__` to its own basename (e.g. `"smoke_test"`), not
`"__main__"`. A `if __name__ == "__main__": main()` guard silently never
fires — no error, no output, exit code 0. All scripts in this repo call
`main()` unconditionally instead.

**Smoke test**

`scripts/smoke_test.py` builds a trivial flat sheet-metal plate (40mm x
40mm, 2mm thick — a closed rectangular sketch run through
`SheetMetalBaseCmd.SMBaseBend`, no flanges/holes yet) and exports it as
STEP, to prove the full chain (`freecadcmd` → FreeCAD core → SheetMetal
workbench → STEP export) is wired correctly before touching real geometry.

Run it:

```bash
/opt/miniconda3/envs/freecad/bin/freecadcmd scripts/smoke_test.py
```

It checks the resulting shape's volume against the expected
`40 x 40 x 2 = 3200 mm^3` (5% tolerance) before exporting, and verifies the
STEP file is non-empty. Output goes to `output/smoke_test.step`
(gitignored — outputs are never committed, only the scripts that produce
them).

Confirmed passing:

```
Base wall shape OK. BoundBox: 40.00 x 40.00 x 2.00 mm, volume=3200.00 mm^3
Volume sanity check passed (expected ~3200.00 mm^3).
STEP export OK: output/smoke_test.step (6909 bytes)
SMOKE TEST PASSED
```

## Stage 2 — One hardcoded part (done)

Built the target part as a **U-channel bracket**: a 100×60mm base plate
(2mm gauge), a 90° edge flange bent up from each of the two short ends
(30mm leg each), a 4-hole M6 bolt pattern in the base, folded to STEP and
unfolded to a flat-pattern DXF. (Called an "L-bracket with two edge
flanges" in the original brief — built as a symmetric U-channel here since
a literal L has only one bend; two bends on opposite edges is the closest
sane reading of "two edge flanges.")

Run it:

```bash
/opt/miniconda3/envs/freecad/bin/freecadcmd scripts/build_bracket.py
```

Pipeline: sketch → `SheetMetalBaseCmd.SMBaseBend` (base wall) →
`SheetMetalCmd.SMBendWall` × 2 (edge flanges, second one chained onto the
first's resulting shape so both flanges end up in the same solid) →
`Part::Cut` (bolt holes) → STEP export → `SheetMetalUnfoldCmd.SMUnfold` →
DXF export of the generated flat-pattern sketch.

**Dimensional sanity check.** Cross-checked FreeCAD's own unfold output
against the bend-allowance formula the SheetMetal workbench documents itself
(`tools/calc-unfold.py` in shaise/FreeCAD_SheetMetal):

```
t = K_factor * thickness
bend_allowance = 2*pi*(radius + t) * (angle / 360)
expected_flat_length = base_length + 2 * (flange_leg_length + bend_allowance)
```

With thickness=2mm, K=0.38 (ANSI), radius=2mm, angle=90°: bend allowance =
4.335mm per bend. Expected flat length = 100 + 2×(30 + 4.335) =
**168.671mm**. FreeCAD's unfolder measured **168.671mm** — matches to the
6th decimal place. Flat pattern width (60mm) is also checked and confirmed
unchanged from the plate width, since both bends run parallel to it. Both
checks are automated in the script and fail the build (non-zero exit) if
they drift.

**A real headless bug in the SheetMetal workbench, found and worked
around:** with the networkx-based "new" unfolder (the default once
`networkx` is installed — recommended over the old unfolder, so installed
it into the conda env), `SMUnfold` with `GenerateSketch=True` and its
default `ShowBendAngles=True` crashes under `freecadcmd`:

```
AttributeError: 'NoneType' object has no attribute 'PointSize'
  (SheetMetalNewUnfolder.py: bend_labels_doc_obj.ViewObject.PointSize = 0)
```

`ViewObject` is always `None` with no GUI; the bend-angle-label code path
doesn't check `FreeCAD.GuiUp` before touching it. Workaround: set
`unfold.ShowBendAngles = False`. This only suppresses in-sketch bend-angle
text annotations — it does not touch the actual flat-pattern geometry
(outline, bend lines, hole positions), which is unaffected and was
independently verified above. `scripts/build_bracket.py::unfold_part` sets
this and documents why inline.

**Another export gotcha, avoided rather than worked around:** exporting the
raw 3D unfolded *solid* directly to DXF (`importDXF.export([unfold_obj], ...)`)
produces duplicate overlapping entities — every hole came out as 4 identical
overlapping circles instead of 1, because the exporter walks every edge of
the still-3mm-thick solid (top face rim, bottom face rim, and OCCT's
periodic-surface seam splitting each into two). The workbench's own intended
path avoids this: request `GenerateSketch=True` on the `SMUnfold` object and
export the resulting 2D `Sketch` object instead — genuinely flat, no
duplicate geometry (verified: exactly 4 circles, one per hole, correct
6mm diameter). `scripts/build_bracket.py` uses this path.

Output (gitignored, sent to the user directly since they're binary):
`output/bracket_folded.step`, `output/bracket_flat.dxf`.

## Stage 3 — Parametrize (done)

`scripts/bracket_model.py` now holds the parametrized `build_bracket()`
function -- every dimension Stage 2 hardcoded (plate length/width, gauge,
flange length, bend angle, bend radius, K-factor) is a function argument.
`build_bracket.py` is now a thin wrapper calling it with Stage 2's exact
values (confirmed identical output -- same bbox, same volume, same flat
length to the mm, so the refactor changed nothing observable).

`scripts/test_matrix.py` sweeps 15 cases -- the baseline plus the edge
cases asked for (very short flange, tight bend radius, thin vs. thick
gauge) -- and writes results to
[`reports/stage3_test_matrix.md`](reports/stage3_test_matrix.md). Run it:

```bash
/opt/miniconda3/envs/freecad/bin/freecadcmd scripts/test_matrix.py
```

**Result: 13 passed, 2 failed.** The 2 failures are clean and expected --
`flange_length=0` and `flange_length=-5` both raise
`RuntimeError: Flange1: empty/null shape`, caught and logged, no crash, no
silent bad geometry.

**The real finding here isn't the failures -- it's what didn't fail and
arguably should have.** Every bend-radius and gauge extreme I threw at it
built successfully at the FreeCAD/OCCT level, including several that are
not physically buildable on a real press brake:

- **`bend_radius=0.0`** (a mathematically sharp, zero-radius bend) built
  fine and exported valid geometry. Real sheet metal has a material-
  dependent minimum bend radius (cracks/tears below it); this tool enforces
  none of that.
- **`thickness=8.0` with `bend_radius=2.0`** (radius well under a common
  rule-of-thumb minimum of roughly 1x material thickness for many
  materials/tempers) also built fine.
- **`flange_length=1.0` with `bend_radius=2.0`, `thickness=2.0`** -- a 1mm
  flat leg on a bend that itself consumes ~4mm of material -- built fine
  and unfolded to a sane-looking flat length. No real press brake tooling
  clears a flange that short; it'd be crushed into the bend.

None of this is a SheetMetal workbench bug -- it's a plain geometry kernel
doing exactly what it's told, with zero manufacturability opinion. **This
matters for Stage 4/5**: reading dimensions out of an Excel sheet and
handing them straight to this pipeline will happily produce STEP/DXF for
parts no shop can actually bend. Stage 4's per-row validation should reject
(not just log) at minimum: `bend_radius` below some fraction of
`thickness`, and `flange_length` below `bend_radius + thickness` plus a
tooling clearance margin -- these are business-rule checks this pipeline
needs to add itself, not something to expect from the CAD engine.

## Stage 4 — Excel I/O (done)

`scripts/excel_io.py` reads one row per part from an `.xlsx` via openpyxl
(no geometry/type logic -- just header row -> dict per data row).
`scripts/run_batch.py` loops the rows, validates each (Stage 3's
manufacturability checks, now enforced rather than just reported), builds
via `bracket_model.build_bracket`, and writes `{JobID}_folded.step` +
`{JobID}_flat.dxf` per row. Every row is independently wrapped in
try/except -- a bad cell value or a failed validation check is logged and
the batch moves to the next row, never aborts the run.

Expected columns: `JobID, Material, PlateLength, PlateWidth, Thickness,
FlangeLength, BendAngle, BendRadius, HoleDia, HoleX, HoleY`. (`Material`
resolves to a K-factor via Stage 5's lookup table below, rather than being
supplied directly as a number.)

Run it:

```bash
/opt/miniconda3/envs/freecad/bin/python scripts/make_sample_input.py  # generates input/parts_sample.xlsx
/opt/miniconda3/envs/freecad/bin/freecadcmd scripts/run_batch.py       # defaults to that file
# or: freecadcmd scripts/run_batch.py path/to/your.xlsx
```

**Another freecadcmd gotcha, alongside Stage 1's `__name__` one:**
`sys.argv` under freecadcmd is shifted one further than a normal Python
script -- `argv[0]` is the `freecadcmd` binary itself, `argv[1]` is the
script's own path, and real CLI arguments start at `argv[2]`, not
`argv[1]`. Got this wrong on the first pass (`run_batch.py` tried to open
its own `.py` file as an Excel workbook); fixed and documented inline.

## Stage 5 — K-factor / bend allowance table (done)

`config/kfactor_table.json` replaces the hardcoded `K_FACTOR = 0.38` with a
material x thickness-band lookup (`scripts/kfactor_lookup.py`), wired into
`run_batch.py`: each row supplies a `Material` name instead of a raw
K-factor number, and the batch script resolves it against the table before
calling `build_bracket`. Three materials seeded (`mild_steel`,
`stainless_304`, `aluminum_5052`) with placeholder ANSI-style bands by
gauge -- **explicitly flagged in the table's own `_note` field as widely-
cited rule-of-thumb approximations, not certified data** -- swap in your
shop's actual measured/supplied K-factors before using this on real parts.
A thickness beyond a material's characterized range extrapolates from the
largest band and prints a warning rather than failing outright; an unknown
material raises cleanly (`KeyError`, caught like any other bad-row failure).

`input/parts_sample.xlsx` (committed) now has 6 rows: 3 valid (one per
seeded material, varying gauge/size), 3 deliberately bad, covering every
distinct failure mode a batch run has to survive without dying:

| Job ID | Status | Detail |
|---|---|---|
| BR-001 | OK | mild_steel, 2mm -> K=0.38 (matches Stages 2-4's hardcoded value -- continuity check), flat=168.671x60.0mm |
| BR-002 | OK | aluminum_5052, 1mm -> K=0.35, flat=114.869x50.0mm |
| BR-003 | OK | stainless_304, 4mm -> K=0.38, flat=247.342x80.0mm |
| BR-004 | FAIL | manufacturability check failed: bend_radius 1.0mm is below 1.0x thickness (5.0mm) |
| BR-005 | FAIL | column 'Thickness' is not a number: 'N/A' |
| BR-006 | FAIL | unknown material 'unobtainium' (known materials: aluminum_5052, mild_steel, stainless_304) |

(Full log: [`reports/stage4_sample_batch_log.md`](reports/stage4_sample_batch_log.md).
Per-row STEP/DXF outputs go to `output/batch/`, gitignored like all
generated CAD exports.)

## Status

All 5 stages complete. Everything above ran headless via `freecadcmd`, end
to end: Excel row in, validated against real manufacturability limits, STEP
+ DXF out, K-factor from a real (if placeholder) material table rather than
a guess.

**What's still placeholder, not real:** the target part family (a U-channel
built from the brief's own example text, since real job specs were never
provided), the manufacturability thresholds in `bracket_model.py`
(`MIN_BEND_RADIUS_TO_THICKNESS_RATIO`, `MIN_FLANGE_LENGTH_FACTOR`), and the
K-factor table's actual numbers. All three are called out inline/in this
README everywhere they appear -- replace them with real shop/material data
before trusting this for production parts.
