"""04_TRANSFORMER_SIZING, 05_GENERATOR_SIZING and 06_UPS_SIZING.

One generic builder: the scenario table of the Python engine (normal, loss of the other path, loss of one unit, loss of both) as live formulas, with the
loads from the load estimate as editable inputs, the equipment ratings and derating factors as inputs that accept datasheet values, and the four statuses.
"""
from __future__ import annotations

from pathlib import Path

from ohmetry_dc.calculations import PowerSystemSizing
from ohmetry_dc.calculations.sizing import Sizing
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds
from ohmetry_dc.validation import CheckResult

from .common import (FILL_INPUT, FILL_RESULT, Inputs, blue, _header, _page, _put, base, bold, colour_statuses, new_workbook, note, readme, revision_sheet, status_block, title)

KINDS = {
    "transformer": ("04_TRANSFORMER_SIZING.xlsx", "Transformer sizing", ["transformer_loading"]),
    "generator": ("05_GENERATOR_SIZING.xlsx", "Generator sizing", ["generator_loading_kw", "generator_loading"]),      # same order as the blocks: kW, then kVA
    "ups": ("06_UPS_SIZING.xlsx", "UPS sizing", ["ups_loading_kw", "ups_loading_kva"]),
}
SHEETS = ["README", "INPUTS", "CALCULATIONS", "RESULTS", "REVISION_LOG"]
LOAD_SRC = "Preliminary: from the load estimate (02_LOAD_ESTIMATION). Replace with your own load figures."


def _options_sheet(wb, cfg, kind, sizing, blocks, block_cells, I) -> None:
    """OPTIONS: the retained rating and an illustrative alternative side by side, as live formulas on the CALCULATIONS scenarios. The package selects nothing."""
    from ohmetry_dc.calculations.options import equipment_options

    ws = wb.create_sheet("OPTIONS", index=wb.sheetnames.index("REVISION_LOG"))
    _page(ws)
    ws["A1"].value, ws["A1"].font = "Options side by side (the engineer selects; the package selects nothing)", title
    ws["A2"].value, ws["A2"].font = ("Each row applies the CALCULATIONS scenarios, derating and loading policy to a rating. The retained row follows the INPUTS sheet. The option row is an illustrative rating you can overwrite (blue). "
                                      "Derating factors are 1.00 placeholders. Not manufacturer data."), note
    _header(ws, 4, ["Metric", "Option", "Rating", "Worst credible loading %", "Status", "Python at generation (%)", "Agreement"], [14, 26, 14, 24, 16, 22, 40])
    rows = [o for o in equipment_options(cfg, sizing) if o.equipment == kind]
    r = 5
    for metric, s in blocks:
        b = block_cells[metric]
        for o in rows:
            ws[f"A{r}"].value, ws[f"B{r}"].value = metric, o.label
            if o.retained:
                _put(ws, f"C{r}", f"={I(f'rating_{metric}')}", base, FILL_RESULT, "#,##0")
            else:
                _put(ws, f"C{r}", o.rating[metric], blue, FILL_INPUT, "#,##0")
            terms = ",".join(f"IF(AND(CALCULATIONS!$C${k}=1,CALCULATIONS!$D${k}=1,CALCULATIONS!$F${k}*CALCULATIONS!$G${k}>0),CALCULATIONS!$E${k}/(CALCULATIONS!$F${k}*CALCULATIONS!$G${k}*C{r}*{b['comb']}),0)" for k in range(b["first"], b["last"] + 1))
            _put(ws, f"D{r}", f"=100*MAX({terms})", bold, FILL_RESULT, "0.00")
            _put(ws, f"E{r}", f'=IF(D{r}>{I("limit_pct")}+0.000000001,"FAIL",IF(D{r}>{I("target_pct")}+0.000000001,"WARNING","PASS"))', bold)
            _put(ws, f"F{r}", o.loadings_pct[metric], base, None, "0.00")
            _put(ws, f"G{r}", f'=IF(ABS(D{r}-F{r})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
            r += 1
    colour_statuses(ws, f"E5:E{r - 1}")
    ws[f"A{r + 1}"].value, ws[f"A{r + 1}"].font = ("The transformer-limited fault figure rises with the rating at the same impedance (see 10_SHORT_CIRCUIT). It is not the bus fault level." if kind == "transformer" else
                                                  "UPS ratings and output power factor come from the manufacturer. The option kW is the kVA scaled by the retained ratio."), note


def _scen(s: Sizing, sid: str):
    return next((x for x in s.scenarios if x.id == sid), None)


def build_sizing_workbook(cfg: ProjectConfig, kind: str, sizing: PowerSystemSizing, checks: list[CheckResult], path: str | Path, stamp: str) -> Path:
    file, heading, check_ids = KINDS[kind]
    wb, _ = new_workbook(cfg, stamp, heading)
    ws0 = wb.active
    ws0.title = "README"
    inp_ws, calc, res, rev = (wb.create_sheet(n) for n in SHEETS[1:])
    for w in wb.worksheets:
        _page(w)
    blocks: list[tuple[str, Sizing]] = {"transformer": [("kVA", sizing.transformer)], "ups": [("kW", sizing.ups_kw), ("kVA", sizing.ups_kva)],
                                        "generator": [("kW", sizing.generator_kw), ("kVA", sizing.generator)]}[kind]
    ref = blocks[0][1]
    inp = Inputs(inp_ws, f"{heading}: inputs", "Preliminary values are retained from the master configuration. Enter datasheet values in column E with their source in column H.")
    P = lambda pid: cfg.get(pid)
    pst = lambda pid: ds.data_status(P(pid))
    src = lambda pid: P(pid).source
    g = ref.policy
    inp.add("growth_pct", "Future expansion allowance", "%", cfg.value("general.future_expansion_allowance"), pst("general.future_expansion_allowance"), src("general.future_expansion_allowance"), "SITE_DATA")
    inp.add("units_per_path", "Units per power path", "-", ref.units_per_path, ds.PRELIMINARY_ASSUMPTION, "Equipment quantity divided by the number of paths (master configuration)", "MANUFACTURER")
    inp.add("double_contingency", "Loss of one unit while the other path is also lost is a credible case (1 = yes, 0 = no)", "-", 1 if cfg.value("redundancy.double_contingency_credible") else 0,
            pst("redundancy.double_contingency_credible"), src("redundancy.double_contingency_credible"), "SITE_DATA")
    redundant = 1 if (kind != "generator" or "N+1" in str(cfg.value("redundancy.generator_concept"))) else 0
    inp.add("redundant_unit", "Spare unit in each path, so loss of one unit is assessed (1 = yes, 0 = no)", "-", redundant, ds.PRELIMINARY_ASSUMPTION, "Redundancy concept (master configuration)", "SITE_DATA")
    inp.add("target_pct", "Preferred loading target", "%", g.target_pct, ds.PROJECT_INPUT, "Project owner decision, 2026-11-05", "SITE_DATA", "Above the target: WARNING.")
    inp.add("limit_pct", "Maximum loading", "%", g.limit_pct, ds.PROJECT_INPUT, "Project owner decision, 2026-11-05", "SITE_DATA", "Above the maximum: FAIL.")
    for part in ("ambient", "altitude", "installation"):
        pid = f"derating.{kind}_{part}_factor"
        inp.add(f"derate_{part}", f"{part.capitalize()} derating factor ({kind})", "-", cfg.value(pid), pst(pid), src(pid), "MANUFACTURER", "From the manufacturer's derating curve at the site conditions. 1.00 applies no derating.")
    if kind == "transformer":
        pid = "derating.transformer_contingency_factor"
        inp.add("contingency_factor", "Contingency derating factor (surviving transformer, loss of the other path)", "-", cfg.value(pid), pst(pid), src(pid), "MANUFACTURER")
    if kind == "transformer":
        inp.add("rating_kVA", "Transformer continuous rating (each)", "kVA", cfg.value("equipment.transformer_rating"), pst("equipment.transformer_rating"), src("equipment.transformer_rating"), "MANUFACTURER")
    elif kind == "ups":
        inp.add("rating_kW", "UPS rating (each), active power", "kW", cfg.value("equipment.ups_rating"), pst("equipment.ups_rating"), src("equipment.ups_rating"), "MANUFACTURER")
        inp.add("rating_kVA", "UPS rating (each), apparent power", "kVA", cfg.value("equipment.ups_rating_kva"), pst("equipment.ups_rating_kva"), src("equipment.ups_rating_kva"), "MANUFACTURER")
    else:
        basis = str(cfg.value("generators.rating_basis")).upper()
        pid = {"PRP": "equipment.generator_rating", "ESP": "equipment.generator_esp_rating", "COP": "equipment.generator_cop_rating"}[basis]
        inp.add("rating_kVA", f"Generator {basis} rating (each), apparent power", "kVA", cfg.value(pid), pst(pid), src(pid), "MANUFACTURER",
                "Assumed to be a PRP rating. NOT confirmed by manufacturer documentation (ISO 8528: PRP, ESP and COP are different ratings).")
        pid = "equipment.generator_rating_power_factor"
        inp.add("rated_pf", "Generator rated power factor", "-", cfg.value(pid), pst(pid), src(pid), "MANUFACTURER", "Converts the kVA rating to engine kW.")
    for metric, s in blocks:
        n_ = _scen(s, f"{ {'transformer': 'TX', 'ups': 'UPS', 'generator': 'GEN'}[kind] }-NORMAL")
        t_ = _scen(s, f"{ {'transformer': 'TX', 'ups': 'UPS', 'generator': 'GEN'}[kind] }-PATH-OUT")
        f = 1 + (cfg.value("general.future_expansion_allowance") or 0) / 100.0
        inp.add(f"normal_{metric}", f"Load on the more heavily loaded path, normal operation ({metric})", metric, None if n_ is None else n_.load / f, ds.PRELIMINARY_ASSUMPTION, LOAD_SRC, "SITE_DATA")
        inp.add(f"total_{metric}", f"Whole load carried by one path after loss of the other ({metric})", metric, None if t_ is None else t_.load / f, ds.PRELIMINARY_ASSUMPTION, LOAD_SRC, "SITE_DATA")
    inp.finish()
    I = inp.eff

    # ---- CALCULATIONS: one block per metric
    calc["A1"].value, calc["A1"].font = f"{heading}: calculations", title
    calc["A2"].value, calc["A2"].font = "Loading is against the derated continuous rating. No short-duration overload capability is used. Scenarios follow the Python engine.", note
    cols = ["Scenario", "Description", "Applies (1/0)", "Judged (1/0)", "Load", "Units", "Factor", "Capacity each (derated)", "Capacity total", "Loading", "Loading %", "Result",
            "Credible loading", "Derated each needed for target", "Derated each needed for limit"]
    widths = [22, 56, 9, 9, 12, 7, 8, 14, 14, 10, 10, 16, 12, 16, 16]
    block_cells: dict[str, dict] = {}
    top = 4
    ck = {"transformer": "TX", "ups": "UPS", "generator": "GEN"}[kind]
    for metric, s in blocks:
        calc[f"A{top}"].value, calc[f"A{top}"].font = f"{metric} block", bold
        if kind == "generator" and metric == "kW":
            rating = f"{I('rating_kVA')}*{I('rated_pf')}"
        else:
            rating = I(f"rating_{metric}")
        comb = f"{I('derate_ambient')}*{I('derate_altitude')}*{I('derate_installation')}"
        _put(calc, f"A{top+1}", "Derated rating each", base)
        _put(calc, f"B{top+1}", f"={rating}*{comb}", bold, FILL_RESULT, "#,##0.0")
        _put(calc, f"A{top+2}", "Combined derating factor", base)
        _put(calc, f"B{top+2}", f"={comb}", bold, FILL_RESULT, "0.0000")
        _header(calc, top + 3, cols, widths)
        first = top + 4
        n = I("units_per_path")
        cont = I("contingency_factor") if kind == "transformer" else "1"
        rows = [(f"{ck}-NORMAL", "Normal operation: the more heavily loaded path on its own units", "1", "1", f"{I(f'normal_{metric}')}*(1+{I('growth_pct')}/100)", n, "1"),
                (f"{ck}-PATH-OUT", "Loss of the other path: the surviving path carries the whole load", "1", "1", f"{I(f'total_{metric}')}*(1+{I('growth_pct')}/100)", n, cont),
                (f"{ck}-UNIT-OUT", "Loss of one unit (N+1): the path load on the remaining units", f"IF(AND({I('redundant_unit')}=1,{n}>=2),1,0)", f"IF(AND({I('redundant_unit')}=1,{n}>=2),1,0)",
                 f"{I(f'normal_{metric}')}*(1+{I('growth_pct')}/100)", f"{n}-1", "1"),
                (f"{ck}-PATH-OUT-UNIT-OUT", "Loss of the other path and one unit (combined contingency: N+1 engine-out on the surviving path)", f"IF(AND({I('redundant_unit')}=1,{n}>=2),1,0)",
                 f"IF(AND({I('redundant_unit')}=1,{n}>=2,{I('double_contingency')}=1),1,0)", f"{I(f'total_{metric}')}*(1+{I('growth_pct')}/100)", f"{n}-1", cont)]
        for k, (sid, desc, app, jud, load, units, fac) in enumerate(rows):
            r = first + k
            _put(calc, f"A{r}", sid)
            _put(calc, f"B{r}", desc, base, align=None)
            _put(calc, f"C{r}", f"={app}")
            _put(calc, f"D{r}", f"={jud}")
            _put(calc, f"E{r}", f"={load}", base, FILL_RESULT, "#,##0.0")
            _put(calc, f"F{r}", f"={units}")
            _put(calc, f"G{r}", f"={fac}", base, None, "0.0000")
            _put(calc, f"H{r}", f"=$B${top+1}*G{r}", base, FILL_RESULT, "#,##0.0")
            _put(calc, f"I{r}", f"=H{r}*F{r}", base, FILL_RESULT, "#,##0.0")
            _put(calc, f"J{r}", f'=IF(AND(C{r}=1,ISNUMBER(I{r})),IF(I{r}>0,E{r}/I{r},""),"")', base, FILL_RESULT, "0.0000")
            _put(calc, f"K{r}", f'=IF(J{r}="","",J{r}*100)', base, FILL_RESULT, "0.0")
            _put(calc, f"L{r}", f'=IF(C{r}<>1,"NOT APPLICABLE",IF(D{r}<>1,"INFORMATIONAL",IF(K{r}>{I("limit_pct")}+0.000000001,"FAIL",IF(K{r}>{I("target_pct")}+0.000000001,"WARNING","PASS"))))', bold)
            _put(calc, f"M{r}", f'=IF(AND(C{r}=1,D{r}=1,J{r}<>""),J{r},-1)')
            _put(calc, f"N{r}", f'=IF(AND(C{r}=1,D{r}=1,F{r}*G{r}>0),E{r}/(F{r}*G{r})/({I("target_pct")}/100),0)', base, None, "#,##0.0")
            _put(calc, f"O{r}", f'=IF(AND(C{r}=1,D{r}=1,F{r}*G{r}>0),E{r}/(F{r}*G{r})/({I("limit_pct")}/100),0)', base, None, "#,##0.0")
        last = first + 3
        colour_statuses(calc, f"L{first}:L{last}")
        wr = last + 1
        _put(calc, f"A{wr}", "Worst credible loading", bold)
        _put(calc, f"E{wr}", f"=MAX(M{first}:M{last})", bold, FILL_RESULT, "0.0000")
        _put(calc, f"F{wr}", f"=INDEX(A{first}:A{last},MATCH(E{wr},M{first}:M{last},0))", bold)
        block_cells[metric] = {"first": first, "last": last, "worst": f"CALCULATIONS!$E${wr}", "worst_id": f"CALCULATIONS!$F${wr}", "derated": f"CALCULATIONS!$B${top+1}",
                               "comb": f"CALCULATIONS!$B${top+2}", "req_t": f"MAX(CALCULATIONS!$N${first}:$N${last})/CALCULATIONS!$B${top+2}", "req_l": f"MAX(CALCULATIONS!$O${first}:$O${last})/CALCULATIONS!$B${top+2}"}
        calc.freeze_panes = "C4"
        top = wr + 3

    sheets_listed = SHEETS
    if kind in ("transformer", "ups"):
        sheets_listed = SHEETS[:-1] + ["OPTIONS"] + SHEETS[-1:]
        _options_sheet(wb, cfg, kind, sizing, blocks, block_cells, I)

    # ---- RESULTS
    res["A1"].value, res["A1"].font = f"{heading}: results and statuses", title
    res["A2"].value, res["A2"].font = "A successful calculation is not a verified design. The four statuses are shown separately.", note
    res.column_dimensions["A"].width = 58
    res.column_dimensions["B"].width = 26
    res.column_dimensions["C"].width = 26
    res.column_dimensions["D"].width = 60
    row = 4
    cmap = {c.id: c for c in checks}
    pyvals: dict = {}
    required = [I(k) for k in inp.rows if k not in ("double_contingency", "redundant_unit")]
    for (metric, s), cid in zip(blocks, check_ids):
        b = block_cells[metric]
        _put(res, f"A{row}", f"{heading}: {metric}", title, border=None)
        _put(res, f"A{row+1}", "Worst credible loading (% of derated rating)", base)
        _put(res, f"B{row+1}", f"={b['worst']}*100", bold, FILL_RESULT, "0.00")
        _put(res, f"A{row+2}", "Worst credible scenario", base)
        _put(res, f"B{row+2}", f"={b['worst_id']}", bold)
        _put(res, f"A{row+3}", f"Rating each needed to meet the target ({s.equipment} nameplate, {metric})", base)
        _put(res, f"B{row+3}", f"={b['req_t']}", bold, FILL_RESULT, "#,##0")
        _put(res, f"A{row+4}", f"Rating each needed to meet the maximum ({metric})", base)
        _put(res, f"B{row+4}", f"={b['req_l']}", bold, FILL_RESULT, "#,##0")
        crit = ("(" + b["worst"] + f'*100>{I("limit_pct")}+0.000000001,"FAIL",IF({b["worst"]}*100>{I("target_pct")}+0.000000001,"WARNING","PASS"))')
        refs = status_block(res, row + 6, f"Statuses: {metric}", required, f'IF{crit}', inp.status_range())
        # Python values at generation, for the agreement check
        py = cmap.get(cid)
        w = s.worst_credible
        pv = {"worst_pct": None if w is None else w.loading * 100, "worst_id": None if w is None else w.id,
              "req_target": s.required_rating_each_for_target, "req_limit": s.required_rating_each_for_limit,
              "calc_result": py.calculation_result if py else None, "overall": py.status.value if py else None, "input_status": py.input_status if py else None}
        pyvals[metric] = pv
        _put(res, f"C{row+1}", pv["worst_pct"], base, None, "0.00")
        _put(res, f"C{row+2}", pv["worst_id"])
        _put(res, f"C{row+3}", pv["req_target"], base, None, "#,##0")
        _put(res, f"C{row+4}", pv["req_limit"], base, None, "#,##0")
        _put(res, f"C{row+8}", pv["calc_result"])
        _put(res, f"C{row+11}", pv["overall"])
        _put(res, f"C{row+9}", pv["input_status"])
        _put(res, f"D{row+1}", f'=IF(ABS(B{row+1}-C{row+1})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
        _put(res, f"D{row+3}", f'=IF(ABS(B{row+3}-C{row+3})<=0.0001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
        _put(res, f"D{row+8}", f'=IF(B{row+8}=C{row+8},"MATCH","DIFFERENT (inputs changed since generation)")', note)
        _put(res, f"D{row+11}", f'=IF(B{row+11}=C{row+11},"MATCH","DIFFERENT (inputs changed since generation)")', note)
        row += 14
    _put(res, "C3", "Python engine at generation", bold)
    _put(res, "D3", "Agreement", bold)
    readme(ws0, f"{heading}: " + cfg.project.name, file, cfg, stamp,
           "Loading of the equipment against its derated continuous rating in normal operation, loss of the other path, and loss of one unit, with the preferred target and maximum from the project owner. "
           "Required rating to meet the target and the maximum.",
           "Loads are taken from the preliminary load estimate and must be replaced by project loads. Overload capability is not used. Generator load steps, transients, UPS rectifier interaction and minimum "
           "load are not assessed here (see the Python engine notes). Derating factors of 1.00 are placeholders for ideal conditions.", sheets_listed)
    revision_sheet(rev, cfg, stamp, file)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
