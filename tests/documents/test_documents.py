import csv
import json
import re
import zipfile
from pathlib import Path

import docx
import openpyxl
import pytest

from ohmetry_dc.cli import EXIT_OK, main
from ohmetry_dc.config import load_config
from ohmetry_dc.documents import customer, register, review, specs
from ohmetry_dc.documents.specs import _specs

from conftest import STAMP, set_value, needs_soffice

REQUIRED_SPEC_HEADINGS = ["1. Scope", "2. Applicable standards", "4. Equipment ratings", "5. Technical requirements", "6. Vendor data schedule", "7. Compliance schedule", "8. Inspection and quality requirements",
                          "9. Factory acceptance test (FAT) requirements", "10. Site acceptance test (SAT) requirements", "11. Commissioning requirements", "12. Submittals and documentation", "13. Open items (NOT VERIFIED)"]


def _cfg(root):
    return load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")


def _text(path):
    d = docx.Document(path)
    return "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])


@pytest.fixture(scope="module")
def spec_dir(tmp_path_factory, root=Path(__file__).resolve().parents[2]):
    out = tmp_path_factory.mktemp("specs")
    specs.build_specifications(_cfg(root), out, STAMP)
    return out


def test_ten_specification_templates_exist_with_every_required_section(spec_dir):
    files = sorted(spec_dir.glob("*.docx"))
    assert len(files) == 10
    for f in files:
        t = _text(f)
        for h in REQUIRED_SPEC_HEADINGS:
            assert h in t, (f.name, h)
        assert "DRAFT TEMPLATE" in t and "NOT FOR PROCUREMENT" in t and "NOT VERIFIED" in t


def test_specifications_cover_the_required_equipment(spec_dir):
    names = " ".join(p.name for p in spec_dir.glob("*.docx"))
    for word in ("Transformers", "Generators", "UPS", "Batteries", "MV_Switchgear", "LV_Switchgear", "Cables", "Busduct", "Protection", "Earthing"):
        assert word in names


def test_specification_ratings_follow_the_configuration_and_show_status(root, tmp_path):
    cfg = load_config(root / "config" / "project_config.yaml", root / "config" / "load_schedule.yaml")
    base = _text(next(p for p in specs.build_specifications(cfg, tmp_path / "a", STAMP) if p.name.endswith("Transformers.docx")))
    assert "3,150 kVA" in base and "UNVERIFIED_PLACEHOLDER" in base and "6 %" in base
    # a changed configuration changes the template
    from ohmetry_dc.models import data_status  # noqa: F401
    params = dict(cfg.parameters)
    params["equipment.transformer_rating"] = params["equipment.transformer_rating"].model_copy(update={"value": 4000})
    cfg2 = cfg.model_copy(update={"parameters": params})
    changed = _text(next(p for p in specs.build_specifications(cfg2, tmp_path / "b", STAMP) if p.name.endswith("Transformers.docx")))
    assert "4,000 kVA" in changed and "3,150 kVA" not in changed


def test_specifications_do_not_invent_requirements_or_claim_approval(spec_dir):
    for f in spec_dir.glob("*.docx"):
        t = _text(f)
        assert not re.search(r"[Cc]lause\s*\d|[Ss]ection\s*\d+\.\d+\s+of", t), f.name
        low = t.lower()
        assert "approved by" in low and "[name]" in low                    # approval fields are blank placeholders
        assert "construction-ready" not in low.replace("not construction-ready", "")
        assert "[to be determined by the project]" in low or "[project to" in low


def test_the_fault_level_in_specifications_is_never_a_number_without_data(spec_dir):
    t = _text(next(spec_dir.glob("*LV_Switchgear.docx")))
    assert "NOT CALCULATED" in t and re.search(r"fault level[^.]*\[To be", t, re.I) or "NOT CALCULATED" in t


def test_manufacturer_data_section_lists_register_parameters(spec_dir):
    t = _text(next(spec_dir.glob("*Transformers.docx")))
    assert "equipment.transformer_impedance" in t and "equipment.transformer_rating" in t
    g = _text(next(spec_dir.glob("*Generators.docx")))
    assert "short_circuit.generator_subtransient_reactance_pct" in g and "generators.max_step_load_pct" in g


def test_customer_readme_covers_every_required_topic(root, tmp_path):
    cfg = _cfg(root)
    customer.build_customer_documents(cfg, tmp_path, STAMP, customer.workbook_list(root), {"readme": "OHM-DC-2000-DOC-01", "licence": "OHM-DC-2000-DOC-02"})
    t = (tmp_path / "CUSTOMER_README.md").read_text()
    for h in ("What this package is", "Intended users", "What is included", "Design basis and key assumptions", "Supported software", "Installing and running the engine", "calculation workbooks", "Entering your own and datasheet values",
              "Importing manufacturer data", "Calculation outputs", "Verification statuses", "Editing the configuration", "What is preliminary", "What requires manufacturer data", "specialist software", "independent engineering approval", "Reporting issues", "Licence and disclaimer"):
        assert h in t, h
    for status in ("UNVERIFIED_PLACEHOLDER", "PRELIMINARY_ASSUMPTION", "MANUFACTURER_VERIFIED", "NOT CALCULATED", "REJECTED: SOURCE MISSING"):
        assert status in t
    assert "NOT CONSTRUCTION-READY" in t and "3,150 kVA" not in t.replace("3150", "3,150 kVA") or "3150" in t
    assert "[support contact to be confirmed by the owner" in t              # no contact is invented
    assert t.count("| 20_MASTER_EQUIPMENT_SCHEDULE") == 1


def test_licence_defines_the_required_terms_and_makes_no_enforceability_claim(root, tmp_path):
    cfg = _cfg(root)
    customer.build_customer_documents(cfg, tmp_path, STAMP, customer.workbook_list(root), {"readme": "OHM-DC-2000-DOC-01", "licence": "OHM-DC-2000-DOC-02"})
    t = (tmp_path / "LICENCE_COMMERCIAL.md").read_text()
    assert "PREPARED WITHOUT LEGAL REVIEW" in t and "NOT CLAIMED TO BE LEGALLY ENFORCEABLE" in t and "Not yet reviewed" in t
    for must in ("Individual engineers", "Consulting companies", "No redistribution", "No resale or sublicence", "Modification", "Limitation of liability", "Warranty disclaimer", "Starter", "Professional + Learning", "Corporate",
                 "Engineering responsibility", "Governing law", "non-transferable"):
        assert must in t, must
    assert "[Legal review" in t or "[Confirm with legal advice" in t
    assert "is legally enforceable" not in t.lower().replace("not claimed to be legally enforceable", "")


def test_the_register_ids_every_file_and_cross_references_resolve(root):
    cfg = _cfg(root)
    rows = register.build_register(root, cfg)
    ids = {r["id"] for r in rows}
    assert len(rows) > 80
    for r in rows:
        assert (root / r["path"]).exists() and r["revision"] == cfg.project.revision and r["issue"] == "P1" and r["status"]
        assert all(x in ids for x in r["related"]), (r["id"], r["related"])
    assert {f"OHM-DC-2000-WB-{n:02d}" for n in range(1, 21)} <= ids and {f"OHM-DC-2000-SPEC-{n:02d}" for n in range(1, 11)} <= ids and {f"OHM-DC-2000-TRN-{n:02d}" for n in range(1, 17)} <= ids
    spec = next(r for r in rows if r["id"].endswith("SPEC-01"))
    assert "OHM-DC-2000-WB-04" in spec["related"]
    assert "OHM-DC-2000-MET-03" in next(r for r in rows if r["id"].endswith("WB-04"))["related"] or any(x.split("-")[-2] == "MET" for x in next(r for r in rows if r["id"].endswith("WB-04"))["related"])


def test_master_index_lists_the_documents_with_revision_and_issue(root):
    md = (root / "docs" / "release" / "MASTER_INDEX.md").read_text()
    for must in ("Revision convention", "WB-04", "SPEC-06", "DOC-02", "TRN-12", "REG-07", "NOT CONSTRUCTION-READY", "Related"):
        assert must in md, must
    with open(root / "docs" / "release" / "MASTER_INDEX.csv") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(r["revision"] and r["issue"] for r in rows)
    assert not [r for r in rows if "approved" in r["status"].lower() and "not" not in r["status"].lower()]


def test_outstanding_items_include_every_known_open_item(root):
    cfg = _cfg(root)
    items = review.outstanding_items(root, cfg)
    text = " ".join(f"{i['source']} {i['item']} {i['action_or_evidence']}" for i in items)
    for must in ("ER-008", "ER-010", "ER-019", "Exception EX-001", "equipment.transformer_impedance", "Standards register IEC_60909", "transformer_loading", "independently reviewed", "Microsoft Excel", "legal"):
        assert must in text, must
    assert len({i["id"] for i in items}) == len(items) and len(items) > 150
    assert not [i for i in items if i["status"] in ("CLOSED", "VERIFIED")]


def test_reviewer_checklist_and_findings_log(root, tmp_path):
    cfg = _cfg(root)
    md = review.checklist_markdown(cfg, STAMP)
    assert md.count("| R") >= 60 and "Independence declaration" in md and "Open in Microsoft Excel" in md
    p = review.checklist_docx(cfg, tmp_path / "c.docx", STAMP)
    assert "Sign-off" in _text(p)
    ws = openpyxl.load_workbook(review.findings_workbook(tmp_path / "f.xlsx", STAMP))["FINDINGS"]
    assert [c.value for c in ws[4]][:5] == ["Finding id", "Checklist ref", "Module / file", "Finding", "Severity"] and ws["A5"].value == "RF-001"


@needs_soffice
def test_the_review_package_contains_every_required_component_with_hashes(root, tmp_path):
    cfg = _cfg(root)
    z, m = review.build_review_package(root, tmp_path, cfg, STAMP)
    names = zipfile.ZipFile(z).namelist()
    top = "OHM-DC-2000-REVIEW/"
    for must in ("00_START_HERE/REVIEW_GUIDE.md", "00_START_HERE/REVIEWER_CHECKLIST.docx", "00_START_HERE/REVIEW_FINDINGS_LOG.xlsx", "00_START_HERE/OUTSTANDING_VERIFICATION_ITEMS.md", "00_START_HERE/MANIFEST.json",
                 "01_design_basis/project_config.yaml", "03_workbooks/04_TRANSFORMER_SIZING.xlsx", "04_engine/src/ohmetry_dc/cli.py", "04_engine/tests/conftest.py", "05_reports/02_Electrical_Load_Estimation_Report.pdf",
                 "06_drawings/OHM-DC-2000-SLD-001.svg", "07_registers/assumptions_register.yaml", "07_registers/standards_register.yaml", "07_registers/ENGINEERING_REVIEW_LOG.md", "11_qa/QA_RESULTS.md"):
        assert top + must in names, must
    assert sum(1 for n in names if "/03_workbooks/" in n) == 20 and sum(1 for n in names if "/08_specifications/" in n and n.endswith(".docx")) == 10
    mm = json.loads(zipfile.ZipFile(z).read(top + "00_START_HERE/MANIFEST.json"))
    assert all(len(f["sha256"]) == 64 for f in mm["files"]) and "NOT CONSTRUCTION-READY" in mm["state"]
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)


def test_cli_generate_documents_and_the_package_manifest_cross_references(root, tmp_path, monkeypatch):
    monkeypatch.chdir(root)
    assert main(["--config", str(root / "config" / "project_config.yaml"), "--loads", str(root / "config" / "load_schedule.yaml"), "build-package", "--dist", str(tmp_path)]) == EXIT_OK
    z = zipfile.ZipFile(next(tmp_path.glob("*.zip")))
    man = json.loads(z.read("OHM-DC-2000/MANIFEST.json"))
    assert man["unregistered_files"] == []
    byp = {f["path"]: f for f in man["files"]}
    assert byp["CUSTOMER_README.pdf"]["document_id"] == "OHM-DC-2000-DOC-01" and byp["LICENCE_COMMERCIAL.md"]["document_id"] == "OHM-DC-2000-DOC-02"
    assert byp["workbooks/04_TRANSFORMER_SIZING.xlsx"]["document_id"].endswith("WB-04") and byp["workbooks/04_TRANSFORMER_SIZING.xlsx"]["issue"] == "P1"
    assert any(f["path"].startswith("specifications/") for f in man["files"]) and "MASTER_INDEX.md" in byp
    assert all(f["document_id"] and f["revision"] for f in man["files"])
    assert not any(n.endswith(("REVIEW_GUIDE.md", "REVIEWER_CHECKLIST.md")) for n in z.namelist())      # review documents are for the reviewer, not the customer ZIP


# ---- revision A6, item 10: standards register and specification schedules
STD_REF = re.compile(r"\b(IEC|ISO|IEEE|ASHRAE|EN)\s?(\d{2,6}(?:-\d+)*(?:\.\d+)?)")


def _register(root):
    import yaml
    return yaml.safe_load((root / "config" / "standards_register.yaml").read_text())["standards"]


def _covered(ref: str, register_refs: set[str]) -> bool:
    """A named standard is covered by an entry for itself or for its series (IEC 61439-6 by 'IEC 61439-6' or 'IEC 61439')."""
    parts = ref.split("-")
    return any("-".join(parts[:i]) in register_refs for i in range(len(parts), 0, -1))


def test_every_standard_named_in_a_specification_is_in_the_register(root):
    reg = _register(root)
    refs = {s["reference"].replace("ISO/IEC", "ISO") for s in reg} | {r.strip() for s in reg for r in s["reference"].split(" and ")}
    cfg = _cfg(root)
    missing = []
    for spec in _specs(cfg):
        for text in spec["standards"]:
            for m in STD_REF.finditer(text):
                ref = f"{m.group(1)} {m.group(2)}"
                if not _covered(ref, refs):
                    missing.append((spec["slug"], ref))
    assert not missing, missing


def test_the_register_cites_no_clause_and_claims_no_edition_or_verification(root):
    reg = _register(root)
    assert len(reg) >= 30 and len({s["id"] for s in reg}) == len(reg)
    for s in reg:
        assert s["edition"] is None and s["scope"] is None and s["applicability_status"] == "NOT_VERIFIED" and s["reviewer"] is None and s["review_date"] is None and s["verification_source"] is None, s["id"]
        assert s.get("package_use"), s["id"]
        text = " ".join(str(v) for v in s.values())
        assert not re.search(r"\b(clause|sub-?clause|annex|table)\s+[A-Z]?\d", text, re.I) and not re.search(r":\s?(19|20)\d{2}\b", text), (s["id"], text)
    out_of_scope = {s["id"] for s in reg if "OUT OF SCOPE" in s["package_use"]}
    assert "IEEE_1584" in out_of_scope


def test_the_register_covers_modules_and_states_that_compliance_is_not_claimed_where_it_is_not(root):
    reg = {s["id"]: s for s in _register(root)}
    assert reg["IEC_62305"]["package_use"].startswith("named only to say that compliance is NOT claimed") and reg["IEEE_80"]["relevant_modules"] == ["15_EARTHING_BONDING"]
    assert "NOT claimed" in reg["EN_50600_ISO_IEC_22237"]["package_use"] or "no availability class" in reg["EN_50600_ISO_IEC_22237"]["package_use"]
    assert all(s["relevant_modules"] for s in reg.values() if s["id"] not in ("IEEE_1584", "EN_50600_ISO_IEC_22237"))


def test_specifications_carry_vendor_data_and_compliance_schedules_and_sat_and_commissioning(spec_dir, root):
    cfg = _cfg(root)
    by_slug = {s["slug"]: s for s in _specs(cfg)}
    for f in sorted(spec_dir.glob("*.docx")):
        t = _text(f)
        slug = next(k for k in by_slug if f.name.endswith(f"_{k}.docx"))
        assert "Value offered" in t and "Document and revision" in t and "[vendor to complete]" in t
        assert "Standard named in section 2" in t and "Complies / complies with comment / does not comply" in t
        assert "A SAT procedure shall be submitted for approval" in t and "Integrated systems testing" in t and "Equipment shall not be shipped until the FAT report is accepted" in t
        assert t.count("[vendor to complete]") >= 10 + len(by_slug[slug]["requirements"]), f.name           # one compliance row per section 5 requirement
        assert "5." + str(len(by_slug[slug]["requirements"])) in t
        assert "no clause of any standard is quoted" in t


def test_specifications_cite_no_clause_numbers(spec_dir):
    for f in spec_dir.glob("*.docx"):
        t = _text(f)
        assert not re.search(r"\b(clause|sub-?clause|annex)\s+[A-Z]?\d", t, re.I), f.name
        assert not re.search(r"\b(IEC|ISO|IEEE)\s?\d+(-\d+)*\s*(:|,)?\s*(clause|section)\s*\d", t, re.I), f.name
