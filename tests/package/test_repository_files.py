import yaml

REQUIRED = ["README.md", "LICENSE", "pyproject.toml", "requirements.txt", ".gitignore", "DEVELOPMENT_STATUS.md", "RELEASE_CHECKLIST.md", "ENGINEERING_REVIEW_LOG.md",
            "config/project_config.yaml", "config/load_schedule.yaml", "config/equipment_data_template.yaml", "config/standards_register.yaml", "config/assumptions_register.yaml", "config/design_basis_revisions.yaml"]


def test_required_files_exist(root):
    for rel in REQUIRED:
        assert (root / rel).is_file(), rel


def test_no_secrets_or_personal_data_in_the_repository(root):
    banned = ["password", "api_key", "secret", "@gmail.com", "BEGIN PRIVATE KEY"]
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts and "output" not in p.relative_to(root).parts[:1] and p.suffix in {".md", ".yaml", ".py", ".toml", ".txt"} and p.name != "test_repository_files.py":
            text = p.read_text(errors="ignore").lower()
            for b in banned:
                assert b.lower() not in text, f"{b!r} found in {p}"


def test_every_standard_starts_not_verified_with_no_invented_edition(root):
    reg = yaml.safe_load((root / "config" / "standards_register.yaml").read_text())
    assert len(reg["standards"]) >= 16
    for s in reg["standards"]:
        assert s["applicability_status"] == "NOT_VERIFIED" and s["edition"] is None, s["id"]


def test_equipment_template_contains_no_values(root):
    t = yaml.safe_load((root / "config" / "equipment_data_template.yaml").read_text())["equipment_template"]
    assert all(v in (None, "MANUFACTURER_DATA", "PENDING", "NOT_STARTED") or isinstance(v, dict) for v in t.values())


# ---- revision A6, item 11: document control and QA
import re as _re


def _er_rows(root):
    rows = []
    for line in (root / "ENGINEERING_REVIEW_LOG.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| ER-"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def test_engineering_review_log_is_complete_contiguous_and_every_row_has_nine_columns(root):
    rows = _er_rows(root)
    ids = [r[0] for r in rows]
    assert ids == [f"ER-{i:03d}" for i in range(1, len(ids) + 1)] and len(ids) >= 34
    assert all(len(r) == 9 for r in rows), [r[0] for r in rows if len(r) != 9]


def test_every_er_reference_in_the_code_tests_and_docs_exists_in_the_log(root):
    ids = {r[0] for r in _er_rows(root)}
    seen = set()
    for base in ("src", "tests", "docs", "config", "README.md", "DEVELOPMENT_STATUS.md", "RELEASE_CHECKLIST.md"):
        p = root / base
        for f in ([p] if p.is_file() else [x for x in p.rglob("*") if x.suffix in (".py", ".md", ".yaml")]):
            seen |= set(_re.findall(r"\bER-\d{3}\b", f.read_text(encoding="utf-8", errors="ignore")))
    assert not (seen - ids), sorted(seen - ids)


def test_open_items_have_no_closure_evidence_and_closed_or_addressed_items_name_it(root):
    for r in _er_rows(root):
        status, closure = r[7], r[8]
        if status.startswith("OPEN"):
            assert closure == "", r[0]
        if status.startswith(("CLOSED", "ADDRESSED")):
            assert closure, f"{r[0]} is {status} but names no closure evidence"


def test_no_generated_file_carries_a_different_revision_from_the_configuration(root):
    import json
    from ohmetry_dc.config import load_config
    rev = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml").project.revision
    stale = []
    for f in (root / "output").glob("*"):
        if f.suffix == ".json":
            m = _re.search(r'"revision":\s*"(A\d+)"', f.read_text(encoding="utf-8"))
            found = {m.group(1)} if m else set()
        elif f.suffix in (".md", ".csv"):
            found = set(_re.findall(r"\b[Rr]evision (A\d+)\b", f.read_text(encoding="utf-8")))
        else:
            continue
        if found - {rev}:
            stale.append((f.name, sorted(found)))
    assert not stale, f"generated files from another revision (regenerate with the release): {stale}"


def test_the_excel_limitation_is_stated_in_the_documents_a_buyer_or_reviewer_reads(root):
    for rel in ("ENGINEERING_REVIEW_LOG.md", "docs/release/CUSTOMER_README.md", "docs/release/REVIEW_GUIDE.md", "docs/release/REVIEWER_CHECKLIST.md"):
        t = " ".join((root / rel).read_text(encoding="utf-8").split())
        assert "Excel" in t and ("LibreOffice only" in t or "not available" in t), rel
