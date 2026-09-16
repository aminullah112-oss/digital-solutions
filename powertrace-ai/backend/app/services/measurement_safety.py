"""Measurement input safety validation.

The failure this guards against is someone binding a 0-10 V analog input to a
4160 V circuit because the software let them type it in. Configuration that
would imply a direct connection to a voltage above the touch-safe limit is
rejected, not warned about.

This is a software check on configuration. It does not make an installation
safe: the isolation has to exist in hardware, rated and installed correctly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import settings
from ..domain import MEDIUM_VOLTAGE_THRESHOLD_V, MV_SAFETY_NOTICE, utcnow

ISOLATING_DEVICES = {"PT", "VT", "CT", "TRANSDUCER", "ISOLATION_AMPLIFIER"}
INPUT_TYPES = {
    "VOLTAGE_DC", "VOLTAGE_AC", "CURRENT_DC", "CURRENT_AC", "CURRENT_LOOP_4_20MA",
    "DIGITAL", "RTD", "THERMOCOUPLE", "FREQUENCY",
}


@dataclass
class Check:
    level: str   # ERROR | WARNING | INFO
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


def validate_channel(cfg: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    input_type = (cfg.get("input_type") or "").upper()
    conditioning = (cfg.get("signal_conditioning") or "DIRECT").upper()
    nominal = cfg.get("nominal_circuit_voltage_v")
    max_rated = cfg.get("max_rated_input")
    isolation = cfg.get("isolation_rating_v")
    ratio = cfg.get("conditioning_ratio") or 1.0

    if input_type not in INPUT_TYPES:
        checks.append(Check("ERROR", "INPUT_TYPE",
                            f"Unknown input type {input_type!r}. Expected one of: "
                            + ", ".join(sorted(INPUT_TYPES))))
    if max_rated is None:
        checks.append(Check("ERROR", "NO_RATING",
                            "Maximum rated input must be declared for this channel."))
    if nominal is None:
        checks.append(Check("WARNING", "NO_NOMINAL",
                            "Nominal circuit voltage is not declared, so the input rating "
                            "cannot be checked against the circuit."))

    if nominal is not None:
        if nominal > settings.direct_input_voltage_limit_v and conditioning == "DIRECT":
            checks.append(Check(
                "ERROR", "DIRECT_CONNECTION_REFUSED",
                f"A direct input cannot be bound to a {nominal:g} V circuit. Above "
                f"{settings.direct_input_voltage_limit_v:g} V the signal must arrive through a "
                "rated PT/VT, CT or isolating transducer, and that device must be declared here.",
            ))
        if conditioning in ISOLATING_DEVICES and ratio <= 1.0 and nominal > 240:
            checks.append(Check(
                "WARNING", "RATIO_SUSPECT",
                f"Signal conditioning is declared as {conditioning} but the ratio is {ratio:g}:1. "
                "Confirm the transformer/transducer ratio.",
            ))
        if max_rated is not None:
            at_input = nominal / ratio if ratio else nominal
            if at_input > max_rated:
                checks.append(Check(
                    "ERROR", "OVER_RANGE",
                    f"Expected {at_input:.4g} {cfg.get('max_rated_input_unit', 'V')} at the input "
                    f"after conditioning, which exceeds the channel's {max_rated:g} rating.",
                ))
        if isolation is not None and isolation < nominal:
            checks.append(Check(
                "ERROR", "ISOLATION_INSUFFICIENT",
                f"Channel isolation rating ({isolation:g} V) is below the circuit's nominal "
                f"voltage ({nominal:g} V).",
            ))
        if isolation is None and nominal > settings.direct_input_voltage_limit_v:
            checks.append(Check("ERROR", "NO_ISOLATION_RATING",
                                "Isolation rating must be declared for a channel bound to a "
                                "circuit above the direct-input limit."))
        if nominal >= MEDIUM_VOLTAGE_THRESHOLD_V:
            checks.append(Check("INFO", "MEDIUM_VOLTAGE", MV_SAFETY_NOTICE))

    due = cfg.get("calibration_due_at")
    if due:
        due_dt = due if isinstance(due, datetime) else datetime.fromisoformat(str(due))
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=utcnow().tzinfo)
        if due_dt < utcnow():
            checks.append(Check("WARNING", "CALIBRATION_OVERDUE",
                                f"Calibration was due {due_dt.date()}. Measurements from this "
                                "channel are recorded but flagged."))
    elif cfg.get("calibrated_at") is None:
        checks.append(Check("WARNING", "NO_CALIBRATION",
                            "No calibration record for this channel."))

    return checks


def blocking(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.level == "ERROR"]
