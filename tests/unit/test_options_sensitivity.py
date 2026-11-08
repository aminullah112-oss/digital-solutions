"""A5 review items 1 to 4: the generator contingency basis, transformer and UPS options side by side, EX-001 reconciliation, load-model sensitivity."""
import pytest

from ohmetry_dc.calculations import estimate_loads, size_power_system
from ohmetry_dc.calculations import options as opt
from ohmetry_dc.calculations import sensitivity as sens
from ohmetry_dc.config import load_config
from ohmetry_dc.validation import run_all_checks
from ohmetry_dc.validation.status import CheckStatus as S

from conftest import set_value


@pytest.fixture
def cfg(root):
    return load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")


def by_id(checks):
    return {c.id: c for c in checks}


# ---- item 1: generator combined contingency
def test_generator_combined_contingency_is_judged_warning_on_kw_and_never_converted_to_pass(cfg):
    c = by_id(run_all_checks(cfg))
    assert c["generator_loading"].values["loading_pct"] == pytest.approx(71.36, abs=0.01) and c["generator_loading"].calculation_result == "PASS"        # 71.4 % of 4,000 kVA is under the 80 % target
    assert c["generator_loading_kw"].values["loading_pct"] == pytest.approx(83.98, abs=0.01) and c["generator_loading_kw"].status is S.WARNING      # 84.0 % of 3,200 kW: above 80 %, below 100 %
    assert c["generator_loading_kw"].values["loading_pct"] < 100


def test_the_contingency_basis_must_be_selected_by_an_engineer_and_the_alternatives_are_shown(cfg):
    chk = by_id(run_all_checks(cfg))["generator_contingency_basis"]
    assert chk.status is S.NOT_VERIFIED and "THE ENGINEER MUST SELECT AND DOCUMENT THE CONTINGENCY BASIS" in chk.detail and "N+1" in chk.detail
    cases = chk.values["cases"]
    assert set(cases) == {"GEN-PATH-OUT", "GEN-UNIT-OUT", "GEN-PATH-OUT-UNIT-OUT"}
    assert cases["GEN-PATH-OUT"]["kw_pct"] == pytest.approx(55.98, abs=0.01) and cases["GEN-UNIT-OUT"]["kw_pct"] == pytest.approx(41.99, abs=0.01)
    assert "NOT converted to a PASS" in chk.detail


def test_with_the_flag_off_the_combined_case_is_informational_and_the_basis_check_says_so(write_config, root):
    cfg = load_config(write_config(lambda d: set_value(d, "redundancy", "double_contingency_credible", False)), root / "config" / "load_schedule.yaml")
    chk = by_id(run_all_checks(cfg))["generator_contingency_basis"]
    assert "informational (not judged)" in chk.detail and by_id(run_all_checks(cfg))["generator_loading_kw"].values["loading_pct"] == pytest.approx(55.98, abs=0.01)


# ---- item 2: transformer, EX-001
def test_transformer_options_side_by_side_and_the_larger_one_exceeds_the_practical_fault_limit(cfg):
    rows = [r for r in opt.equipment_options(cfg, size_power_system(cfg, estimate_loads(cfg))) if r.equipment == "transformer"]
    assert [r.rating["kVA"] for r in rows] == [3150, 4000] and [r.retained for r in rows] == [True, False]
    assert rows[0].loadings_pct["kVA"] == pytest.approx(90.97, abs=0.01) and rows[0].overall == "WARNING"
    assert rows[1].loadings_pct["kVA"] == pytest.approx(71.64, abs=0.01) and rows[1].overall == "PASS"
    assert rows[0].extra["transformer_limited_ka"] == pytest.approx(82.64, abs=0.01) and rows[1].extra["transformer_limited_ka"] == pytest.approx(104.9, abs=0.1)
    assert not any("EXCEEDS" in n for n in rows[0].notes) and any("EXCEEDS" in n and "practical limit" in n for n in rows[1].notes)
    assert rows[1].extra["full_load_current_a"] == pytest.approx(5773.7, abs=0.5)


def test_ex_001_is_reconciled_with_the_exact_loading_and_a_small_margin_and_stays_a_warning(cfg):
    t = by_id(run_all_checks(cfg))["transformer_loading"]
    assert t.status is S.WARNING and "90.97 %" in t.detail and "0.03 percentage points" in t.detail and "voids the exception" in t.detail and "100 % limit are unchanged" in t.detail
    assert t.values["exception"]["applies"] is True


# ---- item 3: UPS
def test_ups_kw_and_kva_are_separate_and_the_3000_kva_option_is_shown(cfg):
    rows = [r for r in opt.equipment_options(cfg, size_power_system(cfg, estimate_loads(cfg))) if r.equipment == "ups"]
    assert [r.rating["kVA"] for r in rows] == [2500, 3000]
    a, b = rows
    assert a.loadings_pct["kW"] == pytest.approx(80.0, abs=1e-6) and a.statuses["kW"] == "PASS" and a.loadings_pct["kVA"] == pytest.approx(84.21, abs=0.01) and a.statuses["kVA"] == "WARNING" and a.overall == "WARNING"
    assert b.loadings_pct["kVA"] == pytest.approx(70.18, abs=0.01) and b.loadings_pct["kW"] == pytest.approx(66.67, abs=0.01) and b.overall == "PASS"


def test_the_options_check_selects_nothing(cfg):
    chk = by_id(run_all_checks(cfg))["equipment_options"]
    assert chk.status is S.NOT_VERIFIED and "NO OPTION IS SELECTED" in chk.detail and len(chk.values["options"]) == 4


# ---- item 4: load model review and sensitivity
def test_sensitivity_covers_plus_minus_ten_percent_and_does_not_change_the_configuration(cfg):
    before = (estimate_loads(cfg).facility_kw, [i.unit_rating_kw for i in cfg.load_items], cfg.value("equipment.ups_efficiency"))
    cases = sens.it_load_cases(cfg) + sens.loss_cases(cfg)
    assert (estimate_loads(cfg).facility_kw, [i.unit_rating_kw for i in cfg.load_items], cfg.value("equipment.ups_efficiency")) == before          # the copies were varied, not the configuration
    held = {c.label: c for c in cases if "held as scheduled" in c.label}
    assert held["IT -10 %, plant held as scheduled"].it_kw == pytest.approx(1800) and held["IT +10 %, plant held as scheduled"].it_kw == pytest.approx(2200)
    assert held["IT +0 %, plant held as scheduled"].pue == pytest.approx(1.3487, abs=1e-4) and held["IT +0 %, plant held as scheduled"].facility_kw == pytest.approx(2697.3, abs=0.05)
    assert held["IT -10 %, plant held as scheduled"].pue > held["IT +0 %, plant held as scheduled"].pue > held["IT +10 %, plant held as scheduled"].pue         # fixed plant: PUE falls as IT load rises
    plus = held["IT +10 %, plant held as scheduled"]
    assert plus.transformer_pct == pytest.approx(98.0, abs=0.1) and plus.exception_covers is False and plus.transformer_status == "WARNING"


def test_pue_range_is_reported_as_an_output_and_no_target_is_forced(cfg):
    lo, hi = sens.pue_range(sens.it_load_cases(cfg) + sens.loss_cases(cfg))
    assert 1.30 < lo < 1.35 < hi < 1.40
    md = " ".join(sens.sensitivity_markdown(cfg))
    assert "PUE is an output" in md and "no input was adjusted to reach a target" in md
    chk = by_id(run_all_checks(cfg))["load_pue_vs_target"]
    assert chk.values["pue_is_an_output"] is True and "OUTPUT" in chk.detail and "not an input constraint" in chk.detail and "Do not retune" in chk.next_action


def test_whole_unit_allocation_shows_the_chillers_do_not_split_evenly(cfg):
    rows = {r.item: r for r in sens.discrete_allocation_review(cfg)}
    assert rows["MC-1"].running == 3 and rows["MC-1"].model_per_path_kw == pytest.approx(180) and rows["MC-1"].discrete_worst_path_kw == pytest.approx(240) and "cannot split evenly" in rows["MC-1"].note
    assert rows["MC-2"].discrete_worst_path_kw == pytest.approx(60) and rows["MC-3"].running == 4 and rows["MC-3"].discrete_worst_path_kw == pytest.approx(30)


def test_review_notes_cover_cooling_redundancy_path_split_and_losses():
    t = " ".join(sens.REVIEW_NOTES)
    for word in ("Chillers", "pumps", "CRAH", "50 / 50", "UPS losses", "Distribution losses", "OUTPUT", "N+1"):
        assert word in t
