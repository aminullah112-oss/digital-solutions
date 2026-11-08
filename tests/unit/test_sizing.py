import math

import pytest

from ohmetry_dc.calculations import Derating, LoadingStatus, classify, estimate_loads, size_power_system
from ohmetry_dc.calculations.sizing import Policy, _sizes
from ohmetry_dc.config import load_config
from ohmetry_dc.models import ConfigError

from conftest import DEFAULT_ITEMS, reference_model, set_value

NO_SMALL_POWER = [i for i in DEFAULT_ITEMS if not (i[0] == 1 and i[1] == 20)]


def run(root, write_config=None, mutate=None):
    path = write_config(mutate) if (write_config and mutate) else root / "config" / "project_config.yaml"
    cfg = load_config(path, root / "config" / "load_schedule.yaml")
    return cfg, size_power_system(cfg, estimate_loads(cfg))


def param(section, key, value):
    return lambda d: d["sections"][section][key].update(value=value)


# ---- policy ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pct, expected", [(50, "PASS"), (90.0, "PASS"), (90.0000000001, "PASS"), (90.01, "WARNING"), (100.0, "WARNING"), (100.0000000001, "WARNING"), (100.01, "FAIL"), (150, "FAIL")])
def test_status_boundaries_against_target_90_and_maximum_100(pct, expected):
    assert classify(pct / 100, Policy(90, 100)) is LoadingStatus(expected)


def test_missing_policy_is_not_verified_never_a_pass():
    assert classify(0.1, Policy(None, 100)) is LoadingStatus.NOT_VERIFIED
    assert classify(0.1, Policy(90, None)) is LoadingStatus.NOT_VERIFIED


def test_policy_is_per_equipment_not_universal(root):
    cfg, r = run(root)
    assert (r.transformer.policy.target_pct, r.ups_kw.policy.target_pct, r.generator.policy.target_pct) == (90, 80, 80)
    assert all(s.policy.limit_pct == 100 for s in (r.transformer, r.ups_kw, r.ups_kva, r.generator))


# ---- derating before loading -----------------------------------------------------------------------------------------
def test_derating_is_applied_before_the_percentage_is_taken(root, write_config):
    ref = reference_model(DEFAULT_ITEMS)
    _, r = run(root, write_config, param("derating", "transformer_ambient_factor", 0.9))
    assert r.transformer.derated_each == pytest.approx(3150 * 0.9)
    assert r.transformer.worst_credible.loading == pytest.approx(ref["kva"] / (3150 * 0.9), rel=1e-12)
    assert r.transformer.status is LoadingStatus.FAIL           # 101.1 % of the derated rating, although 91.0 % of the nameplate


def test_derating_factors_multiply(root, write_config):
    def mutate(d):
        d["sections"]["derating"]["generator_ambient_factor"]["value"] = 0.95
        d["sections"]["derating"]["generator_altitude_factor"]["value"] = 0.9
        d["sections"]["derating"]["generator_installation_factor"]["value"] = 0.98
    _, r = run(root, write_config, mutate)
    assert r.generator.derating["combined"] == pytest.approx(0.95 * 0.9 * 0.98)
    assert r.generator.derated_each == pytest.approx(2000 * 0.95 * 0.9 * 0.98)


@pytest.mark.parametrize("bad", [0, -0.5, 1.05])
def test_a_derating_factor_cannot_raise_a_rating_or_be_zero(bad):
    with pytest.raises(ConfigError):
        Derating(bad, 1, 1)


def test_a_missing_derating_factor_is_an_error_not_a_default(root, write_config):
    def mutate(d):
        d["sections"]["derating"]["ups_altitude_factor"].update(value=None, status="MANUFACTURER_DATA")
    with pytest.raises(ConfigError, match="ups_altitude_factor"):
        run(root, write_config, mutate)


def test_transformer_contingency_factor_affects_only_the_path_out_case(root, write_config):
    _, base = run(root)
    _, r = run(root, write_config, param("derating", "transformer_contingency_factor", 0.9))
    sc = {s.id: s for s in r.transformer.scenarios}
    assert sc["TX-NORMAL"].loading == pytest.approx({s.id: s for s in base.transformer.scenarios}["TX-NORMAL"].loading)
    assert sc["TX-PATH-OUT"].loading == pytest.approx({s.id: s for s in base.transformer.scenarios}["TX-PATH-OUT"].loading / 0.9)


# ---- transformers, UPS --------------------------------------------------------------------------------------------------
def test_surviving_transformer_carries_the_whole_facility_load(root):
    ref = reference_model(DEFAULT_ITEMS)
    _, r = run(root)
    sc = {s.id: s for s in r.transformer.scenarios}
    assert sc["TX-PATH-OUT"].load == pytest.approx(ref["kva"], rel=1e-12)
    assert sc["TX-NORMAL"].load == pytest.approx(ref["kva"] / 2, rel=1e-9)        # equal 50/50 split
    assert r.transformer.worst_credible.id == "TX-PATH-OUT"


def test_ups_checks_both_kw_and_kva(root, write_config):
    _, r = run(root)
    it_kva = math.hypot(2000, 2000 * math.tan(math.acos(0.95)))
    assert r.ups_kw.worst_credible.loading == pytest.approx(0.8) and r.ups_kw.status is LoadingStatus.PASS
    assert r.ups_kva.worst_credible.loading == pytest.approx(it_kva / 2500) and r.ups_kva.status is LoadingStatus.WARNING
    # a smaller kVA rating fails on kVA while kW stays inside its target
    _, tight = run(root, write_config, param("equipment", "ups_rating_kva", 2000))
    assert tight.ups_kva.status is LoadingStatus.FAIL and tight.ups_kw.status is LoadingStatus.PASS


def test_required_rating_and_suggested_size(root, write_config):
    ref = reference_model(DEFAULT_ITEMS)
    _, r = run(root)
    assert r.transformer.required_rating_each_for_target == pytest.approx(ref["kva"] / 0.9, rel=1e-12)
    assert r.transformer.required_rating_each_for_limit == pytest.approx(ref["kva"], rel=1e-12)
    assert r.transformer.suggested_size_for_target == 4000 and r.transformer.suggested_size_for_limit == 3150
    # a derating factor raises the nameplate rating needed
    _, d = run(root, write_config, param("derating", "transformer_installation_factor", 0.9))
    assert d.transformer.required_rating_each_for_target == pytest.approx(ref["kva"] / 0.9 / 0.9, rel=1e-12)


def test_size_lists_must_be_numbers(root, write_config):
    cfg = load_config(write_config(param("equipment", "transformer_size_list_kva", "630,big")), root / "config" / "load_schedule.yaml")
    with pytest.raises(ConfigError, match="comma-separated"):
        _sizes(cfg, "equipment.transformer_size_list_kva")


# ---- generators ---------------------------------------------------------------------------------------------------------
def test_generator_n_plus_1_scenarios_match_hand_calculation(root):
    ess = reference_model(NO_SMALL_POWER)          # everything but the small-power item is on the generators
    _, r = run(root)
    sc = {s.id: s for s in r.generator.scenarios}
    assert sc["GEN-NORMAL"].load == pytest.approx(ess["kva"] / 2, rel=1e-9) and sc["GEN-NORMAL"].units_available == 3
    assert sc["GEN-UNIT-OUT"].units_available == 2 and sc["GEN-UNIT-OUT"].loading == pytest.approx(ess["kva"] / 2 / 4000, rel=1e-9)
    assert sc["GEN-PATH-OUT"].loading == pytest.approx(ess["kva"] / 6000, rel=1e-9)
    assert r.generator.worst_credible.id == "GEN-PATH-OUT-UNIT-OUT"          # the combined contingency is judged (A5 review item 1)


def test_the_combined_contingency_is_judged_as_shipped_and_informational_when_the_flag_is_false(root, write_config):
    _, r = run(root)
    dbl = {s.id: s for s in r.generator.scenarios}["GEN-PATH-OUT-UNIT-OUT"]
    assert dbl.credible and r.generator.worst_credible.id == "GEN-PATH-OUT-UNIT-OUT" and dbl.loading == pytest.approx(0.7136, abs=1e-4)
    kw = {s.id: s for s in r.generator_kw.scenarios}["GEN-PATH-OUT-UNIT-OUT"]
    assert kw.loading == pytest.approx(0.8398, abs=1e-4) and kw.status is LoadingStatus.WARNING and kw.units_available == 2          # two 1,600 kW engines: WARNING against the 80 % target, below the 100 % limit
    _, c = run(root, write_config, param("redundancy", "double_contingency_credible", False))
    off = {s.id: s for s in c.generator.scenarios}["GEN-PATH-OUT-UNIT-OUT"]
    assert not off.credible and off.status is LoadingStatus.NOT_APPLICABLE and c.generator.worst_credible.id == "GEN-PATH-OUT"


def test_prp_is_the_default_and_esp_cop_are_distinct_bases(root, write_config):
    _, prp = run(root)
    assert prp.generator.rating_each == 2000
    _, esp_missing = run(root, write_config, param("generators", "rating_basis", "ESP"))
    assert esp_missing.generator.scenarios == [] and any("generator_esp_rating" in m for m in esp_missing.generator.missing_data)    # never borrows the PRP rating

    def esp(d):
        d["sections"]["generators"]["rating_basis"]["value"] = "ESP"
        d["sections"]["equipment"]["generator_esp_rating"]["value"] = 2200
    _, e = run(root, write_config, esp)
    assert e.generator.rating_each == 2200 and e.generator.worst_credible.loading == pytest.approx(prp.generator.worst_credible.loading * 2000 / 2200)
    _, bad = run(root, write_config, param("generators", "rating_basis", "STANDBY"))
    assert bad.generator.scenarios == [] and any("PRP, ESP or COP" in m for m in bad.generator.missing_data)


def test_manufacturer_overload_capability_is_recorded_but_never_used(root, write_config):
    _, base = run(root)
    _, r = run(root, write_config, param("generators", "overload_capability", "110 % for 1 hour"))
    assert r.generator.worst_credible.loading == base.generator.worst_credible.loading
    assert [s.loading for s in r.transformer.scenarios] == [s.loading for s in base.transformer.scenarios]


def test_generator_step_loads_are_an_upper_bound_and_never_verified(root, write_config):
    ess = reference_model(NO_SMALL_POWER)
    cfg, r = run(root)
    st = r.generator_steps
    assert st.status is LoadingStatus.NOT_VERIFIED and any("walk-in" in x for x in st.requirements)
    step1_kw = (2000 + 2000 * (1 / 0.96 - 1)) * 1.01
    step1_kvar = 2000 * math.tan(math.acos(0.95)) + 2000 * (1 / 0.96 - 1) * math.tan(math.acos(0.95)) + (2000 + 2000 * (1 / 0.96 - 1)) * 0.01 * math.tan(math.acos(0.95))
    assert st.blocks[0].step_kva == pytest.approx(math.hypot(step1_kw, step1_kvar), rel=1e-3)
    assert st.blocks[-1].cumulative_kva == pytest.approx(ess["kva"], rel=1e-9)
    # a manufacturer step limit below the largest block raises a WARNING, and a generous limit still does not verify the transient
    _, tight = run(root, write_config, param("generators", "max_step_load_pct", 20))
    assert tight.generator_steps.status is LoadingStatus.WARNING
    _, loose = run(root, write_config, param("generators", "max_step_load_pct", 60))
    assert loose.generator_steps.status is LoadingStatus.NOT_VERIFIED


# ---- battery interface --------------------------------------------------------------------------------------------------
def test_battery_gives_arithmetic_energy_but_never_a_battery_size(root, write_config):
    _, r = run(root)
    b = r.battery
    assert b.energy_at_ups_output_kwh == pytest.approx(2000 * 10 / 60) and b.indicative_nominal_energy_kwh is None
    assert b.status is LoadingStatus.NOT_VERIFIED and "battery.constant_power_discharge_data" in b.missing_data

    def factors(d):
        d["sections"]["battery"]["inverter_efficiency_pct"]["value"] = 95
        d["sections"]["battery"]["end_of_life_capacity_factor"]["value"] = 0.8
        d["sections"]["battery"]["temperature_correction_factor"]["value"] = 1.0
        d["sections"]["battery"]["design_margin_factor"]["value"] = 1.1
    _, f = run(root, write_config, factors)
    assert f.battery.indicative_nominal_energy_kwh == pytest.approx(2000 * 10 / 60 / 0.95 / 0.8 * 1.1, rel=1e-12)
    assert f.battery.status is LoadingStatus.NOT_VERIFIED       # still not a sizing without the discharge data


# ---- demand data ---------------------------------------------------------------------------------------------------------
def test_new_demand_figures_flow_through_without_code_changes(root, write_config):
    _, base = run(root)
    _, more = run(root, write_config, param("demand_data", "it_critical_load_kw", 2500))
    assert more.transformer.worst_credible.loading > base.transformer.worst_credible.loading
    assert more.ups_kw.worst_credible.loading == pytest.approx(2500 / 2500) and more.ups_kw.status is LoadingStatus.WARNING    # exactly 100 % is above the 80 % target, not above the maximum
