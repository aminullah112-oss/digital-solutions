"""Distribution engineering framework: cable sizing, voltage drop, busducts and switchgear data checks.

Cable current ratings, busduct and switchgear ratings, impedances and short-circuit ratings are manufacturer or standard data. This module
never derives or invents them. Where they are missing it reports the REQUIRED value so the engineer can check it against the data sheet or
table, and the status is NOT VERIFIED. Conductor resistance is derived from resistivity (a physical relationship). Reactance is an input.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ohmetry_dc.models import Category, ConfigError, ProjectConfig

from .load import LoadEstimate
from .sizing import LoadingStatus, PowerSystemSizing

# Conductor constants at 20 degC. Reference values (the same constants as the Ohmetry calculators). Verify against the standard in use.
CONDUCTORS = {"copper": (0.017241, 0.00393), "aluminium": (0.028264, 0.00403)}      # resistivity (ohm.mm2/m), temperature coefficient (1/degC)


def resistance_ohm_per_m(conductor: str, cross_section_mm2: float, temperature_c: float) -> float:
    """R = rho20 x (1 + alpha x (T - 20)) / A, in ohm per metre of one conductor."""
    try:
        rho, alpha = CONDUCTORS[conductor.lower()]
    except KeyError:
        raise ConfigError(f"Unknown conductor material '{conductor}' (use copper or aluminium)") from None
    if cross_section_mm2 <= 0:
        raise ConfigError("The conductor cross-section must be above zero")
    return rho * (1 + alpha * (temperature_c - 20.0)) / cross_section_mm2


def voltage_drop_three_phase(current_a: float, length_m: float, r_ohm_per_m: float, x_ohm_per_m: float, power_factor: float, voltage_v: float) -> tuple[float, float]:
    """Line-to-line voltage drop in volts and percent: sqrt(3) x I x L x (R cos(phi) + X sin(phi))."""
    if not 0 < power_factor <= 1:
        raise ConfigError("The power factor must be above 0 and at most 1")
    sinphi = math.sqrt(1 - power_factor ** 2)
    dv = math.sqrt(3) * current_a * length_m * (r_ohm_per_m * power_factor + x_ohm_per_m * sinphi)
    return dv, dv / voltage_v * 100.0


def classify_max(loading_pct: float, limit_pct: float | None) -> LoadingStatus:
    """PASS up to the limit, FAIL above it. There is no warning band for these items. A missing limit gives NOT VERIFIED."""
    if limit_pct is None:
        return LoadingStatus.NOT_VERIFIED
    return LoadingStatus.FAIL if loading_pct > limit_pct + 1e-9 else LoadingStatus.PASS


@dataclass
class ItemResult:
    tag: str
    kind: str                       # cable, busduct, switchgear
    description: str
    design_current_a: float
    basis: str
    voltage_v: float
    derating_total: float
    required_rating_a: float                       # rated or tabulated current needed per run or per unit, after derating
    rating_a: float | None                         # the supplied rating (manufacturer or table), if any
    loading_pct: float | None
    loading_status: LoadingStatus
    runs: int = 1
    required_runs: int | None = None
    voltage_drop_pct: float | None = None
    voltage_drop_v: float | None = None
    voltage_drop_status: LoadingStatus = LoadingStatus.NOT_VERIFIED
    short_circuit_status: LoadingStatus = LoadingStatus.NOT_VERIFIED
    missing_data: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class DistributionResult:
    cables: list[ItemResult]
    busducts: list[ItemResult]
    switchgear: list[ItemResult]
    limits: dict


def _num(cfg: ProjectConfig, pid: str):
    v = cfg.value(pid) if pid in cfg.parameters else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _voltage_v(cfg: ProjectConfig, ref: str) -> float:
    v = _num(cfg, ref)
    if v is None:
        raise ConfigError(f"The voltage '{ref}' is missing")
    return v * 1000.0 if cfg.get(ref).unit.lower() == "kv" else v


def design_current(basis: str, cfg: ProjectConfig, est: LoadEstimate, sizing: PowerSystemSizing, voltage_v: float) -> float:
    """Design current in amps for a named basis. Every basis is a worst credible contingency (the other path lost) unless stated."""
    root3 = math.sqrt(3)
    g = 1 + est.growth_pct / 100.0
    if basis == "transformer_path_out_load":
        w = {s.id: s for s in sizing.transformer.scenarios}.get("TX-PATH-OUT")
        if w is None:
            raise ConfigError("The transformer sizing could not be built, so no transformer design current exists")
        return w.load * 1000 / (root3 * voltage_v)
    if basis == "generator_rated":
        r = sizing.generator.rating_each
        if r is None:
            raise ConfigError("The generator rating is missing, so no generator current exists")
        return r * 1000 / (root3 * voltage_v)
    it = [i for i in est.items if i.category == Category.IT_CRITICAL.value]
    if basis == "ups_output_path_out":
        return math.hypot(sum(i.demand_kw for i in it), sum(i.demand_kvar for i in it)) * g * 1000 / (root3 * voltage_v)
    if basis == "ups_input_path_out":
        eta, pf = est.ups_efficiency_pct / 100.0, _num(cfg, "equipment.ups_input_power_factor")
        if not pf:
            raise ConfigError("The UPS input power factor (equipment.ups_input_power_factor) is missing")
        return sum(i.demand_kw for i in it) * g / eta / pf * 1000 / (root3 * voltage_v)
    if basis == "mechanical_path_out":
        m = [i for i in est.items if i.category == Category.MECHANICAL_COOLING.value]
        return math.hypot(sum(i.demand_kw for i in m), sum(i.demand_kvar for i in m)) * g * 1000 / (root3 * voltage_v)
    raise ConfigError(f"Unknown design_current_basis '{basis}'")


def _derate(d: dict) -> float:
    t = 1.0
    for k, v in d.items():
        if not isinstance(v, (int, float)) or not 0 < v <= 1:
            raise ConfigError(f"The derating factor '{k}' must be above 0 and at most 1; got {v!r}")
        t *= float(v)
    return t


def assess_distribution(cfg: ProjectConfig, est: LoadEstimate, sizing: PowerSystemSizing) -> DistributionResult:
    dist = cfg.distribution or {}
    vd_limit = _num(cfg, "design_criteria.voltage_drop_limit_pct")
    limits = {"voltage_drop_pct": vd_limit, "cable_max_loading_pct": _num(cfg, "design_criteria.cable_max_loading"),
              "busduct_max_loading_pct": _num(cfg, "design_criteria.busduct_max_loading"), "switchgear_max_loading_pct": _num(cfg, "design_criteria.switchgear_max_loading")}
    temp = _num(cfg, "cable_data.conductor_operating_temperature")
    cables: list[ItemResult] = []
    for f in dist.get("feeders") or []:
        v = _voltage_v(cfg, f["voltage_ref"])
        i_total = design_current(f["design_current_basis"], cfg, est, sizing, v)
        n = int(f["parallel_runs"])
        if n < 1:
            raise ConfigError(f"{f['tag']}: parallel_runs must be at least 1")
        k = _derate(f.get("derating") or {})
        per_run = i_total / n
        req = i_total / (n * k)
        tab = f.get("tabulated_rating_a")
        miss: list[str] = []
        notes = [f"Required tabulated current rating per run, after derating: {req:,.0f} A. Compare it with the cable table or data sheet for the installation method; no rating is assumed."]
        if tab is None:
            miss.append(f"{f['tag']}.tabulated_rating_a")
            load_pct, ls, req_runs = None, LoadingStatus.NOT_VERIFIED, None
        else:
            load_pct = per_run / (tab * k) * 100
            ls = classify_max(load_pct, limits["cable_max_loading_pct"])
            req_runs = math.ceil(i_total / (tab * k) - 1e-9)
        x_per_km = _num(cfg, f["reactance_ref"])
        if temp is None or x_per_km is None:
            vdp = vdv = None
            vs = LoadingStatus.NOT_VERIFIED
            miss.append("cable_data.conductor_operating_temperature / reactance")
        else:
            r = resistance_ohm_per_m(f["conductor"], f["cross_section_mm2"], temp)
            vdv, vdp = voltage_drop_three_phase(per_run, f["length_m"], r, x_per_km / 1000.0, f["power_factor"], v)
            vs = classify_max(vdp, vd_limit)
        notes.append("Voltage drop uses resistance derived from resistivity at the stated conductor temperature and a placeholder reactance. It is preliminary.")
        cables.append(ItemResult(f["tag"], "cable", f["description"], i_total, f["design_current_basis"], v, k, req, tab, load_pct, ls, n, req_runs, vdp, vdv, vs, LoadingStatus.NOT_VERIFIED, miss, notes))

    busducts: list[ItemResult] = []
    for b in dist.get("busducts") or []:
        v = _voltage_v(cfg, b["voltage_ref"])
        i_total = design_current(b["design_current_basis"], cfg, est, sizing, v)
        k = _derate(b.get("derating") or {})
        req = i_total / k
        rated = b.get("rated_current_a")
        miss = [f"{b['tag']}.{f}" for f in ("rated_current_a", "resistance_ohm_per_km", "reactance_ohm_per_km", "short_circuit_withstand_ka") if b.get(f) is None]
        load_pct = None if rated is None else i_total / (rated * k) * 100
        ls = LoadingStatus.NOT_VERIFIED if rated is None else classify_max(load_pct, limits["busduct_max_loading_pct"])
        vdp = vdv = None
        vs = LoadingStatus.NOT_VERIFIED
        if b.get("resistance_ohm_per_km") is not None and b.get("reactance_ohm_per_km") is not None:
            vdv, vdp = voltage_drop_three_phase(i_total, b["length_m"], b["resistance_ohm_per_km"] / 1000.0, b["reactance_ohm_per_km"] / 1000.0, b["power_factor"], v)
            vs = classify_max(vdp, vd_limit)
        sc = LoadingStatus.NOT_VERIFIED
        busducts.append(ItemResult(b["tag"], "busduct", b["description"], i_total, b["design_current_basis"], v, k, req, rated, load_pct, ls, 1, None, vdp, vdv, vs, sc, miss,
                                   [f"Required rated current after derating: {req:,.0f} A. The short-circuit withstand must exceed the Stage 5 fault level. Manufacturer data is required for all ratings."]))

    sw: list[ItemResult] = []
    for s in dist.get("switchgear") or []:
        v = _voltage_v(cfg, s["voltage_ref"])
        i_total = design_current(s["incomer_basis"], cfg, est, sizing, v)
        k = _derate(s.get("derating") or {})
        req = i_total / k
        rated = s.get("rated_current_a")
        miss = [f"{s['tag']}.{f}" for f in ("rated_current_a", "short_circuit_rating_ka", "form_of_separation", "ip_rating", "verification_evidence") if s.get(f) is None]
        load_pct = None if rated is None else i_total / (rated * k) * 100
        ls = LoadingStatus.NOT_VERIFIED if rated is None else classify_max(load_pct, limits["switchgear_max_loading_pct"])
        label = "IEC 61439" if s["voltage_class"] == "LV" else "IEC 62271"
        sw.append(ItemResult(s["tag"], "switchgear", s["description"], i_total, s["incomer_basis"], v, k, req, rated, load_pct, ls, 1, None, None, None, LoadingStatus.NOT_VERIFIED, LoadingStatus.NOT_VERIFIED, miss,
                             [f"Required busbar rated current after derating: {req:,.0f} A. {label} verification evidence, the short-circuit rating (from the Stage 5 fault study), separation and IP rating are manufacturer data."]))
    return DistributionResult(cables, busducts, sw, limits)
