"""Separate calculation validity from design verification.

A calculation that runs on a preliminary assumption can be perfectly valid arithmetic, but it is not evidence that the design works. This module
therefore never lets such a result reach PASS: the calculation result is kept (PASS, WARNING or FAIL, labelled preliminary), and the overall design
status is NOT VERIFIED until every input is reference data, a project decision, or manufacturer or site data that a reviewer has verified.
A preliminary WARNING or FAIL is kept, because an exceedance on an assumed value is still worth seeing.
"""
from __future__ import annotations

from pathlib import Path

from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds

from .status import CheckResult, CheckStatus

LOAD = ["general.it_critical_load", "general.design_power_factor", "general.future_expansion_allowance", "demand_data.it_critical_load_kw", "equipment.ups_efficiency",
        "losses.distribution_loss_fraction"]
CUR = LOAD + ["equipment.transformer_quantity", "equipment.transformer_rating", "equipment.generator_rating", "equipment.generator_quantity_per_path", "equipment.ups_input_power_factor",
              "electrical_system.lv_line_voltage", "electrical_system.mv_supply_voltage"]
SC = ["short_circuit.*", "equipment.transformer_rating", "equipment.transformer_impedance", "equipment.generator_rating", "equipment.generator_quantity_per_path",
      "equipment.generator_rating_power_factor", "electrical_system.lv_line_voltage", "electrical_system.mv_supply_voltage", "electrical_system.frequency"]

# check id -> the inputs its result depends on. "x.*" or "x.y_*" matches a prefix. "@distribution" stands for the placeholder distribution schedule.
# A check that is not listed tests the arithmetic or the input completeness, not the design, and is reported as N/A for verification.
CHECK_INPUTS: dict[str, list[str]] = {
    "transformer_secondary_current": ["equipment.transformer_rating", "electrical_system.lv_line_voltage"],
    "load_pue_vs_target": LOAD + ["general.target_pue"],
    "transformer_loading": LOAD + ["equipment.transformer_quantity", "equipment.transformer_rating", "derating.transformer_*", "design_criteria.transformer_*"],
    "ups_loading_kw": LOAD + ["equipment.ups_quantity", "equipment.ups_rating", "derating.ups_*", "design_criteria.ups_*"],
    "ups_loading_kva": LOAD + ["equipment.ups_quantity", "equipment.ups_rating_kva", "derating.ups_*", "design_criteria.ups_*"],
    "generator_loading": LOAD + ["equipment.generator_quantity_per_path", "equipment.generator_rating", "derating.generator_*", "design_criteria.generator_*", "generators.rating_basis"],
    "generator_loading_kw": LOAD + ["equipment.generator_quantity_per_path", "equipment.generator_rating", "equipment.generator_rating_power_factor", "derating.generator_*",
                                    "design_criteria.generator_*", "generators.rating_basis"],
    "generator_rating_basis": ["equipment.generator_rating", "generators.rating_basis", "generators.rating_basis_confirmed"],
    "generator_step_load": ["generators.*", "equipment.generator_rating"],
    "generator_prp_load_factor": ["generators.prp_max_average_load_factor_pct"],
    "battery_sizing": ["battery.*", "redundancy.battery_autonomy"],
    "derating_factors": ["derating.*"],
    "cable_voltage_drop": CUR + ["cable_data.*", "design_criteria.voltage_drop_limit_pct", "@distribution"],
    "cable_ampacity": CUR + ["design_criteria.cable_max_loading", "installation.*", "@distribution"],
    "cable_derating_basis": CUR + ["installation.*", "environment.design_ambient_temperature", "cable_data.conductor_operating_temperature", "@distribution"],
    "busduct_rating": CUR + ["design_criteria.busduct_max_loading", "@distribution"],
    "busduct_voltage_drop": CUR + ["@distribution"],
    "switchgear_ratings": CUR + ["design_criteria.switchgear_max_loading", "@distribution"],
    "short_circuit_levels": SC,
    "fault_level_vs_limit": SC,
    "short_circuit_withstand": SC + ["@distribution"],
    "cable_thermal_withstand": SC + ["@distribution"],
    "protection_devices": SC + ["@distribution"],
    "earthing_framework": ["earthing.*", "earthing_study.*"],
}


def _expand(cfg: ProjectConfig, patterns: list[str]) -> list[str]:
    out: list[str] = []
    for p in patterns:
        if p.endswith("*"):
            out += [k for k in cfg.parameters if k.startswith(p[:-1])]
        elif p == "@distribution" or p in cfg.parameters:
            out.append(p)
    return list(dict.fromkeys(out))


def verified_ids(cfg: ProjectConfig) -> set[str]:
    """Parameters whose supplied value a reviewer has signed off in the register."""
    from ohmetry_dc.reporting.manufacturer_register import load_register_meta

    path = Path(cfg.base_dir) / "manufacturer_data_register.yaml"
    if not path.exists():
        return set()
    from ohmetry_dc.models.attestation import is_complete

    return {e["parameter"] for e in load_register_meta(path) if is_complete(e)}


def input_statuses(cfg: ProjectConfig, ids: list[str], verified: set[str] | None = None) -> list[tuple[str, str]]:
    verified = verified_ids(cfg) if verified is None else verified
    out = []
    for i in ids:
        if i == "@distribution":
            out.append((i, ds.UNVERIFIED_PLACEHOLDER))     # the shipped schedule is illustrative; real selections arrive through the overrides file
        else:
            out.append((i, ds.data_status(cfg.parameters[i], i in verified)))
    return out


def _calc_status(r: CheckResult) -> str:
    low = r.detail.lower()
    if any(m in low for m in ("not calculated", "not calculable", "cannot be calculated", "not assessed", "cannot be judged")):
        return "NOT CALCULATED" if r.status == CheckStatus.NOT_VERIFIED and not r.values.get("lv_cases") and "calculated:" not in low else "PARTIAL"
    return "CALCULATED" if r.status in (CheckStatus.PASS, CheckStatus.WARNING, CheckStatus.FAIL) else "PARTIAL"


def apply_verification(cfg: ProjectConfig, results: list[CheckResult]) -> list[CheckResult]:
    verified = verified_ids(cfg)
    for r in results:
        r.calculation_status = _calc_status(r)
        r.calculation_result = r.status.value if r.status in (CheckStatus.PASS, CheckStatus.WARNING, CheckStatus.FAIL) else "N/A"
        ids = CHECK_INPUTS.get(r.id)
        if ids is None:
            r.input_status, r.verification_status = "N/A", "N/A"
            continue
        used = input_statuses(cfg, _expand(cfg, ids), verified)
        r.inputs_used = [{"parameter": i, "data_status": s, "value": (cfg.parameters[i].value if i in cfg.parameters else None),
                          "unit": (cfg.parameters[i].unit if i in cfg.parameters else "")} for i, s in used]
        r.input_status = ds.worst([s for _, s in used])
        ok = bool(used) and all(ds.RANK[s] >= ds.ACCEPTABLE for _, s in used)
        r.verification_status = "VERIFIED" if ok and r.status == CheckStatus.PASS else "NOT VERIFIED"
        if r.status == CheckStatus.PASS and not ok:
            r.status = CheckStatus.NOT_VERIFIED
            weak = [i for i, s in used if ds.RANK[s] < ds.ACCEPTABLE]
            r.detail += (f" CALCULATION RESULT: PASS (preliminary). OVERALL STATUS: NOT VERIFIED, because {len(weak)} input(s) are not verified (worst: {r.input_status}). "
                         "A calculation on unverified inputs is not evidence that the design works.")
            r.next_action = r.next_action or "Replace the preliminary inputs with verified manufacturer, site or project data."
        elif r.status in (CheckStatus.WARNING, CheckStatus.FAIL) and not ok:
            r.detail += f" This is a preliminary result on unverified inputs (worst: {r.input_status})."
    return results
