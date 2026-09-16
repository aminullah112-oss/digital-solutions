"""Normalized data model.

The frontend never sees a Modbus address.  An adapter produces readings keyed
by `parameter_name`; the register definition carries a `normalized_key` that
maps it onto the catalogue below.  Swapping EMCP 4.4 for a different
controller means importing a different register map, not touching the UI.

A key that no register maps to is reported as UNKNOWN with a null value — it
is never filled in from a similar signal or estimated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import settings
from ..domain import DataSource, Quality, utcnow
from ..protocols.base import Reading


@dataclass(frozen=True)
class SignalSpec:
    key: str
    display_name: str
    group: str
    unit: str
    kind: str = "analog"  # analog | discrete | state | counter


GENERATOR_SIGNALS = [
    SignalSpec("voltage_L1_L2", "Voltage L1-L2", "generator", "V"),
    SignalSpec("voltage_L2_L3", "Voltage L2-L3", "generator", "V"),
    SignalSpec("voltage_L3_L1", "Voltage L3-L1", "generator", "V"),
    SignalSpec("voltage_L1_N", "Voltage L1-N", "generator", "V"),
    SignalSpec("current_L1", "Current L1", "generator", "A"),
    SignalSpec("current_L2", "Current L2", "generator", "A"),
    SignalSpec("current_L3", "Current L3", "generator", "A"),
    SignalSpec("frequency", "Frequency", "generator", "Hz"),
    SignalSpec("rpm", "Speed", "generator", "rpm"),
    SignalSpec("kw", "Real power", "generator", "kW"),
    SignalSpec("kvar", "Reactive power", "generator", "kVAr"),
    SignalSpec("kva", "Apparent power", "generator", "kVA"),
    SignalSpec("power_factor", "Power factor", "generator", ""),
    SignalSpec("breaker_status", "Breaker status", "generator", "", kind="discrete"),
    SignalSpec("engine_status", "Engine status", "generator", "", kind="state"),
    SignalSpec("generator_status", "Generator status", "generator", "", kind="state"),
]

ENGINE_SIGNALS = [
    SignalSpec("oil_pressure", "Oil pressure", "engine", "psi"),
    SignalSpec("coolant_temperature", "Coolant temperature", "engine", "degC"),
    SignalSpec("fuel_level", "Fuel level", "engine", "%"),
    SignalSpec("battery_voltage", "Battery voltage", "engine", "V"),
    SignalSpec("engine_speed", "Engine speed", "engine", "rpm"),
    SignalSpec("engine_hours", "Engine hours", "engine", "h", kind="counter"),
]

CONTROLLER_SIGNALS = [
    SignalSpec("control_voltage", "Control voltage", "controller", "V"),
    SignalSpec("breaker_close_command", "Breaker close command", "controller", "", kind="discrete"),
    SignalSpec("breaker_closed_feedback", "Breaker closed feedback", "controller", "",
               kind="discrete"),
]

CATALOGUE: dict[str, SignalSpec] = {
    s.key: s for s in (*GENERATOR_SIGNALS, *ENGINE_SIGNALS, *CONTROLLER_SIGNALS)
}

GROUPS = ("generator", "engine", "controller", "io", "other")


def classify(key: str) -> SignalSpec:
    """Return the catalogue entry for a key, or a generic one.

    Discrete I/O points (DO_07, DI_11, ...) are common to every controller but
    their meaning is site-specific, so they are grouped rather than named.
    """
    if key in CATALOGUE:
        return CATALOGUE[key]
    upper = key.upper()
    if upper.startswith(("DO_", "DI_", "AI_", "AO_")):
        return SignalSpec(key, key.replace("_", "-"), "io", "",
                          kind="discrete" if upper[:3] in ("DO_", "DI_") else "analog")
    return SignalSpec(key, key, "other", "")


def normalize(readings: list[Reading], *, simulated: bool = False) -> dict[str, dict]:
    """Turn adapter readings into keyed, provenance-tagged envelopes."""
    out: dict[str, dict] = {}
    for r in readings:
        key = r.normalized_key or r.parameter_name
        spec = classify(key)
        out[key] = {
            "key": key,
            "display_name": spec.display_name,
            "group": spec.group,
            "kind": spec.kind,
            "value": r.value,
            "unit": r.unit or spec.unit,
            "timestamp": r.timestamp.isoformat(),
            "quality": (Quality.SIMULATED if simulated else r.quality).value,
            "source": (DataSource.SIMULATED if simulated else r.source).value,
            "source_detail": r.source_detail,
            "error": r.error,
        }
    return out


def apply_staleness(envelope: dict, *, now: datetime | None = None) -> dict:
    """Downgrade quality to STALE once a value is older than the threshold.

    Offline mode shows the last value with its age, never a bare number.
    """
    now = now or utcnow()
    ts = envelope.get("timestamp")
    if not ts:
        return envelope
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return envelope
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (now - parsed).total_seconds()
    envelope = {**envelope, "age_s": round(age, 2)}
    if age > settings.stale_after_s and envelope.get("quality") in ("GOOD", "SIMULATED"):
        envelope["quality"] = Quality.STALE.value
    return envelope
