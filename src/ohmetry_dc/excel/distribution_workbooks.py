"""08_CABLE_SIZING (current rating framework, voltage drop, short-circuit thermal withstand) and 10_SHORT_CIRCUIT (IEC 60909 levels, equipment ratings).

Every input accepts a datasheet value with its source. Anything that cannot be calculated from the inputs present reads NOT CALCULATED; nothing is
substituted. The Python engine's values at generation are stored beside the results so a change in inputs shows as DIFFERENT, not as an error.
"""
from __future__ import annotations

from pathlib import Path

from ohmetry_dc.calculations import assess_distribution, assess_short_circuit, estimate_loads, size_power_system
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds
from ohmetry_dc.validation import CheckResult

from .common import (FILL_RESULT, Inputs, _header, _page, _put, agg_status, base, bold, colour_statuses, new_workbook, note, readme, revision_sheet, status_block, title)

SHEETS = ["README", "INPUTS", "CALCULATIONS", "RESULTS", "REVISION_LOG"]
CABLE_FILE, SC_FILE = "08_CABLE_SIZING.xlsx", "10_SHORT_CIRCUIT.xlsx"
NC = '"NOT CALCULATED"'


def _hdr(ws, row, labels, widths):
    _header(ws, row, labels, widths)


def build_short_circuit_workbook(cfg: ProjectConfig, checks: list[CheckResult], path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "short-circuit levels")
    ws0 = wb.active
    ws0.title = "README"
    iw, calc, res, rev = (wb.create_sheet(n) for n in SHEETS[1:])
    for w in wb.worksheets:
        _page(w)
    py = assess_short_circuit(cfg)
    inp = Inputs(iw, "Short-circuit levels: inputs", "Utility, transformer and generator data are pending project and manufacturer inputs unless the master configuration holds a preliminary value.")
    st = lambda pid: ds.data_status(cfg.get(pid))
    rows = [("utility_mva", "short_circuit.utility_fault_level_mva", "SITE_DATA", "Utility's written statement of the maximum fault level."),
            ("utility_xr", "short_circuit.utility_x_r_ratio", "SITE_DATA", "Utility source X/R ratio."),
            ("mv_kv", "electrical_system.mv_supply_voltage", "SITE_DATA", "Nominal MV line-to-line voltage (kV)."),
            ("lv_v", "electrical_system.lv_line_voltage", "SITE_DATA", "Nominal LV line-to-line voltage (V)."),
            ("freq", "electrical_system.frequency", "SITE_DATA", ""),
            ("c_mv", "short_circuit.voltage_factor_c_max_mv", "MANUFACTURER", "IEC 60909 voltage factor, maximum fault, MV. Reference data: verify the edition."),
            ("c_lv", "short_circuit.voltage_factor_c_max_lv", "MANUFACTURER", "IEC 60909 voltage factor, maximum fault, LV. Use 1.10 for a 10 % tolerance. Reference data."),
            ("tx_kva", "equipment.transformer_rating", "MANUFACTURER", ""),
            ("tx_uk", "equipment.transformer_impedance", "MANUFACTURER", "Short-circuit impedance from the transformer test report."),
            ("tx_xr", "short_circuit.transformer_x_r_ratio", "MANUFACTURER", "From the transformer test report."),
            ("gen_kva", "equipment.generator_rating", "MANUFACTURER", "Assumed PRP rating, not confirmed."),
            ("gen_n", "equipment.generator_quantity_per_path", "MANUFACTURER", "Generators that can run in parallel on one path."),
            ("gen_xd", "short_circuit.generator_subtransient_reactance_pct", "MANUFACTURER", "Saturated subtransient reactance x''d from the generator data sheet."),
            ("gen_xr", "short_circuit.generator_x_r_ratio", "MANUFACTURER", "From the generator data sheet."),
            ("gen_pf", "equipment.generator_rating_power_factor", "MANUFACTURER", "Rated power factor."),
            ("parallel", "short_circuit.generator_parallel_with_utility", "SITE_DATA", "1 if generators can run in parallel with the utility (closed transition), 0 for open transition."),
            ("clear_t", "short_circuit.assumed_clearing_time_s", "MANUFACTURER", "From the protection study. A placeholder until then."),
            ("lv_limit", "short_circuit.lv_fault_level_limit_ka", "SITE_DATA", "Ohmetry preliminary policy, not a standard limit.")]
    for key, pid, sup, nt in rows:
        p = cfg.get(pid)
        v = p.value
        if isinstance(v, bool):
            v = 1 if v else 0
        inp.add(key, p.name, p.unit, v, st(pid), p.source, sup, nt)
    for tag, field, label in (("BD-TX-A", "short_circuit_withstand_ka", "Busduct BD-TX-A short-circuit withstand"), ("LV-MSB-A", "short_circuit_rating_ka", "LV switchboard LV-MSB-A short-circuit rating"),
                              ("MV-SWG-A", "short_circuit_rating_ka", "MV switchgear MV-SWG-A short-circuit rating")):
        it = next((x for g in ("busducts", "switchgear") for x in (cfg.distribution or {}).get(g) or [] if x["tag"] == tag), None)
        inp.add(f"rating_{tag}", label, "kA", None if it is None else it.get(field), ds.UNVERIFIED_PLACEHOLDER, "Manufacturer data pending", "MANUFACTURER", "Required: the manufacturer's rated value and the type-test evidence.")
    for dv in (cfg.distribution or {}).get("protection_devices") or []:
        inp.add(f"break_{dv['tag']}", f"{dv['tag']} breaking capacity", "kA", dv.get("breaking_capacity_ka"), ds.UNVERIFIED_PLACEHOLDER, "Manufacturer data pending", "MANUFACTURER")
    inp.finish()
    I = inp.eff

    calc["A1"].value, calc["A1"].font = "Short-circuit levels: calculations (IEC 60909, maximum three-phase)", title
    calc["A2"].value, calc["A2"].font = "A case reads NOT CALCULATED until all its inputs are present. Motor contribution, cable impedance to the bus and minimum fault current are not included.", note
    _hdr(calc, 4, ["Step", "Value", "Unit", "Formula note"], [46, 18, 10, 70])
    r = [5]
    cells: dict[str, str] = {}

    def line(key, label, formula, unit="", fmt="0.0000", nt="", needs=None):
        row = r[0]
        r[0] += 1
        if needs:
            formula = f'IF(COUNT({",".join(needs)})<{len(needs)},{NC},{formula})'
        _put(calc, f"A{row}", label)
        _put(calc, f"B{row}", f"={formula}", bold, FILL_RESULT, fmt)
        _put(calc, f"C{row}", unit)
        _put(calc, f"D{row}", nt, note)
        cells[key] = f"B{row}"
        return f"B{row}"

    ok = lambda *ks: f"AND({','.join('ISNUMBER(' + cells[k] + ')' for k in ks)})"
    num = lambda k: cells[k]
    # MV
    mvn = [I("utility_mva"), I("utility_xr"), I("c_mv"), I("mv_kv")]
    line("mv_v", "MV voltage", f"{I('mv_kv')}*1000", "V", "#,##0", needs=[I("mv_kv")])
    line("zq", "Utility impedance at MV, |Zq| = c Un^2 / S''kQ", f"{I('c_mv')}*({I('mv_kv')}*1000)^2/({I('utility_mva')}*1000000)", "ohm", "0.000000", needs=mvn)
    line("rq", "Utility resistance", f"{num('zq')}/SQRT(1+{I('utility_xr')}^2)", "ohm", "0.000000", needs=mvn)
    line("xq", "Utility reactance", f"{num('rq')}*{I('utility_xr')}", "ohm", "0.000000", needs=mvn)
    line("ik_mv", "MV bus: initial symmetrical Ik''", f"{I('c_mv')}*{num('mv_v')}/(SQRT(3)*{num('zq')})/1000", "kA", "0.000", needs=mvn)
    kap = lambda x: f"(1.02+0.98*EXP(-3/{x}))"
    ith = lambda k, f_, t_: f"IF({k}<=1,1,SQRT((EXP(4*{f_}*{t_}*LN({k}-1))-1)/(2*{f_}*{t_}*LN({k}-1))+1))"
    line("ip_mv", "MV bus: peak ip = kappa x sqrt2 x Ik''", f"{kap(I('utility_xr'))}*SQRT(2)*{num('ik_mv')}", "kA", "0.000", needs=mvn + [I("clear_t")])
    line("ith_mv", "MV bus: thermal equivalent Ith", f"{ith(kap(I('utility_xr')), I('freq'), I('clear_t'))}*{num('ik_mv')}", "kA", "0.000", needs=mvn + [I("clear_t"), I("freq")])
    # LV transformer
    txn = [I("tx_kva"), I("tx_uk"), I("c_lv"), I("lv_v")]
    line("kt", "Transformer correction factor K_T = 0.95 c / (1 + 0.6 xT)", f"0.95*{I('c_lv')}/(1+0.6*{I('tx_uk')}/100)", "-", "0.0000", needs=[I("c_lv"), I("tx_uk")])
    line("zt", "Transformer impedance K_T x uk Un^2/Sr", f"({I('tx_uk')}/100)*{I('lv_v')}^2/({I('tx_kva')}*1000)*{num('kt')}", "ohm", "0.000000", needs=txn)
    line("ik_b", "LV bus: transformer-limited figure, utility contribution only (infinite source; NOT the bus fault level)", f"{I('c_lv')}*{I('lv_v')}/(SQRT(3)*{num('zt')})/1000", "kA", "0.000", needs=txn,
         nt="Needs only the transformer data. Limits the utility contribution through one transformer. Generator and motor contributions are excluded: NOT a design value.")
    un = txn + [I("tx_xr")] + mvn
    line("rt", "Transformer resistance", f"{num('zt')}/SQRT(1+{I('tx_xr')}^2)", "ohm", "0.000000", needs=un)
    line("xt", "Transformer reactance", f"{num('rt')}*{I('tx_xr')}", "ohm", "0.000000", needs=un)
    line("rtot", "Total resistance at LV (utility referred to LV + transformer)", f"{num('rq')}*({I('lv_v')}/{num('mv_v')})^2+{num('rt')}", "ohm", "0.000000", needs=un)
    line("xtot", "Total reactance at LV", f"{num('xq')}*({I('lv_v')}/{num('mv_v')})^2+{num('xt')}", "ohm", "0.000000", needs=un)
    line("ik_u", "LV bus: utility and one transformer, Ik''", f"{I('c_lv')}*{I('lv_v')}/(SQRT(3)*SQRT({num('rtot')}^2+{num('xtot')}^2))/1000", "kA", "0.000", needs=un)
    line("xr_u", "X/R of that path", f"{num('xtot')}/{num('rtot')}", "-", "0.000", needs=un)
    line("ip_u", "LV bus, utility: peak", f"{kap(num('xr_u'))}*SQRT(2)*{num('ik_u')}", "kA", "0.000", needs=un + [I("clear_t")])
    line("ith_u", "LV bus, utility: thermal equivalent", f"{ith(kap(num('xr_u')), I('freq'), I('clear_t'))}*{num('ik_u')}", "kA", "0.000", needs=un + [I("clear_t"), I("freq")])
    # generators
    gn = [I("gen_kva"), I("gen_n"), I("gen_xd"), I("gen_xr"), I("gen_pf"), I("c_lv"), I("lv_v")]
    line("kg", "Generator correction factor K_G = c / (1 + x''d sin(phi))", f"{I('c_lv')}/(1+{I('gen_xd')}/100*SQRT(1-{I('gen_pf')}^2))", "-", "0.0000", needs=[I("c_lv"), I("gen_xd"), I("gen_pf")])
    line("zg", "Generators in parallel, impedance", f"({I('gen_xd')}/100)*{I('lv_v')}^2/({I('gen_kva')}*1000)*{num('kg')}/{I('gen_n')}", "ohm", "0.000000", needs=gn)
    line("ik_g", "LV bus: generators, Ik''", f"{I('c_lv')}*{I('lv_v')}/(SQRT(3)*{num('zg')})/1000", "kA", "0.000", needs=gn)
    line("ip_g", "LV bus, generators: peak", f"{kap(I('gen_xr'))}*SQRT(2)*{num('ik_g')}", "kA", "0.000", needs=gn + [I("clear_t")])
    line("ith_g", "LV bus, generators: thermal equivalent", f"{ith(kap(I('gen_xr')), I('freq'), I('clear_t'))}*{num('ik_g')}", "kA", "0.000", needs=gn + [I("clear_t"), I("freq")])
    both = f"AND(ISNUMBER({num('ik_u')}),ISNUMBER({num('ik_g')}))"
    line("ik_par", "LV bus: utility and generators in parallel (sum, upper bound)", f'IF({both},{num("ik_u")}+{num("ik_g")},{NC})', "kA", "0.000")
    line("ik_d", "LV design level", f'IF({both},IF({I("parallel")}=1,{num("ik_par")},MAX({num("ik_u")},{num("ik_g")})),{NC})', "kA", "0.000",
         nt="Open transition: the larger single source. Parallel: the sum. Needs the utility and generator cases.")
    line("ip_d", "LV design peak", f'IF({both},IF({I("parallel")}=1,{num("ip_u")}+{num("ip_g")},IF({num("ik_u")}>={num("ik_g")},{num("ip_u")},{num("ip_g")})),{NC})', "kA", "0.000")
    line("ith_d", "LV design thermal equivalent", f'IF({both},IF({I("parallel")}=1,{num("ith_u")}+{num("ith_g")},IF({num("ik_u")}>={num("ik_g")},{num("ith_u")},{num("ith_g")})),{NC})', "kA", "0.000")
    calc.freeze_panes = "A5"

    # ---- RESULTS
    res["A1"].value, res["A1"].font = "Short-circuit levels: results and statuses", title
    res["A2"].value, res["A2"].font = "A calculated level is not a verified design. The utility, transformer and generator data are pending or preliminary.", note
    for c, w in zip("ABCDE", (50, 24, 24, 22, 44)):
        res.column_dimensions[c].width = w
    _put(res, "B3", "Excel", bold)
    _put(res, "C3", "Python at generation", bold)
    _put(res, "D3", "Agreement", bold)
    pycase = {c.name: c for c in py.lv_cases}
    u = next((c for c in py.lv_cases if c.name.startswith("Utility and one")), None)
    g_ = next((c for c in py.lv_cases if "generators" in c.name and not c.name.startswith("Utility")), None)
    b_ = next((c for c in py.lv_cases if c.name.startswith("Transformer-limited")), None)
    items = [("MV bus, utility Ik'' (kA)", "ik_mv", py.mv_case.ik_ka if py.mv_case else None), ("LV: transformer-limited bound (kA)", "ik_b", b_.ik_ka if b_ else None),
             ("LV: utility and one transformer Ik'' (kA)", "ik_u", u.ik_ka if u else None), ("LV: generators Ik'' (kA)", "ik_g", g_.ik_ka if g_ else None),
             ("LV design level (kA)", "ik_d", py.design_lv.ik_ka if py.design_lv else None), ("LV design peak (kA)", "ip_d", py.design_lv.ip_ka if py.design_lv else None),
             ("LV design thermal equivalent (kA)", "ith_d", py.design_lv.ith_ka if py.design_lv else None)]
    for k, (label, key, pv) in enumerate(items):
        rr = 4 + k
        _put(res, f"A{rr}", label)
        _put(res, f"B{rr}", f"=CALCULATIONS!{cells[key]}", bold, FILL_RESULT, "0.000")
        _put(res, f"C{rr}", "NOT CALCULATED" if pv is None else pv, base, None, "0.000")
        _put(res, f"D{rr}", f'=IF(AND(ISNUMBER(B{rr}),ISNUMBER(C{rr})),IF(ABS(B{rr}-C{rr})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)"),IF(B{rr}=C{rr},"MATCH","DIFFERENT (inputs changed since generation)"))', note)
    top = 13
    lim = I("lv_limit")
    pyc = {c.id: c for c in checks}.get("fault_level_vs_limit")
    d = f"CALCULATIONS!{cells['ik_d']}"
    refs = status_block(res, top, "Statuses: LV design level against the practical limit", [I("lv_limit")] + [f"CALCULATIONS!{cells['ik_d']}"], f'IF({d}>{lim}+0.000000001,"WARNING","PASS")',
                        inp.status_range(["utility_mva", "utility_xr", "tx_kva", "tx_uk", "tx_xr", "gen_kva", "gen_xd", "gen_xr", "gen_pf", "c_lv", "c_mv", "lv_v", "mv_kv", "gen_n", "parallel", "lv_limit"]))
    _put(res, f"C{top+1+1}", pyc.calculation_result if pyc else None)
    _put(res, f"C{top+5}", pyc.status.value if pyc else None)
    _put(res, f"D{top+5}", f'=IF(B{top+5}=C{top+5},"MATCH","DIFFERENT (inputs changed since generation)")', note)
    # equipment ratings
    er = top + 8
    _put(res, f"A{er-1}", "Equipment short-circuit ratings against the fault level", title, border=None)
    _hdr(res, er, ["Item", "Required (kA)", "Rating entered (kA)", "Calculation result", "Overall design status"], [50, 24, 24, 22, 44])
    agg_all = agg_status(inp.status_range())
    eq = [("BD-TX-A busduct withstand", "ik_d", "rating_BD-TX-A"), ("LV-MSB-A switchboard", "ik_d", "rating_LV-MSB-A"), ("MV-SWG-A switchgear", "ik_mv", "rating_MV-SWG-A")]
    for dv in (cfg.distribution or {}).get("protection_devices") or []:
        eq.append((f"{dv['tag']} breaking capacity", "ik_mv" if dv["bus"] == "MV" else "ik_d", f"break_{dv['tag']}"))
    for k, (label, req, rk) in enumerate(eq):
        rr = er + 1 + k
        _put(res, f"A{rr}", label)
        _put(res, f"B{rr}", f"=CALCULATIONS!{cells[req]}", base, FILL_RESULT, "0.000")
        _put(res, f"C{rr}", f'=IF({I(rk)}="","",{I(rk)})', base, None, "0.0")
        _put(res, f"D{rr}", f'=IF(OR(NOT(ISNUMBER(B{rr})),C{rr}=""),"NOT VERIFIED",IF(C{rr}>=B{rr},"PASS","FAIL"))', bold)
        _put(res, f"E{rr}", f'=IF(D{rr}="FAIL","FAIL",IF(AND(D{rr}="PASS",{agg_all}="VERIFIED_OR_ACCEPTED"),"PASS","NOT VERIFIED"))', bold)
    colour_statuses(res, f"D{er+1}:E{er+len(eq)}")
    readme(ws0, "Short-circuit levels: " + cfg.project.name, SC_FILE, cfg, stamp,
           "Maximum three-phase fault level at the MV and LV busbars by the IEC 60909 method: utility, one transformer, generators, a transformer-limited upper bound, peak and thermal values, and a comparison "
           "with the short-circuit ratings and breaking capacities you enter.",
           "Utility fault level and X/R, transformer X/R and generator reactance are pending data: the cases that need them read NOT CALCULATED. Motor contribution, impedance of cables and busduct, "
           "minimum fault current, arc-flash and discrimination are not included. The transformer-limited bound needs only the transformer rating and impedance.", SHEETS)
    revision_sheet(rev, cfg, stamp, SC_FILE)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def build_cable_workbook(cfg: ProjectConfig, checks: list[CheckResult], path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "cable sizing")
    ws0 = wb.active
    ws0.title = "README"
    iw, calc, res, rev = (wb.create_sheet(n) for n in SHEETS[1:])
    for w in wb.worksheets:
        _page(w)
    est = estimate_loads(cfg)
    dist = assess_distribution(cfg, est, size_power_system(cfg, est))
    sc = assess_short_circuit(cfg)
    inp = Inputs(iw, "Cable sizing: inputs", "Design currents come from the load estimate and sizing results (preliminary). Cable data, tabulated ratings and the fault current accept your values.")
    st = lambda pid: ds.data_status(cfg.get(pid))
    P = lambda pid: cfg.get(pid)
    inp.add("temp", "Conductor temperature for resistance", "degC", cfg.value("cable_data.conductor_operating_temperature"), st("cable_data.conductor_operating_temperature"), P("cable_data.conductor_operating_temperature").source, "MANUFACTURER")
    inp.add("vd_limit", "Voltage drop limit", "%", cfg.value("design_criteria.voltage_drop_limit_pct"), st("design_criteria.voltage_drop_limit_pct"), P("design_criteria.voltage_drop_limit_pct").source, "SITE_DATA")
    inp.add("load_limit", "Maximum cable loading", "%", cfg.value("design_criteria.cable_max_loading"), st("design_criteria.cable_max_loading"), P("design_criteria.cable_max_loading").source, "SITE_DATA")
    inp.add("k_factor", "Cable short-circuit constant k", "A.s^0.5/mm2", cfg.value("short_circuit.cable_short_circuit_k_factor"), st("short_circuit.cable_short_circuit_k_factor"), P("short_circuit.cable_short_circuit_k_factor").source, "MANUFACTURER", "Reference value for copper XLPE.")
    inp.add("clear_t", "Fault clearing time", "s", cfg.value("short_circuit.assumed_clearing_time_s"), st("short_circuit.assumed_clearing_time_s"), P("short_circuit.assumed_clearing_time_s").source, "MANUFACTURER")
    d = sc.design_lv
    inp.add("ith_lv", "LV thermal-equivalent fault current (from 10_SHORT_CIRCUIT)", "kA", None if d is None else d.ith_ka, ds.PRELIMINARY_ASSUMPTION, "Pending: from the short-circuit study", "SITE_DATA", "Blank until the short-circuit inputs are supplied.")
    inp.add("ith_mv", "MV thermal-equivalent fault current (from 10_SHORT_CIRCUIT)", "kA", None if sc.mv_case is None else sc.mv_case.ith_ka, ds.PRELIMINARY_ASSUMPTION, "Pending: from the short-circuit study", "SITE_DATA")
    feeders = {f["tag"]: f for f in (cfg.distribution or {}).get("feeders") or []}
    for c in dist.cables:
        f = feeders[c.tag]
        is_mv = str(f["voltage_ref"]).startswith("electrical_system.mv")
        x_pid = f["reactance_ref"]
        der = f.get("derating") or {}
        inp.add(f"{c.tag}.I", f"{c.tag}: design current (total)", "A", c.design_current_a, ds.PRELIMINARY_ASSUMPTION, f"Load model and sizing, basis {c.basis}", "SITE_DATA")
        inp.add(f"{c.tag}.V", f"{c.tag}: voltage", "V", c.voltage_v, ds.PRELIMINARY_ASSUMPTION, "Master configuration", "SITE_DATA")
        inp.add(f"{c.tag}.n", f"{c.tag}: parallel runs", "-", f["parallel_runs"], ds.UNVERIFIED_PLACEHOLDER, "Illustrative distribution schedule", "MANUFACTURER")
        inp.add(f"{c.tag}.L", f"{c.tag}: length", "m", f["length_m"], ds.UNVERIFIED_PLACEHOLDER, "Illustrative distribution schedule", "SITE_DATA")
        inp.add(f"{c.tag}.A", f"{c.tag}: conductor cross-section", "mm2", f["cross_section_mm2"], ds.UNVERIFIED_PLACEHOLDER, "Illustrative distribution schedule", "MANUFACTURER")
        inp.add(f"{c.tag}.rho", f"{c.tag}: resistivity at 20 degC ({f['conductor']})", "ohm.mm2/m", {"copper": 0.017241, "aluminium": 0.028264}[f["conductor"].lower()], ds.REFERENCE_DATA, "Reference constant (verify against the standard in use)", "MANUFACTURER")
        inp.add(f"{c.tag}.alpha", f"{c.tag}: temperature coefficient", "1/degC", {"copper": 0.00393, "aluminium": 0.00403}[f["conductor"].lower()], ds.REFERENCE_DATA, "Reference constant", "MANUFACTURER")
        inp.add(f"{c.tag}.x", f"{c.tag}: reactance", "ohm/km", cfg.value(x_pid), st(x_pid), P(x_pid).source, "MANUFACTURER", "Depends on the cable and its layout.")
        inp.add(f"{c.tag}.pf", f"{c.tag}: load power factor", "-", f["power_factor"], ds.UNVERIFIED_PLACEHOLDER, "Illustrative distribution schedule", "SITE_DATA")
        for fk, fl in (("grouping", "grouping (parallel runs and neighbouring circuits)"), ("ambient", "ambient temperature"), ("installation", "installation method and layout")):
            inp.add(f"{c.tag}.k_{fk}", f"{c.tag}: derating factor, {fl}", "-", der.get(fk, 1.0), ds.UNVERIFIED_PLACEHOLDER,
                    "PLACEHOLDER 1.00 (no derating applied): NOT a verified value. Take it from the cable table or data sheet for the installation method.", "MANUFACTURER",
                    "A 1.00 here is never evidence of anything: with several parallel runs the real grouping factor is below 1.00." if fk == "grouping" else "")
        inp.add(f"{c.tag}.share", f"{c.tag}: allowance for unequal current sharing between parallel runs", "%", None, ds.UNVERIFIED_PLACEHOLDER,
                "NOT SUPPLIED: no allowance is included, so the required rating is a minimum", "MANUFACTURER", "Blank = no allowance. Depends on equal lengths, matched cross-section and the layout of the runs.")
        inp.add(f"{c.tag}.tab", f"{c.tag}: tabulated current rating per run", "A", f.get("tabulated_rating_a"), ds.UNVERIFIED_PLACEHOLDER, "Pending: cable standard table or data sheet for the installation method", "MANUFACTURER",
                "Never assumed. Without it the cable cannot be judged for current rating.")
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Cable sizing: calculations", title
    calc["A2"].value, calc["A2"].font = "R = rho20 (1 + alpha (T - 20)) / A. Voltage drop = sqrt3 x I per run x L x (R cos phi + X sin phi). Current rating needs a tabulated value that is never assumed.", note
    cols = ["Feeder", "Per-run current (A)", "Required tabulated rating per run (A)", "R (ohm/m)", "Voltage drop (V)", "Voltage drop (%)", "Voltage drop result", "Loading vs table (%)", "Ampacity result",
            "Min. section for the fault (mm2)", "Thermal withstand result", "Overall design status"]
    _hdr(calc, 4, cols, [18, 14, 20, 14, 14, 14, 16, 14, 16, 18, 18, 18])
    agg_all = agg_status(inp.status_range())
    pyd = {c.tag: c for c in dist.cables}
    for k, c in enumerate(dist.cables):
        r = 5 + k
        t = c.tag
        n, L, A, V = I(f"{t}.n"), I(f"{t}.L"), I(f"{t}.A"), I(f"{t}.V")
        is_mv = str(feeders[t]["voltage_ref"]).startswith("electrical_system.mv")
        ith = I("ith_mv") if is_mv else I("ith_lv")
        _put(calc, f"A{r}", t, bold)
        _put(calc, f"B{r}", f"={I(f'{t}.I')}/{n}", base, FILL_RESULT, "#,##0.0")
        kk = f"({I(f'{t}.k_grouping')}*{I(f'{t}.k_ambient')}*{I(f'{t}.k_installation')})"
        sh = f"(1+N({I(f'{t}.share')})/100)"
        _put(calc, f"C{r}", f"={I(f'{t}.I')}/({n}*{kk})*{sh}", base, FILL_RESULT, "#,##0.0")
        _put(calc, f"D{r}", f"={I(f'{t}.rho')}*(1+{I(f'{t}.alpha')}*({I('temp')}-20))/{A}", base, FILL_RESULT, "0.000000000")
        _put(calc, f"E{r}", f"=SQRT(3)*B{r}*{L}*(D{r}*{I(f'{t}.pf')}+{I(f'{t}.x')}/1000*SQRT(1-{I(f'{t}.pf')}^2))", base, FILL_RESULT, "0.000")
        _put(calc, f"F{r}", f"=E{r}/{V}*100", base, FILL_RESULT, "0.000")
        _put(calc, f"G{r}", f'=IF(F{r}>{I("vd_limit")}+0.000000001,"FAIL","PASS")', bold)
        _put(calc, f"H{r}", f'=IF({I(f"{t}.tab")}="","",B{r}*{sh}/({I(f"{t}.tab")}*{kk})*100)', base, FILL_RESULT, "0.0")
        _put(calc, f"I{r}", f'=IF(H{r}="","NOT VERIFIED",IF(H{r}>{I("load_limit")}+0.000000001,"FAIL","PASS"))', bold)
        _put(calc, f"J{r}", f'=IF({ith}="","NOT CALCULATED",{ith}*1000/{n}*SQRT({I("clear_t")})/{I("k_factor")})', base, FILL_RESULT, "0.0")
        _put(calc, f"K{r}", f'=IF(J{r}="NOT CALCULATED","NOT VERIFIED",IF({A}>=J{r},"PASS","FAIL"))', bold)
        _put(calc, f"L{r}", f'=IF(OR(G{r}="FAIL",I{r}="FAIL",K{r}="FAIL"),"FAIL",IF(AND(G{r}="PASS",I{r}="PASS",K{r}="PASS",{agg_all}="VERIFIED_OR_ACCEPTED"),"PASS","NOT VERIFIED"))', bold)
    colour_statuses(calc, f"G5:G{4+len(dist.cables)}")
    colour_statuses(calc, f"I5:I{4+len(dist.cables)}")
    colour_statuses(calc, f"K5:L{4+len(dist.cables)}")
    calc.freeze_panes = "B5"
    res["A1"].value, res["A1"].font = "Cable sizing: results and statuses", title
    res["A2"].value, res["A2"].font = "The calculation result (voltage drop, current rating, thermal withstand) is separate from the overall design status.", note
    _hdr(res, 4, ["Feeder", "Voltage drop (%)", "Python (%)", "Agreement", "Required rating per run (A)", "Python (A)", "Agreement", "Calculation status", "Input-data status", "Overall design status"], [18, 16, 14, 16, 22, 14, 16, 20, 26, 20])
    for k, c in enumerate(dist.cables):
        r = 5 + k
        _put(res, f"A{r}", c.tag, bold)
        _put(res, f"B{r}", f"=CALCULATIONS!F{r}", bold, FILL_RESULT, "0.000")
        _put(res, f"C{r}", c.voltage_drop_pct, base, None, "0.000")
        _put(res, f"D{r}", f'=IF(ABS(B{r}-C{r})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
        _put(res, f"E{r}", f"=CALCULATIONS!C{r}", bold, FILL_RESULT, "#,##0.0")
        _put(res, f"F{r}", c.required_rating_a, base, None, "#,##0.0")
        _put(res, f"G{r}", f'=IF(ABS(E{r}-F{r})<=0.0001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
        _put(res, f"H{r}", f'=IF(COUNT(CALCULATIONS!F{r},CALCULATIONS!C{r})<2,"NOT CALCULATED",IF(CALCULATIONS!J{r}="NOT CALCULATED","PARTIAL","CALCULATED"))', bold)
        _put(res, f"I{r}", f"={agg_all}", bold)
        _put(res, f"J{r}", f"=CALCULATIONS!L{r}", bold)
    colour_statuses(res, f"H5:J{4+len(dist.cables)}")
    readme(ws0, "Cable sizing: " + cfg.project.name, CABLE_FILE, cfg, stamp,
           "Design current per run, required tabulated rating after derating, three-phase voltage drop from conductor resistance and reactance, and the adiabatic thermal withstand against a fault current.",
           "Tabulated ratings are never assumed: with none entered, the current rating reads NOT VERIFIED. The three derating factors (grouping, ambient, installation) are 1.00 placeholders, not verified values, and no allowance for unequal sharing between parallel runs is included, so every required rating is a minimum until real values are entered. Reactance is a placeholder and depends on the cable layout. Cable and busduct impedance does not "
           "feed back into the fault level. Path B is assumed identical to path A.", SHEETS)
    revision_sheet(rev, cfg, stamp, CABLE_FILE)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
