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
