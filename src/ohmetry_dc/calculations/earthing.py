"""Preliminary earthing screening: grid resistance (IEEE 80 Sverak equation), ground potential rise, and tolerable touch voltage.

Soil resistivity and grid geometry are PLACEHOLDERS. This is a screening estimate, not an earthing design: mesh and step voltages are not
calculated, soil layering is ignored, and the grid current split factor is taken as 1 (conservative).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ohmetry_dc.models import ConfigError, ProjectConfig


def grid_resistance(rho: float, area_m2: float, length_m: float, depth_m: float) -> float:
    """Rg = rho [1/LT + 1/sqrt(20 A) (1 + 1/(1 + h sqrt(20/A)))]."""
    return rho * (1.0 / length_m + 1.0 / math.sqrt(20 * area_m2) * (1 + 1 / (1 + depth_m * math.sqrt(20 / area_m2))))


def surface_layer_factor(rho: float, rho_s: float, h_s: float) -> float:
    """Cs = 1 - 0.09 (1 - rho/rho_s) / (2 hs + 0.09)."""
    return 1 - 0.09 * (1 - rho / rho_s) / (2 * h_s + 0.09)


def tolerable_touch_v(rho_s: float, cs: float, t_s: float, body_kg: int = 70) -> float:
    coef = 0.157 if body_kg == 70 else 0.116
    return (1000 + 1.5 * cs * rho_s) * coef / math.sqrt(t_s)


def tolerable_step_v(rho_s: float, cs: float, t_s: float, body_kg: int = 70) -> float:
    coef = 0.157 if body_kg == 70 else 0.116
    return (1000 + 6 * cs * rho_s) * coef / math.sqrt(t_s)


class MissingInputs(ConfigError):
    def __init__(self, ids: list[str]):
        super().__init__("Missing inputs: " + ", ".join(ids))
        self.ids = ids


@dataclass
class EarthingResult:
    system_type: str
    rho: float
    grid_resistance_ohm: float
    gpr_v: float | None
    tolerable_touch_v: float | None
    tolerable_step_v: float | None
    screening: str                  # PASS, WARNING or NOT VERIFIED
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _num(cfg: ProjectConfig, pid: str):
    v = cfg.value(pid) if pid in cfg.parameters else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def assess_earthing(cfg: ProjectConfig) -> EarthingResult:
    sys_t = cfg.optional_value("earthing.earthing_system_type")
    rho, a, l, h = (_num(cfg, f"earthing.{k}") if k == "soil_resistivity" else _num(cfg, f"earthing_study.{k}") for k in ("soil_resistivity", "grid_area_m2", "grid_conductor_length_m", "grid_burial_depth_m"))
    req = (("earthing.earthing_system_type", sys_t), ("earthing.soil_resistivity", rho), ("earthing_study.grid_area_m2", a), ("earthing_study.grid_conductor_length_m", l), ("earthing_study.grid_burial_depth_m", h))
    if any(v is None for _, v in req):
        raise MissingInputs([k for k, v in req if v is None])
    rg = grid_resistance(rho, a, l, h)
    ig, ts, rs, hs = (_num(cfg, f"earthing_study.{k}") for k in ("earth_fault_current_ka", "fault_clearing_time_s", "surface_layer_resistivity_ohm_m", "surface_layer_thickness_m"))
    miss = [f"earthing_study.{k}" for k, x in (("earth_fault_current_ka", ig), ("fault_clearing_time_s", ts), ("surface_layer_resistivity_ohm_m", rs), ("surface_layer_thickness_m", hs)) if x is None]
    gpr = ig * 1000 * rg if ig is not None else None
    touch = step = None
    if None not in (ts, rs, hs) and ts > 0:
        cs = surface_layer_factor(rho, rs, hs)
        touch, step = tolerable_touch_v(rs, cs, ts), tolerable_step_v(rs, cs, ts)
    if gpr is None or touch is None:
        screening = "NOT VERIFIED"
    else:
        screening = "PASS" if gpr <= touch else "WARNING"
    notes = ["Grid resistance uses the IEEE 80 Sverak equation with a uniform soil. Soil layering, rods and the grid current split factor are not modelled.",
             "A ground potential rise at or below the tolerable touch voltage is a screening pass only. A higher value needs a detailed mesh and step voltage calculation, not a rejection.",
             "Soil resistivity and grid geometry are placeholders. A real project needs a Wenner-method soil survey.",
             f"System earthing {sys_t}: earth-fault loop impedance and disconnection times need the protective device data (manufacturer) and are NOT VERIFIED."]
    return EarthingResult(str(sys_t), rho, rg, gpr, touch, step, screening, miss, notes)
