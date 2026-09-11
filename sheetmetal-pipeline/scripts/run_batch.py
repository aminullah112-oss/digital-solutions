"""Stage 4: batch-generate STEP + DXF from an Excel spec sheet.

Reads one row per part from an .xlsx (columns matching bracket_model's
parameters, see excel_io.py), builds each with bracket_model.build_bracket,
and writes {job_id}_folded.step + {job_id}_flat.dxf per row.

Each row is fully isolated: a bad value, a validation failure (Stage 3's
manufacturability checks), or a geometry failure in one row is caught,
logged, and the batch moves on to the next row. Nothing here lets one bad
row take down the run.

Run with:
    /opt/miniconda3/envs/freecad/bin/freecadcmd scripts/run_batch.py [path/to/parts.xlsx]

Defaults to input/parts_sample.xlsx if no path is given.

NOTE: freecadcmd's sys.argv is shifted one further than a normal Python
script's: argv[0] is the freecadcmd binary itself, argv[1] is this script's
own path, and any real extra CLI args start at argv[2] -- not argv[1] as
they would running `python3 run_batch.py foo.xlsx` directly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_sheetmetal_to_path

add_sheetmetal_to_path()

from bracket_model import build_bracket, validate_params
from excel_io import read_rows

PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INPUT = os.path.join(PIPELINE_ROOT, "input", "parts_sample.xlsx")

# Excel column name -> build_bracket() keyword argument.
COLUMN_MAP = {
    "PlateLength": "plate_length",
    "PlateWidth": "plate_width",
    "Thickness": "thickness",
    "FlangeLength": "flange_length",
    "BendAngle": "bend_angle",
    "BendRadius": "bend_radius",
    "KFactor": "k_factor",
    "HoleDia": "hole_dia",
    "HoleX": "hole_x",
    "HoleY": "hole_y",
}


def require_float(row, column):
    if column not in row or row[column] is None:
        raise ValueError(f"missing required column '{column}'")
    try:
        return float(row[column])
    except (TypeError, ValueError):
        raise ValueError(f"column '{column}' is not a number: {row[column]!r}")


def parse_row(row):
    return {param: require_float(row, column) for column, param in COLUMN_MAP.items()}


def main():
    # argv[1] is this script's own path under freecadcmd -- see module docstring.
    input_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_INPUT
    if not os.path.isfile(input_path):
        raise SystemExit(f"Input file not found: {input_path}")

    out_dir = os.path.join(PIPELINE_ROOT, "output", "batch")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Reading: {input_path}")
    results = []
    for i, row in enumerate(read_rows(input_path), start=1):
        raw_job_id = row.get("JobID")
        job_id = str(raw_job_id).strip() if raw_job_id not in (None, "") else f"row{i}"

        try:
            params = parse_row(row)
            problems = validate_params(**params)
            if problems:
                raise ValueError("manufacturability check failed: " + "; ".join(problems))

            result = build_bracket(
                doc_name=f"Job_{job_id}",
                export_dir=out_dir,
                export_prefix=job_id,
                **params,
            )
            if not result["ok"]:
                raise RuntimeError(result["error"])

            m = result["metrics"]
            print(f"[OK]   {job_id}: flat={m['flat_length']}x{m['flat_width']}mm -> {m['step_path']}, {m['dxf_path']}")
            results.append((job_id, "OK", m))

        except Exception as exc:  # noqa: BLE001 -- one bad row must never kill the batch
            print(f"[FAIL] {job_id}: {type(exc).__name__}: {exc}")
            results.append((job_id, "FAIL", str(exc)))

    n_ok = sum(1 for _, status, _ in results if status == "OK")
    n_fail = len(results) - n_ok
    print(f"\n{n_ok} succeeded, {n_fail} failed out of {len(results)} rows")

    write_log(results, out_dir)


def write_log(results, out_dir):
    path = os.path.join(out_dir, "batch_log.md")
    lines = ["# Batch run log", "", "| Job ID | Status | Detail |", "|---|---|---|"]
    for job_id, status, detail in results:
        detail_str = (
            f"flat={detail['flat_length']}x{detail['flat_width']}mm"
            if status == "OK" else str(detail)
        ).replace("|", "\\|")
        lines.append(f"| {job_id} | {status} | {detail_str} |")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Log written: {path}")


main()
