"""Backend API: actually runs the FreeCAD pipeline and returns real files.

This is the piece the static UI (ui/) cannot be: FreeCAD's Python bindings
only import correctly once its lib directory is on sys.path (freecadcmd's
launcher does this for you; a bare Python process has to do it itself --
see FREECAD_LIB_DIR below), so this process must run inside the same
conda env Stage 1's setup_env.sh built, not a generic Python environment.

Endpoints:
    GET  /health          -- liveness check, reports the FreeCAD version in use
    GET  /api/materials   -- the same config/kfactor_table.json run_batch.py reads
    POST /api/build       -- build one part, return {job_id}_folded.step and
                              {job_id}_flat.dxf zipped together

Runs one request at a time per worker process (gunicorn sync workers --
see gunicorn_conf.py): FreeCAD/OCCT's C++ state is not meant to be shared
across concurrent requests in one process, so process-level isolation
(not threads) is what keeps one bad request from corrupting another, and
means a native crash on pathological geometry only takes down the one
worker handling it -- gunicorn respawns it, other workers keep serving.
"""

import io
import os
import shutil
import sys
import tempfile
import zipfile

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

FREECAD_LIB_DIR = os.environ.get("FREECAD_LIB_DIR", "/opt/miniconda3/envs/freecad/lib")
sys.path.insert(0, FREECAD_LIB_DIR)

PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PIPELINE_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from common import add_sheetmetal_to_path  # noqa: E402  (path setup must run first)

add_sheetmetal_to_path()

from bracket_model import build_bracket, validate_params  # noqa: E402
from kfactor_lookup import load_table, lookup_k_factor  # noqa: E402

import FreeCAD  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1MB -- this API only ever takes small JSON bodies

# Comma-separated list of allowed origins, e.g. the GitHub Pages site this
# UI is served from. "*" (default) is fine for a small demo tool with no
# auth and no state, but tighten this via env var for anything beyond that.
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")
CORS(app, origins=ALLOWED_ORIGINS.split(",") if ALLOWED_ORIGINS != "*" else "*")

KFACTOR_TABLE = load_table()

REQUIRED_FIELDS = [
    "job_id", "material", "plate_length", "plate_width", "thickness",
    "flange_length", "bend_angle", "bend_radius", "hole_dia", "hole_x", "hole_y",
]


@app.route("/health")
def health():
    return jsonify(status="ok", freecad_version=".".join(FreeCAD.Version()[:3]))


@app.route("/api/materials")
def materials():
    return jsonify(KFACTOR_TABLE)


@app.route("/api/build", methods=["POST"])
def api_build():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="request body must be JSON"), 400

    missing = [f for f in REQUIRED_FIELDS if f not in data or data[f] in (None, "")]
    if missing:
        return jsonify(error=f"missing required field(s): {', '.join(missing)}"), 400

    job_id = str(data["job_id"]).strip()
    material = str(data["material"]).strip()
    try:
        numeric = {
            k: float(data[k]) for k in REQUIRED_FIELDS if k not in ("job_id", "material")
        }
    except (TypeError, ValueError) as exc:
        return jsonify(error=f"non-numeric field value: {exc}"), 400

    try:
        k_factor, extrapolated = lookup_k_factor(KFACTOR_TABLE, material, numeric["thickness"])
    except KeyError as exc:
        return jsonify(error=str(exc)), 422

    params = {**numeric, "k_factor": k_factor}
    problems = validate_params(**params)
    if problems:
        return jsonify(error="manufacturability check failed", problems=problems), 422

    work_dir = tempfile.mkdtemp(prefix=f"job_{job_id}_")
    try:
        result = build_bracket(
            doc_name=f"API_{job_id}",
            export_dir=work_dir,
            export_prefix=job_id,
            **params,
        )
        if not result["ok"]:
            return jsonify(error=result["error"]), 500

        m = result["metrics"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(m["step_path"], arcname=os.path.basename(m["step_path"]))
            zf.write(m["dxf_path"], arcname=os.path.basename(m["dxf_path"]))
        buf.seek(0)

        response = send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{job_id}.zip",
        )
        response.headers["X-K-Factor"] = str(k_factor)
        response.headers["X-K-Factor-Extrapolated"] = str(extrapolated).lower()
        response.headers["X-Flat-Length-Mm"] = str(m["flat_length"])
        response.headers["X-Flat-Width-Mm"] = str(m["flat_width"])
        response.headers["Access-Control-Expose-Headers"] = (
            "X-K-Factor, X-K-Factor-Extrapolated, X-Flat-Length-Mm, X-Flat-Width-Mm"
        )
        return response

    except Exception as exc:  # noqa: BLE001 -- never let one bad request crash the response cycle
        return jsonify(error=f"{type(exc).__name__}: {exc}"), 500

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    # Dev server only. Production uses gunicorn (see Dockerfile / gunicorn_conf.py).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
