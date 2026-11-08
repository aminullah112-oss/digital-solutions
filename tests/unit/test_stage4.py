import math

import yaml

from ohmetry_dc.calculations.distribution import classify_max, resistance_ohm_per_m, voltage_drop_three_phase
from ohmetry_dc.config import load_config
from ohmetry_dc.reporting import build_rows, load_register_meta, problems, required_ids
from ohmetry_dc.validation import run_all_checks
from ohmetry_dc.validation.status import CheckStatus as S

from conftest import attest, set_value


def load(write_config, root, mutate=lambda d: None):
    return load_config(write_config(mutate), root / "config" / "load_schedule.yaml")


def by_id(results):
    return {r.id: r for r in results}


# Hand calculation: 630 mm2 copper at 90 C
def test_conductor_resistance_matches_hand_calculation():
    assert math.isclose(resistance_ohm_per_m("copper", 630, 90) * 1e6, 34.895, rel_tol=1e-4)  # 0.017241 x (1 + 0.00393 x 70) / 630 = 3.4895e-5 ohm/m, referred to 20 C


def test_three_phase_voltage_drop_formula():
    v, pct = voltage_drop_three_phase(1000, 100, 1e-4, 0.0, 1.0, 400)
    assert math.isclose(v, math.sqrt(3) * 1000 * 100 * 1e-4, rel_tol=1e-9)
    assert math.isclose(pct, v / 400 * 100, rel_tol=1e-9)


def test_max_loading_classification():
    assert classify_max(100.0, 100.0).value == "PASS" and classify_max(100.1, 100.0).value == "FAIL"


def test_transformer_exception_never_turns_warning_into_pass(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))["transformer_loading"]
    assert r.status is S.WARNING and "EX-001" in (r.detail + str(r.values))


def test_exception_does_not_cover_a_result_above_its_ceiling(write_config, root):
    cfg = load(write_config, root, lambda d: d["sections"]["equipment"]["transformer_rating"].update(value=2900))
    r = by_id(run_all_checks(cfg))["transformer_loading"]      # about 98.8 percent: above the 91.0 percent ceiling
    assert r.status is S.WARNING and r.values["exception"]["applies"] is False
    cfg = load(write_config, root, lambda d: d["sections"]["equipment"]["transformer_rating"].update(value=2700))
    assert by_id(run_all_checks(cfg))["transformer_loading"].status is S.FAIL      # above 100 percent


def test_transformer_derating_raises_loading(write_config, root):
    base = by_id(run_all_checks(load(write_config, root)))["transformer_loading"].values
    cfg = load(write_config, root, lambda d: set_value(d, "derating", "transformer_ambient_factor", 0.9))
    r = by_id(run_all_checks(cfg))["transformer_loading"]
    assert r.status is S.FAIL and r.values != base


def test_unconfirmed_prp_basis_is_reported_not_verified(write_config, root):
    r = by_id(run_all_checks(load(write_config, root)))["generator_rating_basis"]
    assert r.status is S.NOT_VERIFIED


def test_generator_kw_loading_is_checked_with_the_rated_power_factor(write_config, root):
    ids = by_id(run_all_checks(load(write_config, root)))
    assert "generator_loading_kw" in ids and ids["generator_loading_kw"].calculation_result in ("PASS", "WARNING")


def test_missing_cable_data_is_not_verified_never_pass(write_config, root):
    ids = by_id(run_all_checks(load(write_config, root)))
    assert ids["cable_ampacity"].status is S.NOT_VERIFIED and ids["busduct_voltage_drop"].status is S.NOT_VERIFIED


def test_voltage_drop_limit_failure(write_config, root):
    cfg = load(write_config, root, lambda d: d["sections"]["design_criteria"]["voltage_drop_limit_pct"].update(value=0.1))
    ids = by_id(run_all_checks(cfg))
    assert any(x.status is S.FAIL for x in ids.values() if x.id == "cable_voltage_drop")


def test_register_covers_every_manufacturer_item(write_config, root):
    cfg = load(write_config, root)
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    assert problems(cfg, meta) == []
    assert required_ids(cfg) <= {e["parameter"] for e in meta}
    assert all(r.data_state != "NOT APPLICABLE" for r in build_rows(cfg, meta))


def test_register_detects_a_missing_entry(write_config, root):
    cfg = load(write_config, root)
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")[1:]
    assert any("missing register entry" in p for p in problems(cfg, meta))


def test_register_rejects_verification_of_a_placeholder(write_config, root):
    cfg = load(write_config, root)
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    meta[0] = attest(dict(meta[0]))
    assert any("still a placeholder" in p for p in problems(cfg, meta))


def test_supplying_manufacturer_data_changes_the_register_state(write_config, root):
    cfg = load(write_config, root, lambda d: d["sections"]["generators"]["max_step_load_pct"].update(value=60, status="MANUFACTURER_DATA"))
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    row = next(r for r in build_rows(cfg, meta) if r.parameter == "generators.max_step_load_pct")
    assert row.data_state == "SUPPLIED, REVIEW REQUIRED" and row.value == 60 and row.data_class == "MANUFACTURER_SUPPLIED"


# ---- revision A6, item 9
def test_a_register_entry_with_only_a_name_is_an_incomplete_record_and_is_not_verified(write_config, root):
    cfg = load(write_config, root, lambda d: d["sections"]["generators"]["max_step_load_pct"].update(value=60, status="MANUFACTURER_DATA"))
    meta = load_register_meta(root / "config" / "manufacturer_data_register.yaml")
    e = next(x for x in meta if x["parameter"] == "generators.max_step_load_pct")
    e["verified_by"] = "A. Reviewer"                                      # a bare name: the whole record is not there
    row = next(r for r in build_rows(cfg, meta) if r.parameter == "generators.max_step_load_pct")
    assert row.verified_by is None and row.data_class == "MANUFACTURER_SUPPLIED" and row.data_state == "SUPPLIED, REVIEW REQUIRED"
    msg = " ".join(problems(cfg, meta))
    assert "incomplete verification record" in msg and "verified_org" in msg and "evidence_ref" in msg and "verification_scope" in msg
    attest(e)
    row = next(r for r in build_rows(cfg, meta) if r.parameter == "generators.max_step_load_pct")
    assert row.verified_by == "A. Reviewer" and "self-declared attestation" in row.attestation and "Data sheet DS-1 rev A" in row.attestation
    assert row.data_class == "MANUFACTURER_SUPPLIED"       # a value typed into the master config is not an import, so it can never read VERIFIED (the import path is tested in test_cli)


def test_the_register_text_states_the_name_is_not_authenticated(write_config, root):
    from ohmetry_dc.reporting import to_csv, to_markdown
    cfg = load(write_config, root)
    rows = build_rows(cfg, load_register_meta(root / "config" / "manufacturer_data_register.yaml"))
    assert "not an authenticated identity" in to_markdown(rows, "stamp") and to_csv(rows).splitlines()[0].endswith("attestation")


def test_a_design_exception_needs_a_complete_record_before_it_reads_verified(write_config, root):
    from ohmetry_dc.validation.exceptions import apply_exceptions
    def detail(mut):
        def m(d):
            pass
        cfg = load(write_config, root)
        for ex in cfg.exceptions:
            mut(ex)
        res = {r.id: r for r in apply_exceptions(cfg, run_all_checks(cfg))}
        return res["transformer_loading"]
    none = detail(lambda ex: None)
    assert "pending independent technical verification" in none.detail and none.values["exception"]["verified"] is False
    partial = detail(lambda ex: setattr(ex, "verified_by", "A. Reviewer"))
    assert "INCOMPLETE" in partial.detail and partial.values["exception"]["verified"] is False and partial.status is S.WARNING
    def full(ex):
        for k, v in dict(verified_by="A. Reviewer", verified_org="Example Engineering Ltd", verification_date="2026-11-01", evidence_ref="TX data sheet rev A", verification_scope="rating and cooling class").items():
            setattr(ex, k, v)
    done = detail(full)
    assert "attested verified" in done.detail and done.values["exception"]["verified"] is True and done.status is S.WARNING       # an exception never turns a WARNING into a PASS
