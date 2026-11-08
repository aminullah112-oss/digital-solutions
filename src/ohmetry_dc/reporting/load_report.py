"""Electrical Load Estimation Report (PDF), generated from the same configuration and result objects as the workbook."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ohmetry_dc import __version__
from ohmetry_dc.calculations import LoadEstimate
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.validation import CheckResult, release_gate, summarise

INK = colors.HexColor("#0E171E")
STATUS_COLOURS = {"PASS": "#CDEBD3", "WARNING": "#FFE9A8", "FAIL": "#F8C9C4", "NOT VERIFIED": "#E4DCF2", "NOT APPLICABLE": "#DDDDDD"}


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, alignment=0),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=INK, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13),
        "small": ParagraphStyle("s", parent=ss["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#555555")),
        "cell": ParagraphStyle("c", parent=ss["BodyText"], fontName="Helvetica", fontSize=8, leading=10),
        "cellb": ParagraphStyle("cb", parent=ss["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=10),
        "warn": ParagraphStyle("w", parent=ss["BodyText"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.HexColor("#8A1C12")),
    }


def _table(data, widths, st, header=True, status_col=None):
    rows = [[Paragraph(str(c), st["cellb"] if (header and i == 0) else st["cell"]) for c in r] for i, r in enumerate(data)]
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D2DA")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        rows[0] = [Paragraph(f'<font color="white">{c}</font>', st["cellb"]) for c in data[0]]
        t = Table(rows, colWidths=widths, repeatRows=1)
    if status_col is not None:
        for i, r in enumerate(data[1:], 1):
            c = STATUS_COLOURS.get(str(r[status_col]))
            if c:
                style.append(("BACKGROUND", (status_col, i), (status_col, i), colors.HexColor(c)))
    t.setStyle(TableStyle(style))
    return t


def build_load_report(cfg: ProjectConfig, est: LoadEstimate, checks: list[CheckResult], path: str | Path, generated_utc: str | None = None) -> Path:
    generated_utc = generated_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st = _styles()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = summarise(checks)
    gate = release_gate(checks, cfg.project.release_state)
    W = A4[0] - 30 * mm

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(15 * mm, 10 * mm, f"{cfg.project.code}  |  Electrical Load Estimation Report  |  revision {cfg.project.revision}  |  PRELIMINARY, not for construction")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"{cfg.project.code} Electrical Load Estimation Report", author="Ohmetry", invariant=1)
    s: list = []
    P = lambda text, style="body": Paragraph(text, st[style])

    s += [P(cfg.project.name, "title"), P("Electrical Load Estimation Report", "h1"),
          P(f"Project code {cfg.project.code}. Revision {cfg.project.revision}. Package version {__version__}. Generated {generated_utc}. Release state: {cfg.project.release_state.value}. Release gate: {gate.value}."),
          Spacer(1, 4 * mm),
          P("PRELIMINARY ILLUSTRATIVE REPORT. NOT FOR CONSTRUCTION. This report is an educational and preliminary engineering reference. It is not construction-ready, not code-compliant, not certified and not independently approved. "
            "Every input is an illustrative assumption for the sample project, chosen for ideal conditions. It requires review by suitably qualified engineers before any use beyond education.", "warn"),
          Spacer(1, 4 * mm)]

    s += [P("1. Executive summary", "h1"),
          P(f"The load model gives a facility demand of {est.facility_kw:,.1f} kW ({est.facility_kva:,.1f} kVA at a power factor of {est.power_factor:.3f}) for an IT critical load of {est.it_demand_kw:,.1f} kW. "
            f"The design-point PUE is {est.pue:.3f} against a target of {cfg.value('general.target_pue')}. In normal operation each path carries {est.path_a.kw:,.1f} kW and {est.path_b.kw:,.1f} kW; "
            f"if one path is lost, the other carries all {est.facility_kw:,.1f} kW ({est.facility_kva:,.1f} kVA). "
            f"Checks: {', '.join(f'{k} {v}' for k, v in summary.items() if v)}. A PASS is a software check against the stated assumptions, not an engineering approval."),
          P("2. Purpose and scope", "h1"),
          P("This report estimates the connected and demand electrical load of the reference data centre, the UPS and distribution losses, the design-point PUE and the allocation of load to the A and B power paths. "
            "It does not size transformers, generators, UPS or batteries (Stage 3), cables (Stage 4), or perform short-circuit, protection, earthing or power-quality studies (Stages 4 and 5)."),
          P("3. Design basis", "h1")]
    basis_ids = ["general.it_critical_load", "general.target_pue", "general.estimated_facility_demand", "general.design_power_factor", "general.future_expansion_allowance",
                 "electrical_system.mv_supply_voltage", "electrical_system.lv_line_voltage", "electrical_system.frequency", "redundancy.architecture", "redundancy.ups_topology", "redundancy.generator_concept"]
    rows = [["Parameter", "Value", "Unit", "Status"]] + [[cfg.get(i).name, cfg.get(i).value, cfg.get(i).unit, cfg.get(i).status.value] for i in basis_ids]
    s += [_table(rows, [W * .46, W * .27, W * .1, W * .17], st)]

    s += [P("4. Input data and sources", "h1"),
          P("The load schedule below is read from config/load_schedule.yaml. Every item is an illustrative assumption for the sample project, not a measured or manufacturer value.")]
    rows = [["ID", "Description", "Qty x kW", "PF", "DF", "Path A", "Status"]]
    for it, ci in zip(est.items, cfg.load_items):
        rows.append([it.id, it.description, f"{it.quantity:g} x {it.unit_rating_kw:g}", f"{it.power_factor:.2f}", f"{it.demand_factor:.2f}", f"{it.path_a_fraction:.2f}", ci.status.value])
    s += [_table(rows, [W * .08, W * .42, W * .16, W * .07, W * .07, W * .08, W * .12], st)]

    s += [P("5. Assumptions", "h1"),
          P("All of the following are assumptions made for the sample project. They are not manufacturer data. They are listed in config/assumptions_register.yaml with their confirmation status (UNCONFIRMED).")]
    rows = [["Assumption", "Value", "Unit"]]
    for pid in ["equipment.ups_efficiency", "losses.distribution_loss_fraction", "general.future_expansion_allowance", "general.design_power_factor", "general.target_pue"]:
        p = cfg.get(pid)
        rows.append([p.name, p.value, p.unit])
    rows += [["Operating arrangement", "Chillers 3 of 4 run, pumps 4 of 6 run, all IT dual-corded and split 50/50 between paths", "-"],
             ["Path-out scenarios", "All load transfers to the surviving path", "-"]]
    s += [_table(rows, [W * .5, W * .4, W * .1], st)]

    s += [P("6. Calculation methodology", "h1"),
          P("For each item, connected load = quantity x unit rating, and demand = connected load x demand factor. Reactive power = demand kW x tan(acos(power factor)). "
            "Totals add real and reactive power separately and apparent power is sqrt(P<super>2</super> + Q<super>2</super>). UPS losses = IT demand x (1 / efficiency - 1). "
            "Distribution losses = loss percentage x (load items + UPS losses). Facility demand = load items + UPS losses + distribution losses. "
            "PUE = facility kW / IT kW at the design point. Path A load sums each item's demand times its path A fraction, plus the UPS losses by the IT split, plus its own distribution losses; path B is the remainder."),
          P("PUE definition and limits: the figure here is a design-point power ratio. The metric as usually reported is an energy ratio over a period, which depends on IT utilisation, climate and operating modes that this model does not simulate.")]

    s += [P("7. Results", "h1")]
    rows = [["Category", "Demand (kW)"]] + [[k, f"{v:,.2f}"] for k, v in est.category_demand_kw.items()]
    s += [_table(rows, [W * .6, W * .4], st), Spacer(1, 3 * mm)]
    rows = [["Quantity", "Value", "Unit"],
            ["Connected load of all items", f"{est.connected_kw:,.1f}", "kW"], ["Demand of all load items", f"{est.items_demand_kw:,.2f}", "kW"],
            ["UPS losses", f"{est.ups_loss.kw:,.2f}", "kW"], ["Distribution losses", f"{est.distribution_loss.kw:,.2f}", "kW"],
            ["Facility demand", f"{est.facility_kw:,.2f}", "kW"], ["Facility reactive demand", f"{est.facility_kvar:,.2f}", "kvar"],
            ["Facility apparent demand", f"{est.facility_kva:,.2f}", "kVA"], ["Facility power factor", f"{est.power_factor:.4f}", "-"],
            ["Design-point PUE", f"{est.pue:.4f}", "-"], ["Design demand including growth allowance", f"{est.design_demand_kw:,.2f}", "kW"],
            ["Design apparent demand including growth", f"{est.design_demand_kva:,.2f}", "kVA"]]
    s += [_table(rows, [W * .6, W * .25, W * .15], st), Spacer(1, 3 * mm)]
    rows = [["A/B allocation", "kW", "kvar", "kVA"],
            ["Normal: path A", f"{est.path_a.kw:,.2f}", f"{est.path_a.kvar:,.2f}", f"{est.path_a.kva:,.2f}"], ["Normal: path B", f"{est.path_b.kw:,.2f}", f"{est.path_b.kvar:,.2f}", f"{est.path_b.kva:,.2f}"],
            ["One path out: surviving path carries all", f"{est.facility_kw:,.2f}", f"{est.facility_kvar:,.2f}", f"{est.facility_kva:,.2f}"]]
    s += [_table(rows, [W * .46, W * .18, W * .18, W * .18], st)]

    s += [P("8. Design checks and status", "h1"),
          P("Statuses: PASS (the check ran and found no problem, not an approval), WARNING (a possible inconsistency), FAIL (a defect that blocks release), NOT VERIFIED (cannot be judged without data or a limit that has not been supplied), NOT APPLICABLE.")]
    rows = [["Check", "Status", "Detail"]] + [[c.title, c.status.value, c.detail] for c in checks]
    s += [_table(rows, [W * .27, W * .13, W * .6], st, status_col=1)]

    s += [P("9. Limitations", "h1"),
          P("The load list is illustrative. Demand factors depend on the real operating arrangement. UPS losses assume all IT load is on the UPS at one efficiency. Distribution losses use a single percentage. "
            "Power factors of losses use the design assumption. PUE is a design-point ratio, not an annual energy figure. Path-out scenarios assume all load transfers to the surviving path and ignore load shedding and equipment limits. "
            "No harmonic, step-loading, transient or short-circuit effects are included. A spreadsheet or script is not a substitute for specialist software or manufacturer sizing tools where those are required.")]
    deferred = cfg.deferred()
    s += [P("10. Outstanding information", "h1"),
          P("The following inputs are needed in later stages and are not yet supplied: " + ("; ".join(f"{p.id} (Stage {p.needed_from_stage})" for p in deferred) if deferred else "none") + ".")]
    s += [P("11. Required engineering review", "h1"),
          P("The design basis, every assumption in the register and every result require independent review by suitably qualified engineers. No review has taken place. Release gate: " + gate.value + ".")]
    s += [P("12. Revision history", "h1"), _table([["Revision", "Date", "Description", "Reviewer"], [cfg.project.revision, generated_utc[:10], "First generated load estimate (Stage 2). Illustrative assumptions for the sample project.", "not assigned"]], [W * .12, W * .16, W * .5, W * .22], st)]
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return path
