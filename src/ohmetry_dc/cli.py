"""Command-line interface. Stages 1 and 2: validation, the assumptions register, the load model, the load workbook and the load report."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from ohmetry_dc import __version__
from ohmetry_dc.config import load_config
from ohmetry_dc.config.assumptions import build_register, dump_register
from ohmetry_dc.models import ConfigError
from ohmetry_dc.utilities.logging import setup_logging
from ohmetry_dc.validation import release_gate, run_all_checks, summarise

NOT_IMPLEMENTED = ()
EXIT_OK, EXIT_FAIL, EXIT_CONFIG, EXIT_NOT_IMPLEMENTED = 0, 1, 2, 3


def _load(args):
    return load_config(args.config, args.loads)


def cmd_validate(args) -> int:
    cfg = _load(args)
    results = run_all_checks(cfg)
    gate = release_gate(results, cfg.project.release_state)
    summary = summarise(results)
    print(f"{cfg.project.code}  revision {cfg.project.revision}  declared state {cfg.project.release_state.value}")
    for r in results:
        print(f"[{r.status.value:<14}] {r.id}: {r.detail}")
        if r.verification_status not in ("", "N/A"):
            print(f"{'':<17}calculation: {r.calculation_status} ({r.calculation_result}) | inputs: {r.input_status} | verification: {r.verification_status}")
        if r.next_action:
            print(f"{'':17}next: {r.next_action}")
    print("\nSummary: " + ", ".join(f"{k} {v}" for k, v in summary.items()))
    print(f"Release gate: {gate.value}")
    if args.json:
        Path(args.json).write_text(json.dumps({"project_code": cfg.project.code, "revision": cfg.project.revision, "declared_state": cfg.project.release_state.value,
                                               "release_gate": gate.value, "summary": summary, "checks": [r.as_dict() for r in results]}, indent=2), encoding="utf-8")
    return EXIT_FAIL if summary["FAIL"] else EXIT_OK


def cmd_register(args) -> int:
    text = dump_register(build_register(_load(args)))
    target = Path(args.register)
    if args.check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != text:
            print(f"{target} is out of date. Run build-assumptions-register without --check.")
            return EXIT_FAIL
        print(f"{target} matches the configuration.")
        return EXIT_OK
    target.write_text(text, encoding="utf-8")
    print(f"Wrote {target}")
    return EXIT_OK


def _stamp(args) -> str | None:
    """A fixed timestamp makes the outputs reproducible. Without it the current time is used."""
    return args.generated or os.environ.get("OHMETRY_GENERATED_UTC")


def _run(args):
    from ohmetry_dc.calculations import estimate_loads

    cfg = _load(args)
    est = estimate_loads(cfg)
    return cfg, est, run_all_checks(cfg)


def cmd_calculate(args) -> int:
    from dataclasses import asdict

    cfg, est, checks = _run(args)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    from ohmetry_dc.calculations import size_power_system
    from ohmetry_dc.reporting import power_system_to_dict

    data = asdict(est)
    data["pue"] = est.pue
    sizing = power_system_to_dict(size_power_system(cfg, est))
    (out / "results.json").write_text(json.dumps({"project_code": cfg.project.code, "revision": cfg.project.revision, "load_estimate": data, "sizing": sizing,
                                                  "checks": [c.as_dict() for c in checks]}, indent=2, default=str), encoding="utf-8")
    print(f"IT {est.it_demand_kw:,.1f} kW; facility {est.facility_kw:,.1f} kW ({est.facility_kva:,.1f} kVA, pf {est.power_factor:.3f}); PUE {est.pue:.3f}")
    print(f"Wrote {out / 'results.json'}")
    return EXIT_OK


def cmd_workbooks(args) -> int:
    from ohmetry_dc.calculations import size_power_system
    from ohmetry_dc.excel import SIZING_KINDS, build_cable_workbook, build_load_workbook, build_short_circuit_workbook, build_sizing_workbook
    from ohmetry_dc.excel import CABLE_FILE, SC_FILE

    cfg, est, checks = _run(args)
    out = Path(args.workbooks)
    sizing = size_power_system(cfg, est)
    stamp = _stamp(args)
    paths = [build_load_workbook(cfg, est, checks, out / "02_LOAD_ESTIMATION.xlsx", stamp)]
    paths += [build_sizing_workbook(cfg, kind, sizing, checks, out / SIZING_KINDS[kind][0], stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")) for kind in ("transformer", "generator", "ups")]
    paths.append(build_cable_workbook(cfg, checks, out / CABLE_FILE, stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    paths.append(build_short_circuit_workbook(cfg, checks, out / SC_FILE, stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    from ohmetry_dc.excel import OTHER_FILES, build_battery_workbook, build_earthing_workbook, build_rating_workbook

    st = stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    paths.append(build_battery_workbook(cfg, out / OTHER_FILES["battery"], st))
    paths += [build_rating_workbook(cfg, k, out / OTHER_FILES[k], st) for k in ("lv", "mv", "busduct")]
    paths.append(build_earthing_workbook(cfg, checks, out / OTHER_FILES["earthing"], st))
    from ohmetry_dc.excel import (ARCH_FILES, build_architecture_workbook, build_basis_workbook, build_equipment_schedule, build_voltage_drop_workbook)

    paths.append(build_basis_workbook(cfg, checks, out / ARCH_FILES["basis"], st))
    paths.append(build_architecture_workbook(cfg, out / ARCH_FILES["arch"], st))
    paths.append(build_voltage_drop_workbook(cfg, out / ARCH_FILES["vdrop"], st))
    paths.append(build_equipment_schedule(cfg, out / ARCH_FILES["equip"], st))
    from ohmetry_dc.excel import (STUDY_FILES, build_energy_workbook, build_fuel_workbook, build_lightning_workbook, build_power_quality_workbook, build_protection_workbook)

    paths += [build_protection_workbook(cfg, out / STUDY_FILES["protection"], st), build_lightning_workbook(cfg, out / STUDY_FILES["lightning"], st), build_power_quality_workbook(cfg, out / STUDY_FILES["pq"], st),
              build_energy_workbook(cfg, out / STUDY_FILES["energy"], st), build_fuel_workbook(cfg, out / STUDY_FILES["fuel"], st)]
    for p in paths:
        print(f"Wrote {p}")
    return EXIT_OK


def cmd_reports(args) -> int:
    from ohmetry_dc.reporting import build_load_report

    cfg, est, checks = _run(args)
    path = build_load_report(cfg, est, checks, Path(args.reports) / "02_Electrical_Load_Estimation_Report.pdf", _stamp(args))
    print(f"Wrote {path}")
    return EXIT_OK


def cmd_sizing(args) -> int:
    from ohmetry_dc.reporting import build_sizing_summary

    cfg = _load(args)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    text = build_sizing_summary(cfg, _stamp(args))
    (out / "stage3_sizing_summary.md").write_text(text, encoding="utf-8")
    print(f"Wrote {out / 'stage3_sizing_summary.md'}")
    return EXIT_OK


def cmd_revision(args) -> int:
    from ohmetry_dc.reporting import append_revision_log, compare, compare_markdown

    new = _load(args)
    old = load_config(args.previous_config, args.previous_loads or args.loads)
    diff = compare(old, new)
    print(compare_markdown(diff, old.project.revision, new.project.revision))
    if args.record:
        append_revision_log(Path(args.log), new.project.revision, args.record, diff)
        print(f"Recorded in {args.log}")
    return EXIT_OK


def cmd_mfr(args) -> int:
    from ohmetry_dc.reporting import build_rows, load_register_meta, problems, to_csv, to_markdown

    cfg = _load(args)
    meta = load_register_meta(Path(args.register))
    bad = problems(cfg, meta)
    rows = build_rows(cfg, meta)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (out / "manufacturer_data_register.md").write_text(to_markdown(rows, stamp), encoding="utf-8")
    (out / "manufacturer_data_register.csv").write_text(to_csv(rows), encoding="utf-8")
    from ohmetry_dc.reporting import import_template

    (out / "manufacturer_data_import_template.csv").write_text(import_template(rows), encoding="utf-8")
    print(f"Wrote {out / 'manufacturer_data_register.md'} and .csv ({len(rows)} entries)")
    for b in bad:
        print(f"DEFECT: {b}")
    return EXIT_FAIL if bad else EXIT_OK


def cmd_import(args) -> int:
    """Import supplied manufacturer, utility or site data from a CSV into the overrides file, rerun every check, and show what changed."""
    from ohmetry_dc.config import load_config
    from ohmetry_dc.reporting import build_rows, import_data, import_template, load_register_meta, to_csv, to_markdown

    cfg = _load(args)
    before = {r.id: (r.status.value, r.calculation_result) for r in run_all_checks(cfg)}
    meta = load_register_meta(Path(args.register))
    known = {e["parameter"] for e in meta}
    path = Path(cfg.base_dir) / "manufacturer_data_overrides.yaml"
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n, bad = import_data(Path(args.file).read_text(encoding="utf-8"), path, cfg, known, stamp)
    for b in bad:
        print(f"REJECTED: {b}")
    if bad:
        print("Nothing was imported.")
        return EXIT_FAIL
    cfg2 = load_config(args.config, args.loads)
    after = run_all_checks(cfg2)
    print(f"Imported {n} value(s) into {path}. The master design-basis file was not changed. Rerunning every dependent calculation:")
    changed = [r for r in after if before.get(r.id) != (r.status.value, r.calculation_result)]
    for r in changed:
        print(f"  {r.id}: {before.get(r.id, ('-', '-'))[0]} -> {r.status.value} (calculation result {before.get(r.id, ('-', '-'))[1]} -> {r.calculation_result}; inputs {r.input_status})")
    if not changed:
        print("  no check changed status (values may still have changed; see validate-config)")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    rows = build_rows(cfg2, meta)
    (out / "manufacturer_data_register.md").write_text(to_markdown(rows, stamp), encoding="utf-8")
    (out / "manufacturer_data_register.csv").write_text(to_csv(rows), encoding="utf-8")
    (out / "manufacturer_data_import_template.csv").write_text(import_template(rows), encoding="utf-8")
    print(f"Register refreshed in {out}. Supplied values stay NOT VERIFIED until a reviewer runs record-verification.")
    return EXIT_OK


def cmd_verify(args) -> int:
    """Record that a reviewer verified a supplied value against its source document. Refused for a placeholder."""
    import yaml

    from ohmetry_dc.reporting import load_register_meta, problems

    cfg = _load(args)
    reg = Path(args.register)
    meta = load_register_meta(reg)
    entry = next((e for e in meta if e["parameter"] == args.parameter), None)
    if entry is None:
        print(f"REJECTED: {args.parameter} is not in the register")
        return EXIT_FAIL
    from ohmetry_dc.models import attestation as at

    entry.update({"verified_by": args.by, "verified_org": args.org, "verification_date": args.date or dt.date.today().isoformat(), "evidence_ref": args.evidence, "verification_scope": args.scope})
    gap = at.missing_fields(entry)
    if gap:
        print("REJECTED: the verification record is incomplete or invalid: " + ", ".join(at.LABELS.get(g, g) for g in gap) + ". " + at.NOTICE)
        return EXIT_FAIL
    bad = [b for b in problems(cfg, meta) if args.parameter in b]
    if bad:
        print("REJECTED: " + "; ".join(bad) + ". Only a value imported from a source document can be verified; a placeholder cannot.")
        return EXIT_FAIL
    txt = reg.read_text(encoding="utf-8")
    hdr = "".join(l for l in txt.splitlines(True) if l.startswith("#"))
    reg.write_text(hdr + yaml.safe_dump({"schema_version": 1, "entries": meta}, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
    log = reg.parent / "verification_log.yaml"                                  # append-only: the register keeps the latest record, the log keeps every one
    past = (yaml.safe_load(log.read_text(encoding="utf-8")) or {}).get("records", []) if log.exists() else []
    past.append({"parameter": args.parameter, **{f: entry[f] for f in at.ATTESTATION_FIELDS}, "recorded": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")})
    log.write_text("# Append-only log of verification attestations. Names are self-declared and not authenticated.\n" + yaml.safe_dump({"schema_version": 1, "records": past}, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
    print(f"Recorded: {args.parameter} attested as verified by {args.by} ({args.org}) on {entry['verification_date']}; evidence {args.evidence}; scope {args.scope}. It becomes MANUFACTURER_VERIFIED or SITE_DATA_VERIFIED. {at.NOTICE}")
    return EXIT_OK


def cmd_drawings(args) -> int:
    """Generate the single-line diagram (SVG, and PDF when LibreOffice is available) from the master configuration."""
    import shutil

    from ohmetry_dc.drawings import build_single_line_svg

    cfg = _load(args)
    out = Path(args.drawings)
    (out / "svg").mkdir(parents=True, exist_ok=True)
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    svg = out / "svg" / "OHM-DC-2000-SLD-001.svg"
    svg.write_text(build_single_line_svg(cfg, stamp), encoding="utf-8")
    print(f"Wrote {svg}")
    if shutil.which("soffice"):
        (out / "pdf").mkdir(parents=True, exist_ok=True)
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out / "pdf"), str(svg)], capture_output=True, timeout=180)
        if (out / "pdf" / "OHM-DC-2000-SLD-001.pdf").exists():
            print(f"Wrote {out / 'pdf' / 'OHM-DC-2000-SLD-001.pdf'}")
    return EXIT_OK


def cmd_training(args) -> int:
    """Generate the twelve training modules (Markdown and PDF), exercise workbook, answer key, question bank and certificate template."""
    from ohmetry_dc.training import build_training

    cfg = _load(args)
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    paths = build_training(cfg, Path(args.training), stamp)
    print(f"Wrote {len(paths)} training files under {args.training}")
    return EXIT_OK


def cmd_documents(args) -> int:
    """Generate the specification templates, customer README, commercial licence draft, outstanding items, reviewer checklist and guide, findings log, and the master index."""
    from ohmetry_dc.documents import customer, register, review, specs

    cfg = _load(args)
    root = Path(".")
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pre = register.PREFIX
    spec_files = specs.build_specifications(cfg, root / "specifications", stamp)
    rel = root / "docs" / "release"
    rel.mkdir(parents=True, exist_ok=True)
    customer.build_customer_documents(cfg, rel, stamp, customer.workbook_list(root), {"readme": f"{pre}-DOC-01", "licence": f"{pre}-DOC-02"})
    items = review.outstanding_items(root, cfg)
    (root / "output").mkdir(exist_ok=True)
    (root / "output" / "OUTSTANDING_VERIFICATION_ITEMS.md").write_text(review.outstanding_markdown(items, cfg, stamp), encoding="utf-8")
    (root / "output" / "OUTSTANDING_VERIFICATION_ITEMS.csv").write_text(review.outstanding_csv(items), encoding="utf-8")
    (rel / "REVIEWER_CHECKLIST.md").write_text(review.checklist_markdown(cfg, stamp), encoding="utf-8")
    cl = review.checklist_docx(cfg, rel / "REVIEWER_CHECKLIST.docx", stamp)
    from ohmetry_dc.documents import docx_tools

    docx_tools.to_pdf(cl, rel)
    n_files = len(list((root / "src").rglob("*.py"))) + 200
    (rel / "REVIEW_GUIDE.md").write_text(review.guide_markdown(cfg, stamp, n_files), encoding="utf-8")
    review.findings_workbook(rel / "REVIEW_FINDINGS_LOG.xlsx", stamp)
    for _ in range(2):                        # the index lists itself, so build it twice
        rows = register.build_register(root, cfg)
        (rel / "MASTER_INDEX.md").write_text(register.index_markdown(rows, cfg, stamp), encoding="utf-8")
        (rel / "MASTER_INDEX.csv").write_text(register.index_csv(rows), encoding="utf-8")
    print(f"Wrote {len(spec_files)} specification files, the customer README and licence draft, {len(items)} outstanding items, the reviewer checklist and guide, the findings log and the master index ({len(rows)} registered files)")
    return EXIT_OK


def cmd_review_package(args) -> int:
    """Assemble the independent engineering review package (a ZIP). Run generate-documents and qa-report first."""
    from ohmetry_dc.documents.review import build_review_package

    cfg = _load(args)
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    z, m = build_review_package(Path("."), Path(args.dist), cfg, stamp)
    print(f"Wrote {z} ({len(m['files'])} files). {m['state']}")
    return EXIT_OK


def cmd_package(args) -> int:
    """Assemble the customer ZIP from the workbooks, reports, docs and registers that exist. Run generate-workbooks, generate-reports, build-manufacturer-register and qa-report first."""
    from ohmetry_dc.packaging import build_package

    cfg = _load(args)
    zpath, m = build_package(Path("."), Path(args.dist), cfg.project.code, cfg.project.revision, args.include_engine)
    print(f"Wrote {zpath} ({len(m['files'])} files, {len(m['workbooks_included'])} of 20 workbooks). State: {m['state']}")
    return EXIT_OK


def cmd_qa(args) -> int:
    """Run the tests and write the QA results (counts and every test with its outcome)."""
    import xml.etree.ElementTree as ET

    junit = Path(args.output) / "junit.xml"
    Path(args.output).mkdir(parents=True, exist_ok=True)
    code = subprocess.call([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"])
    root = ET.parse(junit).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    cases = [(c.get("classname", ""), c.get("name", ""), "FAIL" if (c.find("failure") is not None or c.find("error") is not None) else "SKIP" if c.find("skipped") is not None else "PASS") for c in suite.iter("testcase")]
    counts = {k: sum(1 for c in cases if c[2] == k) for k in ("PASS", "FAIL", "SKIP")}
    stamp = _stamp(args) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# QA test results", "", f"Run {stamp}. Package version {__version__}. **{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped.**", "",
         "A passing test shows the code behaves as specified. It does not show the engineering is correct: that needs an independent review.", "", "| Module | Test | Result |", "|---|---|---|"]
    L += [f"| {m.replace('tests.', '')} | {n} | {r} |" for m, n, r in cases]
    out = Path(args.output) / "QA_RESULTS.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Wrote {out}: {counts}")
    return code


def cmd_tests(args) -> int:
    return subprocess.call([sys.executable, "-m", "pytest", "-q"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ohmetry_dc", description="Ohmetry OHM-DC-2000 data centre engineering package (Stage 1).")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--config", default="config/project_config.yaml")
    p.add_argument("--loads", default="config/load_schedule.yaml")
    p.add_argument("--generated", help="Fixed generation timestamp for reproducible outputs (also OHMETRY_GENERATED_UTC)")
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate-config", help="Validate the configuration and run the design-basis checks")
    v.add_argument("--json", help="Also write the results as JSON to this path")
    v.set_defaults(func=cmd_validate)
    r = sub.add_parser("build-assumptions-register", help="Generate config/assumptions_register.yaml from the configuration")
    r.add_argument("--register", default="config/assumptions_register.yaml")
    r.add_argument("--check", action="store_true", help="Check that the register is up to date instead of writing it")
    r.set_defaults(func=cmd_register)
    c = sub.add_parser("run-calculations", help="Run the load model and write output/results.json")
    c.add_argument("--output", default="output")
    c.set_defaults(func=cmd_calculate)
    w = sub.add_parser("generate-workbooks", help="Generate the Excel workbooks (Stage 2: 02_LOAD_ESTIMATION.xlsx)")
    w.add_argument("--workbooks", default="workbooks/generated")
    w.set_defaults(func=cmd_workbooks)
    rp = sub.add_parser("generate-reports", help="Generate the PDF reports (Stage 2: the load estimation report)")
    rp.add_argument("--reports", default="reports/generated")
    rp.set_defaults(func=cmd_reports)
    z = sub.add_parser("sizing-summary", help="Write the Stage 3 power system sizing summary (Markdown)")
    z.add_argument("--output", default="output")
    z.set_defaults(func=cmd_sizing)
    rv = sub.add_parser("revision-impact", help="Compare the current design basis with a previous one and show the equipment sizing changes")
    rv.add_argument("--previous-config", required=True)
    rv.add_argument("--previous-loads")
    rv.add_argument("--record", help="Append the comparison to the revision log with this description")
    rv.add_argument("--log", default="config/design_basis_revisions.yaml")
    rv.set_defaults(func=cmd_revision)
    mr = sub.add_parser("build-manufacturer-register", help="Write the manufacturer-data register (Markdown and CSV) with live values from the configuration")
    mr.add_argument("--register", default="config/manufacturer_data_register.yaml")
    mr.add_argument("--output", default="output")
    mr.set_defaults(func=cmd_mfr)
    im = sub.add_parser("import-manufacturer-data", help="Import supplied data (CSV from the import template) into config/manufacturer_data_overrides.yaml")
    im.add_argument("--file", required=True)
    im.add_argument("--register", default="config/manufacturer_data_register.yaml")
    im.add_argument("--output", default="output")
    im.set_defaults(func=cmd_import)
    vf = sub.add_parser("record-verification", help="Record that a reviewer verified an imported value against its source document")
    vf.add_argument("--parameter", required=True)
    vf.add_argument("--by", required=True, help="Reviewer name (a self-declared attestation, not authenticated)")
    vf.add_argument("--org", required=True, help="Reviewer's organisation")
    vf.add_argument("--evidence", required=True, help="Evidence reference: the data sheet, document and revision the value was checked against")
    vf.add_argument("--scope", required=True, help="What was verified (for example: value and unit against the data sheet; not the design)")
    vf.add_argument("--date", default=None, help="ISO date of the review (default: today)")
    vf.add_argument("--register", default="config/manufacturer_data_register.yaml")
    vf.set_defaults(func=cmd_verify)
    tr = sub.add_parser("generate-training", help="Generate the training suite (modules, exercises, answer key, question bank, certificate template)")
    tr.add_argument("--training", default="training")
    tr.set_defaults(func=cmd_training)
    dr = sub.add_parser("generate-drawings", help="Generate the preliminary single-line diagram (SVG and PDF)")
    dr.add_argument("--drawings", default="drawings")
    dr.set_defaults(func=cmd_drawings)
    gd = sub.add_parser("generate-documents", help="Generate specifications, customer README, licence draft, review documents and the master index")
    gd.set_defaults(func=cmd_documents)
    rp = sub.add_parser("build-review-package", help="Assemble the independent engineering review package (ZIP)")
    rp.add_argument("--dist", default="dist")
    rp.set_defaults(func=cmd_review_package)
    pk = sub.add_parser("build-package", help="Assemble the customer ZIP from what exists (no engine source unless --include-engine)")
    pk.add_argument("--dist", default="dist")
    pk.add_argument("--include-engine", action="store_true", help="Also include the Python engine and master configuration")
    pk.set_defaults(func=cmd_package)
    qa = sub.add_parser("qa-report", help="Run the tests and write QA_RESULTS.md")
    qa.add_argument("--output", default="output")
    qa.set_defaults(func=cmd_qa)
    t = sub.add_parser("run-tests", help="Run the automated tests")
    t.set_defaults(func=cmd_tests)
    for name in NOT_IMPLEMENTED:
        n = sub.add_parser(name, help="Not implemented in Stage 1")
        n.set_defaults(func=lambda a, name=name: (print(f"'{name}' is not implemented in Stage 1. See DEVELOPMENT_STATUS.md."), EXIT_NOT_IMPLEMENTED)[1])
    args = p.parse_args(argv)
    setup_logging(args.verbose)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
