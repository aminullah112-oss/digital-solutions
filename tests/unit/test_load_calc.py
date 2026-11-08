import math

import pytest

from ohmetry_dc.calculations import estimate_loads, pue
from ohmetry_dc.config import load_config
from ohmetry_dc.models import ConfigError

from conftest import DEFAULT_ITEMS, reference_model, set_value


def load(root, write_config=None, mutate=None, loads=None):
    cfg_path = write_config(mutate) if (write_config and mutate) else root / "config" / "project_config.yaml"
    return load_config(cfg_path, loads or root / "config" / "load_schedule.yaml")


def test_shipped_values_match_hand_calculation(root):
    est = estimate_loads(load(root))
    # By hand: IT 2000; chillers 4 x 120 x 0.75 = 360; CRAH 20 x 6 = 120; pumps 6 x 15 x 0.67 = 60.3; lighting 12; small power 10; auxiliary 25
    assert est.it_demand_kw == pytest.approx(2000.0)
    assert est.items_demand_kw == pytest.approx(2000 + 360 + 120 + 60.3 + 12 + 10 + 25)       # 2587.3
    assert est.ups_loss.kw == pytest.approx(2000 * (1 / 0.96 - 1))                          # 83.3333
    assert est.distribution_loss.kw == pytest.approx(0.01 * (2587.3 + 83.33333333))          # 26.7063
    assert est.facility_kw == pytest.approx(2697.3397, abs=1e-3)
    assert est.pue == pytest.approx(1.34867, abs=1e-5)
    assert est.connected_kw == pytest.approx(2000 + 480 + 120 + 90 + 15 + 20 + 25)


def test_matches_the_independent_reference_model(root):
    est, ref = estimate_loads(load(root)), reference_model(DEFAULT_ITEMS)
    for got, want in ((est.it_demand_kw, ref["it"]), (est.ups_loss.kw, ref["ups"]), (est.distribution_loss.kw, ref["dist"]), (est.facility_kw, ref["kw"]),
                      (est.facility_kvar, ref["kvar"]), (est.facility_kva, ref["kva"]), (est.power_factor, ref["pf"]), (est.pue, ref["pue"])):
        assert got == pytest.approx(want, rel=1e-12)


def test_apparent_power_is_from_p_and_q_not_a_sum_of_kva(root):
    est = estimate_loads(load(root))
    assert est.facility_kva == pytest.approx(math.hypot(est.facility_kw, est.facility_kvar))
    assert est.facility_kva < sum(i.demand_kva for i in est.items) + est.ups_loss.kva + est.distribution_loss.kva


def test_path_allocation_adds_up_and_splits_evenly_for_equal_fractions(root):
    est = estimate_loads(load(root))
    assert est.path_a.kw + est.path_b.kw == pytest.approx(est.facility_kw, rel=1e-12)
    assert est.path_a.kvar + est.path_b.kvar == pytest.approx(est.facility_kvar, rel=1e-12)
    assert est.path_a.kw == pytest.approx(est.path_b.kw, rel=1e-12)
    assert est.scenarios["PATH_B_OUT_PATH_A_CARRIES_ALL"].kw == pytest.approx(est.facility_kw)


def test_uneven_path_split_moves_load_between_paths(root, write_loads):
    def mutate(d):
        for it in d["load_items"]:
            it["path_a_fraction"] = 0.6
    est = estimate_loads(load(root, loads=write_loads(mutate)))
    assert est.path_a.kw > est.path_b.kw
    assert est.path_a.kw + est.path_b.kw == pytest.approx(est.facility_kw, rel=1e-12)


def test_higher_ups_efficiency_lowers_losses_and_pue(root, write_config):
    base = estimate_loads(load(root))
    better = estimate_loads(load(root, write_config, lambda d: d["sections"]["equipment"]["ups_efficiency"].update(value=98)))
    assert better.ups_loss.kw < base.ups_loss.kw and better.pue < base.pue


def test_zero_distribution_losses_give_zero_loss_and_a_lower_pue(root, write_config):
    est = estimate_loads(load(root, write_config, lambda d: d["sections"]["losses"]["distribution_loss_fraction"].update(value=0)))
    assert est.distribution_loss.kw == 0
    assert est.facility_kw == pytest.approx(est.items_demand_kw + est.ups_loss.kw)


def test_growth_allowance_scales_the_design_demand_but_not_the_pue(root, write_config):
    base = estimate_loads(load(root))
    grown = estimate_loads(load(root, write_config, lambda d: set_value(d, "general", "future_expansion_allowance", 20)))
    assert grown.design_demand_kw == pytest.approx(base.facility_kw * 1.2)
    assert grown.pue == pytest.approx(base.pue)


def test_changing_the_it_load_changes_the_facility_load(root, write_config):
    base = estimate_loads(load(root))
    more = estimate_loads(load(root, write_config, lambda d: set_value(d, "general", "it_critical_load", 3000)))
    assert more.it_demand_kw == pytest.approx(3000) and more.facility_kw > base.facility_kw
    assert more.ups_loss.kw == pytest.approx(3000 * (1 / 0.96 - 1))


def test_missing_required_value_raises_a_clear_error_and_is_never_defaulted(root, write_config):
    def mutate(d):
        d["sections"]["equipment"]["ups_efficiency"].update(value=None, status="USER_INPUT")
    with pytest.raises(ConfigError, match="equipment.ups_efficiency"):
        estimate_loads(load(root, write_config, mutate))


@pytest.mark.parametrize("value", [0, 101, -5])
def test_ups_efficiency_out_of_range_is_rejected(root, write_config, value):
    with pytest.raises(ConfigError):
        estimate_loads(load(root, write_config, lambda d: d["sections"]["equipment"]["ups_efficiency"].update(value=value)))


def test_no_it_load_is_rejected(root, write_loads):
    def mutate(d):
        d["load_items"] = [i for i in d["load_items"] if i["category"] != "it_critical"]
    with pytest.raises(ConfigError, match="IT critical"):
        estimate_loads(load(root, loads=write_loads(mutate)))


def test_pue_definition_and_guards():
    assert pue(2700, 2000) == pytest.approx(1.35)
    with pytest.raises(ValueError):
        pue(2700, 0)
    with pytest.raises(ValueError):
        pue(1900, 2000)       # facility power cannot be below the IT power
