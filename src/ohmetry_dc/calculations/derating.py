"""Derating of continuous ratings for ambient temperature, altitude and installation.

The factors come from the manufacturer and are inputs. This module never derives or invents one. The derated continuous rating is
rating x ambient factor x altitude factor x installation factor, and percentage loading is always taken against that derated rating.
"""
from __future__ import annotations

from dataclasses import dataclass

from ohmetry_dc.models import ConfigError, ProjectConfig


@dataclass(frozen=True)
class Derating:
    ambient: float
    altitude: float
    installation: float

    def __post_init__(self):
        for name in ("ambient", "altitude", "installation"):
            v = getattr(self, name)
            if not (0 < v <= 1):
                raise ConfigError(f"The {name} derating factor must be above 0 and at most 1 (a derating cannot raise a rating); got {v}")

    @property
    def combined(self) -> float:
        return self.ambient * self.altitude * self.installation

    def derate(self, rating: float) -> float:
        return rating * self.combined


def derating_for(cfg: ProjectConfig, equipment: str) -> Derating:
    """equipment is 'transformer', 'ups' or 'generator'."""
    vals = []
    for kind in ("ambient", "altitude", "installation"):
        pid = f"derating.{equipment}_{kind}_factor"
        v = cfg.value(pid)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise ConfigError(f"Derating needs '{pid}', which is missing. Enter the manufacturer's factor (1.00 only if the manufacturer confirms no derating).")
        vals.append(float(v))
    return Derating(*vals)
