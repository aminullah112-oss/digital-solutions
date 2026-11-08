import cmath
import math

import pytest

from ohmetry_dc.calculations.earthing import grid_resistance, surface_layer_factor, tolerable_touch_v
from ohmetry_dc.calculations.short_circuit import assess_short_circuit, cable_min_section_mm2, peak_factor, thermal_factor
from ohmetry_dc.config import load_config
from ohmetry_dc.validation import run_all_checks
from ohmetry_dc.validation.status import CheckStatus as S

from conftest import set_value, supply_sc


def load(write_config, root, mutate=supply_sc):      # most tests supply the TEST INPUTS the shipped configuration leaves pending
    def both(d):
        supply_sc(d)
        mutate(d)
    return load_config(write_config(both), root / "config" / "load_schedule.yaml")


def by_id(results):
    return {r.id: r for r in results}


def case(sc, prefix):
    return next(c for c in sc.lv_cases if c.name.startswith(prefix))


def z(mag, xr):
    r = mag / math.sqrt(1 + xr ** 2)
    return complex(r, r * xr)


# Independent hand calculation of the shipped placeholders (IEC 60909, maximum fault):
#   MV: 1.10 x 13.8 kV^2 / 500 MVA = 0.41894 ohm; Ik'' = 500 MVA / (sqrt3 x 13.8 kV) = 20.92 kA
#   LV utility case: ZQ = 0.41894 x (400/13800)^2 = 3.5195e-4 ohm; ZT = 0.06 x 400^2 / 3.15 MVA x K_T, K_T = 0.95 x 1.05 / (1 + 0.6 x 0.06)
def test_mv_fault_level_equals_the_utility_power_over_root3_un(write_config, root):
    sc = assess_short_circuit(load(write_config, root))
    assert math.isclose(sc.mv_case.ik_ka, 500e6 / (math.sqrt(3) * 13800) / 1000, rel_tol=1e-9)


def test_lv_utility_case_matches_independent_complex_calculation(write_config, root):
    sc = assess_short_circuit(load(write_config, root))
    zq = z(1.10 * 13800 ** 2 / 500e6, 10) * (400 / 13800) ** 2
    kt = 0.95 * 1.05 / (1 + 0.6 * 0.06)
    zt = z(0.06 * 400 ** 2 / 3.15e6, 8) * kt
    expect = 1.05 * 400 / (math.sqrt(3) * abs(zq + zt)) / 1000
    assert math.isclose(case(sc, 'Utility and one').ik_ka, expect, rel_tol=1e-9) and 73.0 < expect < 74.5


def test_generator_case_uses_n_units_in_parallel(write_config, root):
    sc = assess_short_circuit(load(write_config, root))
    kg = 1.05 / (1 + 0.14 * 0.6)
    zg = z(0.14 * 400 ** 2 / 2.0e6, 20) * kg / 3
    assert math.isclose(case(sc, '3 generators').ik_ka, 1.05 * 400 / (math.sqrt(3) * abs(zg)) / 1000, rel_tol=1e-9)


def test_design_value_is_the_larger_single_source_unless_parallel_is_allowed(write_config, root):
    sc = assess_short_circuit(load(write_config, root))
    assert math.isclose(sc.design_lv.ik_ka, max(case(sc, 'Utility and one').ik_ka, case(sc, '3 generators').ik_ka))
    sc2 = assess_short_circuit(load(write_config, root, lambda d: set_value(d, "short_circuit", "generator_parallel_with_utility", True)))
    assert math.isclose(sc2.design_lv.ik_ka, case(sc2, 'Utility and one').ik_ka + case(sc2, '3 generators').ik_ka)


def test_a_higher_utility_fault_level_raises_the_lv_level(write_config, root):
    a = assess_short_circuit(load(write_config, root)).design_lv.ik_ka
    b = assess_short_circuit(load(write_config, root, lambda d: set_value(d, "short_circuit", "utility_fault_level_mva", 1500))).design_lv.ik_ka
    assert b > a


def test_peak_and_thermal_factors():
    assert math.isclose(peak_factor(10), 1.02 + 0.98 * math.exp(-0.3))
    assert thermal_factor(1.0, 1, 60) == 1.0 and thermal_factor(1.8, 1, 60) >= 1.0


def test_cable_adiabatic_minimum_section():
    assert math.isclose(cable_min_section_mm2(10.0, 1.0, 143), 10000 / 143)


def test_fault_level_above_the_limit_warns(write_config, root):
    r = by_id(run_all_checks(load(write_config, root, lambda d: set_value(d, "short_circuit", "lv_fault_level_limit_ka", 50))))
    assert r["fault_level_vs_limit"].status is S.WARNING


def test_the_parallel_case_is_flagged_when_it_exceeds_the_limit(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))["fault_level_vs_limit"]
    assert r.calculation_result == "PASS" and r.status is S.NOT_VERIFIED and "prevent the utility and generators" in r.detail


def test_equipment_ratings_below_the_fault_level_fail_and_above_pass(write_config, root, tmp_path):
    import copy
    import shutil

    import yaml

    cfg_path = write_config(supply_sc)
    dist = yaml.safe_load((cfg_path.parent / "distribution.yaml").read_text())
    for it in dist["switchgear"]:
        it["short_circuit_rating_ka"] = 50 if it["tag"] == "LV-MSB-A" else 31.5
    for it in dist["protection_devices"]:
        it["breaking_capacity_ka"] = 100
    (cfg_path.parent / "distribution.yaml").write_text(yaml.safe_dump(dist))
    ids = by_id(run_all_checks(load_config(cfg_path, root / "config" / "load_schedule.yaml")))
    items = {i["tag"]: i["status"] for i in ids["short_circuit_withstand"].values["items"]}
    assert items["LV-MSB-A"] == "FAIL" and items["MV-SWG-A"] == "PASS" and items["BD-TX-A"] == "NOT VERIFIED"
    assert ids["protection_devices"].calculation_result == "PASS" and ids["protection_devices"].status is S.NOT_VERIFIED      # ratings pass, inputs are unverified
    assert ids["short_circuit_withstand"].status is S.FAIL


def test_no_rating_means_not_verified_never_pass(write_config, root):
    ids = by_id(run_all_checks(load(write_config, root)))
    assert ids["short_circuit_withstand"].status is S.NOT_VERIFIED and ids["protection_devices"].status is S.NOT_VERIFIED


def test_an_undersized_cable_fails_thermal_withstand(write_config, root):
    cfg = load(write_config, root, lambda d: set_value(d, "short_circuit", "assumed_clearing_time_s", 5.0))
    assert by_id(run_all_checks(cfg))["cable_thermal_withstand"].status is S.FAIL


def test_grid_resistance_hand_calculation():
    # 100 ohm.m, 2500 m2, 1200 m, 0.5 m: 100 x (1/1200 + (1/223.607) x (1 + 1/1.044721)) = 0.9586 ohm
    assert math.isclose(grid_resistance(100, 2500, 1200, 0.5), 0.95862, rel_tol=1e-4)


def test_tolerable_touch_voltage_hand_calculation():
    cs = surface_layer_factor(100, 3000, 0.1)            # 1 - 0.09 x (1 - 100/3000) / 0.29 = 0.6998
    assert math.isclose(cs, 1 - 0.09 * (1 - 100 / 3000) / 0.29)
    assert math.isclose(tolerable_touch_v(3000, cs, 0.5), (1000 + 1.5 * cs * 3000) * 0.157 / math.sqrt(0.5))


def test_earthing_is_not_verified_without_fault_current_and_screens_when_supplied(write_config, root):
    assert by_id(run_all_checks(load(write_config, root)))["earthing_framework"].status is S.NOT_VERIFIED
    def sup(d):
        for k, v in (("earth_fault_current_ka", 0.5), ("fault_clearing_time_s", 0.5), ("surface_layer_resistivity_ohm_m", 3000), ("surface_layer_thickness_m", 0.1)):
            set_value(d, "earthing_study", k, v)
    r = by_id(run_all_checks(load(write_config, root, sup)))["earthing_framework"]
    assert r.calculation_result in ("PASS", "WARNING") and r.values["gpr_v"] == pytest.approx(0.5 * 1000 * 0.95862, rel=1e-3)


def test_the_shipped_configuration_holds_no_invented_utility_manufacturer_or_site_values(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    for pid in ("short_circuit.utility_fault_level_mva", "short_circuit.utility_x_r_ratio", "short_circuit.transformer_x_r_ratio", "short_circuit.generator_subtransient_reactance_pct",
                "short_circuit.generator_x_r_ratio", "earthing.soil_resistivity", "earthing_study.grid_area_m2", "earthing_study.grid_conductor_length_m",
                "earthing_study.grid_burial_depth_m"):
        assert cfg.value(pid) is None, pid


def test_shipped_results_are_not_calculated_and_list_what_is_missing(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    ids = by_id(run_all_checks(cfg))
    sc = assess_short_circuit(cfg)
    assert sc.mv_case is None and sc.design_lv is None
    assert [c.name for c in sc.lv_cases] == ["Transformer-limited upper bound"]      # the one result the available inputs support
    assert "short_circuit.utility_fault_level_mva" in sc.unavailable["MV bus, utility"]
    for cid in ("short_circuit_levels", "fault_level_vs_limit", "short_circuit_withstand", "protection_devices", "earthing_framework", "cable_thermal_withstand"):
        assert ids[cid].status is S.NOT_VERIFIED, cid
    assert "NOT CALCULATED" in ids["short_circuit_levels"].detail and "Source needed" in ids["short_circuit_levels"].detail
    assert "soil_resistivity" in ids["earthing_framework"].detail and "No default is substituted" in ids["earthing_framework"].detail


def test_the_transformer_limited_bound_needs_only_transformer_data(write_config, root):
    def only_tx(d):
        set_value(d, "equipment", "transformer_impedance", 6)
    sc = assess_short_circuit(load(write_config, root, only_tx) if False else load_config(write_config(only_tx), root / "config" / "load_schedule.yaml"))
    assert sc.mv_case is None and sc.design_lv is None
    b = case(sc, "Transformer-limited")
    kt = 0.95 * 1.05 / (1 + 0.6 * 0.06)
    assert math.isclose(b.ik_ka, 1.05 * 400 / (math.sqrt(3) * 0.06 * 400 ** 2 / 3.15e6 * kt) / 1000, rel_tol=1e-9)
    assert b.ip_ka is None            # no X/R supplied, so no peak is calculated


def _import(write_config, root, csv_text, mutate=lambda d: None):
    from ohmetry_dc.reporting import import_data, load_register_meta
    cfg_path = write_config(mutate)
    cfg = load_config(cfg_path, root / "config" / "load_schedule.yaml")
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    n, bad = import_data(csv_text, cfg_path.parent / "manufacturer_data_overrides.yaml", cfg, {e["parameter"] for e in meta}, "2026-11-06 09:00 UTC")
    return cfg_path, n, bad


HEAD = "parameter,value,unit,source,datasheet_revision,datasheet_reference\n"
LS = lambda root: root / "config" / "load_schedule.yaml"


def test_importing_data_reruns_dependent_calculations_without_touching_the_engine(write_config, root):
    rows = ("short_circuit.utility_fault_level_mva,500,MVA,Utility letter ref TEST-1,A,p2\nshort_circuit.utility_x_r_ratio,10,-,Utility letter ref TEST-1,A,p2\n"
            "short_circuit.transformer_x_r_ratio,8,-,Transformer data sheet TEST-2,B,table 3\n")
    cfg_path, n, bad = _import(write_config, root, HEAD + rows)
    assert n == 3 and bad == []
    cfg = load_config(cfg_path, LS(root))
    p = cfg.get("short_circuit.utility_fault_level_mva")
    assert p.status.value == "USER_INPUT" and "TEST-1" in p.source and p.datasheet_revision == "A" and p.original_value is None
    assert cfg.get("short_circuit.transformer_x_r_ratio").status.value == "MANUFACTURER_DATA"
    sc = assess_short_circuit(cfg)
    assert sc.mv_case is not None and case(sc, "Utility and one") is not None and sc.design_lv is None      # generator data still missing
    ids = by_id(run_all_checks(cfg))
    assert ids["short_circuit_levels"].status is S.NOT_VERIFIED
    assert "LV bus, generators" in ids["short_circuit_levels"].values["unavailable"]


def test_the_original_value_is_preserved_and_the_master_file_is_untouched(write_config, root):
    master = (root / "config" / "project_config.yaml").read_text()
    cfg_path, n, bad = _import(write_config, root, HEAD + "equipment.transformer_impedance,5.75,%,Transformer test report TEST-9,C,table 2\n")
    cfg = load_config(cfg_path, LS(root))
    p = cfg.get("equipment.transformer_impedance")
    assert p.value == 5.75 and p.original_value == 6 and "retained by the project owner" in p.original_source and p.status.value == "MANUFACTURER_DATA"
    assert (root / "config" / "project_config.yaml").read_text() == master


def test_history_is_append_only_and_records_previous_values(write_config, root):
    import yaml
    cfg_path, _, _ = _import(write_config, root, HEAD + "equipment.transformer_impedance,5.75,%,Report TEST-9,C,t2\n")
    from ohmetry_dc.reporting import import_data, load_register_meta
    cfg = load_config(cfg_path, LS(root))
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    import_data(HEAD + "equipment.transformer_impedance,6.1,%,Report TEST-9,D,t2\n", cfg_path.parent / "manufacturer_data_overrides.yaml", cfg, {e["parameter"] for e in meta}, "2026-11-07 09:00 UTC")
    data = yaml.safe_load((cfg_path.parent / "manufacturer_data_overrides.yaml").read_text())
    h = [x for x in data["history"] if x["parameter"] == "equipment.transformer_impedance"]
    assert [x["new_value"] for x in h] == [5.75, 6.1] and h[0]["previous_effective_value"] == 6 and h[1]["previous_effective_value"] == 5.75
    assert len(data["overrides"]) == 1 and data["overrides"][0]["datasheet_revision"] == "D"


def test_units_are_converted_and_unsupported_units_rejected(write_config, root):
    cfg_path, n, bad = _import(write_config, root, HEAD + "equipment.transformer_rating,3.15,MVA,Data sheet TEST-4,A,p1\nequipment.generator_rating,2,MVA,Data sheet TEST-5,A,p1\n")
    assert n == 2 and bad == []
    cfg = load_config(cfg_path, LS(root))
    assert cfg.value("equipment.transformer_rating") == pytest.approx(3150) and cfg.value("equipment.generator_rating") == pytest.approx(2000)
    for row, msg in (("equipment.transformer_rating,3150,hp,src,A,\n", "unsupported unit"), ("equipment.transformer_rating,3150,kW,src,A,\n", "cannot be converted"),
                     ("equipment.transformer_rating,3150,,src,A,\n", "needs a unit")):
        _, n, bad = _import(write_config, root, HEAD + row)
        assert n == 0 and msg in bad[0]


def test_values_are_range_checked(write_config, root):
    for row in ("equipment.generator_rating_power_factor,1.4,-,src,A,\n", "equipment.ups_efficiency,120,%,src,A,\n", "equipment.transformer_rating,-5,kVA,src,A,\n", "equipment.transformer_rating,abc,kVA,src,A,\n"):
        _, n, bad = _import(write_config, root, HEAD + row)
        assert n == 0 and bad, row


def test_import_rejects_unknown_parameters_missing_sources_and_missing_revisions(write_config, root):
    cfg_path, n, bad = _import(write_config, root, HEAD + "not.a.parameter,1,x,src,A,\nshort_circuit.utility_x_r_ratio,10,-,,A,\nequipment.transformer_impedance,6,%,src,,\n")
    assert n == 0 and len(bad) == 3 and not (cfg_path.parent / "manufacturer_data_overrides.yaml").exists()


def test_one_bad_row_rejects_the_whole_file(write_config, root):
    cfg_path, n, bad = _import(write_config, root, HEAD + "equipment.transformer_impedance,6,%,src,A,\nnot.a.parameter,1,x,src,A,\n")
    assert n == 0 and not (cfg_path.parent / "manufacturer_data_overrides.yaml").exists()


def test_distribution_fields_can_be_imported_with_their_source(write_config, root):
    cfg_path, n, bad = _import(write_config, root, HEAD + "distribution.LV-MSB-A.short_circuit_rating_ka,50,kA,Switchgear data sheet TEST-3,B,table 1\ndistribution.LV-MSB-A.ip_rating,IP31,,Switchgear data sheet TEST-3,B,\n")
    assert n == 2 and bad == []
    cfg = load_config(cfg_path, LS(root))
    sw = next(x for x in cfg.distribution["switchgear"] if x["tag"] == "LV-MSB-A")
    assert sw["short_circuit_rating_ka"] == 50 and sw["ip_rating"] == "IP31" and sw["data_sources"]["short_circuit_rating_ka"]["datasheet_revision"] == "B"


def test_manufacturer_verified_is_reachable_only_through_import_and_a_recorded_reviewer(write_config, root):
    from ohmetry_dc.models import data_status as ds
    cfg = load_config(root / "config" / "project_config.yaml", LS(root))
    for pid in ("equipment.transformer_impedance", "equipment.transformer_rating", "short_circuit.generator_x_r_ratio"):
        assert ds.data_status(cfg.get(pid), verified=True) not in (ds.MANUFACTURER_VERIFIED, ds.SITE_DATA_VERIFIED)      # a reviewer cannot verify a placeholder or a missing value
    cfg_path, _, _ = _import(write_config, root, HEAD + "short_circuit.generator_x_r_ratio,18,-,Generator data sheet TEST-6,A,p4\n")
    cfg2 = load_config(cfg_path, LS(root))
    assert ds.data_status(cfg2.get("short_circuit.generator_x_r_ratio"), False) == ds.MANUFACTURER_SUPPLIED
    assert ds.data_status(cfg2.get("short_circuit.generator_x_r_ratio"), True) == ds.MANUFACTURER_VERIFIED


def test_the_register_refuses_verification_of_a_placeholder(write_config, root):
    from ohmetry_dc.reporting import load_register_meta, problems
    cfg = load_config(write_config(lambda d: None), LS(root))
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    next(e for e in meta if e["parameter"] == "equipment.transformer_impedance")["verified_by"] = "A. Reviewer"
    assert any("still a placeholder" in p for p in problems(cfg, meta))


def test_register_lists_every_required_column_and_uses_the_data_status_vocabulary(root):
    from ohmetry_dc.reporting import build_rows, load_register_meta, to_markdown
    cfg = load_config(root / "config" / "project_config.yaml", LS(root))
    rows = build_rows(cfg, load_register_meta(root / "config" / "manufacturer_data_register.yaml"))
    classes = {r.data_class for r in rows}
    assert {"MISSING", "UNVERIFIED_PLACEHOLDER"} <= classes
    assert not classes & {"MANUFACTURER_VERIFIED", "SITE_DATA_VERIFIED"}          # nothing in the shipped package is verified
    md = to_markdown(rows, "now")
    for col in ("Equipment category", "Placeholder or current value", "Unit", "Verification status", "Outstanding verification action", "Input data status"):
        assert col in md
    assert next(r for r in rows if r.parameter == "equipment.transformer_impedance").category == "Transformer"


# ---- revision A6, item 7: short-circuit and protection honesty
def _cfg(root):
    from ohmetry_dc.config import load_config
    return load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")


def test_no_rating_or_requirement_is_selected_from_the_transformer_limited_figure(root):
    from ohmetry_dc.validation.checks import check_short_circuit
    cfg = _cfg(root)
    sc = assess_short_circuit(cfg)
    assert sc.design_lv is None and [c.name for c in sc.lv_cases] == ["Transformer-limited upper bound"]
    chk = {c.id: c for c in check_short_circuit(cfg)}
    for cid in ("short_circuit_withstand", "protection_devices"):
        assert all(i.get("required_ka", i.get("required_breaking_ka")) is None for i in (chk[cid].values.get("items") or chk[cid].values.get("devices"))), cid
        assert chk[cid].status.value == "NOT VERIFIED"
    assert all(i["min_section_mm2"] is None for i in chk["cable_thermal_withstand"].values["items"])


def test_the_transformer_limited_figure_is_never_described_as_the_bus_fault_level_or_a_design_value(root):
    from ohmetry_dc.validation.checks import check_short_circuit
    chk = {c.id: c for c in check_short_circuit(_cfg(root))}
    for cid in ("short_circuit_levels", "fault_level_vs_limit"):
        d = chk[cid].detail
        assert "excludes" in d or "not included" in d or "excludes the generator" in d, cid
        assert "valid for any utility fault level" not in d and "LV bus calculated" not in d
    assert "NOT a design value" in chk["short_circuit_levels"].detail and "NOT CALCULATED" in chk["fault_level_vs_limit"].detail
    assert chk["short_circuit_levels"].status.value == "NOT VERIFIED"


def test_every_case_that_lacks_data_reads_not_calculated_and_no_default_is_substituted(root):
    sc = assess_short_circuit(_cfg(root))
    assert set(sc.unavailable) >= {"MV bus, utility", "LV bus, generators"} or len(sc.unavailable) >= 3
    assert sc.mv_case is None and sc.design_lv is None


def test_arc_flash_is_explicitly_out_of_scope_and_never_calculated(root):
    from ohmetry_dc.validation.checks import check_short_circuit
    chk = {c.id: c for c in check_short_circuit(_cfg(root))}["arc_flash_scope"]
    assert chk.status.value == "NOT APPLICABLE" and "OUT OF SCOPE" in chk.detail and "No incident energy" in chk.detail


# ---- revision A6, item 8: earthing is a screening, lightning is out of scope
def test_earthing_is_labelled_a_screening_and_not_a_mesh_and_step_study_in_every_state(write_config, root):
    from ohmetry_dc.validation.checks import check_earthing
    r0 = check_earthing(_cfg(root))                       # the shipped configuration: no soil survey, no grid design
    assert "screening only" in r0.detail and "NOT CALCULATED" in r0.detail and "No default is substituted" in r0.detail
    def sup(d):
        for k, v in (("soil_resistivity", 100), ("grid_area_m2", 2500), ("grid_conductor_length_m", 1200), ("grid_burial_depth_m", 0.5), ("earth_fault_current_ka", 10), ("fault_clearing_time_s", 0.5),
                     ("surface_layer_resistivity_ohm_m", 3000), ("surface_layer_thickness_m", 0.1)):
            set_value(d, "earthing" if k == "soil_resistivity" else "earthing_study", k, v)
    r1 = by_id(run_all_checks(load(write_config, root, sup)))["earthing_framework"]
    assert "PRELIMINARY SCREENING ONLY" in r1.detail and "NOT a mesh and step voltage study" in r1.detail and "not an earthing design" in r1.detail
    assert r1.values["scope"].startswith("GPR screening only")


def test_lightning_is_out_of_scope_and_iec_62305_compliance_is_not_claimed(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))["lightning_scope"]
    assert r.status is S.NOT_APPLICABLE and "NOT claimed" in r.detail and r.values["compliance_claimed"] is False
