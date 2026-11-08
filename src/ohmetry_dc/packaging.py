"""Assemble the customer ZIP from what has actually been built. Nothing is invented: a missing deliverable is listed as NOT INCLUDED."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from ohmetry_dc import __version__

PLANNED_WORKBOOKS = ["01_MASTER_DESIGN_BASIS", "02_LOAD_ESTIMATION", "03_POWER_ARCHITECTURE", "04_TRANSFORMER_SIZING", "05_GENERATOR_SIZING", "06_UPS_SIZING", "07_BATTERY_SIZING", "08_CABLE_SIZING",
                     "09_VOLTAGE_DROP", "10_SHORT_CIRCUIT", "11_LV_SWITCHGEAR", "12_MV_SWITCHGEAR", "13_BUSDUCT_SIZING", "14_PROTECTION_COORDINATION", "15_EARTHING_BONDING",
                     "16_LIGHTNING_PROTECTION", "17_POWER_QUALITY", "18_ENERGY_EFFICIENCY", "19_GENERATOR_FUEL", "20_MASTER_EQUIPMENT_SCHEDULE"]
DOCS = ["README.md", "DEVELOPMENT_STATUS.md", "RELEASE_CHECKLIST.md", "ENGINEERING_REVIEW_LOG.md", "LICENSE"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_package(root: Path, out_dir: Path, project_code: str, revision: str, include_engine: bool = False) -> tuple[Path, dict]:
    files: list[tuple[Path, str]] = []          # (source, path inside the zip)
    for p in sorted((root / "workbooks" / "generated").glob("*.xlsx")):
        files.append((p, f"workbooks/{p.name}"))
    for p in sorted((root / "reports" / "generated").glob("*.pdf")):
        files.append((p, f"reports/{p.name}"))
    for p in sorted((root / "drawings" / "svg").glob("*.svg")):
        files.append((p, f"drawings/{p.name}"))
    for p in sorted((root / "drawings" / "pdf").glob("*.pdf")):
        files.append((p, f"drawings/{p.name}"))
    for p in sorted((root / "training").rglob("*")):
        if p.is_file() and p.name != ".gitkeep":
            files.append((p, f"training/{p.relative_to(root / 'training')}"))
    for p in sorted((root / "docs").rglob("*.md")):
        if p.relative_to(root / "docs").parts[0] == "release":
            continue                                     # release documents are placed at the top level below
        files.append((p, f"docs/{p.relative_to(root / 'docs')}"))
    for p in sorted((root / "specifications").rglob("*")):
        if p.is_file() and p.name != ".gitkeep":
            files.append((p, f"specifications/{p.relative_to(root / 'specifications')}"))
    for name in ("CUSTOMER_README.md", "CUSTOMER_README.pdf", "CUSTOMER_README.docx", "LICENCE_COMMERCIAL.md", "LICENCE_COMMERCIAL.pdf", "LICENCE_COMMERCIAL.docx", "MASTER_INDEX.md", "MASTER_INDEX.csv"):
        if (root / "docs" / "release" / name).exists():
            files.append((root / "docs" / "release" / name, name))
    for name in ("OUTSTANDING_VERIFICATION_ITEMS.md", "OUTSTANDING_VERIFICATION_ITEMS.csv"):
        if (root / "output" / name).exists():
            files.append((root / "output" / name, f"registers_and_qa/{name}"))
    for name in ("document_revisions.yaml", "design_exceptions.yaml", "design_basis_revisions.yaml", "manufacturer_data_overrides.yaml"):
        if (root / "config" / name).exists():
            files.append((root / "config" / name, f"registers_and_qa/{name}"))
    for name in DOCS:
        if (root / name).exists():
            files.append((root / name, name))
    for name in ("manufacturer_data_register.md", "manufacturer_data_register.csv", "manufacturer_data_import_template.csv", "QA_RESULTS.md"):
        if (root / "output" / name).exists():
            files.append((root / "output" / name, f"registers_and_qa/{name}"))
    for name in ("assumptions_register.yaml", "standards_register.yaml", "manufacturer_data_register.yaml"):
        files.append((root / "config" / name, f"registers_and_qa/{name}"))
    if include_engine:
        for p in sorted(root.glob("config/*.yaml")):
            files.append((p, f"engine/config/{p.name}"))
        for p in sorted((root / "src").rglob("*.py")):
            files.append((p, f"engine/src/{p.relative_to(root / 'src')}"))
        files.append((root / "pyproject.toml", "engine/pyproject.toml"))
    have = {p.stem for p, z in files if p.suffix == ".xlsx" and z.startswith("workbooks/")}
    missing = [w for w in PLANNED_WORKBOOKS if w not in have]
    from ohmetry_dc.documents.register import build_register

    from types import SimpleNamespace

    reg = {r["path"]: r for r in build_register(root, SimpleNamespace(project=SimpleNamespace(revision=revision)))}
    unreg = [str(src.relative_to(root)) for src, _ in files if str(src.relative_to(root)) not in reg]
    manifest = {"product": project_code, "revision": revision, "package_version": __version__, "state": "DEVELOPMENT: preliminary, educational and reference use only. Not construction-ready. Not verified.",
                "workbooks_included": sorted(have), "workbooks_planned_total": 20, "workbooks_not_included": missing,
                "not_included": ["drawings other than the preliminary single-line diagram", "any manufacturer data, device curve, soil survey, lightning risk assessment or measurement (workbooks 14, 16, 17 and 19 are input registers)"],
                "engine_included": include_engine, "unregistered_files": unreg,
                "files": [{"path": z, "sha256": _sha(p), "bytes": p.stat().st_size, "document_id": reg.get(str(p.relative_to(root)), {}).get("id"), "revision": reg.get(str(p.relative_to(root)), {}).get("revision"),
                           "issue": reg.get(str(p.relative_to(root)), {}).get("issue"), "title": reg.get(str(p.relative_to(root)), {}).get("title"), "related": reg.get(str(p.relative_to(root)), {}).get("related", [])} for p, z in files]}
    status = ("PACKAGE STATUS: DEVELOPMENT\n\nThis package is a preliminary educational and engineering reference. It is NOT construction-ready and NOT verified.\n"
              f"Workbooks included: {len(have)} of 20 planned ({', '.join(sorted(have))}).\n"
              "All equipment values are preliminary assumptions or unverified placeholders unless a manufacturer data sheet has been entered and reviewed.\n"
              "Open each workbook's README sheet, then INPUTS: enter datasheet values with their source, and read the four statuses on RESULTS.\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"{project_code}_{revision}_PRELIMINARY.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for src, name in files:
            z.write(src, f"{project_code}/{name}")
        z.writestr(f"{project_code}/PACKAGE_STATUS.txt", status)
        z.writestr(f"{project_code}/MANIFEST.json", json.dumps(manifest, indent=2))
    return zpath, manifest
