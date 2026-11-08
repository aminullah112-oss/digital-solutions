import math

import pytest

from ohmetry_dc.config import load_config
from ohmetry_dc.models import ReleaseState
from ohmetry_dc.validation import release_gate, run_all_checks, summarise
from ohmetry_dc.validation.checks import check_phase_voltage_relation, check_power_system_sizing, check_pue_arithmetic, check_transformer_current, check_voltage_frequency
from ohmetry_dc.validation.status import CheckStatus as S

from conftest import DEFAULT_ITEMS, reference_model, set_value


def load(write_config, root, mutate=lambda d: None):
    return load_config(write_config(mutate), root / "config" / "load_schedule.yaml")


def by_id(results):
    return {r.id: r for r in results}


# Reference values below come from calculations done independently of the code (conftest.reference_model, or by hand):
#   2000 kW x 1.35 = 2700 kW
#   3150 kVA at 400 V: 3,150,000 / (1.7320508 x 400) = 4546.7 A
#   facility kVA from the load model = 2865.595; one 3150 kVA transformer per path -> 90.97 %
#   UPS: 2000 kW on one 2500 kW unit per path -> 80.0 %
#   generators: 2865.595 kVA on (3 - 1) x 2000 kVA = 4000 kVA -> 71.64 %

def test_pue_arithmetic_passes_for_the_stated_values(write_config, root):
    r = check_pue_arithmetic(load(write_config, root))
    assert r.status is S.PASS and r.values["expected_demand_kw"] == pytest.approx(2700)


def test_pue_arithmetic_fails_when_demand_does_not_follow_it_load_and_pue(write_config, root):
    cfg = load(write_config, root, lambda d: set_value(d, "general", "estimated_facility_demand", 3500))
    r = check_pue_arithmetic(cfg)
    assert r.status is S.FAIL and "not adjusted automatically" in r.detail


def test_changing_the_it_load_alone_makes_the_inconsistency_visible(write_config, root):
    cfg = load(write_config, root, lambda d: set_value(d, "general", "it_critical_load", 3000))
    assert check_pue_arithmetic(cfg).status is S.FAIL


def test_phase_voltage_relation(write_config, root):
    assert check_phase_voltage_relation(load(write_config, root)).status is S.PASS
    bad = load(write_config, root, lambda d: set_value(d, "electrical_system", "lv_phase_voltage", 200))
    assert check_phase_voltage_relation(bad).status is S.FAIL


def test_400v_with_60hz_warns_until_the_owner_decision_is_recorded(write_config, root):
    shipped = check_voltage_frequency(load(write_config, root))
    assert shipped.status is S.NOT_VERIFIED and "project owner's decision" in shipped.detail   # recorded, still not verified
    undecided = load(write_config, root, lambda d: d["sections"]["electrical_system"].pop("voltage_frequency_basis"))
    assert check_voltage_frequency(undecided).status is S.WARNING
    cfg50 = load(write_config, root, lambda d: set_value(d, "electrical_system", "frequency", 50))
    assert check_voltage_frequency(cfg50).status is S.NOT_VERIFIED


def test_transformer_secondary_current_matches_hand_calculation(write_config, root):
    r = check_transformer_current(load(write_config, root))
    assert r.values["full_load_current_a"] == pytest.approx(4546.7, abs=0.1)
    assert r.status is S.NOT_VERIFIED  # no verified limit exists, so it is never a PASS


def test_loadings_match_hand_calculation_and_the_policy_statuses(write_config, root):
    res = by_id(check_power_system_sizing(load(write_config, root)))
    ref = reference_model(DEFAULT_ITEMS)
    assert res["transformer_loading"].values["loading_pct"] == pytest.approx(ref["kva"] / 3150 * 100, abs=1e-9)
    assert res["transformer_loading"].values["loading_pct"] == pytest.approx(90.97, abs=0.01)
    assert res["ups_loading_kw"].values["loading_pct"] == pytest.approx(80.0, abs=1e-9)
    it_kva = math.hypot(2000, 2000 * math.tan(math.acos(0.95)))
    assert res["ups_loading_kva"].values["loading_pct"] == pytest.approx(it_kva / 2500 * 100, abs=1e-9)
    # generators carry everything except the small-power item (not on the generator): hand-built reference. The judged case is the combined contingency (one path out and one engine out): two units of 2,000 kVA
    ess = reference_model([i for i in DEFAULT_ITEMS if not (i[0] == 1 and i[1] == 20)])
    assert res["generator_loading"].values["loading_pct"] == pytest.approx(ess["kva"] / 4000 * 100, abs=1e-9)
    assert res["generator_loading"].values["loading_pct"] == pytest.approx(71.36, abs=0.01) and res["generator_loading_kw"].values["loading_pct"] == pytest.approx(83.98, abs=0.01)
    assert (res["transformer_loading"].status, res["ups_loading_kw"].status, res["ups_loading_kva"].status, res["generator_loading"].status) == (S.WARNING, S.PASS, S.WARNING, S.PASS)
    assert res["generator_loading_kw"].status is S.WARNING                      # 83.98 % of 3,200 kW is above the 80 % target and below the 100 % limit; never converted to PASS


def test_policy_is_configurable_through_the_master_configuration(write_config, root):
    def relaxed(d):
        d["sections"]["design_criteria"]["transformer_target_loading"]["value"] = 95
    assert by_id(check_power_system_sizing(load(write_config, root, relaxed)))["transformer_loading"].status is S.PASS     # 90.97 % under a 95 % target

    def tight(d):
        d["sections"]["design_criteria"]["transformer_target_loading"]["value"] = 80
        d["sections"]["design_criteria"]["transformer_max_loading"]["value"] = 90
    assert by_id(check_power_system_sizing(load(write_config, root, tight)))["transformer_loading"].status is S.FAIL         # 90.97 % over a 90 % maximum


def test_more_load_raises_loading_and_more_generators_lower_it(write_config, root):
    base = by_id(check_power_system_sizing(load(write_config, root)))["generator_loading"].values["loading_pct"]
    more_load = load(write_config, root, lambda d: set_value(d, "general", "it_critical_load", 2400))
    assert by_id(check_power_system_sizing(more_load))["generator_loading"].values["loading_pct"] > base
    more_gens = load(write_config, root, lambda d: set_value(d, "equipment", "generator_quantity_per_path", 4))
    assert by_id(check_power_system_sizing(more_gens))["generator_loading"].values["loading_pct"] < base


def test_missing_inputs_fail_and_are_listed_never_defaulted(write_config, root):
    def mutate(d):
        d["sections"]["general"]["future_expansion_allowance"].update(value=None, status="USER_INPUT")
    r = by_id(run_all_checks(load(write_config, root, mutate)))["required_user_inputs"]
    assert r.status is S.FAIL and "general.future_expansion_allowance" in r.values["missing"]


def test_inputs_for_later_stages_are_reported_as_deferred_not_failed(write_config, root):
    def no_time(d):
        d["project"].update(current_stage=4)
        d["sections"]["short_circuit"]["assumed_clearing_time_s"].update(value=None, status="USER_INPUT", requires_manufacturer_verification=False)
    res = by_id(run_all_checks(load(write_config, root, no_time)))
    assert res["required_user_inputs"].status is S.PASS
    assert res["inputs_deferred"].status is S.NOT_VERIFIED
    assert "short_circuit.assumed_clearing_time_s" in res["inputs_deferred"].detail


def test_at_stage_5_the_clearing_time_becomes_required(write_config, root):
    def no_time(d):
        d["sections"]["short_circuit"]["assumed_clearing_time_s"].update(value=None, status="USER_INPUT", requires_manufacturer_verification=False)
    res = by_id(run_all_checks(load(write_config, root, no_time)))
    assert res["required_user_inputs"].status is S.FAIL and "short_circuit.assumed_clearing_time_s" in res["required_user_inputs"].values["missing"]


def test_outstanding_manufacturer_data_is_listed_not_hidden(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))["manufacturer_data_pending"]
    assert r.status is S.NOT_VERIFIED
    assert {"generators.max_step_load_pct", "generators.prp_max_average_load_factor_pct", "equipment.generator_esp_rating"} <= set(r.values["pending"])


def test_missing_input_in_a_check_returns_not_verified(write_config, root):
    def mutate(d):
        d["sections"]["equipment"]["ups_rating"].update(value=None, status="USER_INPUT")
    res = by_id(check_power_system_sizing(load(write_config, root, mutate)))
    assert res["ups_loading_kw"].status is S.NOT_VERIFIED and "equipment.ups_rating" in res["ups_loading_kw"].detail


def test_release_gate_is_blocked_by_a_fail_and_never_approves(write_config, root):
    cfg = load(write_config, root, lambda d: set_value(d, "general", "estimated_facility_demand", 3500))
    results = run_all_checks(cfg)
    assert summarise(results)["FAIL"] >= 1
    assert release_gate(results, ReleaseState.DEVELOPMENT) is ReleaseState.RELEASE_BLOCKED
    ok = [r for r in results if r.status is not S.FAIL]
    assert release_gate(ok, ReleaseState.APPROVED_FOR_EDUCATIONAL_DISTRIBUTION) is ReleaseState.ENGINEERING_REVIEW_REQUIRED
    assert release_gate(ok, ReleaseState.DEVELOPMENT) is ReleaseState.DEVELOPMENT


# ---- revision A6, item 6: distribution derating, installation, parallel arrangement and current sharing
def _dist(root, mutate=None):
    import yaml
    from ohmetry_dc.calculations import assess_distribution, estimate_loads, size_power_system
    from ohmetry_dc.config import load_config
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    if mutate:
        mutate(cfg.distribution)
    est = estimate_loads(cfg)
    return cfg, assess_distribution(cfg, est, size_power_system(cfg, est))


def test_a_derating_of_one_is_never_treated_as_verified(root):
    _, r = _dist(root)
    for c in r.cables:
        assert set(c.derating_unverified) == {"grouping", "ambient", "installation"} and c.lower_bound
    assert all(c.lower_bound for c in r.busducts) and all(c.lower_bound for c in r.switchgear)


def test_grouping_of_one_with_parallel_runs_is_called_out_as_a_placeholder(root):
    _, r = _dist(root)
    gen = next(c for c in r.cables if c.tag == "CAB-GEN-A")
    assert gen.runs == 6 and any("grouping factor of 1.00 for 6 parallel runs" in n for n in gen.notes)
    assert any("MINIMUM" in n for n in gen.notes) and any("not supplied" in n.lower() for n in gen.notes)


def test_evidence_for_a_factor_removes_it_from_the_unverified_list_but_the_others_stay(root):
    def m(d):
        d["feeders"][1]["derating"]["grouping"] = 0.72
        d["feeders"][1]["derating_evidence"] = {"grouping": "Cable table T-3, 6 circuits, touching (example reference)"}
    _, r = _dist(root, m)
    gen = next(c for c in r.cables if c.tag == "CAB-GEN-A")
    assert gen.derating_unverified == ["ambient", "installation"]


def test_current_sharing_allowance_raises_the_required_rating_and_removes_the_minimum_flag_for_sharing(root):
    _, base = _dist(root)
    _, shared = _dist(root, lambda d: d["feeders"][1].update(current_sharing_allowance_pct=10))
    b = next(c for c in base.cables if c.tag == "CAB-GEN-A")
    s = next(c for c in shared.cables if c.tag == "CAB-GEN-A")
    assert abs(s.required_rating_a / b.required_rating_a - 1.10) < 1e-9 and s.sharing_allowance_pct == 10 and b.sharing_allowance_pct is None
    assert not any("MINIMUM. Equal sharing" in n for n in s.notes) and any("MINIMUM. Equal sharing" in n for n in b.notes)


def test_parallel_feeder_without_an_arrangement_lists_it_as_missing_data(root):
    _, r = _dist(root)
    gen = next(c for c in r.cables if c.tag == "CAB-GEN-A")
    mv = next(c for c in r.cables if c.tag == "CAB-MV-A")
    assert "CAB-GEN-A.parallel_arrangement" in gen.missing_data and "CAB-MV-A.parallel_arrangement" not in mv.missing_data


def test_invalid_sharing_allowance_is_rejected(root):
    import pytest
    from ohmetry_dc.models import ConfigError
    with pytest.raises(ConfigError):
        _dist(root, lambda d: d["feeders"][1].update(current_sharing_allowance_pct=-5))


def test_derating_basis_check_is_not_verified_and_says_the_ratings_are_minimums(root):
    from ohmetry_dc.config import load_config
    from ohmetry_dc.validation.checks import check_distribution
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    chk = {c.id: c for c in check_distribution(cfg)}["cable_derating_basis"]
    assert chk.status.value == "NOT VERIFIED" and "MINIMUMS" in chk.detail and "placeholder" in chk.detail and "NOT SUPPLIED" in chk.detail
