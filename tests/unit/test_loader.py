import pytest
import yaml

from ohmetry_dc.config import load_config
from ohmetry_dc.models import ConfigError, ReleaseState

from conftest import set_value


def test_shipped_configuration_loads(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    assert cfg.project.code == "OHM-DC-2000"
    assert cfg.project.release_state is ReleaseState.DEVELOPMENT
    assert cfg.value("general.it_critical_load") == 2000
    assert cfg.value("electrical_system.frequency") == 60


def test_every_parameter_has_complete_provenance(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    for pid, p in cfg.parameters.items():
        assert p.name and p.unit and p.description and p.source and p.revision and p.status, pid


def test_it_load_is_read_from_the_design_basis_not_copied(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    it = next(i for i in cfg.load_items if i.id == "IT-1")
    assert it.unit_rating_kw == cfg.value("general.it_critical_load") and it.rating_from == "general.it_critical_load"


def test_changing_the_it_load_changes_the_load_schedule(write_config, root):
    path = write_config(lambda d: set_value(d, "general", "it_critical_load", 3000))
    cfg = load_config(path, root / "config" / "load_schedule.yaml")
    assert next(i for i in cfg.load_items if i.id == "IT-1").unit_rating_kw == 3000


def test_missing_values_stay_missing_not_zero(root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    assert cfg.value("generators.max_step_load_pct") is None and cfg.value("battery.dc_bus_voltage_v") is None
    assert cfg.deferred() == []      # no input is deferred to a later stage at Stage 5


def test_inputs_for_later_stages_are_deferred_until_their_stage(write_config, root):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    assert [p.id for p in cfg.missing() if p.status.value == "USER_INPUT"] == []      # only manufacturer data is outstanding at this stage
    later = load_config(write_config(lambda d: d["project"].update(current_stage=5)), root / "config" / "load_schedule.yaml")
    assert later.missing() == cfg.missing()      # stage 5 inputs were supplied as placeholders, so nothing new is missing


def test_missing_file_gives_a_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml_gives_a_clear_error(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("a: [unclosed")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(p)


def test_dangling_value_ref_is_an_error(tmp_path, root):
    ls = yaml.safe_load((root / "config" / "load_schedule.yaml").read_text())
    ls["load_items"][0]["unit_rating_ref"] = "general.does_not_exist"
    p = tmp_path / "ls.yaml"
    p.write_text(yaml.safe_dump(ls))
    with pytest.raises(ConfigError, match="does not exist"):
        load_config(root / "config" / "project_config.yaml", p)


def test_wrong_schema_version_is_an_error(write_config):
    path = write_config(lambda d: d.update(schema_version=2))
    with pytest.raises(ConfigError, match="schema_version"):
        load_config(path)


def test_invalid_parameter_names_the_parameter(write_config):
    def mutate(d):
        d["sections"]["general"]["target_pue"]["status"] = "GUESS"
    with pytest.raises(ConfigError, match="general.target_pue"):
        load_config(write_config(mutate))


def test_load_schedule_errors_name_the_item(write_loads, root):
    def mutate(d):
        d["load_items"][1]["power_factor"] = 1.5
    with pytest.raises(ConfigError, match="MC-1"):
        load_config(root / "config" / "project_config.yaml", write_loads(mutate))


def test_duplicate_load_item_ids_are_rejected(write_loads, root):
    def mutate(d):
        d["load_items"][1]["id"] = "IT-1"
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(root / "config" / "project_config.yaml", write_loads(mutate))
