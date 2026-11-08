"""Design-basis consistency checks.

These flag inconsistencies in the preliminary configuration. They do not force the configuration to look consistent, and a
check that needs a design limit that has not been supplied returns NOT VERIFIED with the computed value, never PASS.
"""
from __future__ import annotations

import math

from ohmetry_dc.models import ProjectConfig

from .status import CheckResult, CheckStatus

S = CheckStatus


def _n(cfg: ProjectConfig, pid: str):
    v = cfg.value(pid)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _missing(cfg: ProjectConfig, ids: list[str]) -> list[str]:
    return [i for i in ids if _n(cfg, i) is None]


def check_required_inputs(cfg: ProjectConfig) -> list[CheckResult]:
    missing = cfg.missing()
    user = [p.id for p in missing if p.status.value == "USER_INPUT"]
    manuf = [p.id for p in cfg.parameters.values() if p.status.value == "MANUFACTURER_DATA" and p.missing and p.needed_from_stage <= cfg.project.current_stage]
    other = [p.id for p in missing if p.status.value not in ("USER_INPUT", "MANUFACTURER_DATA")]
    stage = cfg.project.current_stage
    r1 = CheckResult("required_user_inputs", f"Inputs needed up to Stage {stage} are supplied", S.FAIL if (user or other) else S.PASS,
                     f"{len(user) + len(other)} required input(s) missing: {', '.join(user + other)}" if (user or other) else "All required user inputs for the current stage are present.",
                     {"missing": user + other}, "Supply the missing inputs in config/project_config.yaml or config/load_schedule.yaml." if (user or other) else "")
    r2 = CheckResult("manufacturer_data_pending", f"Manufacturer data needed up to Stage {stage} is supplied", S.NOT_VERIFIED if manuf else S.PASS,
                     f"{len(manuf)} manufacturer data item(s) pending: {', '.join(manuf)}" if manuf else "No manufacturer data is pending for the current stage.",
                     {"pending": manuf}, "Obtain the data sheets and enter the values with their source." if manuf else "")
    deferred = cfg.deferred()
    r3 = CheckResult("inputs_deferred", "Inputs needed in later stages", S.NOT_VERIFIED if deferred else S.PASS,
                     "; ".join(f"{p.id} (Stage {p.needed_from_stage})" for p in deferred) if deferred else "Nothing is deferred.",
                     {"deferred": [{"id": p.id, "stage": p.needed_from_stage} for p in deferred]},
                     "Supply these before the stage that needs them. Release stays blocked from approval while any remain." if deferred else "")
    return [r1, r2, r3]


def check_pue_arithmetic(cfg: ProjectConfig) -> CheckResult:
    ids = ["general.it_critical_load", "general.target_pue", "general.estimated_facility_demand"]
    miss = _missing(cfg, ids)
    if miss:
        return CheckResult("pue_arithmetic", "Facility demand equals IT load times target PUE", S.NOT_VERIFIED, f"Missing: {', '.join(miss)}.")
    it, pue, dem = (_n(cfg, i) for i in ids)
    exp = it * pue
    rel = abs(dem - exp) / exp
    ok = rel <= 0.005  # 0.5 %: rounding of the stated figures, not an engineering limit
    return CheckResult("pue_arithmetic", "Facility demand equals IT load times target PUE", S.PASS if ok else S.FAIL,
                       f"{it:g} kW x {pue:g} = {exp:,.1f} kW against {dem:g} kW stated ({rel * 100:.2f} % apart)." + ("" if ok else " The stated demand does not follow from the IT load and PUE; it is not adjusted automatically."),
                       {"it_kw": it, "target_pue": pue, "expected_demand_kw": exp, "stated_demand_kw": dem, "difference_pct": rel * 100},
                       "" if ok else "Correct the stated demand or the PUE; the Stage 2 load model will replace the estimate.")


def check_phase_voltage_relation(cfg: ProjectConfig) -> CheckResult:
    miss = _missing(cfg, ["electrical_system.lv_line_voltage", "electrical_system.lv_phase_voltage"])
    if miss:
        return CheckResult("lv_phase_relation", "LV line and phase voltages are consistent", S.NOT_VERIFIED, f"Missing: {', '.join(miss)}.")
    vll, vph = _n(cfg, "electrical_system.lv_line_voltage"), _n(cfg, "electrical_system.lv_phase_voltage")
    ratio = vll / vph
    rel = abs(ratio - math.sqrt(3)) / math.sqrt(3)
    ok = rel <= 0.02  # nominal voltages are rounded, so a 2 % tolerance on the square-root-of-3 relation
    return CheckResult("lv_phase_relation", "LV line and phase voltages are consistent", S.PASS if ok else S.FAIL,
                       f"{vll:g} V / {vph:g} V = {ratio:.3f} against sqrt(3) = {math.sqrt(3):.3f}.", {"ratio": ratio, "sqrt3": math.sqrt(3)})


def check_voltage_frequency(cfg: ProjectConfig) -> CheckResult:
    title = "LV voltage and frequency pairing"
    miss = _missing(cfg, ["electrical_system.lv_line_voltage", "electrical_system.frequency"])
    if miss:
        return CheckResult("lv_voltage_frequency", title, S.NOT_VERIFIED, f"Missing: {', '.join(miss)}.")
    v, f = _n(cfg, "electrical_system.lv_line_voltage"), _n(cfg, "electrical_system.frequency")
    basis_param = cfg.parameters.get("electrical_system.voltage_frequency_basis")
    basis = basis_param.value if basis_param is not None else None
    vals = {"lv_line_voltage_v": v, "frequency_hz": f}
    if v == 400 and f == 60:
        if basis:
            return CheckResult("lv_voltage_frequency", title, S.NOT_VERIFIED,
                               "400/230 V at 60 Hz is an unusual pairing. The project owner's decision is recorded and has not been independently verified: " + str(basis), vals,
                               "For a real project, obtain the serving utility's written confirmation.")
        return CheckResult("lv_voltage_frequency", title, S.WARNING,
                           "400/230 V is commonly associated with 50 Hz systems, and 60 Hz systems commonly use other LV levels. This is a heuristic, not a verified rule.", vals,
                           "Confirm the nominal LV voltage and frequency with the serving utility, record the basis in electrical_system.voltage_frequency_basis, or correct the configuration.")
    return CheckResult("lv_voltage_frequency", title, S.NOT_VERIFIED, "No mismatch pattern was found by the heuristic. The pairing still has to be confirmed with the serving utility.", vals, "Confirm with the serving utility.")


def _per_path(cfg: ProjectConfig, qty_id: str):
    paths = _n(cfg, "redundancy.power_paths")
    qty = _n(cfg, qty_id)
    if paths is None or qty is None or paths <= 0:
        return None
    return qty / paths


def check_equipment_vs_paths(cfg: ProjectConfig) -> CheckResult:
    paths = _n(cfg, "redundancy.power_paths")
    bad = []
    for pid in ("equipment.transformer_quantity", "equipment.ups_quantity"):
        q = _n(cfg, pid)
        if q is None or paths is None:
            return CheckResult("equipment_vs_paths", "Equipment quantities divide evenly between power paths", S.NOT_VERIFIED, "Missing quantities or number of paths.")
        if q % paths:
            bad.append(f"{pid} = {q:g}")
    return CheckResult("equipment_vs_paths", "Equipment quantities divide evenly between power paths", S.WARNING if bad else S.PASS,
                       f"Not divisible by {paths:g} paths: {', '.join(bad)}." if bad else f"Transformer and UPS quantities divide evenly between {paths:g} paths.", {"paths": paths})


def check_transformer_current(cfg: ProjectConfig) -> CheckResult:
    miss = _missing(cfg, ["equipment.transformer_rating", "electrical_system.lv_line_voltage"])
    if miss:
        return CheckResult("transformer_secondary_current", "Transformer secondary full-load current", S.NOT_VERIFIED, f"Missing: {', '.join(miss)}.")
    s, v = _n(cfg, "equipment.transformer_rating"), _n(cfg, "electrical_system.lv_line_voltage")
    i = s * 1000 / (math.sqrt(3) * v)
    return CheckResult("transformer_secondary_current", "Transformer secondary full-load current", S.NOT_VERIFIED,
                       f"{s:g} kVA at {v:g} V gives {i:,.0f} A. Whether LV switchgear and busduct exist at this current, and the prospective fault level, must be verified in Stages 4 and 5. No limit is applied here.",
                       {"rating_kva": s, "lv_voltage_v": v, "full_load_current_a": i}, "Verify LV equipment availability and fault level with manufacturer data.")


_STATUS = {"PASS": S.PASS, "WARNING": S.WARNING, "FAIL": S.FAIL, "NOT VERIFIED": S.NOT_VERIFIED, "NOT APPLICABLE": S.NOT_APPLICABLE}


def _sizing_result(cid: str, title: str, sz, unit: str) -> CheckResult:
    """One check per piece of equipment: the status is that of the worst credible contingency, against the derated rating."""
    if sz.worst_credible is None:
        return CheckResult(cid, title, S.NOT_VERIFIED, "Not assessed: " + "; ".join(sz.missing_data or ["no credible scenario could be built"]), {"missing": sz.missing_data},
                           "Supply the missing data.")
    w = sz.worst_credible
    pol = sz.policy
    np = f" Against the nameplate rating it is {sz.nameplate_loading_worst * 100:.1f} %, shown for information only: the status uses the derated rating." if sz.nameplate_loading_worst is not None else ""
    cont = "within" if w.loading * 100 <= pol.limit_pct + 1e-9 else "ABOVE"
    detail = (f"Worst credible case {w.id}: {w.load:,.0f} {unit} on {w.units_available} x {w.capacity_each:,.0f} {unit} derated = {w.capacity_total:,.0f} {unit}, loading {w.loading * 100:.1f} % of the site-derated continuous rating "
              f"(target {pol.target_pct:g} %, maximum {pol.limit_pct:g} %), {cont} the maximum.{np} Preliminary: derating factors are placeholders, no overload used. ")
    if sz.required_rating_each_for_target:
        detail += f"Rating per unit to meet the target {sz.required_rating_each_for_target:,.0f} {unit}" + (f" (suggested size {sz.suggested_size_for_target:,.0f})" if sz.suggested_size_for_target else "") + ". "
    values = {"worst_scenario": w.id, "loading_pct": w.loading * 100, "target_pct": pol.target_pct, "limit_pct": pol.limit_pct, "derating": sz.derating,
              "scenarios": [{"id": x.id, "credible": x.credible, "load": x.load, "units": x.units_available, "capacity_total": x.capacity_total, "loading_pct": x.loading * 100, "status": x.status.value} for x in sz.scenarios],
              "required_rating_each_for_target": sz.required_rating_each_for_target, "required_rating_each_for_limit": sz.required_rating_each_for_limit,
              "suggested_size_for_target": sz.suggested_size_for_target, "missing_manufacturer_data": sz.missing_data}
    action = {"PASS": "", "WARNING": "Above the preferred target: review the concept or accept the exception in the design record.", "FAIL": "Above the maximum continuous loading: revise the concept.",
              "NOT VERIFIED": "Supply the loading policy."}[sz.status.value]
    return CheckResult(cid, title, _STATUS[sz.status.value], detail, values, action)


def check_power_system_sizing(cfg: ProjectConfig) -> list[CheckResult]:
    from ohmetry_dc.calculations import estimate_loads, size_power_system
    from ohmetry_dc.models import ConfigError

    ids = {"transformer_loading": "Transformer loading, worst credible contingency", "ups_loading_kw": "UPS loading in kW, worst credible contingency", "ups_loading_kva": "UPS loading in kVA, worst credible contingency",
           "generator_loading": "Generator loading in kVA, worst credible N+1 contingency", "generator_loading_kw": "Generator loading in kW, worst credible N+1 contingency", "generator_rating_basis": "Generator rating basis confirmed", "generator_step_load": "Generator load steps and transient performance", "generator_prp_load_factor": "Generator PRP load-factor and operating-hour limits",
           "battery_sizing": "Battery sizing", "derating_factors": "Derating factors"}
    try:
        est = estimate_loads(cfg)
        r = size_power_system(cfg, est)
    except ConfigError as e:
        return [CheckResult(i, t, S.NOT_VERIFIED, f"Not assessed: {e}") for i, t in ids.items()]
    out = [_sizing_result("transformer_loading", ids["transformer_loading"], r.transformer, "kVA"), _sizing_result("ups_loading_kw", ids["ups_loading_kw"], r.ups_kw, "kW"),
           _sizing_result("ups_loading_kva", ids["ups_loading_kva"], r.ups_kva, "kVA"), _sizing_result("generator_loading", ids["generator_loading"], r.generator, "kVA"),
           _sizing_result("generator_loading_kw", ids["generator_loading_kw"], r.generator_kw, "kW")]
    confirmed = bool(cfg.optional_value("generators.rating_basis_confirmed"))
    out.append(CheckResult("generator_rating_basis", ids["generator_rating_basis"], S.PASS if confirmed else S.NOT_VERIFIED,
                           (f"The {cfg.value('generators.rating_basis')} rating is confirmed by manufacturer documentation." if confirmed else
                            f"The {cfg.value('equipment.generator_rating'):g} kVA rating is ASSUMED to be a {cfg.value('generators.rating_basis')} rating. Manufacturer documentation has not confirmed it, and it must not be treated as one until it does. The rated power factor ({cfg.optional_value('equipment.generator_rating_power_factor')}) is a placeholder."),
                           {"confirmed": confirmed}, "" if confirmed else "Obtain the generator set data sheet stating the ISO 8528 rating basis, kW and kVA, and site derating."))
    st = r.generator_steps
    out.append(CheckResult("generator_step_load", ids["generator_step_load"], _STATUS[st.status.value],
                           f"Upper-bound steps: " + ", ".join(f"{b.id} {b.step_kva:,.0f} kVA ({b.percent_of_running_capacity:.1f} % of running capacity)" for b in st.blocks) + f". {st.note} Transient performance is not verified: manufacturer step, dip, walk-in and harmonic data are required.",
                           {"blocks": [vars(b) for b in st.blocks], "requirements": st.requirements, "max_step_load_pct": st.max_step_load_pct}, "Obtain the manufacturer's step-load and UPS interaction data."))
    g = r.generator.worst_credible
    lf = f"{g.loading * 100:.1f} %" if g else "not available"
    miss = [p for p in ("generators.prp_max_average_load_factor_pct", "generators.operating_hours_restriction") if cfg.value(p) is None]
    out.append(CheckResult("generator_prp_load_factor", ids["generator_prp_load_factor"], S.NOT_VERIFIED,
                           f"Worst credible loading {lf} is an upper bound on the average load factor during an outage. The manufacturer's average load factor limit and operating-hour restriction for the {str(cfg.value('generators.rating_basis'))} rating are "
                           + ("not yet supplied." if miss else "supplied, but the outage duration and load profile are needed to judge them."), {"missing": miss}, "Record the manufacturer's PRP load factor and hour restrictions."))
    b = r.battery
    out.append(CheckResult("battery_sizing", ids["battery_sizing"], S.NOT_VERIFIED,
                           f"{b.ups_output_kw:,.0f} kW for {b.autonomy_min:g} min is {b.energy_at_ups_output_kwh:,.0f} kWh at the UPS output (arithmetic, not a battery size). No battery is sized without the manufacturer's constant-power discharge data. Missing: {', '.join(b.missing_data) or 'none'}.",
                           {"energy_at_ups_output_kwh": b.energy_at_ups_output_kwh, "missing": b.missing_data}, "Obtain the battery manufacturer's constant-power discharge data."))
    ph = [p.id for p in cfg.parameters.values() if p.id.startswith("derating.") and p.status.value == "ASSUMPTION" and p.value == 1.0]
    out.append(CheckResult("derating_factors", ids["derating_factors"], S.NOT_VERIFIED if ph else S.PASS,
                           (f"{len(ph)} derating factor(s) are placeholders of 1.00 for ideal conditions (30 degC, 0 m): no derating is applied. Replace them with the manufacturer's values at the site conditions: " + ", ".join(ph)) if ph else "Derating factors are supplied.",
                           {"placeholders": ph}, "Obtain the manufacturers' derating data for the site conditions."))
    return out


def _worst(statuses) -> CheckStatus:
    order = [S.FAIL, S.WARNING, S.NOT_VERIFIED, S.PASS]
    mapped = [_STATUS[x.value] if hasattr(x, "value") else x for x in statuses]
    return next((o for o in order if o in mapped), S.NOT_VERIFIED)


def check_distribution(cfg: ProjectConfig) -> list[CheckResult]:
    from ohmetry_dc.calculations import assess_distribution, estimate_loads, size_power_system
    from ohmetry_dc.models import ConfigError

    ids = {"cable_voltage_drop": "Cable voltage drop", "cable_ampacity": "Cable current rating against the design current", "busduct_rating": "Busduct rating against the design current",
           "busduct_voltage_drop": "Busduct voltage drop", "cable_derating_basis": "Cable and busduct derating, installation, parallel arrangement and current sharing", "switchgear_ratings": "Switchgear rated current and verification data", "short_circuit_withstand": "Short-circuit withstand of cables, busducts and switchgear",
           "distribution_selections": "Distribution selections are placeholders"}
    if not cfg.distribution:
        return [CheckResult(i, t, S.NOT_VERIFIED, "No distribution schedule is configured (config/distribution.yaml).") for i, t in ids.items()]
    try:
        est = estimate_loads(cfg)
        r = assess_distribution(cfg, est, size_power_system(cfg, est))
    except ConfigError as e:
        return [CheckResult(i, t, S.NOT_VERIFIED, f"Not assessed: {e}") for i, t in ids.items()]
    lim = r.limits
    line = lambda c: f"{c.tag}: {c.design_current_a:,.0f} A" + (f" on {c.runs} runs ({c.design_current_a / c.runs:,.0f} A per run)" if c.runs > 1 else "")
    vd = r.cables
    out = [CheckResult("cable_voltage_drop", ids["cable_voltage_drop"], _worst([c.voltage_drop_status for c in vd]),
                       "; ".join(f"{line(c)}, drop {c.voltage_drop_pct:.2f} %" if c.voltage_drop_pct is not None else f"{c.tag}: not assessed" for c in vd) +
                       f". Limit {lim['voltage_drop_pct']:g} % (a placeholder criterion). Resistance is derived at the stated conductor temperature; reactance is a placeholder.",
                       {"limit_pct": lim["voltage_drop_pct"], "feeders": [{"tag": c.tag, "voltage_drop_pct": c.voltage_drop_pct, "voltage_drop_v": c.voltage_drop_v, "status": c.voltage_drop_status.value} for c in vd]},
                       "Replace the placeholder reactance and the criterion with project data."),
           CheckResult("cable_ampacity", ids["cable_ampacity"], _worst([c.loading_status for c in vd]),
                       "; ".join(f"{c.tag}: needs {c.required_rating_a:,.0f} A per run after derating" + ("" if c.rating_a is None else f", table {c.rating_a:,.0f} A gives {c.loading_pct:.1f} %") for c in vd) +
                       ". No tabulated rating has been supplied, so none is assumed and the cables cannot be judged. Compare each required rating with the cable table or data sheet for the installation method. "
                       "Where the derating factors are placeholders or the sharing between parallel runs is not supplied, the required rating is a MINIMUM (see cable_derating_basis).",
                       {"feeders": [{"tag": c.tag, "required_rating_per_run_a": c.required_rating_a, "runs": c.runs, "tabulated_rating_a": c.rating_a, "loading_pct": c.loading_pct, "required_runs": c.required_runs,
                                     "status": c.loading_status.value} for c in vd]}, "Supply the tabulated ratings and the real derating factors (grouping, ambient, installation)."),
           _derating_basis_check(ids["cable_derating_basis"], r),
           CheckResult("busduct_rating", ids["busduct_rating"], _worst([c.loading_status for c in r.busducts]),
                       "; ".join(f"{line(c)}, needs {c.required_rating_a:,.0f} A rated after derating" for c in r.busducts) + ". The busduct rating is manufacturer data and is not supplied.",
                       {"items": [{"tag": c.tag, "design_current_a": c.design_current_a, "required_rating_a": c.required_rating_a, "rating_a": c.rating_a, "missing": c.missing_data} for c in r.busducts]}, "Obtain the busduct data sheet."),
           CheckResult("busduct_voltage_drop", ids["busduct_voltage_drop"], _worst([c.voltage_drop_status for c in r.busducts]),
                       "Busduct impedance is manufacturer data and is not supplied, so the voltage drop cannot be calculated.", {}, "Obtain the busduct resistance and reactance."),
           CheckResult("switchgear_ratings", ids["switchgear_ratings"], _worst([c.loading_status for c in r.switchgear]),
                       "; ".join(f"{c.tag}: busbars need {c.required_rating_a:,.0f} A rated (missing: {', '.join(m.split('.')[-1] for m in c.missing_data)})" for c in r.switchgear) +
                       ". Ratings, separation, IP rating and IEC 61439 or IEC 62271 verification evidence are manufacturer data and are not supplied.",
                       {"items": [{"tag": c.tag, "required_rating_a": c.required_rating_a, "rating_a": c.rating_a, "missing": c.missing_data} for c in r.switchgear]}, "Obtain the switchgear data and verification evidence."),
           CheckResult("distribution_selections", ids["distribution_selections"], S.NOT_VERIFIED,
                       "Cable sizes, runs and lengths in config/distribution.yaml are illustrative placeholders. Only path A is modelled; path B is assumed identical by symmetry. A selection is not a verified design.",
                       {}, "Replace with the routed, engineered selections.")]
    return out


def _derating_basis_check(title: str, r) -> CheckResult:
    """Cable, busduct and switchgear derating: never reported as verified while the factors are placeholders."""
    items = [*r.cables, *r.busducts, *r.switchgear]
    parts, rows = [], []
    for c in items:
        bits = []
        if c.kind == "cable":
            bits.append(f"method: {c.installation_method or 'NOT SUPPLIED'}")
            if c.runs > 1:
                bits.append(f"{c.runs} parallel runs, arrangement: {c.parallel_arrangement or 'NOT SUPPLIED'}")
                bits.append("sharing allowance: " + ("NOT SUPPLIED (no allowance included)" if c.sharing_allowance_pct is None else f"{c.sharing_allowance_pct:g} %"))
        if c.derating_unverified:
            bits.append("derating NOT VERIFIED (" + ", ".join(f"{k} {c.derating_factors.get(k, 1.0):.2f}" for k in c.derating_unverified) + ", placeholders)")
        if bits:
            parts.append(f"{c.tag}: " + "; ".join(bits))
        rows.append({"tag": c.tag, "kind": c.kind, "installation_method": c.installation_method, "parallel_runs": c.runs, "parallel_arrangement": c.parallel_arrangement, "sharing_allowance_pct": c.sharing_allowance_pct,
                     "derating_factors": c.derating_factors, "derating_unverified": c.derating_unverified, "required_rating_is_minimum": c.lower_bound})
    n_min = sum(1 for c in items if c.lower_bound)
    return CheckResult("cable_derating_basis", title, S.NOT_VERIFIED,
                       f"{n_min} of {len(items)} required ratings are MINIMUMS: a derating factor of 1.00 is a placeholder, not a verified value, and no allowance for unequal sharing between parallel runs is included. " + " | ".join(parts),
                       {"items": rows}, "Supply the cable table or data sheet reference for each derating factor (grouping, ambient, installation), the layout of the parallel runs and the current-sharing allowance.")


def _pending(cfg: ProjectConfig, ids: list[str]) -> str:
    from ohmetry_dc.reporting.manufacturer_register import explain_missing

    return explain_missing(cfg, ids)


def check_short_circuit(cfg: ProjectConfig) -> list[CheckResult]:
    from ohmetry_dc.calculations.short_circuit import assess_short_circuit, cable_min_section_mm2

    ids = {"short_circuit_levels": "Prospective short-circuit levels", "fault_level_vs_limit": "LV fault level against the practical limit",
           "short_circuit_withstand": "Short-circuit withstand of cables, busducts and switchgear", "cable_thermal_withstand": "Cable thermal withstand against the fault level",
           "protection_devices": "Protection devices: breaking capacity and settings"}
    sc = assess_short_circuit(cfg)
    missing_all = sorted({m for v in sc.unavailable.values() for m in v})
    tried = lambda case: ", ".join(case.name + f" {case.ik_ka:.1f} kA" for case in sc.lv_cases) if sc.lv_cases else "none"
    parts = []
    if sc.mv_case:
        parts.append(f"MV bus {sc.mv_case.ik_ka:.1f} kA.")
    if sc.lv_cases:
        parts.append("LV bus: only the transformer-limited figure is available (" + tried(None) + "). It limits the utility contribution through one transformer and excludes generator and motor contributions, so it is NOT the LV bus fault level and NOT a design value; no rating is selected from it.")
    for case, m in sc.unavailable.items():
        parts.append(f"NOT CALCULATED, {case}: missing {', '.join(m)}.")
    detail = " ".join(parts) + " Engineering impact and the documents needed: " + _pending(cfg, missing_all) if missing_all else " ".join(parts)
    d = sc.design_lv
    out = [CheckResult("short_circuit_levels", ids["short_circuit_levels"], S.NOT_VERIFIED, detail + " " + " ".join(sc.notes) + " A result is NOT VERIFIED until the utility, transformer and generator data are confirmed.",
                       {"mv_ik_ka": sc.mv_case.ik_ka if sc.mv_case else None, "lv_cases": [{"name": c.name, "ik_ka": c.ik_ka, "ip_ka": c.ip_ka, "ith_ka": c.ith_ka} for c in sc.lv_cases],
                        "design_lv_ik_ka": d.ik_ka if d else None, "unavailable": sc.unavailable, "generator_parallel_with_utility": sc.parallel_allowed},
                       "Supply the missing data (see the manufacturer-data register) and rerun.")]
    lim = cfg.optional_value("short_circuit.lv_fault_level_limit_ka")
    bound = next((c for c in sc.lv_cases if c.name.startswith("Transformer-limited")), None)
    if lim is None:
        out.append(CheckResult("fault_level_vs_limit", ids["fault_level_vs_limit"], S.NOT_VERIFIED, "No practical limit is configured (short_circuit.lv_fault_level_limit_ka)."))
    elif d is None and bound is None:
        out.append(CheckResult("fault_level_vs_limit", ids["fault_level_vs_limit"], S.NOT_VERIFIED, "The LV fault level cannot be calculated: required inputs are missing, listed in short_circuit_levels. No default is substituted.", {"limit_ka": lim}, "Supply the missing data."))
    elif d is None:
        st = S.WARNING if bound.ik_ka > lim else S.NOT_VERIFIED
        out.append(CheckResult("fault_level_vs_limit", ids["fault_level_vs_limit"], st,
                               f"Only the transformer-limited figure can be calculated: {bound.ik_ka:.1f} kA, the most that the utility can contribute through one transformer for any utility fault level. " + ("It exceeds" if bound.ik_ka > lim else "It does not exceed") +
                               f" the {lim:g} kA practical limit (Ohmetry preliminary policy), but it excludes the generator and motor contributions, so it does not show that the bus stays below the limit. The design level is NOT CALCULATED: it needs the utility and generator data.", {"bound_ka": bound.ik_ka, "limit_ka": lim}, "Supply the missing data."))
    else:
        par = next((c for c in sc.lv_cases if c.name.startswith("Utility and generators")), None)
        over = d.ik_ka > lim
        extra = "" if par is None or sc.parallel_allowed or par.ik_ka <= lim else f" The parallel case ({par.ik_ka:.1f} kA) exceeds the limit, so the design must prevent the utility and generators from supplying the bus together."
        out.append(CheckResult("fault_level_vs_limit", ids["fault_level_vs_limit"], S.WARNING if over else S.PASS,
                               f"Design LV fault level {d.ik_ka:.1f} kA against a practical limit of {lim:g} kA (Ohmetry preliminary policy, not a standard limit)." + extra,
                               {"design_ik_ka": d.ik_ka, "limit_ka": lim}, "Result stays preliminary until the inputs are confirmed."))
    need_ka = d.ik_ka if d else None
    need_ip = d.ip_ka if d else None
    mv = sc.mv_case
    items = []
    for grp, key in (("busducts", "short_circuit_withstand_ka"), ("switchgear", "short_circuit_rating_ka")):
        for it in (cfg.distribution or {}).get(grp) or []:
            is_mv = str(it.get("voltage_ref", "")).startswith("electrical_system.mv")
            req = (mv.ik_ka if mv else None) if is_mv else need_ka
            rating = it.get(key)
            st = S.NOT_VERIFIED if rating is None or req is None else (S.PASS if rating >= req else S.FAIL)
            items.append({"tag": it["tag"], "required_ka": req, "rating_ka": rating, "status": st.value})
    sts = [S(i["status"]) for i in items]
    out.append(CheckResult("short_circuit_withstand", ids["short_circuit_withstand"], _worst(sts) if sts else S.NOT_VERIFIED,
                           "; ".join(f"{i['tag']}: " + ("required level not calculable" if i["required_ka"] is None else f"needs at least {i['required_ka']:.1f} kA") + ("" if i["rating_ka"] is None else f", rated {i['rating_ka']:g} kA") for i in items) +
                           ". A rating that is not supplied is not assumed, so the item cannot be judged. A peak withstand above the peak current is needed as well.", {"items": items}, "Obtain the short-circuit ratings and the fault levels, then compare."))
    cab = []
    k = cfg.optional_value("short_circuit.cable_short_circuit_k_factor")
    t = sc.clearing_time_s
    for f in (cfg.distribution or {}).get("feeders") or []:
        is_mv = str(f.get("voltage_ref", "")).startswith("electrical_system.mv")
        ith = (mv.ith_ka if mv else None) if is_mv else (d.ith_ka if d else None)
        n = int(f["parallel_runs"])
        s_min = cable_min_section_mm2(ith / n, t, float(k)) if (ith is not None and k and t) else None
        st = S.NOT_VERIFIED if s_min is None else (S.PASS if f["cross_section_mm2"] >= s_min else S.FAIL)
        cab.append({"tag": f["tag"], "min_section_mm2": s_min, "section_mm2": f["cross_section_mm2"], "runs": n, "status": st.value})
    out.append(CheckResult("cable_thermal_withstand", ids["cable_thermal_withstand"], _worst([S(c["status"]) for c in cab]) if cab else S.NOT_VERIFIED,
                           ("; ".join(f"{c['tag']}: needs {c['min_section_mm2']:.0f} mm2 per run, selected {c['section_mm2']:.0f} mm2 on {c['runs']} runs ({c['status']})" for c in cab if c["min_section_mm2"] is not None) or "The fault current is not available, so no cable can be judged.") +
                           f" Adiabatic equation with k = {k} (reference value, verify against the cable data sheet) and an assumed clearing time of {('not supplied' if t is None else format(t, 'g') + ' s')}, a placeholder until the protection study. Fault taken at the bus the cable leaves, split equally over parallel runs.",
                           {"items": cab}, "Supply the fault levels and replace the clearing time with the coordination study result."))
    devs = []
    for dv in (cfg.distribution or {}).get("protection_devices") or []:
        req = (mv.ik_ka if mv else None) if dv["bus"] == "MV" else need_ka
        bc = dv.get("breaking_capacity_ka")
        st = S.NOT_VERIFIED if bc is None or req is None else (S.PASS if bc >= req else S.FAIL)
        devs.append({"tag": dv["tag"], "required_breaking_ka": req, "breaking_ka": bc, "status": st.value})
    out.append(CheckResult("protection_devices", ids["protection_devices"], _worst([S(x["status"]) for x in devs]) if devs else S.NOT_VERIFIED,
                           "; ".join(f"{x['tag']}: " + ("required breaking capacity not calculable" if x["required_breaking_ka"] is None else f"needs breaking {x['required_breaking_ka']:.1f} kA") for x in devs) +
                           ". Device ratings, time-current curves and settings are manufacturer data and are not supplied. Discrimination, arc-flash and sensitivity to minimum fault current are not assessed.", {"devices": devs}, "Obtain device data and curves, then run the coordination study."))
    out.append(CheckResult("arc_flash_scope", "Arc-flash (incident energy) assessment", S.NOT_APPLICABLE,
                           "OUT OF SCOPE for this package. No incident energy, arc-flash boundary, PPE category or label is calculated or implied. It needs a coordination study, protection settings and clearing times from the "
                           "manufacturers' data, to IEEE 1584 or an equivalent method used by a competent person.", {"in_scope": False}, "Commission a separate arc-flash study when the protection design exists."))
    return out


def check_earthing(cfg: ProjectConfig) -> CheckResult:
    from ohmetry_dc.calculations.earthing import MissingInputs, assess_earthing

    title = "Earthing: grid resistance and ground potential rise screening"
    try:
        e = assess_earthing(cfg)
    except MissingInputs as ex:
        return CheckResult("earthing_framework", title, S.NOT_VERIFIED, "NOT CALCULATED. Missing: " + _pending(cfg, ex.ids) + " No default is substituted.", {"missing": ex.ids},
                           "Supply the soil survey and grid design, then rerun.")
    st = {"PASS": S.PASS, "WARNING": S.WARNING}.get(e.screening, S.NOT_VERIFIED)
    det = f"{e.system_type} system. Soil {e.rho:g} ohm.m. Estimated grid resistance {e.grid_resistance_ohm:.2f} ohm."
    if e.gpr_v is not None:
        det += f" Ground potential rise {e.gpr_v:,.0f} V" + (f" against a tolerable touch voltage of {e.tolerable_touch_v:,.0f} V" if e.tolerable_touch_v is not None else "") + "."
    if e.missing:
        det += " Not supplied: " + _pending(cfg, e.missing) + " The safety screening is NOT VERIFIED."
    return CheckResult("earthing_framework", title, st, det + " " + " ".join(e.notes),
                       {"grid_resistance_ohm": e.grid_resistance_ohm, "gpr_v": e.gpr_v, "tolerable_touch_v": e.tolerable_touch_v, "tolerable_step_v": e.tolerable_step_v, "missing": e.missing},
                       "Commission a soil resistivity survey, obtain the earth-fault current and clearing time, then run a detailed grounding study.")


def check_manufacturer_register(cfg: ProjectConfig, register_path=None) -> CheckResult:
    from pathlib import Path

    from ohmetry_dc.reporting.manufacturer_register import build_rows, load_register_meta, problems

    title = "Manufacturer-data register is complete and honest"
    path = Path(register_path) if register_path else Path(cfg.base_dir) / "manufacturer_data_register.yaml"
    if path is None or not path.exists():
        return CheckResult("manufacturer_register", title, S.FAIL, "The manufacturer-data register file (config/manufacturer_data_register.yaml) was not found.", {}, "Create it.")
    meta = load_register_meta(path)
    bad = problems(cfg, meta)
    rows = build_rows(cfg, meta)
    unverified = [r for r in rows if not r.verified_by]
    if bad:
        return CheckResult("manufacturer_register", title, S.FAIL, f"{len(bad)} register defect(s): " + "; ".join(bad[:8]), {"defects": bad}, "Fix the register.")
    return CheckResult("manufacturer_register", title, S.NOT_VERIFIED if unverified else S.PASS,
                       f"The register covers every manufacturer-data item and placeholder ({len(rows)} entries). {len(unverified)} are NOT VERIFIED: "
                       f"{sum(1 for r in rows if r.data_state == 'PENDING')} pending, {sum(1 for r in rows if r.data_state.startswith('PLACEHOLDER'))} placeholders, "
                       f"{sum(1 for r in rows if r.data_state.startswith('DATA SUPPLIED'))} supplied and awaiting review. Placeholders are not validated equipment data.",
                       {"entries": len(rows), "unverified": len(unverified)}, "Obtain the data sheets listed in the register.")


def check_load_model(cfg: ProjectConfig) -> list[CheckResult]:
    from ohmetry_dc.calculations import estimate_loads
    from ohmetry_dc.models import Category, ConfigError

    ids = ("load_it_matches_design_basis", "load_pue_vs_target", "load_demand_vs_initial_estimate", "load_pf_vs_design", "load_path_allocation_consistent")
    titles = {"load_it_matches_design_basis": "IT load in the schedule matches the design basis", "load_pue_vs_target": "Design-point PUE against the target",
              "load_demand_vs_initial_estimate": "Load model against the initial facility demand estimate", "load_pf_vs_design": "Facility power factor against the design assumption",
              "load_path_allocation_consistent": "A/B path allocation adds up to the facility load"}
    try:
        est = estimate_loads(cfg)
    except ConfigError as e:
        return [CheckResult(i, titles[i], S.NOT_VERIFIED, f"The load model could not run: {e}") for i in ids]
    out: list[CheckResult] = []
    it_cfg = _n(cfg, "general.it_critical_load")
    it_sched = sum(i.quantity * (i.unit_rating_kw or 0) for i in cfg.load_items if i.category == Category.IT_CRITICAL)
    ok = it_cfg is not None and abs(it_sched - it_cfg) <= 1e-9 * max(1.0, it_cfg)
    out.append(CheckResult(ids[0], titles[ids[0]], S.PASS if ok else S.FAIL, f"Connected IT load in the schedule {it_sched:,.1f} kW against the design basis {it_cfg} kW.",
                           {"schedule_kw": it_sched, "design_basis_kw": it_cfg}, "" if ok else "Make the IT items agree with general.it_critical_load."))
    target = _n(cfg, "general.target_pue")
    if target is None:
        out.append(CheckResult(ids[1], titles[ids[1]], S.NOT_VERIFIED, f"Design-point PUE {est.pue:.3f}. No target is configured."))
    else:
        out.append(CheckResult(ids[1], titles[ids[1]], S.PASS if est.pue <= target else S.WARNING,
                               f"Design-point PUE {est.pue:.3f} against a target of {target:g}. A design-point power ratio under the stated assumptions, not an annual energy PUE.",
                               {"pue": est.pue, "target": target}, "" if est.pue <= target else "Review the cooling and loss assumptions, or revisit the target."))
    initial = _n(cfg, "general.estimated_facility_demand")
    if initial is None:
        out.append(CheckResult(ids[2], titles[ids[2]], S.NOT_VERIFIED, f"Load model {est.facility_kw:,.1f} kW. No initial estimate is configured."))
    else:
        diff = (est.facility_kw - initial) / initial * 100
        ok = abs(diff) <= 2.0  # a review trigger, not an engineering limit
        out.append(CheckResult(ids[2], titles[ids[2]], S.PASS if ok else S.WARNING,
                               f"Load model {est.facility_kw:,.1f} kW against the initial estimate {initial:g} kW ({diff:+.2f} %). The initial estimate is not adjusted to match. 2 % is a review trigger, not an engineering limit.",
                               {"model_kw": est.facility_kw, "initial_estimate_kw": initial, "difference_pct": diff}, "" if ok else "Replace the initial estimate with the load model result after review."))
    pf = _n(cfg, "general.design_power_factor")
    if pf is None:
        out.append(CheckResult(ids[3], titles[ids[3]], S.NOT_VERIFIED, f"Model power factor {est.power_factor:.3f}. No design power factor is configured."))
    else:
        ok = abs(est.power_factor - pf) <= 0.02  # a review trigger, not an engineering limit
        out.append(CheckResult(ids[3], titles[ids[3]], S.PASS if ok else S.WARNING,
                               f"Facility power factor {est.power_factor:.3f} against the design assumption {pf:g}. 0.02 is a review trigger, not an engineering limit.",
                               {"model_pf": est.power_factor, "design_pf": pf}, "" if ok else "Review the item power factors or the design assumption."))
    a, b = est.path_a, est.path_b
    ok = abs(a.kw + b.kw - est.facility_kw) <= 1e-9 * est.facility_kw and abs(a.kvar + b.kvar - est.facility_kvar) <= 1e-9 * est.facility_kvar
    out.append(CheckResult(ids[4], titles[ids[4]], S.PASS if ok else S.FAIL, f"Path A {a.kw:,.1f} kW + path B {b.kw:,.1f} kW against {est.facility_kw:,.1f} kW. A software consistency check, not an engineering verification.",
                           {"path_a_kw": a.kw, "path_b_kw": b.kw, "facility_kw": est.facility_kw}))
    return out


def run_all_checks(cfg: ProjectConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    results += check_required_inputs(cfg)
    results += [check_pue_arithmetic(cfg), check_phase_voltage_relation(cfg), check_voltage_frequency(cfg), check_equipment_vs_paths(cfg),
                check_transformer_current(cfg)]
    results += check_load_model(cfg)
    results += check_power_system_sizing(cfg)
    results += check_distribution(cfg)
    results += check_short_circuit(cfg)
    results.append(check_earthing(cfg))
    results.append(check_manufacturer_register(cfg))
    from .exceptions import apply_exceptions

    from .verification import apply_verification

    return apply_verification(cfg, apply_exceptions(cfg, results))
