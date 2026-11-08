"""Preliminary short-circuit levels, IEC 60909 method (maximum, three-phase, far-from-generator treatment for the utility).

A case is calculated only when ALL its inputs are supplied. Missing inputs are listed and no default is substituted.
The result is a screening level for equipment ratings, not a study. Motor contribution, cable and busduct impedance, and the minimum fault level are not included (see notes).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ohmetry_dc.models import ConfigError, ProjectConfig

ROOT3 = math.sqrt(3)


def peak_factor(x_r: float) -> float:
    """IEC 60909 kappa = 1.02 + 0.98 exp(-3 R/X)."""
    return 1.02 + 0.98 * math.exp(-3.0 / x_r)


def thermal_factor(kappa: float, t_s: float, f_hz: float) -> float:
    """sqrt(m + n) with n = 1: m is the heat effect of the DC component."""
    if kappa <= 1.0 + 1e-9:
        return 1.0
    ln = math.log(kappa - 1.0)
    m = (math.exp(4 * f_hz * t_s * ln) - 1.0) / (2 * f_hz * t_s * ln)
    return math.sqrt(m + 1.0)


def _z(mag: float, x_r: float) -> complex:
    """Impedance of magnitude mag with the given X/R ratio."""
    r = mag / math.sqrt(1 + x_r ** 2)
    return complex(r, r * x_r)


@dataclass
class FaultCase:
    name: str
    description: str
    ik_ka: float
    ip_ka: float | None
    ith_ka: float | None
    x_r: float | None


@dataclass
class ShortCircuitResult:
    mv_case: FaultCase | None
    lv_cases: list[FaultCase]            # calculated cases only
    design_lv: FaultCase | None          # the case that sets the LV rating, None unless every required case could be calculated
    design_mv: FaultCase | None
    parallel_allowed: bool
    clearing_time_s: float | None
    unavailable: dict[str, list[str]]    # case name -> missing parameter ids
    notes: list[str]


def _num(cfg: ProjectConfig, pid: str):
    v = cfg.value(pid) if pid in cfg.parameters else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _case(name, desc, ik_a, x_r, t, f) -> FaultCase:
    ik = ik_a / 1000.0
    if x_r is None or t is None:
        return FaultCase(name, desc, ik, None, None, x_r)
    k = peak_factor(x_r)
    return FaultCase(name, desc, ik, k * math.sqrt(2) * ik, thermal_factor(k, t, f) * ik, x_r)


def _need(cfg: ProjectConfig, ids: list[str]) -> tuple[dict, list[str]]:
    vals = {i: _num(cfg, i) for i in ids}
    return vals, [i for i, v in vals.items() if v is None]


def assess_short_circuit(cfg: ProjectConfig) -> ShortCircuitResult:
    common = ["electrical_system.frequency", "short_circuit.assumed_clearing_time_s"]
    cv, cm = _need(cfg, common)
    f, t = cv["electrical_system.frequency"], cv["short_circuit.assumed_clearing_time_s"]
    unavailable: dict[str, list[str]] = {}
    mv_case = lv_u = lv_g = lv_bound = None

    # MV bus: utility only
    v, miss = _need(cfg, ["short_circuit.utility_fault_level_mva", "short_circuit.utility_x_r_ratio", "short_circuit.voltage_factor_c_max_mv", "electrical_system.mv_supply_voltage"])
    un_mv = None
    if "electrical_system.mv_supply_voltage" in v and v["electrical_system.mv_supply_voltage"] is not None:
        un_mv = v["electrical_system.mv_supply_voltage"] * (1000.0 if cfg.get("electrical_system.mv_supply_voltage").unit.lower() == "kv" else 1.0)
    if miss:
        unavailable["MV bus, utility"] = miss
    else:
        skq, xr, cmv = v["short_circuit.utility_fault_level_mva"] * 1e6, v["short_circuit.utility_x_r_ratio"], v["short_circuit.voltage_factor_c_max_mv"]
        zq_mv = _z(cmv * un_mv ** 2 / skq, xr)
        mv_case = _case("Utility at the MV bus", "Utility source only", cmv * un_mv / (ROOT3 * abs(zq_mv)), xr, t, f)

    # LV bus. The transformer data is common to the utility case and the transformer-limited bound.
    tx_ids = ["equipment.transformer_rating", "equipment.transformer_impedance", "short_circuit.voltage_factor_c_max_lv", "electrical_system.lv_line_voltage"]
    tv, tmiss = _need(cfg, tx_ids)
    k_t = zt_mag = None
    if not tmiss:
        un_lv, clv = tv["electrical_system.lv_line_voltage"], tv["short_circuit.voltage_factor_c_max_lv"]
        uk = tv["equipment.transformer_impedance"] / 100.0
        k_t = 0.95 * clv / (1 + 0.6 * uk)
        zt_mag = uk * un_lv ** 2 / (tv["equipment.transformer_rating"] * 1000.0) * k_t
        lv_bound = _case("Transformer-limited upper bound", f"Infinite source behind one transformer (K_T = {k_t:.4f}). No utility data is used, so the UTILITY contribution through one transformer cannot exceed this for any utility fault level. Generator and motor contributions are not included: this is NOT the LV bus fault level and NOT a design value, and no rating is selected from it",
                         clv * un_lv / (ROOT3 * zt_mag), None, t, f)
    else:
        unavailable["LV bus, transformer-limited upper bound"] = tmiss
    um = ["short_circuit.transformer_x_r_ratio", "short_circuit.utility_fault_level_mva", "short_circuit.utility_x_r_ratio", "short_circuit.voltage_factor_c_max_mv"]
    uv, umiss = _need(cfg, um)
    umiss = tmiss + [m for m in umiss if m not in tmiss] + ([] if un_mv is not None else ["electrical_system.mv_supply_voltage"])
    if not umiss:
        zq = _z(uv["short_circuit.voltage_factor_c_max_mv"] * un_mv ** 2 / (uv["short_circuit.utility_fault_level_mva"] * 1e6), uv["short_circuit.utility_x_r_ratio"]) * (un_lv / un_mv) ** 2
        ztot = zq + _z(zt_mag, uv["short_circuit.transformer_x_r_ratio"])
        lv_u = _case("Utility and one transformer", f"Utility through one transformer (K_T = {k_t:.4f})", clv * un_lv / (ROOT3 * abs(ztot)), ztot.imag / ztot.real, t, f)
    else:
        unavailable["LV bus, utility and one transformer"] = umiss
    gm = ["equipment.generator_rating", "equipment.generator_quantity_per_path", "short_circuit.generator_subtransient_reactance_pct", "short_circuit.generator_x_r_ratio",
          "equipment.generator_rating_power_factor", "short_circuit.voltage_factor_c_max_lv", "electrical_system.lv_line_voltage"]
    gv, gmiss = _need(cfg, gm)
    if not gmiss:
        un_lv, clv, n = gv["electrical_system.lv_line_voltage"], gv["short_circuit.voltage_factor_c_max_lv"], int(gv["equipment.generator_quantity_per_path"])
        xd = gv["short_circuit.generator_subtransient_reactance_pct"] / 100.0
        k_g = clv / (1 + xd * math.sqrt(1 - gv["equipment.generator_rating_power_factor"] ** 2))
        zg = _z(xd * un_lv ** 2 / (gv["equipment.generator_rating"] * 1000.0), gv["short_circuit.generator_x_r_ratio"]) * k_g / n
        lv_g = _case(f"{n} generators", f"All {n} generators of one path in parallel (K_G = {k_g:.4f})", clv * un_lv / (ROOT3 * abs(zg)), gv["short_circuit.generator_x_r_ratio"], t, f)
    else:
        unavailable["LV bus, generators"] = gmiss
    if cm:
        unavailable["Peak and thermal values (all cases)"] = cm

    allowed = bool(cfg.optional_value("short_circuit.generator_parallel_with_utility"))
    cases = [c for c in (lv_bound, lv_u, lv_g) if c is not None]
    design = None
    if lv_u is not None and lv_g is not None:
        if allowed:
            par = FaultCase("Utility and generators in parallel", "Arithmetic sum of the two contributions: a conservative upper bound", lv_u.ik_ka + lv_g.ik_ka,
                            None if None in (lv_u.ip_ka, lv_g.ip_ka) else lv_u.ip_ka + lv_g.ip_ka, None if None in (lv_u.ith_ka, lv_g.ith_ka) else lv_u.ith_ka + lv_g.ith_ka, None)
            cases.append(par)
            design = par
        else:
            design = max((lv_u, lv_g), key=lambda c: c.ik_ka)
            cases.append(FaultCase("Utility and generators in parallel (not the design case)", "Shown only to indicate what closed transition would cost", lv_u.ik_ka + lv_g.ik_ka,
                                   None if None in (lv_u.ip_ka, lv_g.ip_ka) else lv_u.ip_ka + lv_g.ip_ka, None if None in (lv_u.ith_ka, lv_g.ith_ka) else lv_u.ith_ka + lv_g.ith_ka, None))
    notes = ["Maximum three-phase level at the busbars, IEC 60909 method. Cable and busduct impedance between the transformer and the bus are ignored, which is conservative.",
             "Motor contribution (the mechanical plant motors) is not included. It adds to the LV level and needs motor data.",
             "Minimum fault current, needed for protection sensitivity, is not calculated."]
    return ShortCircuitResult(mv_case, cases, design, mv_case, allowed, t, unavailable, notes)


def cable_min_section_mm2(ith_ka_per_run: float, t_s: float, k: float) -> float:
    """Adiabatic equation: S >= I sqrt(t) / k."""
    return ith_ka_per_run * 1000.0 * math.sqrt(t_s) / k
