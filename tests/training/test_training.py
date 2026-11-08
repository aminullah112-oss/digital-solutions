import math
import re

import openpyxl

from ohmetry_dc.calculations import estimate_loads, size_power_system
from ohmetry_dc.config import load_config
from ohmetry_dc.training import build_modules, build_question_bank, build_training
from ohmetry_dc.training.content import _with

from conftest import STAMP, set_value


def _cfg(root):
    return load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")


def test_there_are_twelve_modules_with_every_required_section(root):
    mods = build_modules(_cfg(root))
    assert [m.no for m in mods] == list(range(1, 13))
    for m in mods:
        assert m.objectives and m.explanation and m.formulas and m.example and m.mistakes and m.checklist and m.exercises and m.references and m.limits, m.title
        assert any("not accredited" in x for x in m.limits)


def test_exercise_answers_agree_with_independent_calculations(root):
    ex = {e.id: e for m in build_modules(_cfg(root)) for e in m.exercises}
    assert ex["1.1"].answer == (2500e3 / (math.sqrt(3) * 400)) and abs(ex["1.1"].answer - 3608.44) < 0.01
    assert abs(ex["1.2"].answer - 1897.37) < 0.01 and abs(ex["2.1"].answer - 127.66) < 0.01
    assert abs(ex["4.1"].answer - 2866 / 0.855) < 1e-9 and abs(ex["5.1"].answer - 1600) < 1e-9 and ex["6.1"].answer == 360
    assert abs(ex["8.1"].answer - 0.017241 * (1 + 0.00393 * 70) / 120 * 1000) < 1e-12 and abs(ex["9.2"].answer - 10.459) < 0.001 and abs(ex["10.1"].answer - 0.95862) < 1e-4
    assert ex["11.1"].answer == "NOT VERIFIED" and ex["11.2"].answer == "WARNING" and ex["12.1"].answer == 800


def test_engine_based_exercises_match_the_engine(root):
    cfg = _cfg(root)
    ex = {e.id: e for m in build_modules(cfg) for e in m.exercises}
    c94 = _with(cfg, equipment__ups_efficiency=94.0)
    assert abs(ex["2.2"].answer - estimate_loads(c94).pue) < 1e-12
    c4 = _with(cfg, equipment__transformer_rating=4000)
    t = next(s for s in size_power_system(c4, estimate_loads(c4)).transformer.scenarios if s.id == "TX-PATH-OUT")
    assert abs(ex["3.1"].answer - t.loading * 100) < 1e-9
    # the transformer-limited fault level exercise matches the engine when it is given the same inputs
    from ohmetry_dc.calculations import assess_short_circuit
    c = _with(cfg, equipment__transformer_rating=2500)
    b = next(x for x in assess_short_circuit(c).lv_cases if x.name.startswith("Transformer-limited"))
    assert abs(ex["4.2"].answer - b.ik_ka) < 1e-9


def test_worked_examples_follow_the_configuration(root, write_config):
    base = " ".join(" ".join(m.example) for m in build_modules(_cfg(root)))
    cfg2 = load_config(write_config(lambda d: set_value(d, "equipment", "transformer_rating", 4000)), root / "config" / "load_schedule.yaml")
    changed = " ".join(" ".join(m.example) for m in build_modules(cfg2))
    assert "3,150 kVA" in base and "4,000 kVA" in changed and "3,150 kVA transformer (derating" not in changed


def test_question_bank_is_well_formed(root):
    bank = build_question_bank(build_modules(_cfg(root)))
    assert len(bank) == 48 and len({q["id"] for q in bank}) == 48
    for q in bank:
        assert len(q["options"]) == 4 and 0 <= q["answer_index"] < 4 and q["explanation"] and q["question"].endswith(("?", ":"))
    assert {q["module"] for q in bank} == set(range(1, 13))


def test_no_clause_numbers_or_unverified_claims_are_quoted(root):
    text = " ".join(" ".join(m.explanation + m.example + m.references) for m in build_modules(_cfg(root)))
    assert not re.search(r"[Cc]lause\s*\d|[Ss]ection\s*\d+\.\d|Table\s*\d", text)
    assert "approved" not in text.lower() and "certified" not in text.lower().replace("not accredited", "")


def test_the_suite_is_generated_with_certificate_wording_and_no_answers_in_the_exercises(root, tmp_path):
    paths = build_training(_cfg(root), tmp_path, STAMP)
    names = {p.name for p in paths}
    assert {"Exercise_Workbook.xlsx", "Answer_Key.pdf", "Answer_Key.md", "Question_Bank.csv", "Completion_Certificate_Template.pdf"} <= names
    assert sum(1 for p in paths if p.suffix == ".pdf" and p.parent.name == "modules") == 12 and sum(1 for p in paths if p.parent.name == "source") == 12
    cert = (tmp_path / "Completion_Certificate_Template.md").read_text()
    assert "not a government, university, professional-body or accredited certification" in cert
    ws = openpyxl.load_workbook(tmp_path / "exercises" / "Exercise_Workbook.xlsx")["EXERCISES"]
    assert all(ws.cell(r, 4).value is None for r in range(5, ws.max_row + 1))          # the learner's answer cells are empty
    first = next(build_modules(_cfg(root))[0].exercises.__iter__())
    assert f"{first.answer:,.0f}" not in (tmp_path / "modules" / "source" / "01_Introduction_to_Data_Centre_Electrical_Design.md").read_text()      # the answer is not in the module
