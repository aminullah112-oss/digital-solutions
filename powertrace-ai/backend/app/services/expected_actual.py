"""Deterministic expected-vs-actual comparison.

No heuristics, no AI.  Given an expectation and a measurement, this returns
NORMAL, MARGINAL, ABNORMAL, or — importantly — NOT_MEASURED, which is a
distinct outcome and not a pass.

Absent a measurement the result is NOT_MEASURED even when the controller says
the output is on.  A controller reporting DO-07 energized tells you what the
controller intends, not what is on the terminal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain import ComparisonResult, DataSource, Quality

#: Absolute tolerance floor, so a 0 V expectation still has a usable band.
#: A few hundred millivolts covers ordinary leakage and meter offset on a
#: de-energized 24 V control circuit.
DEFAULT_ZERO_BAND_V = 0.5
#: Inside this fraction of the tolerance band the result is MARGINAL rather
#: than NORMAL — worth a second look, not a callout.
MARGINAL_FRACTION = 0.8


@dataclass
class Expectation:
    value: float | None
    unit: str = "V"
    tolerance_pct: float = 10.0
    absolute_band: float | None = None
    signal_type: str = "DC"
    reference: str = ""
    basis: str = ""  # where the expectation came from: drawing, nameplate, user

    def band(self) -> float:
        if self.absolute_band is not None:
            return abs(self.absolute_band)
        if self.value is None:
            return 0.0
        return max(abs(self.value) * self.tolerance_pct / 100.0, DEFAULT_ZERO_BAND_V)


@dataclass
class Comparison:
    result: ComparisonResult
    reason: str
    expected: dict[str, Any] | None
    actual: dict[str, Any] | None
    deviation: float | None = None
    deviation_pct: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "reason": self.reason,
            "expected": self.expected,
            "actual": self.actual,
            "deviation": self.deviation,
            "deviation_pct": self.deviation_pct,
        }


def compare(
    expectation: Expectation | None,
    measured_value: float | None,
    *,
    measured_unit: str = "V",
    measured_quality: Quality = Quality.GOOD,
    measured_source: DataSource = DataSource.MEASURED,
    measured_at: str | None = None,
) -> Comparison:
    expected_payload = None
    if expectation and expectation.value is not None:
        band = expectation.band()
        expected_payload = {
            "value": expectation.value,
            "unit": expectation.unit,
            "tolerance_pct": expectation.tolerance_pct,
            "band": band,
            "min": expectation.value - band,
            "max": expectation.value + band,
            "signal_type": expectation.signal_type,
            "reference": expectation.reference,
            "source": DataSource.EXPECTATION.value,
            "basis": expectation.basis,
        }

    actual_payload = None
    if measured_value is not None:
        actual_payload = {
            "value": measured_value,
            "unit": measured_unit,
            "quality": measured_quality.value,
            "source": measured_source.value,
            "timestamp": measured_at,
        }

    if measured_value is None:
        return Comparison(
            ComparisonResult.NOT_MEASURED,
            "No physical measurement available for this point.",
            expected_payload, None,
        )
    if measured_source in (DataSource.CONTROLLER, DataSource.SCHEMATIC, DataSource.INFERENCE):
        # Guard rail: a controller-reported state is not a measurement and must
        # not be fed into a voltage comparison.
        return Comparison(
            ComparisonResult.NOT_MEASURED,
            f"Value is {measured_source.value}, not a physical measurement; "
            "comparison against an expected voltage is not valid.",
            expected_payload, actual_payload,
        )
    if measured_quality in (Quality.BAD, Quality.TIMEOUT, Quality.UNKNOWN):
        return Comparison(
            ComparisonResult.NOT_MEASURED,
            f"Measurement quality is {measured_quality.value}.",
            expected_payload, actual_payload,
        )
    if expectation is None or expectation.value is None:
        return Comparison(
            ComparisonResult.NO_EXPECTATION,
            "No engineering expectation configured for this point.",
            expected_payload, actual_payload,
        )
    if expectation.unit and measured_unit and expectation.unit != measured_unit:
        return Comparison(
            ComparisonResult.NO_EXPECTATION,
            f"Unit mismatch: expected {expectation.unit}, measured {measured_unit}.",
            expected_payload, actual_payload,
        )

    band = expectation.band()
    deviation = measured_value - expectation.value
    deviation_pct = (deviation / expectation.value * 100.0) if expectation.value else None

    if abs(deviation) <= band * MARGINAL_FRACTION:
        result, reason = ComparisonResult.NORMAL, "Within configured tolerance."
    elif abs(deviation) <= band:
        result, reason = (
            ComparisonResult.MARGINAL,
            "Within tolerance but near the limit.",
        )
    else:
        result, reason = (
            ComparisonResult.ABNORMAL,
            f"Outside tolerance: expected {expectation.value}{expectation.unit} "
            f"±{band:.3g}, measured {measured_value}{measured_unit}.",
        )
    return Comparison(result, reason, expected_payload, actual_payload,
                      round(deviation, 4), round(deviation_pct, 2) if deviation_pct else None)
