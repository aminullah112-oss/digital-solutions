"""Import supplied manufacturer, utility and site data into config/manufacturer_data_overrides.yaml.

Validation before anything is written (one bad row rejects the whole file, so a partial import cannot happen):
  - the parameter exists in the register
  - a source document is given, and a datasheet revision for manufacturer data
  - the unit is given and is one of a small set of supported, convertible units
  - the value has the right type and a plausible range (percentages 0 to 100, power factors and derating factors above 0 and at most 1, no negative ratings)
The master design-basis file is never edited. Each import appends to an append-only history with the previous effective value.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import yaml

from ohmetry_dc.models import ProjectConfig

# unit -> (family, factor to the family's base unit)
UNITS: dict[str, tuple[str, float]] = {
    "W": ("power", 1.0), "kW": ("power", 1e3), "MW": ("power", 1e6),
    "VA": ("apparent", 1.0), "kVA": ("apparent", 1e3), "MVA": ("apparent", 1e6),
    "V": ("voltage", 1.0), "kV": ("voltage", 1e3),
    "A": ("current", 1.0), "kA": ("current", 1e3),
    "mm": ("length", 1e-3), "m": ("length", 1.0), "km": ("length", 1e3),
    "mm2": ("area", 1.0), "m2": ("area", 1e6),
    "s": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0),
    "%": ("ratio", 1.0), "pu": ("ratio", 100.0),
    "ohm": ("resistance", 1.0), "ohm.m": ("resistivity", 1.0), "Hz": ("frequency", 1.0), "degC": ("temperature", 1.0), "m/s": ("speed", 1.0),
    "ohm/km": ("impedance_per_length", 1.0), "kWh": ("energy", 1.0), "-": ("none", 1.0), "A.s^0.5/mm2": ("k", 1.0),
}
TEXT_FIELDS = {"form_of_separation", "ip_rating", "verification_evidence", "time_current_curve_ref", "settings"}


def convert(value: float, unit: str, target: str) -> float:
    """Convert between units of one family. Raises ValueError for an unsupported unit or a different family."""
    if unit not in UNITS:
        raise ValueError(f"unsupported unit {unit!r}")
    if target not in UNITS:
        raise ValueError(f"the master unit {target!r} is not convertible")
    (fa, ka), (fb, kb) = UNITS[unit], UNITS[target]
    if fa != fb:
        raise ValueError(f"unit {unit!r} ({fa}) cannot be converted to {target!r} ({fb})")
    return value * ka / kb


def _check_range(name: str, unit: str, value: float) -> str | None:
    low = name.lower()
    if unit == "%" and not 0 <= value <= 100:
        return "a percentage must be between 0 and 100"
    if ("power factor" in low or "factor" in low and unit == "-" and "derating" in low) and not 0 < value <= 1:
        return "a power factor or derating factor must be above 0 and at most 1"
    if unit not in ("degC",) and value < 0:
        return "a negative value is not plausible here"
    return None


def import_data(csv_text: str, overrides_path: Path, cfg: ProjectConfig, known: set[str], stamp: str) -> tuple[int, list[str]]:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    existing = (yaml.safe_load(overrides_path.read_text()) if overrides_path.exists() else None) or {}
    existing.setdefault("schema_version", 1)
    cur = {o["parameter"]: o for o in existing.get("overrides") or []}
    history = list(existing.get("history") or [])
    bad: list[str] = []
    staged: list[tuple[dict, dict]] = []
    for i, r in enumerate(rows, start=2):
        pid, raw = (r.get("parameter") or "").strip(), (r.get("value") or "").strip()
        if not raw:
            continue
        if pid not in known:
            bad.append(f"line {i}: unknown parameter {pid!r}")
            continue
        src, rev, unit = (r.get("source") or "").strip(), (r.get("datasheet_revision") or "").strip(), (r.get("unit") or "").strip()
        if not src:
            bad.append(f"line {i}: {pid} has a value but no source document")
            continue
        p = cfg.parameters.get(pid)
        master_unit = p.unit if p else None
        name = p.name if p else pid
        is_text = (pid.startswith("distribution.") and pid.split(".")[-1] in TEXT_FIELDS) or (p is not None and p.unit == "-" and isinstance(p.value, str))
        if p is not None and p.status.value != "USER_INPUT" and not rev:
            bad.append(f"line {i}: {pid} is manufacturer data, so the datasheet revision is required")
            continue
        if is_text:
            staged.append(({"parameter": pid, "value": raw, "unit": "", "source": src, "datasheet_revision": rev, "datasheet_reference": (r.get("datasheet_reference") or "").strip(), "date": stamp},
                           {"supplied": f"{raw}", "applied": raw}))
            continue
        if raw.lower() in ("true", "false"):
            staged.append(({"parameter": pid, "value": raw.lower() == "true", "unit": "", "source": src, "datasheet_revision": rev, "datasheet_reference": (r.get("datasheet_reference") or "").strip(), "date": stamp},
                           {"supplied": raw, "applied": raw.lower() == "true"}))
            continue
        try:
            val = float(raw)
        except ValueError:
            bad.append(f"line {i}: {pid} needs a number, got {raw!r}")
            continue
        target = master_unit if master_unit is not None else (unit or None)
        if target not in (None, "-") or unit:
            if not unit and target not in (None, "-"):
                bad.append(f"line {i}: {pid} needs a unit (master unit {target})")
                continue
        if unit and target is not None:
            try:
                val = convert(val, unit, target)
            except ValueError as e:
                bad.append(f"line {i}: {pid}: {e}")
                continue
        problem = _check_range(name, target or unit, val)
        if problem:
            bad.append(f"line {i}: {pid} = {val:g}: {problem}")
            continue
        val = int(val) if float(val).is_integer() else round(val, 12)
        staged.append(({"parameter": pid, "value": val, "unit": target or unit, "source": src, "datasheet_revision": rev, "datasheet_reference": (r.get("datasheet_reference") or "").strip(), "date": stamp},
                       {"supplied": f"{raw} {unit}".strip(), "applied": val}))
    if bad:
        return 0, bad
    for o, info in staged:
        pid = o["parameter"]
        prev = cur[pid]["value"] if pid in cur else _master_value(cfg, pid)
        history.append({"date": stamp, "parameter": pid, "previous_effective_value": prev, "supplied": info["supplied"], "new_value": info["applied"], "unit": o["unit"],
                        "source": o["source"], "datasheet_revision": o["datasheet_revision"], "datasheet_reference": o["datasheet_reference"]})
        cur[pid] = o
    existing["overrides"] = list(cur.values())
    existing["history"] = history
    hdr = "".join(l for l in overrides_path.read_text().splitlines(True) if l.startswith("#")) if overrides_path.exists() else ""
    overrides_path.write_text(hdr + yaml.safe_dump(existing, sort_keys=False, allow_unicode=True))
    return len(staged), []


def _master_value(cfg: ProjectConfig, pid: str):
    p = cfg.parameters.get(pid)
    if p is not None:
        return p.original_value if p.original_value is not None else p.value
    if pid.startswith("distribution."):
        _, tag, field = pid.split(".", 2)
        for g in ("feeders", "busducts", "switchgear", "protection_devices"):
            for it in (cfg.distribution or {}).get(g) or []:
                if it["tag"] == tag and field in it:
                    return (it.get("original_values") or {}).get(field, it[field])
    return None
