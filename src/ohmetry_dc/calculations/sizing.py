"""Preliminary sizing and contingency loading of transformers, UPS and generators.

Policy (configurable in design_criteria): above the preferred target gives WARNING, above the maximum gives FAIL, both taken against the
DERATED continuous rating in the worst CREDIBLE contingency. Short-duration overload capability is never used. These are preliminary Ohmetry
design policies, not IEC acceptance limits. Every result here is preliminary and needs manufacturer data and engineering verification.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum

from ohmetry_dc.models import ConfigError, ProjectConfig

from .derating import Derating, derating_for
from .load import LoadEstimate, PathLoad


class LoadingStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    NOT_VERIFIED = "NOT VERIFIED"
    NOT_APPLICABLE = "NOT APPLICABLE"


@dataclass(frozen=True)
class Policy:
    target_pct: float | None
    limit_pct: float | None


def classify(loading: float, policy: Policy) -> LoadingStatus:
    """loading is a fraction of the derated continuous rating."""
    if policy.target_pct is None or policy.limit_pct is None:
        return LoadingStatus.NOT_VERIFIED
    eps = 1e-9  # exactly at a limit is not above it; this only absorbs floating-point noise
    if loading * 100 > policy.limit_pct + eps:
        return LoadingStatus.FAIL
    if loading * 100 > policy.target_pct + eps:
        return LoadingStatus.WARNING
    return LoadingStatus.PASS


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    credible: bool
    load: float                  # kVA or kW, as stated by the sizing's unit
    units_available: int
    capacity_each: float         # derated continuous rating of one unit, same unit as load
    capacity_total: float
    loading: float               # fraction of the derated capacity
    status: LoadingStatus
    note: str = ""


@dataclass
class Sizing:
    equipment: str
    metric: str                  # "kVA" or "kW"
    policy: Policy
    derating: dict
    rating_each: float | None
    derated_each: float | None
    units_per_path: int | None
    scenarios: list[Scenario] = field(default_factory=list)
    worst_credible: Scenario | None = None
    nameplate_loading_worst: float | None = None   # the worst credible case as a fraction of the nameplate (not derated) rating, shown beside the derated figure
    required_derated_each_for_target: float | None = None
    required_derated_each_for_limit: float | None = None
    required_rating_each_for_target: float | None = None
    required_rating_each_for_limit: float | None = None
    suggested_size_for_target: float | None = None
    suggested_size_for_limit: float | None = None
    missing_data: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def status(self) -> LoadingStatus:
        if self.worst_credible is None:
            return LoadingStatus.NOT_VERIFIED
        return self.worst_credible.status


def _num(cfg: ProjectConfig, pid: str):
    v = cfg.value(pid) if pid in cfg.parameters else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _sizes(cfg: ProjectConfig, pid: str) -> list[float]:
    raw = cfg.value(pid) if pid in cfg.parameters else None
    if not isinstance(raw, str):
        return []
    try:
        return sorted(float(x) for x in raw.split(",") if x.strip())
    except ValueError:
        raise ConfigError(f"{pid} must be a comma-separated list of numbers") from None


def _next_size(required: float | None, sizes: list[float]) -> float | None:
    if required is None:
        return None
    return next((s for s in sizes if s >= required - 1e-9), None)


def _policy(cfg: ProjectConfig, key: str) -> Policy:
    return Policy(_num(cfg, f"design_criteria.{key}_target_loading"), _num(cfg, f"design_criteria.{key}_max_loading"))


def _units_per_path(cfg: ProjectConfig, total_id: str | None, per_path_id: str | None = None) -> int | None:
    paths = _num(cfg, "redundancy.power_paths")
    if per_path_id:
        v = _num(cfg, per_path_id)
        return int(v) if v else None
    q = _num(cfg, total_id) if total_id else None
    if not q or not paths or q % paths:
        return None
    return int(q / paths)


def _scale(load: PathLoad, growth: float) -> tuple[float, float, float]:
    f = 1 + growth / 100.0
    return load.kw * f, load.kvar * f, math.hypot(load.kw, load.kvar) * f


def _essential(cfg: ProjectConfig, est: LoadEstimate) -> tuple[PathLoad, PathLoad, PathLoad]:
    """Load the generators carry (items flagged on_generator, UPS losses by the IT share on the generator, distribution losses on that load)."""
    from ohmetry_dc.models import Category

    t = math.tan(math.acos(_num(cfg, "general.design_power_factor")))
    items = [r for r in est.items if r.on_generator]
    it_total = est.it_demand_kw
    it_on = sum(r.demand_kw for r in items if r.category == Category.IT_CRITICAL.value)
    ups_share = it_on / it_total if it_total else 0.0
    d = est.distribution_loss_pct / 100.0

    def build(weight) -> PathLoad:
        kw = sum(r.demand_kw * weight(r) for r in items) + est.ups_loss.kw * ups_share * sum(
            r.demand_kw * weight(r) for r in est.items if r.category == Category.IT_CRITICAL.value and r.on_generator) / max(it_on, 1e-12)
        kvar = sum(r.demand_kvar * weight(r) for r in items) + est.ups_loss.kvar * ups_share * sum(
            r.demand_kw * weight(r) for r in est.items if r.category == Category.IT_CRITICAL.value and r.on_generator) / max(it_on, 1e-12)
        dist = d * kw
        return PathLoad(kw + dist, kvar + dist * t)

    total, a = build(lambda r: 1.0), build(lambda r: r.path_a_fraction)
    return total, a, PathLoad(total.kw - a.kw, total.kvar - a.kvar)


def _scenarios(kind: str, per_path: int, normal_path: tuple[float, float], total: tuple[float, float], double_credible: bool, redundant_unit: bool,
               capacity_each: float, policy: Policy, metric_index: int, contingency_factor: float = 1.0) -> list[Scenario]:
    """Build the scenarios for per_path units in each of two paths. normal_path and total are (kW, kVA); metric_index 0 selects kW, 1 selects kVA."""
    out: list[Scenario] = []

    def add(sid, desc, load, units, credible, factor=1.0, note=""):
        cap_each = capacity_each * factor
        cap_total = cap_each * units
        loading = load / cap_total if cap_total > 0 else math.inf
        status = classify(loading, policy) if credible else LoadingStatus.NOT_APPLICABLE
        out.append(Scenario(sid, desc, credible, load, units, cap_each, cap_total, loading, status, note))

    pn, tt = normal_path[metric_index], total[metric_index]
    add(f"{kind}-NORMAL", "Normal operation: the more heavily loaded path on its own units", pn, per_path, True)
    add(f"{kind}-PATH-OUT", "Loss of the other path: the surviving path carries the whole load", tt, per_path, True, contingency_factor,
        "Contingency derating factor applied" if contingency_factor != 1.0 else "")
    if redundant_unit and per_path >= 2:
        add(f"{kind}-UNIT-OUT", "Loss of one unit (N+1): the path load on the remaining units", pn, per_path - 1, True)
        add(f"{kind}-PATH-OUT-UNIT-OUT", "Loss of the other path and one unit (combined contingency: N+1 engine-out on the surviving path)", tt, per_path - 1, double_credible, contingency_factor,
            "" if double_credible else "Informational: not judged against the limits (redundancy.double_contingency_credible is False)")
    return out


def _finish(s: Sizing, sizes: list[float], pid_sizes: str, cfg: ProjectConfig) -> Sizing:
    cred = [x for x in s.scenarios if x.credible]
    s.worst_credible = max(cred, key=lambda x: x.loading) if cred else None
    if s.worst_credible and s.rating_each and s.derated_each:
        w = s.worst_credible
        s.nameplate_loading_worst = w.loading * s.derated_each / s.rating_each
    p = s.policy
    if cred and s.derating:
        need = lambda pct: max(x.load / (x.units_available * (x.capacity_each / s.derated_each)) / (pct / 100.0) for x in cred) if pct else None
        s.required_derated_each_for_target = need(p.target_pct)
        s.required_derated_each_for_limit = need(p.limit_pct)
        comb = s.derating["combined"]
        s.required_rating_each_for_target = s.required_derated_each_for_target / comb if s.required_derated_each_for_target else None
        s.required_rating_each_for_limit = s.required_derated_each_for_limit / comb if s.required_derated_each_for_limit else None
        lst = _sizes(cfg, pid_sizes) if pid_sizes else []
        s.suggested_size_for_target = _next_size(s.required_rating_each_for_target, lst)
        s.suggested_size_for_limit = _next_size(s.required_rating_each_for_limit, lst)
    return s


def size_transformers(cfg: ProjectConfig, est: LoadEstimate) -> Sizing:
    rating, n = _num(cfg, "equipment.transformer_rating"), _units_per_path(cfg, "equipment.transformer_quantity")
    policy = _policy(cfg, "transformer")
    s = Sizing("transformer", "kVA", policy, {}, rating, None, n)
    s.notes += ["Loading is taken against the derated continuous rating. Short-duration emergency overload (for example IEC 60076-7) is not used to justify continuous loading.",
                "The surviving transformer is evaluated under loss of the other supply path with the contingency derating factor."]
    if rating is None or n is None:
        s.missing_data.append("equipment.transformer_rating / equipment.transformer_quantity / redundancy.power_paths (quantity must divide evenly between paths)")
        return s
    der = derating_for(cfg, "transformer")
    s.derating = {**asdict(der), "combined": der.combined}
    s.derated_each = der.derate(rating)
    g = est.growth_pct
    a, b = _scale(est.path_a, g), _scale(est.path_b, g)
    normal = (max(a[0], b[0]), max(a[2], b[2]))
    total = _scale(PathLoad(est.facility_kw, est.facility_kvar), g)
    s.scenarios = _scenarios("TX", n, normal, (total[0], total[2]), bool(cfg.value("redundancy.double_contingency_credible")), True, s.derated_each, policy, 1,
                             _num(cfg, "derating.transformer_contingency_factor") or 1.0)
    s.missing_data += [pid for pid in ("equipment.transformer_impedance",) if _num(cfg, pid) is None]
    s.notes.append("Transformer impedance, losses, cooling class and the manufacturer's loading guide are manufacturer data: " + ("pending." if s.missing_data else "present as an assumption."))
    return _finish(s, [], "equipment.transformer_size_list_kva", cfg)


def size_ups(cfg: ProjectConfig, est: LoadEstimate) -> tuple[Sizing, Sizing]:
    from ohmetry_dc.models import Category

    rating_kw, rating_kva, n = _num(cfg, "equipment.ups_rating"), _num(cfg, "equipment.ups_rating_kva"), _units_per_path(cfg, "equipment.ups_quantity")
    policy = _policy(cfg, "ups")
    kw_s, kva_s = Sizing("ups", "kW", policy, {}, rating_kw, None, n), Sizing("ups", "kVA", policy, {}, rating_kva, None, n)
    note = "Both the kW and kVA limits are checked. Overload capability is not used. Each UPS is assumed to carry the whole critical load when the other path is lost (2N)."
    kw_s.notes.append(note)
    kva_s.notes.append(note)
    if None in (rating_kw, rating_kva, n):
        for s in (kw_s, kva_s):
            s.missing_data.append("equipment.ups_rating / equipment.ups_rating_kva / equipment.ups_quantity")
        return kw_s, kva_s
    if cfg.value("redundancy.ups_topology") != "2N":
        for s in (kw_s, kva_s):
            s.notes.append("Only the 2N topology is implemented. Other topologies are not assessed.")
            s.missing_data.append("redundancy.ups_topology (only 2N is implemented)")
        return kw_s, kva_s
    der = derating_for(cfg, "ups")
    f = 1 + est.growth_pct / 100.0
    it = [r for r in est.items if r.category == Category.IT_CRITICAL.value]
    pa = (sum(r.demand_kw * r.path_a_fraction for r in it) * f, sum(r.demand_kvar * r.path_a_fraction for r in it) * f)
    pb = (sum(r.demand_kw * (1 - r.path_a_fraction) for r in it) * f, sum(r.demand_kvar * (1 - r.path_a_fraction) for r in it) * f)
    tot = (sum(r.demand_kw for r in it) * f, sum(r.demand_kvar for r in it) * f)
    kva = lambda p: math.hypot(*p)
    dbl = bool(cfg.value("redundancy.double_contingency_credible"))
    for s, rating, mi, normal, total in ((kw_s, rating_kw, 0, (max(pa[0], pb[0]), max(kva(pa), kva(pb))), (tot[0], kva(tot))),
                                         (kva_s, rating_kva, 1, (max(pa[0], pb[0]), max(kva(pa), kva(pb))), (tot[0], kva(tot)))):
        s.derating = {**asdict(der), "combined": der.combined}
        s.derated_each = der.derate(rating)
        s.scenarios = _scenarios("UPS", n, normal, total, dbl, True, s.derated_each, policy, mi)
        _finish(s, [], "equipment.ups_size_list_kw", cfg)
    # the size list is in kW, so a kVA suggestion assumes a unity output power factor only when the kVA rating equals the kW rating
    if rating_kva != rating_kw:
        kva_s.suggested_size_for_target = kva_s.suggested_size_for_limit = None
        kva_s.notes.append("Size suggestions are given for kW only because the kVA and kW ratings differ.")
    return kw_s, kva_s


def size_generators(cfg: ProjectConfig, est: LoadEstimate, metric: str = "kVA") -> Sizing:
    """metric 'kVA' checks the alternator rating, 'kW' checks the engine rating (kVA rating x rated power factor, a placeholder)."""
    basis = str(cfg.value("generators.rating_basis") or "").upper()
    policy = _policy(cfg, "generator")
    n = _units_per_path(cfg, None, "equipment.generator_quantity_per_path")
    pid = {"PRP": "equipment.generator_rating", "ESP": "equipment.generator_esp_rating", "COP": "equipment.generator_cop_rating"}.get(basis)
    s = Sizing("generator", metric, policy, {}, None, None, n)
    confirmed = bool(cfg.optional_value("generators.rating_basis_confirmed"))
    s.notes += [f"Rating basis: {basis or 'not set'}" + ("" if confirmed else ", ASSUMED and NOT confirmed by manufacturer documentation") + ". PRP (Prime Power), ESP (Emergency Standby Power) and COP (Continuous Power) are different ISO 8528 ratings and are not interchangeable.",
                "PRP is the default basis. ESP is selectable but should not be relied on for prolonged outages.",
                "No overload capability is used. Final selection must be verified against manufacturer data for load steps, UPS interaction, harmonics, altitude and ambient temperature.",
                "Lightly loaded generators need the manufacturer's minimum-load guidance. A low loading percentage is not automatically better."]
    if pid is None:
        s.missing_data.append("generators.rating_basis must be PRP, ESP or COP")
        return s
    rating = _num(cfg, pid)
    s.rating_each = rating
    if rating is None:
        s.missing_data.append(f"{pid} (rating for the {basis} basis)")
    if n is None:
        s.missing_data.append("equipment.generator_quantity_per_path")
    pf = _num(cfg, "equipment.generator_rating_power_factor")
    if metric == "kW":
        if pf is None:
            s.missing_data.append("equipment.generator_rating_power_factor")
        elif rating is not None:
            s.rating_each = rating * pf
    if rating is None or n is None or (metric == "kW" and pf is None):
        return s
    der = derating_for(cfg, "generator")
    s.derating = {**asdict(der), "combined": der.combined}
    s.derated_each = der.derate(s.rating_each)
    total, a, b = _essential(cfg, est)
    g = est.growth_pct
    ta, aa, bb = _scale(total, g), _scale(a, g), _scale(b, g)
    redundant = "N+1" in str(cfg.value("redundancy.generator_concept"))
    mi = 0 if metric == "kW" else 1
    s.scenarios = _scenarios("GEN", n, (max(aa[0], bb[0]), max(aa[2], bb[2])), (ta[0], ta[2]), bool(cfg.value("redundancy.double_contingency_credible")), redundant, s.derated_each, policy, mi)
    for pid_m in ("generators.prp_max_average_load_factor_pct", "generators.operating_hours_restriction", "generators.max_step_load_pct", "generators.max_frequency_dip_pct",
                  "generators.max_voltage_dip_pct", "generators.ups_rectifier_walk_in_s", "generators.ups_input_current_thd_pct", "generators.overload_capability"):
        if pid_m in cfg.parameters and cfg.value(pid_m) is None:
            s.missing_data.append(pid_m)
    return _finish(s, [], "equipment.generator_size_list_kva" if metric == "kVA" else "", cfg)


@dataclass
class StepBlock:
    id: str
    description: str
    step_kva: float
    cumulative_kva: float
    percent_of_running_capacity: float


@dataclass
class StepLoadRequirements:
    blocks: list[StepBlock]
    running_capacity_kva: float | None
    max_step_load_pct: float | None
    largest_step_pct: float | None
    status: LoadingStatus
    requirements: list[str]
    note: str


def generator_step_loads(cfg: ProjectConfig, est: LoadEstimate, gen: Sizing) -> StepLoadRequirements:
    """Upper-bound load steps on the generators after an outage, and the manufacturer data the transient verification needs.

    Each block is assumed to be applied at once at its steady-state demand. That ignores soft starting, UPS rectifier walk-in and sequencing,
    so it is an upper bound. The status is NOT VERIFIED regardless: transient performance needs the manufacturer's data and analysis.
    """
    from ohmetry_dc.models import Category

    requirements = ["Manufacturer maximum single load step (%) at the site conditions", "Frequency and voltage dip limits of the loads and the UPS during a step",
                    "UPS rectifier walk-in time and input harmonic current on generator supply", "Generator transient response (frequency and voltage recovery) for the proposed step sequence",
                    "Motor starting current and method for each mechanical load", "Harmonic voltage distortion with the UPS rectifier load, and the effect on the alternator rating"]
    note = "Upper bound: each block applied at once at its steady-state demand. Soft starting, rectifier walk-in and sequencing are not modelled."
    running = gen.worst_credible.capacity_total if gen.worst_credible else None
    total, a, b = _essential(cfg, est)
    f = 1 + est.growth_pct / 100.0
    t = math.tan(math.acos(_num(cfg, "general.design_power_factor")))
    items = [r for r in est.items if r.on_generator]
    groups = [("STEP-1", "UPS input (IT load and UPS losses)", [Category.IT_CRITICAL.value]), ("STEP-2", "Mechanical and cooling plant", [Category.MECHANICAL_COOLING.value]),
              ("STEP-3", "Lighting, small power and auxiliary", [Category.LIGHTING_SMALL_POWER.value, Category.AUXILIARY.value])]
    blocks: list[StepBlock] = []
    cum_kw = cum_kvar = 0.0
    it_on = sum(r.demand_kw for r in items if r.category == Category.IT_CRITICAL.value)
    for sid, desc, cats in groups:
        kw = sum(r.demand_kw for r in items if r.category in cats)
        kvar = sum(r.demand_kvar for r in items if r.category in cats)
        if Category.IT_CRITICAL.value in cats and est.it_demand_kw:
            share = it_on / est.it_demand_kw
            kw += est.ups_loss.kw * share
            kvar += est.ups_loss.kvar * share
        kw *= 1 + est.distribution_loss_pct / 100.0
        kvar += kw * (est.distribution_loss_pct / 100.0) / (1 + est.distribution_loss_pct / 100.0) * t
        step = math.hypot(kw * f, kvar * f)
        cum_kw += kw * f
        cum_kvar += kvar * f
        blocks.append(StepBlock(sid, desc, step, math.hypot(cum_kw, cum_kvar), (step / running * 100) if running else math.nan))
    mx = _num(cfg, "generators.max_step_load_pct")
    largest = max((b.percent_of_running_capacity for b in blocks), default=None) if running else None
    status = LoadingStatus.NOT_VERIFIED
    if mx is not None and largest is not None and largest > mx:
        status = LoadingStatus.WARNING
        note += f" The largest block ({largest:.1f} %) exceeds the manufacturer's single-step limit ({mx:g} %). Sequencing is needed."
    return StepLoadRequirements(blocks, running, mx, largest, status, requirements, note)


@dataclass
class BatteryInterface:
    autonomy_min: float | None
    ups_output_kw: float
    energy_at_ups_output_kwh: float | None
    indicative_nominal_energy_kwh: float | None
    status: LoadingStatus
    missing_data: list[str]
    notes: list[str]


def size_battery(cfg: ProjectConfig, est: LoadEstimate) -> BatteryInterface:
    """The interface only. Battery sizing needs the manufacturer's constant-power discharge data, which is never assumed."""
    from ohmetry_dc.models import Category

    f = 1 + est.growth_pct / 100.0
    it_kw = sum(r.demand_kw for r in est.items if r.category == Category.IT_CRITICAL.value) * f   # worst credible: one UPS carries all IT load
    t = _num(cfg, "redundancy.battery_autonomy")
    e_out = it_kw * t / 60.0 if t else None
    required = ["battery.dc_bus_voltage_v", "battery.inverter_efficiency_pct", "battery.end_of_life_capacity_factor", "battery.temperature_correction_factor",
                "battery.design_margin_factor", "battery.constant_power_discharge_data"]
    missing = [p for p in required if p in cfg.parameters and cfg.value(p) is None]
    indicative = None
    eta, eol, temp, margin = (_num(cfg, p) for p in required[1:5])
    if e_out is not None and None not in (eta, eol, temp, margin):
        indicative = e_out / (eta / 100.0) / (eol * temp) * margin
    notes = ["Energy at the UPS output = critical load x autonomy. It is arithmetic, not a battery size.",
             "A battery is sized from the manufacturer's constant-power discharge table (W per cell to the end-of-discharge voltage at the autonomy time), at the end-of-life and temperature conditions. That data is missing, so no battery is sized.",
             "String configuration, DC bus voltage and cell count cannot be determined without it."]
    if indicative is not None:
        notes.append("An indicative nominal energy is shown because the correction factors were supplied. It ignores the discharge-rate dependence of capacity and must not be used to select a battery.")
    return BatteryInterface(t, it_kw, e_out, indicative, LoadingStatus.NOT_VERIFIED, missing, notes)


@dataclass
class PowerSystemSizing:
    transformer: Sizing
    ups_kw: Sizing
    ups_kva: Sizing
    generator: Sizing
    generator_kw: Sizing
    generator_steps: StepLoadRequirements
    battery: BatteryInterface


def size_power_system(cfg: ProjectConfig, est: LoadEstimate) -> PowerSystemSizing:
    tx = size_transformers(cfg, est)
    ukw, ukva = size_ups(cfg, est)
    gen = size_generators(cfg, est)
    return PowerSystemSizing(tx, ukw, ukva, gen, size_generators(cfg, est, "kW"), generator_steps=generator_step_loads(cfg, est, gen), battery=size_battery(cfg, est))
