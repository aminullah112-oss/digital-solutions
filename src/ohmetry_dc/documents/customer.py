"""Customer README and commercial licence, rendered to Markdown, DOCX and PDF from one content structure.

The licence is a DRAFT written without legal review. It is not claimed to be enforceable in any jurisdiction.
"""
from __future__ import annotations

from ohmetry_dc.documents import ISSUE

from pathlib import Path

from ohmetry_dc import __version__
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds

from . import docx_tools as dx

README_REV, LICENCE_REV = ISSUE, ISSUE
LEGAL_BANNER = ("DRAFT LICENCE. PREPARED WITHOUT LEGAL REVIEW. NOT CLAIMED TO BE LEGALLY ENFORCEABLE IN ANY JURISDICTION. "
                "A QUALIFIED LEGAL PROFESSIONAL MUST REVIEW AND ADAPT THIS TEXT BEFORE IT IS USED WITH ANY CUSTOMER.")
STATUS_BANNER = "PRELIMINARY EDUCATIONAL AND REFERENCE PACKAGE. NOT CONSTRUCTION-READY. NOT VERIFIED."

# a section is (heading, [block...]); a block is a str paragraph, ("bullets", [..]), ("table", header, rows)


def _assumption_rows(cfg: ProjectConfig) -> list[list]:
    ids = [("general.it_critical_load", "IT critical load"), ("general.target_pue", "Target PUE"), ("electrical_system.lv_line_voltage", "LV line voltage"), ("electrical_system.frequency", "Frequency"),
           ("electrical_system.mv_supply_voltage", "MV supply"), ("redundancy.architecture", "Architecture"), ("redundancy.ups_topology", "UPS topology"), ("redundancy.generator_concept", "Generator concept"),
           ("equipment.transformer_rating", "Transformer rating"), ("equipment.transformer_impedance", "Transformer impedance"), ("equipment.generator_rating", "Generator rating"), ("equipment.generator_rating_power_factor", "Generator power factor"),
           ("equipment.ups_rating", "UPS rating (kW)"), ("equipment.ups_rating_kva", "UPS rating (kVA)"), ("equipment.ups_efficiency", "UPS efficiency"), ("losses.distribution_loss_fraction", "Distribution losses"),
           ("redundancy.battery_autonomy", "Battery autonomy"), ("design_criteria.transformer_target_loading", "Transformer loading target"), ("design_criteria.transformer_max_loading", "Transformer loading maximum")]
    rows = []
    for pid, label in ids:
        p = cfg.parameters[pid]
        unit = "" if p.unit in ("-", "") else f" {p.unit}"
        rows.append([label, f"{p.value}{unit}", ds.data_status(p)])
    return rows


def readme_sections(cfg: ProjectConfig, workbooks: list[tuple[str, str]], stamp: str) -> list[tuple[str, list]]:
    c = cfg.project
    return [
        ("1. What this package is", [f"The {c.name} ({c.code}) is a SAMPLE PROJECT published by Ohmetry (ohmetry.com) for engineers working on data-centre projects, as a learning and reference example. It is not a real project and not a design for any site. It is a worked electrical engineering reference for a 2 MW (IT load) data centre. It contains calculation workbooks, a calculation engine, reports, a preliminary single-line diagram, specification templates and a training suite. "
                                    f"This is package revision {c.revision}, version {__version__}, generated {stamp}.",
                                    "It shows how a data centre electrical design is built up: design basis, load estimate, redundancy architecture, equipment sizing, distribution, short-circuit levels, protection data, earthing and documentation. Every calculation states its inputs and their status.",
                                    f"Release state: {c.release_state.value}. {STATUS_BANNER}"]),
        ("2. Intended users", [("bullets", ["Working electrical engineers who want a structured, transparent starting point for data centre power design.", "Consulting engineers who want a calculation framework with traceable inputs and honest statuses.",
                                          "Engineers learning data centre design (see the training suite).", "Not intended for: construction, procurement, permit submissions or any use that relies on the results without independent engineering review."])]),
        ("3. What is included", [("table", ["Item", "Content"], [["Workbooks", f"{len(workbooks)} Excel workbooks (01 to 20), listed in section 7"], ["Reports", "Electrical load estimation report (PDF)"], ["Drawings", "OHM-DC-2000-SLD-001 preliminary single-line diagram (SVG and PDF)"],
                                                                 ["Specification templates", "Ten editable DOCX templates with PDF copies: transformers, generators, UPS, batteries, MV and LV switchgear, cables, busduct, protection, earthing"], ["Training suite", "Twelve modules (PDF and Markdown), exercise workbook, 48-question bank, answer key, completion certificate template"],
                                                                 ["Registers", "Assumptions register, standards register, manufacturer-data register and import template, outstanding verification items"], ["Documents", "Calculation methodology, user guides, engineering review log, development status, release checklist, QA results, master index, licence"],
                                                                 ["Engine (optional)", "The Python calculation engine and master configuration, only if included in your licence tier"]])]),
        ("4. Design basis and key assumptions", ["The reference project is a 2,000 kW IT load with dual independent A and B power paths. The values below are the preliminary values in the master configuration. They are assumptions chosen for the reference project, not manufacturer data and not measurements. "
                                                "Each carries a data status (section 11).",
                                                ("table", ["Item", "Value", "Data status"], _assumption_rows(cfg)),
                                                "The 400/230 V at 60 Hz pairing is the project owner's decision and was not independently verified. For a real project, the serving utility's written confirmation is required."]),
        ("5. Supported software", [("bullets", ["Workbooks: they use ordinary formulas (no macros) and are intended for Microsoft Excel 2016 or later or LibreOffice Calc 7 or later. IMPORTANT: they were recalculated and tested with LibreOffice only. Microsoft Excel was not available to the authors, so the workbooks have not been opened in Excel. A static lint checks Excel limits (see WORKBOOK_LINT.md) but cannot show that Excel gives the same results. Check results in Excel before relying on them.", "Reports, drawings and specifications are provided as PDF and DOCX; a PDF reader and a word processor are enough.",
                                              "Engine (if included): Python 3.11 or later with pydantic, PyYAML, openpyxl and reportlab. LibreOffice is used to recalculate workbooks in the test suite."])]),
        ("6. Installing and running the engine (if included)", ["From the folder containing the engine: install the dependencies listed in requirements.txt, then run the commands below with PYTHONPATH=src.",
                                                             ("bullets", ["validate-config: check the configuration and print every check with its statuses.", "generate-workbooks, generate-reports, generate-drawings, generate-training: rebuild the deliverables from the configuration.",
                                                                          "build-assumptions-register, build-manufacturer-register: refresh the registers.", "revision-impact --previous-config OLD --record \"description\": show and record what a configuration change did to the results.",
                                                                          "import-manufacturer-data, record-verification: import supplied data and record a reviewer (section 9).", "qa-report: run the tests and write the QA results."]),
                                                             "Run: python -m ohmetry_dc <command>. Every command is safe to rerun."]),
        ("7. The calculation workbooks", ["Every workbook has the same layout: README (what it does and its limits), INPUTS, CALCULATIONS, RESULTS and REVISION_LOG. The workbooks are live: change an input and the results update.",
                                          ("table", ["Workbook", "Purpose"], [[n, d] for n, d in workbooks]),
                                          "Five workbooks (14 protection, 16 lightning, 17 power quality, 18 energy, 19 fuel) are structured input registers with only the calculations that the entered data supports. They produce no meaningful result until you enter data."]),
        ("8. Entering your own and datasheet values in the workbooks", [("bullets", ["On INPUTS, the yellow column holds the retained preliminary value. Do not overwrite it.", "Type the datasheet value in the blue column E, in the unit shown in column C.", "Type the datasheet source and revision in column H. A value without a source is rejected: the status reads REJECTED: SOURCE MISSING and the preliminary value stays in force.",
                                                                                   "After you check the value against its source, type your name in column I. The status then changes from MANUFACTURER_SUPPLIED to MANUFACTURER_VERIFIED.", "Read RESULTS: the four statuses are shown separately (section 11).",
                                                                                   "Load figures in the sizing workbooks are copied from the preliminary load estimate. Replace them with your project's loads."])]),
        ("9. Importing manufacturer data (engine)", ["The engine keeps the original design-basis values and records supplied data separately, so the original is never overwritten.",
                                                    ("bullets", ["build-manufacturer-register writes the register and a blank import template (parameter, value, unit, source, datasheet revision, datasheet reference).", "Fill the template from the datasheets. Use the unit of the master configuration or a convertible unit (for example MVA for kVA).",
                                                                 "import-manufacturer-data --file <csv> validates every row: a missing source or datasheet revision, an unknown parameter, an unsupported unit or an implausible value rejects the whole file and nothing is imported.", "Accepted values are written to config/manufacturer_data_overrides.yaml with an append-only history (date, previous value, source, revision). Every dependent calculation reruns and the changes are printed.",
                                                                 "record-verification --parameter <id> --by <name> records that a reviewer checked the value against its source. A placeholder cannot be verified."])]),
        ("10. Calculation outputs", [("bullets", ["Workbook RESULTS sheets: calculated values with the four statuses and the Python agreement column.", "The load estimation report (PDF): inputs, load schedule, results, checks and limitations.", "The single-line diagram: architecture and preliminary ratings read from the configuration.",
                                                "The registers: assumptions, manufacturer data (with the engineering impact of each missing item), standards, outstanding verification items.", "The revision log: what changed between revisions and its effect on the results."])]),
        ("11. Verification statuses", ["Every check reports four separate things. A calculation can be correct arithmetic and still say nothing about whether the design works, if its inputs are unconfirmed.",
                                       ("table", ["Status", "Meaning"], [["Calculation status", "CALCULATED, PARTIAL or NOT CALCULATED: did the arithmetic run on complete inputs"], ["Calculation result", "PASS, WARNING or FAIL against the criterion. Preliminary when the inputs are"], ["Input-data status", "The worst status among the inputs (below)"],
                                                                          ["Overall design status", "PASS only if the calculation passes AND every input is verified, reference data or an owner decision. A preliminary pass reads NOT VERIFIED. A preliminary WARNING or FAIL is kept"]]),
                                       ("table", ["Input-data status", "Meaning"], [["MISSING", "No value supplied. Nothing is assumed"], ["UNVERIFIED_PLACEHOLDER", "A preliminary value standing in for manufacturer data"], ["PRELIMINARY_ASSUMPTION", "A value chosen for the reference project"], ["REFERENCE_DATA", "A published constant (verify the edition)"],
                                                                                    ["PROJECT_INPUT", "A decision or policy value from the project owner"], ["MANUFACTURER_SUPPLIED / SITE_DATA_SUPPLIED", "Imported from a document, not yet reviewed"], ["MANUFACTURER_VERIFIED / SITE_DATA_VERIFIED", "Imported and reviewed by a named person"]]),
                                       "NOT CALCULATED means the inputs are missing and the result is not shown. In the shipped package no engineering check reaches PASS."]),
        ("12. Editing the configuration (engine)", ["config/project_config.yaml is the single source of project values; each parameter has a value, unit, source, status and revision. Change a value there (for example the IT load in the demand-data section), rerun the commands, and every workbook, report, drawing and training example follows. "
                                                    "Use revision-impact to record the effect. Do not edit the overrides file by hand except to correct a source reference."]),
        ("13. What is preliminary", [("bullets", ["Every value in section 4 and every equipment rating.", "The load schedule, derating factors (1.00 placeholders), cable selections and lengths, and the illustrative device list.", "The generator rating basis (assumed PRP) and rated power factor.", "All results derived from them."])]),
        ("14. What requires manufacturer data", [("bullets", ["Transformer impedance, X/R, losses and derating; generator PRP and ESP ratings, reactance, step-load and transient data; UPS efficiency curve, input harmonics and walk-in; battery constant-power discharge data.",
                                                            "Cable tabulated ratings; busduct and switchgear ratings, impedance, short-circuit ratings and verification evidence; circuit-breaker and relay curves and settings."]),
                                                 "The manufacturer-data register lists every item, the datasheet needed, and the engineering impact of its absence."]),
        ("15. What requires specialist software or studies", [("bullets", ["Network short-circuit, load-flow and protection coordination studies with validated models (for example in a power systems analysis package).", "Detailed grounding analysis (mesh and step voltage, layered soil).", "Arc-flash assessment.", "Harmonic analysis.",
                                                                          "Cooling and airflow design.", "Lightning protection risk assessment and design.", "Utility studies and the utility's written fault-level data."]),
                                                               "This package provides the framework and the data requirements for these. It does not replace them."]),
        ("16. What requires independent engineering approval", ["Every result, drawing and specification here requires review and approval by a suitably qualified engineer before any use beyond education. Approval fields in the documents are empty: a name written in a field is a record, not a verification performed by this package. "
                                                               "Local code, utility and authority requirements are not stated here and must be added by the project team."]),
        ("17. Reporting issues", ["Report an issue with: the document or workbook name and revision, the input values, what you expected and what you saw. Contact: hello@ohmetry.com (ohmetry.com). "
                                  "Support scope and update rights depend on the licence tier (see the licence)."]),
        ("18. Licence and disclaimer", ["Use of this package is governed by the commercial licence in this package (draft, not legally reviewed). The package is provided as is for education and reference. It is not engineering advice and not a design. "
                                        "Ohmetry does not accept responsibility for any use of the results without independent engineering verification."]),
    ]


def licence_sections(cfg: ProjectConfig) -> list[tuple[str, list]]:
    c = cfg.project
    return [
        ("Notice about this draft", [LEGAL_BANNER, "This text is a starting point for the owner and a legal professional. Items in [square brackets] are to be completed. Nothing in it is a statement that any clause is valid or enforceable where you operate."]),
        ("1. Parties and product", [f"Licensor: Ohmetry (ohmetry.com) [legal entity, registered address and jurisdiction to be confirmed by the owner and the legal professional]. Licensee: the individual or organisation named on the order. Product: the {c.name} ({c.code}) package, revision {c.revision}, in the tier stated on the order."]),
        ("2. Definitions", [("bullets", ["Package: all files supplied, including workbooks, documents, specification templates, drawings, reports, training materials, registers and, where the tier includes it, the calculation engine and configuration.", "Authorised User: a named individual who may use the Package under the tier purchased.",
                                       "Organisation: a company or other entity that holds a Corporate licence.", "Project Deliverable: a document, calculation, drawing or specification the Licensee creates for its own or a client's project using the Package.", "Derived Work: a modification of, or work substantially based on, the Package other than a Project Deliverable."])]),
        ("3. Licence tiers", [("table", ["Tier", "Includes", "Users"], [["Starter", "Selected calculation workbooks, sample design basis", "One individual, personal use"], ["Professional", "Complete package: twenty workbooks, reports, drawings, specification templates", "One named individual, personal or single-user professional use"],
                                                                      ["Professional + Learning", "Professional package plus the twelve training modules, exercises, assessments and the certificate template", "One named individual"], ["Corporate", "As agreed in writing: multi-user or organisation-wide terms, quote-based pricing, defined redistribution and support rights", "Named Organisation and the users stated in the order"]]),
                              "Fees, payment terms and any support or update entitlements for each tier are in the order or the commercial proposal: [to be completed]."]),
        ("4. Grant", ["Subject to this licence and payment of the fees, Ohmetry grants the Licensee a non-exclusive, non-transferable, non-sublicensable licence to use the Package, for the version and tier purchased, for the term in section 14. The Package is licensed, not sold. All rights not granted are reserved."]),
        ("5. Permitted use", [("bullets", ["Individual engineers (Starter, Professional, Professional + Learning): use by the named individual for their own learning and for their own professional work, including work for clients, by incorporating results into Project Deliverables.",
                                         "Consulting companies: use by each named Authorised User under a Professional licence per user, or by the users named under a Corporate licence. A Professional licence is not shared between people.",
                                         "Printing or copying the Package for the Licensee's own backup and for the Authorised User's own reference.", "Use of the calculation outputs and the Licensee's own data in Project Deliverables, provided the status labels and limitations are not removed or misrepresented (section 8)."])]),
        ("6. Restrictions", [("bullets", ["No redistribution: do not copy, share, upload, publish, lend or otherwise make the Package or any part of it available to anyone who is not an Authorised User, including by file-sharing, public repositories, forums, template marketplaces or client handover of the Package itself.",
                                        "No resale or sublicence: do not sell, rent, lease, sublicense or offer the Package, or a Derived Work, or a product substantially similar to it, to others.", "No use of the Package to build or train a competing product or service sold to third parties.",
                                        "No removal or alteration of copyright, licence, status or disclaimer notices.", "No use of the Ohmetry name or marks to suggest endorsement of the Licensee's work.", "Training materials may be used to train the Licensee only, unless a Corporate licence states otherwise."]),
                              "Client handover: a Project Deliverable may be given to the client. The Package, its workbooks and templates in their original form may not be.",
                              "[Confirm with legal advice whether and how these restrictions are enforceable where the Licensee is located.]"]),
        ("7. Modification", ["The Licensee may modify the workbooks, templates and configuration for its own internal use. Modifications are made at the Licensee's own risk, are Derived Works and remain subject to this licence, and may not be distributed. Ohmetry gives no support or warranty for modified files. "
                             "The Licensee must not modify the Package so that unverified or uncalculated results appear verified or passing."]),
        ("8. Engineering responsibility and status labels", ["The Package is a preliminary educational and reference tool. It is not engineering advice, a design, a certification or a statement of compliance with any code or standard. The Licensee, and the engineer who signs any resulting work, remains solely responsible for the correctness, "
                                                              "suitability and verification of any Project Deliverable. The Licensee shall not present results as verified unless the inputs and results have been verified by a suitably qualified person. The status labels (NOT VERIFIED, PRELIMINARY and the like) shall not be removed from material shown to others."]),
        ("9. Outputs and Licensee data", ["The Licensee owns its own data and the Project Deliverables it creates, subject to Ohmetry's rights in the underlying Package. Ohmetry does not claim ownership of the Licensee's project data and does not receive it. Manufacturer datasheets and standards remain the property of their owners; the Licensee must hold lawful copies of any standard it relies on."]),
        ("10. Third-party materials", ["The Package names standards, manufacturers and software but does not reproduce standards text. Open-source components used by the engine (for example pydantic, PyYAML, openpyxl, reportlab) remain under their own licences, which apply to those components."]),
        ("11. Updates and support", ["Updates and support are provided only as stated in the order for the tier: support channel: email hello@ohmetry.com; [update period and response expectations to be completed]. Ohmetry may release corrections. No update obligation exists beyond the stated entitlement."]),
        ("12. Warranty disclaimer", ["To the maximum extent permitted by law, the Package is provided \"as is\" without warranties of any kind, express or implied, including merchantability, fitness for a particular purpose, accuracy, completeness and non-infringement. Ohmetry does not warrant that the Package is free of errors or that its results are correct for any project. [Legal review: confirm wording for the Licensee's jurisdiction.]"]),
        ("13. Limitation of liability", ["To the maximum extent permitted by law: (a) Ohmetry is not liable for any indirect, incidental, special, consequential or punitive loss, loss of profit, loss of data, project delay, rework, equipment damage or injury arising from use of, or reliance on, the Package or its results; "
                                         "(b) Ohmetry's total liability arising from this licence is limited to the fees paid for the Package in the twelve months before the claim; (c) nothing excludes or limits liability that cannot lawfully be excluded or limited. [Legal review required: these limits may not be enforceable in every jurisdiction.]"]),
        ("14. Term and termination", ["The licence lasts for the version purchased until terminated. It terminates automatically if the Licensee breaches sections 5 to 8, and Ohmetry may terminate for other material breach after notice. On termination the Licensee shall stop using the Package and delete or destroy all copies, except Project Deliverables already created. Sections 9, 12, 13 and 16 survive termination."]),
        ("15. Transfer and assignment", ["The licence may not be transferred or assigned without Ohmetry's written consent. A Corporate licence may be assigned only as stated in its terms: [to be completed]."]),
        ("16. Governing law and disputes", ["[Governing law, venue and dispute process to be determined with legal advice.]"]),
        ("17. General", ["[Entire agreement, severability, notices and amendment terms to be completed by the legal professional.] Contact for licence matters: hello@ohmetry.com."]),
        ("Acceptance", [("table", ["Field", "Licensee", "Ohmetry"], [["Name / organisation", "[ ]", "[ ]"], ["Tier and users", "[ ]", "[ ]"], ["Date", "[ ]", "[ ]"], ["Signature or electronic acceptance", "[ ]", "[ ]"]]),
                        "Legal review: reviewed by [name, date]. Not yet reviewed."]),
    ]


def to_markdown(title: str, doc_no: str, rev: str, banner: str, sections: list[tuple[str, list]], stamp: str) -> str:
    L = [f"# {title}", "", f"**Document {doc_no}  Revision {rev}.  Generated {stamp}.**", "", f"> {banner}", ""]
    for h, blocks in sections:
        L += [f"## {h}", ""]
        for b in blocks:
            if isinstance(b, str):
                L += [b, ""]
            elif b[0] == "bullets":
                L += [f"- {x}" for x in b[1]] + [""]
            elif b[0] == "table":
                L += ["| " + " | ".join(b[1]) + " |", "|" + "---|" * len(b[1])] + ["| " + " | ".join(str(x) for x in r) + " |" for r in b[2]] + [""]
    return "\n".join(L)


def to_docx(title: str, doc_no: str, rev: str, banner: str, sections: list[tuple[str, list]], path: Path, stamp: str, header: str) -> Path:
    d = dx.new_document(title, doc_no, rev, "Draft", header)
    dx.title(d, title, f"Document {doc_no}. Revision {rev}. Generated {stamp}.")
    dx.banner(d, banner)
    for h, blocks in sections:
        d.add_heading(h, 2)
        for b in blocks:
            if isinstance(b, str):
                d.add_paragraph(b)
            elif b[0] == "bullets":
                dx.bullets(d, b[1])
            elif b[0] == "table":
                dx.table(d, b[1], b[2])
    d.save(path)
    return path


def build_customer_documents(cfg: ProjectConfig, out: Path, stamp: str, workbooks: list[tuple[str, str]], doc_nos: dict[str, str]) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, title, sections, banner, rev, header in (
        ("readme", "Customer README", readme_sections(cfg, workbooks, stamp), STATUS_BANNER, README_REV, f"OHMETRY {cfg.project.code}: customer README"),
        ("licence", "Commercial Licence (draft)", licence_sections(cfg), LEGAL_BANNER, LICENCE_REV, f"OHMETRY {cfg.project.code}: commercial licence (draft, not legally reviewed)")):
        no = doc_nos[key]
        stem = "CUSTOMER_README" if key == "readme" else "LICENCE_COMMERCIAL"
        md = out / f"{stem}.md"
        label = f"{cfg.project.revision}, Issue {rev}"
        md.write_text(to_markdown(title, no, label, banner, sections, stamp), encoding="utf-8")
        docx = to_docx(title, no, label, banner, sections, out / f"{stem}.docx", stamp, header)
        written += [md, docx]
        pdf = dx.to_pdf(docx, out)
        if pdf:
            written.append(pdf)
    return written


WB_PURPOSE = {1: "Every design-basis parameter with its data status and source; design criteria; assumptions and exclusions; standards links; check statuses; approval fields",
              2: "Itemised load, UPS and distribution losses, facility load, design-point PUE, A/B allocation", 3: "Operating modes, load transfer on loss of a path, UPS or generator, redundancy checks, dependency summary",
              4: "Transformer loading in normal and contingency cases against the derated rating; required rating", 5: "Generator loading in kW and kVA with N+1 cases", 6: "UPS loading in kW and kVA with 2N cases",
              7: "Energy at the UPS output and an indicative nominal energy (no battery selection)", 8: "Design current, required rating, voltage drop and thermal withstand per feeder", 9: "Voltage drop cases, three-phase and single-phase, operating and starting",
              10: "IEC 60909 fault levels at the MV and LV busbars; equipment rating comparison", 11: "LV switchboard required rating, short-circuit rating and evidence", 12: "MV switchgear required rating, short-circuit rating and evidence",
              13: "Busduct required rating, voltage drop and short-circuit withstand", 14: "Protective device schedule, CT/VT and relay settings registers, selectivity evidence (never a coordination PASS)", 15: "Grid resistance, ground potential rise and touch voltage screening",
              16: "Lightning protection input fields, collection area and expected events (no compliance claim)", 17: "Voltage unbalance, THD and frequency deviation from measurements, against limits you enter", 18: "Annual energy and energy-based PUE (design-point upper bound unless you enter measured factors)",
              19: "Fuel consumption and runtime from the manufacturer's fuel curve (nothing without the curve)", 20: "Equipment tags with ratings, datasheet fields, technical and procurement status"}


def workbook_list(root: Path) -> list[tuple[str, str]]:
    out = []
    for p in sorted((root / "workbooks" / "generated").glob("*.xlsx")):
        out.append((p.stem, WB_PURPOSE.get(int(p.name[:2]), "")))
    return out
