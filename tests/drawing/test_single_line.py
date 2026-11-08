import xml.etree.ElementTree as ET

from ohmetry_dc.config import load_config
from ohmetry_dc.drawings import build_single_line_svg

from conftest import STAMP, set_value


def _svg(root, mutate=None, write_config=None):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml") if mutate is None else load_config(write_config(mutate), root / "config" / "load_schedule.yaml")
    return build_single_line_svg(cfg, STAMP)


def test_the_diagram_is_valid_svg_with_every_major_tag(root):
    svg = _svg(root)
    ET.fromstring(svg)
    for tag in ("MV-SWG-A", "MV-SWG-B", "TX-A1", "TX-B1", "LV-MSB-A", "LV-MSB-B", "GEN-A1", "GEN-A3", "GEN-B1", "GEN-B3", "UPS-A1", "UPS-B1", "BAT-A1", "BAT-B1", "BD-TX-A", "ACB-TX-A", "ACB-GEN-B",
                "ACB-UPS-IN-A", "MV-CB-B", "CAB-MECH-A", "IT-DIST-B"):
        assert tag in svg, tag


def test_the_diagram_states_it_is_preliminary_and_shows_no_unverified_values_as_facts(root):
    svg = _svg(root)
    assert "NOT FOR CONSTRUCTION" in svg and "NOT VERIFIED" in svg and "PRELIMINARY" in svg
    assert "NOT CALCULATED" in svg and "NOT confirmed" in svg and "not assigned" in svg
    assert "APPROVED" not in svg.upper().replace("DRAWN / CHECKED / APPROVED", "")      # no approval is implied
    assert " kA" not in svg                                                              # no fault level or device rating is printed


def test_ratings_on_the_diagram_follow_the_master_configuration(root, write_config):
    base = _svg(root)
    assert "3,150 kVA" in base and "2,000 kVA" in base and "2,500 kW" in base
    changed = _svg(root, lambda d: (set_value(d, "equipment", "transformer_rating", 4000), set_value(d, "equipment", "generator_quantity_per_path", 4)), write_config)
    assert "4,000 kVA, 13.8/0.4 kV" in changed and "3,150 kVA, 13.8" not in changed and "GEN-A4" in changed and "GEN-A4" not in base


def test_architecture_concept_symbols_are_drawn_and_labelled_not_designed(root):
    svg = _svg(root)
    for tag in ("GCB-A1", "GCB-A3", "GCB-B1", "PMS-A", "PMS-B", "STS-A", "STS-B", "MBB-A", "MBB-B", "BAT-ISO-A", "BAT-ISO-B", "Interlock ACB-TX / ACB-GEN", "UPS system boundary", "Point of connection and ownership boundary"):
        assert tag in svg, tag
    for words in ("synchronising", "load sharing", "load shedding", "static bypass", "maintenance bypass", "scheme not designed", "not designed"):
        assert words in svg, words


def test_independence_of_the_two_utility_supplies_is_not_claimed(root):
    svg = _svg(root)
    assert "NOT claimed" in svg
    assert "independent supplies" not in svg.lower() and "fully independent" not in svg.lower() and "redundant utility" not in svg.lower()


def test_dual_corded_it_load_is_one_load_not_two_and_never_shown_as_4_mw(root):
    svg = _svg(root)
    assert svg.count(">IT LOAD<") == 1 and "dual-corded" in svg
    assert "4,000 kW" not in svg and "IT LOAD A" not in svg


def test_every_architecture_function_has_a_status_and_a_need_and_a_tag_on_the_drawing(root):
    from ohmetry_dc.models.architecture import ARCHITECTURE_FUNCTIONS, NOT_CLAIMED, NOT_DESIGNED
    assert len({a.id for a in ARCHITECTURE_FUNCTIONS}) == len(ARCHITECTURE_FUNCTIONS) >= 12
    svg = _svg(root)
    for a in ARCHITECTURE_FUNCTIONS:
        assert a.needed and a.shown_as and a.status
        assert a.status in (NOT_CLAIMED, NOT_DESIGNED, "PRELIMINARY ASSUMPTION"), a.id
        assert "VERIFIED" not in a.status.replace("NOT VERIFIED", "") and "APPROVED" not in a.status.upper()
    assert any(a.status == NOT_CLAIMED for a in ARCHITECTURE_FUNCTIONS)
    assert "ACB-GEN" in svg and "GCB-" in svg


def test_generators_per_path_scale_with_the_configuration(root, write_config):
    svg = _svg(root, lambda d: set_value(d, "equipment", "generator_quantity_per_path", 4), write_config)
    ET.fromstring(svg)
    assert "GCB-A4" in svg and "GCB-B4" in svg
