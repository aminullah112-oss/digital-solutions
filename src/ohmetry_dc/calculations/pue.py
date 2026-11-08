"""Power usage effectiveness (PUE), with its definition and limits stated.

Definition used here: PUE = total facility power / IT equipment power, both at the design point (kW).
This is a design-point power ratio. The metric as normally reported is an energy ratio over a period (usually a year),
which depends on IT utilisation, climate and operating modes that this model does not simulate. The two are not the same number.
"""
from __future__ import annotations


def pue(total_facility_kw: float, it_kw: float) -> float:
    if it_kw <= 0:
        raise ValueError("IT power must be above zero to calculate PUE")
    if total_facility_kw < it_kw:
        raise ValueError("Total facility power cannot be below the IT power")
    return total_facility_kw / it_kw
