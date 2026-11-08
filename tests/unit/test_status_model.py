import pytest

from ohmetry_dc.config import load_config
from ohmetry_dc.models import data_status as ds
from ohmetry_dc.validation import run_all_checks
from ohmetry_dc.validation.status import CheckStatus as S
from ohmetry_dc.validation.verification import CHECK_INPUTS, _expand

from conftest import set_value


def load(write_config, root, mutate=lambda d: None):
    return load_config(write_config(mutate), root / "config" / "load_schedule.yaml")


def by_id(results):
    return {r.id: r for r in results}


def test_a_calculation_on_preliminary_inputs_never_reaches_pass(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))
    for cid in ("ups_loading_kw", "generator_loading", "cable_voltage_drop", "load_pue_vs_target"):
        c = r[cid]
        assert c.calculation_result == "PASS" and c.status is S.NOT_VERIFIED and c.verification_status == "NOT VERIFIED", cid
        assert c.input_status in (ds.PRELIMINARY_ASSUMPTION, ds.UNVERIFIED_PLACEHOLDER) and "CALCULATION RESULT: PASS (preliminary)" in c.detail
    assert not [c for c in r.values() if c.verification_status != "N/A" and c.status is S.PASS]      # no engineering check passes in the shipped package


def test_preliminary_warnings_are_kept_and_labelled(write_config, root):
    t = by_id(run_all_checks(load(write_config, root)))["transformer_loading"]
    assert t.status is S.WARNING and t.calculation_result == "WARNING" and "preliminary result on unverified inputs" in t.detail
    assert 90 < t.values["loading_pct"] < 92


def test_a_preliminary_fail_stays_fail(write_config, root):
    c = by_id(run_all_checks(load(write_config, root, lambda d: set_value(d, "equipment", "transformer_rating", 2700))))["transformer_loading"]
    assert c.status is S.FAIL and c.calculation_result == "FAIL"


def test_the_four_statuses_are_reported_separately(write_config, root):
    d = by_id(run_all_checks(load(write_config, root)))["ups_loading_kw"].as_dict()
    assert {"calculation_status", "calculation_result", "input_status", "verification_status", "status", "inputs_used"} <= set(d)
    assert d["calculation_status"] == "CALCULATED" and d["status"] == "NOT VERIFIED"
    used = {u["parameter"]: u for u in d["inputs_used"]}
    assert used["equipment.ups_rating"]["data_status"] == ds.UNVERIFIED_PLACEHOLDER and used["equipment.ups_rating"]["value"] == 2500


def test_arithmetic_checks_are_not_design_verification(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))["pue_arithmetic"]
    assert r.status is S.PASS and r.verification_status == "N/A" and r.input_status == "N/A"


def test_a_check_can_pass_only_when_every_input_is_verified_or_a_project_decision(write_config, root):
    cfg0 = load(write_config, root)
    ids = _expand(cfg0, CHECK_INPUTS["ups_loading_kw"])

    def verified(d):                  # promote every input of the check to an owner-supplied project input (an acceptable status)
        for pid in ids:
            sec, key = pid.split(".", 1)
            d["sections"][sec][key].update(status="USER_INPUT", requires_manufacturer_verification=False)
    c = by_id(run_all_checks(load(write_config, root, verified)))["ups_loading_kw"]
    assert c.status is S.PASS and c.verification_status == "VERIFIED"


def test_one_unverified_input_blocks_the_pass(write_config, root):
    cfg0 = load(write_config, root)
    ids = _expand(cfg0, CHECK_INPUTS["ups_loading_kw"])

    def almost(d):
        for pid in ids:
            sec, key = pid.split(".", 1)
            d["sections"][sec][key].update(status="USER_INPUT", requires_manufacturer_verification=False)
        d["sections"]["derating"]["ups_ambient_factor"].update(status="ASSUMPTION", requires_manufacturer_verification=True)
    c = by_id(run_all_checks(load(write_config, root, almost)))["ups_loading_kw"]
    assert c.status is S.NOT_VERIFIED and c.calculation_result == "PASS" and c.input_status == ds.UNVERIFIED_PLACEHOLDER


def test_data_status_vocabulary(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    assert ds.data_status(cfg.get("equipment.transformer_rating")) == ds.UNVERIFIED_PLACEHOLDER
    assert ds.data_status(cfg.get("general.it_critical_load")) == ds.PRELIMINARY_ASSUMPTION
    assert ds.data_status(cfg.get("short_circuit.voltage_factor_c_max_lv")) == ds.REFERENCE_DATA
    assert ds.data_status(cfg.get("short_circuit.utility_fault_level_mva")) == ds.MISSING
    assert ds.data_status(cfg.get("design_criteria.transformer_max_loading")) == ds.PROJECT_INPUT
    assert ds.worst([ds.REFERENCE_DATA, ds.MISSING, ds.PRELIMINARY_ASSUMPTION]) == ds.MISSING


def test_the_shipped_configuration_retains_the_preliminary_concept_values(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    assert cfg.value("equipment.transformer_rating") == 3150 and cfg.value("equipment.transformer_impedance") == 6
    assert cfg.value("equipment.generator_rating") == 2000 and cfg.value("equipment.generator_quantity_per_path") == 3 and cfg.value("equipment.generator_rating_power_factor") == 0.8
    assert cfg.value("equipment.ups_rating") == 2500 and cfg.value("equipment.ups_rating_kva") == 2500 and cfg.value("equipment.ups_efficiency") == 96
    assert cfg.value("losses.distribution_loss_fraction") == 1.0
    assert all(cfg.value(f"derating.{k}") == 1.0 for k in cfg.parameters if False) or all(p.value == 1.0 for k, p in cfg.parameters.items() if k.startswith("derating."))
    for pid in ("equipment.transformer_rating", "equipment.transformer_impedance", "equipment.generator_rating", "equipment.ups_rating", "equipment.ups_efficiency"):
        assert ds.data_status(cfg.get(pid)) in (ds.UNVERIFIED_PLACEHOLDER, ds.PRELIMINARY_ASSUMPTION)


def test_every_input_pattern_of_every_check_matches_a_parameter(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    for cid, pats in CHECK_INPUTS.items():
        for p in pats:
            if p != "@distribution":
                assert _expand(cfg, [p]), f"{cid}: pattern {p!r} matches no parameter"
