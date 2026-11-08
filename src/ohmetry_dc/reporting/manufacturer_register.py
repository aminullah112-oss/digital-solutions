"""The manufacturer-data register: metadata from config/manufacturer_data_register.yaml joined with live values from the master configuration."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import yaml

from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models.attestation import NOTICE, describe, is_complete, is_started, missing_fields

COLUMNS = ["Equipment category", "Required parameter", "Equipment tags", "Required datasheet", "Placeholder or current value", "Unit", "Input data status", "Source and status", "Engineering impact", "Outstanding verification action", "Verification status"]

CATEGORIES = (("TX", "Transformer"), ("GEN", "Generator"), ("UPS", "UPS"), ("BAT", "Battery"), ("CAB", "Cable"), ("BD", "Busduct"), ("LV", "LV switchgear"), ("MV-SWG", "MV switchgear"), ("MV-CB", "Protection device"),
              ("ACB", "Protection device"), ("EARTH", "Earthing and site"))


@dataclass
class RegisterRow:
    parameter: str
    name: str
    equipment_tags: list[str]
    required_datasheet: str
    value: object
    unit: str
    source: str
    status: str
    engineering_impact: str
    verification_action: str
    data_state: str
    verified_by: str | None
    datasheet_reference: str | None
    category: str = "General"
    data_class: str = ""          # the input data status (see models/data_status.py)
    attestation: str = ""         # who attested, for which evidence and scope (empty unless the record is complete)


def _live(cfg: ProjectConfig, pid: str):
    """(name, value, unit, source, status, flagged, parameter-or-None) for a parameter id or a distribution pseudo-id; None if it does not exist."""
    if pid in cfg.parameters:
        p = cfg.parameters[pid]
        return p.name, p.value, p.unit, p.source, p.status.value, p.requires_manufacturer_verification, p
    if pid.startswith("distribution."):
        _, tag, field = pid.split(".", 2)
        for group in ("feeders", "busducts", "switchgear", "protection_devices"):
            for it in (cfg.distribution or {}).get(group, []):
                if it["tag"] == tag and field in it:
                    ds_ = (it.get("data_sources") or {}).get(field)
                    src = (ds_["source"] + (f", rev {ds_['datasheet_revision']}" if ds_.get("datasheet_revision") else "")) if ds_ else "Manufacturer data pending"
                    return f"{tag}: {field}", it[field], "", src, "MANUFACTURER_DATA", False, None
    return None


def category_of(tags: list[str]) -> str:
    t = tags[0] if tags else ""
    return next((n for pre, n in CATEGORIES if t.startswith(pre)), "General")


def state_of(input_status: str) -> str:
    """Verification status for the register, from the input data status."""
    if input_status == "MISSING":
        return "PENDING"
    if input_status.endswith("_VERIFIED"):
        return "VERIFIED"
    if input_status.endswith("_SUPPLIED"):
        return "SUPPLIED, REVIEW REQUIRED"
    if input_status in ("REFERENCE_DATA", "PROJECT_INPUT"):
        return "NOT APPLICABLE"
    return "NOT VERIFIED"


def load_register_meta(path: str | Path) -> list[dict]:
    return (yaml.safe_load(Path(path).read_text()) or {}).get("entries") or []


def required_ids(cfg: ProjectConfig) -> set[str]:
    """Every parameter that is manufacturer data or a placeholder awaiting it, and every missing manufacturer field in the distribution schedule."""
    ids = {p.id for p in cfg.parameters.values() if p.status.value == "MANUFACTURER_DATA" or p.requires_manufacturer_verification}
    d = cfg.distribution or {}
    fields = {"feeders": ("tabulated_rating_a",), "busducts": ("rated_current_a", "resistance_ohm_per_km", "reactance_ohm_per_km", "short_circuit_withstand_ka"),
              "switchgear": ("rated_current_a", "short_circuit_rating_ka", "form_of_separation", "ip_rating", "verification_evidence"),
              "protection_devices": ("breaking_capacity_ka", "making_capacity_ka", "time_current_curve_ref", "settings")}
    for group, fs in fields.items():
        for it in d.get(group, []):
            ids |= {f"distribution.{it['tag']}.{f}" for f in fs}
    return ids


def _input_status(param, value, verified: bool) -> str:
    from ohmetry_dc.models import data_status as ds

    if param is not None:
        return ds.data_status(param, verified)       # a status is VERIFIED only when a reviewer is recorded AND the value came from an override
    if value is None:
        return ds.MISSING
    return ds.MANUFACTURER_VERIFIED if verified else ds.MANUFACTURER_SUPPLIED


def build_rows(cfg: ProjectConfig, meta: list[dict]) -> list[RegisterRow]:
    rows = []
    for e in meta:
        live = _live(cfg, e["parameter"])
        if live is None:
            continue
        name, value, unit, source, status, flagged, param = live
        done = is_complete(e)
        inp = _input_status(param, value, done)
        rows.append(RegisterRow(e["parameter"], name, e.get("equipment_tags") or [], e["required_datasheet"], value, unit, source, status, e["engineering_impact"], e["verification_action"],
                                state_of(inp), e.get("verified_by") if done else None, e.get("datasheet_reference"), category_of(e.get("equipment_tags") or []), inp, describe(e) if done else ""))
    return rows


def problems(cfg: ProjectConfig, meta: list[dict]) -> list[str]:
    """Register defects: missing entries, dangling entries, and verification claimed for a placeholder."""
    out = []
    have = {e["parameter"] for e in meta}
    for pid in sorted(required_ids(cfg) - have):
        out.append(f"missing register entry for {pid}")
    for e in meta:
        live = _live(cfg, e["parameter"])
        if live is None:
            out.append(f"register entry {e['parameter']} does not exist in the configuration")
            continue
        _, value, _, _, status, flagged, param = live
        supplied = value is not None and (param is None or param.revision == "OVERRIDE")
        if is_started(e):
            gap = missing_fields(e)
            if gap:
                out.append(f"{e['parameter']} has an incomplete verification record (missing or invalid: {', '.join(gap)}); it is NOT treated as verified")
        if is_complete(e) and not supplied:
            out.append(f"{e['parameter']} is marked verified by {e['verified_by']} but its value is still a placeholder or missing")
        if not e.get("equipment_tags"):
            out.append(f"{e['parameter']} has no equipment tag")
    return out


def to_markdown(rows: list[RegisterRow], generated: str) -> str:
    L = ["# Manufacturer-data register", "", f"Generated {generated}. Values, sources and statuses are read live from the master configuration and the supplied-data overrides. **A placeholder is not validated equipment data, and reference data is not manufacturer-confirmed.** "
         "Every row is NOT VERIFIED until a reviewer records the source document for it. " + NOTICE, "", "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rows:
        val = "(none: pending)" if r.value is None else str(r.value)
        L.append(f"| {r.category} | `{r.parameter}` {r.name} | {', '.join(r.equipment_tags)} | {r.required_datasheet} | {val} | {r.unit} | {r.data_class} | {r.source}. Status {r.status} | {r.engineering_impact} | {r.verification_action} | {r.data_state if not r.verified_by else 'ATTESTED VERIFIED: ' + r.attestation} |")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.data_state] = counts.get(r.data_state, 0) + 1
    L += ["", "## Summary", ""] + [f"- {k}: {v}" for k, v in sorted(counts.items())] + [""]
    return "\n".join(L)


IMPORT_COLUMNS = ["parameter", "value", "unit", "source", "datasheet_revision", "datasheet_reference"]


def to_csv(rows: list[RegisterRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "parameter", "equipment_tags", "required_datasheet", "value", "unit", "data_class", "source", "status", "engineering_impact", "verification_action", "verification_status", "verified_by", "datasheet_reference", "attestation"])
    for r in rows:
        w.writerow([r.category, r.parameter, ";".join(r.equipment_tags), r.required_datasheet, "" if r.value is None else r.value, r.unit, r.data_class, r.source, r.status, r.engineering_impact, r.verification_action, r.data_state, r.verified_by or "", r.datasheet_reference or "", r.attestation])
    return buf.getvalue()


def import_template(rows: list[RegisterRow]) -> str:
    """A blank CSV to fill from data sheets. Importing it never edits the calculation engine or the master configuration."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(IMPORT_COLUMNS + ["equipment_tags", "required_datasheet"])
    for r in rows:
        w.writerow([r.parameter, "", r.unit, "", "", "", ";".join(r.equipment_tags), r.required_datasheet])
    return buf.getvalue()


def explain_missing(cfg: ProjectConfig, ids: list[str]) -> str:
    """For each missing parameter: its engineering impact and the document that supplies it, taken from the register."""
    from pathlib import Path

    path = Path(cfg.base_dir) / "manufacturer_data_register.yaml"
    meta = {e["parameter"]: e for e in load_register_meta(path)} if path.exists() else {}
    parts = []
    for i in ids:
        e = meta.get(i)
        name = cfg.parameters[i].name if i in cfg.parameters else i
        parts.append(f"{name} ({i})" + (f": {e['engineering_impact']} Source needed: {e['required_datasheet']}." if e else ". No register entry."))
    return " ".join(parts)
