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

## Stage 2 — One hardcoded part (next)

Full pipeline for the target part family with fixed dimensions: sketch →
base wall → edge flange(s) → hole cuts → STEP export (folded) → unfold →
DXF export (flat pattern).
