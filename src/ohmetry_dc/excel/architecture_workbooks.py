"""01_MASTER_DESIGN_BASIS, 03_POWER_ARCHITECTURE, 09_VOLTAGE_DROP and 20_MASTER_EQUIPMENT_SCHEDULE."""
from __future__ import annotations

from pathlib import Path

import yaml
from openpyxl.worksheet.datavalidation import DataValidation

from ohmetry_dc.calculations import assess_distribution, estimate_loads, size_power_system
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models.architecture import ARCHITECTURE_FUNCTIONS
from ohmetry_dc.models import data_status as ds
from ohmetry_dc.validation import CheckResult

from .common import (attested, FILL_INPUT, FILL_RESULT, Inputs, _header, _page, _put, agg_status, base, blue, bold, colour_statuses, new_workbook, note, readme, revision_sheet, title)
from .other_workbooks import _P, _save
from openpyxl.styles import Protection

FILES = {"basis": "01_MASTER_DESIGN_BASIS.xlsx", "arch": "03_POWER_ARCHITECTURE.xlsx", "vdrop": "09_VOLTAGE_DROP.xlsx", "equip": "20_MASTER_EQUIPMENT_SCHEDULE.xlsx"}
NC = '"NOT CALCULATED"'


def _sheets(wb, names):
    ws0 = wb.active
    ws0.title = names[0]
    out = [ws0] + [wb.create_sheet(n) for n in names[1:]]
    for w in out:
        _page(w)
    return out


def _edit(ws, ref, value=None, fmt="General"):
    c = _put(ws, ref, value, blue, FILL_INPUT, fmt)
    c.protection = Protection(locked=False)
    return c


# ------------------------------------------------------------------ 01
def build_basis_workbook(cfg: ProjectConfig, checks: list[CheckResult], path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "master design basis")
    readme_ws, par, crit, asm, std, chk, appr = _sheets(wb, ["README", "PARAMETERS", "DESIGN_CRITERIA", "ASSUMPTIONS_EXCLUSIONS", "STANDARDS", "CHECK_STATUS", "REVISION_APPROVAL"])
    # PARAMETERS: every master parameter with its data status
    par["A1"].value, par["A1"].font = "Master design basis: parameters (read from config/project_config.yaml at generation)", title
    par["A2"].value, par["A2"].font = "Changing a cell here does not change the engine. Use the master configuration or the data import to change a value.", note
    _header(par, 4, ["Parameter", "Name", "Value", "Unit", "Input data status", "Source", "Revision", "Original value (if overridden)"], [38, 42, 18, 12, 26, 60, 10, 22])
    for i, (pid, p) in enumerate(cfg.parameters.items()):
        r = 5 + i
        _put(par, f"A{r}", pid)
        _put(par, f"B{r}", p.name, align=None)
        _put(par, f"C{r}", "" if p.value is None else p.value)
        _put(par, f"D{r}", p.unit)
        _put(par, f"E{r}", ds.data_status(p))
        _put(par, f"F{r}", p.source)
        _put(par, f"G{r}", p.revision)
        _put(par, f"H{r}", "" if p.original_value is None else p.original_value)
    last = 4 + len(cfg.parameters)
    colour_statuses(par, f"E5:E{last}")
    par.auto_filter.ref = f"A4:H{last}"
    par.freeze_panes = "A5"
    # DESIGN_CRITERIA with live checks
    crit["A1"].value, crit["A1"].font = "Design criteria and basis checks", title
    _header(crit, 4, ["Item", "Value", "Unit", "Status"], [58, 20, 10, 30])
    g = lambda pid: cfg.value(pid)
    rows = [("IT critical load", g("general.it_critical_load"), "kW"), ("Target PUE", g("general.target_pue"), "-"), ("Initial facility estimate", g("general.estimated_facility_demand"), "kW"),
            ("LV line voltage", g("electrical_system.lv_line_voltage"), "V"), ("LV phase voltage", g("electrical_system.lv_phase_voltage"), "V"), ("Frequency", g("electrical_system.frequency"), "Hz"),
            ("Transformer loading target / maximum", f"{g('design_criteria.transformer_target_loading')} / {g('design_criteria.transformer_max_loading')}", "%"),
            ("UPS loading target / maximum", f"{g('design_criteria.ups_target_loading')} / {g('design_criteria.ups_max_loading')}", "%"),
            ("Generator loading target / maximum", f"{g('design_criteria.generator_target_loading')} / {g('design_criteria.generator_max_loading')}", "%"),
            ("Redundancy: architecture", g("redundancy.architecture"), ""), ("Redundancy: UPS topology", g("redundancy.ups_topology"), ""), ("Redundancy: generators", g("redundancy.generator_concept"), ""),
            ("Design ambient temperature", g("environment.design_ambient_temperature"), "degC"), ("Site altitude", g("environment.site_altitude"), "m")]
    for i, (a, b, c) in enumerate(rows):
        r = 5 + i
        _put(crit, f"A{r}", a)
        _put(crit, f"B{r}", b)
        _put(crit, f"C{r}", c)
    r0 = 5 + len(rows) + 1
    _put(crit, f"A{r0}", "Live arithmetic checks", title, border=None)
    chk_rows = [("Initial estimate = IT load x target PUE (kW)", "=B5*B6", "kW"), ("Difference from the stated initial estimate (%)", f"=(B{r0+1}-B7)/B7*100", "%"),
                ("LV line / phase voltage (expect sqrt 3 = 1.732)", "=B8/B9", "-"), ("Relation check", f'=IF(ABS(B{r0+3}-SQRT(3))<0.02,"PASS","WARNING")', "")]
    for i, (a, f, u) in enumerate(chk_rows):
        r = r0 + 1 + i
        _put(crit, f"A{r}", a)
        _put(crit, f"B{r}", f, bold, FILL_RESULT, "0.000")
        _put(crit, f"C{r}", u)
    colour_statuses(crit, f"B{r0+4}:B{r0+4}")
    # ASSUMPTIONS_EXCLUSIONS
    asm["A1"].value, asm["A1"].font = "Assumptions and exclusions", title
    _header(asm, 3, ["Id", "Assumption", "Value", "Unit", "Confirmation"], [38, 46, 18, 10, 22])
    r = 4
    for pid, p in cfg.parameters.items():
        if p.status.value == "ASSUMPTION":
            _put(asm, f"A{r}", pid)
            _put(asm, f"B{r}", p.name, align=None)
            _put(asm, f"C{r}", p.value)
            _put(asm, f"D{r}", p.unit)
            _put(asm, f"E{r}", "UNCONFIRMED")
            r += 1
    r += 1
    _put(asm, f"A{r}", "Exclusions", title, border=None)
    for i, t in enumerate(["No manufacturer data is used unless imported and reviewed.", "No site survey, utility study or geotechnical data is used.", "No protection coordination, arc-flash or harmonic study.",
                           "No lightning, fire or structural design.", "No cooling design beyond the load figures.", "No local code or utility requirement is stated. These must be added by the project team.",
                           "Not construction-ready. Not an approved design."]):
        _put(asm, f"A{r+1+i}", t, base, border=None)
    # STANDARDS
    std["A1"].value, std["A1"].font = "Standards register (names only; edition and applicability NOT_VERIFIED)", title
    _header(std, 3, ["Id", "Reference", "Title", "Edition", "Applicability"], [20, 18, 70, 12, 20])
    reg_path = Path(cfg.base_dir) / "standards_register.yaml"
    if not reg_path.exists():                       # a configuration copied elsewhere: fall back to the shipped register
        reg_path = Path(__file__).resolve().parents[3] / "config" / "standards_register.yaml"
    reg = yaml.safe_load(reg_path.read_text()) if reg_path.exists() else {"standards": []}
    for i, s in enumerate(reg["standards"]):
        r = 4 + i
        for col, key in zip("ABCDE", ("id", "reference", "title", "edition", "applicability_status")):
            _put(std, f"{col}{r}", "" if s[key] is None else s[key])
    # CHECK_STATUS
    chk["A1"].value, chk["A1"].font = "Engineering checks at generation: four statuses", title
    _header(chk, 3, ["Check", "Calculation status", "Calculation result", "Input data status", "Verification", "Overall design status"], [52, 20, 20, 28, 18, 20])
    for i, c in enumerate(checks):
        r = 4 + i
        for col, v in zip("ABCDEF", (c.title, c.calculation_status, c.calculation_result, c.input_status, c.verification_status, c.status.value)):
            _put(chk, f"{col}{r}", v)
    colour_statuses(chk, f"F4:F{3+len(checks)}")
    # REVISION_APPROVAL
    appr["A1"].value, appr["A1"].font = "Revision and approval", title
    _header(appr, 3, ["Field", "Value"], [34, 60])
    for i, (a, b) in enumerate([("Project", cfg.project.name), ("Code", cfg.project.code), ("Revision", cfg.project.revision), ("Release state", cfg.project.release_state.value)]):
        _put(appr, f"A{4+i}", a)
        _put(appr, f"B{4+i}", b)
    for i, a in enumerate(["Prepared by", "Prepared date", "Independent reviewer", "Review date", "Approved by", "Approval date"]):
        _put(appr, f"A{9+i}", a)
        _edit(appr, f"B{9+i}", None)
    _put(appr, "A16", "Approved for educational distribution", bold)
    _put(appr, "B16", '=IF(AND(B10<>"",B12<>"",B13<>"",B14<>""),"RECORDED (not verified by this workbook)","NO")', bold)
    readme(readme_ws, "Master design basis: " + cfg.project.name, FILES["basis"], cfg, stamp,
           "The single readable record of the design basis: every parameter with its data status and source, the design criteria with live arithmetic checks, assumptions and exclusions, the standards register links, "
           "the check statuses, and revision and approval fields.",
           "A summary of the master configuration at generation. Editing it does not change the engine. Approval fields are empty: a name in a cell is a record, not a verification.", ["README", "PARAMETERS", "DESIGN_CRITERIA", "ASSUMPTIONS_EXCLUSIONS", "STANDARDS", "CHECK_STATUS", "REVISION_APPROVAL"])
    return _save(wb, path)


# ------------------------------------------------------------------ 03
def build_architecture_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "power architecture")
    ws0, iw, calc, res, fn, rev = _sheets(wb, ["README", "INPUTS", "CALCULATIONS", "RESULTS", "FUNCTIONS", "REVISION_LOG"])
    est = estimate_loads(cfg)
    sizing = size_power_system(cfg, est)
    inp = Inputs(iw, "Power architecture: inputs", "Quantities and loads from the master configuration and load estimate (preliminary). Replace with your design.")
    P = lambda pid: _P(cfg, pid)
    tx_n = sizing.transformer.units_per_path
    inp.add("paths", "Independent power paths", "-", cfg.value("redundancy.power_paths"), *P("redundancy.power_paths")[1:], "SITE_DATA")
    inp.add("tx_n", "Transformers per path", "-", tx_n, ds.PRELIMINARY_ASSUMPTION, "Equipment quantity divided by paths", "MANUFACTURER")
    inp.add("ups_n", "UPS per path", "-", sizing.ups_kw.units_per_path, ds.PRELIMINARY_ASSUMPTION, "Equipment quantity divided by paths", "MANUFACTURER")
    inp.add("gen_n", "Generators per path", "-", sizing.generator.units_per_path, ds.PRELIMINARY_ASSUMPTION, "Master configuration", "MANUFACTURER")
    inp.add("tx_kva", "Transformer derated rating (each)", "kVA", sizing.transformer.derated_each, ds.UNVERIFIED_PLACEHOLDER, "Rating x derating factors (04_TRANSFORMER_SIZING)", "MANUFACTURER")
    inp.add("ups_kw", "UPS derated rating (each)", "kW", sizing.ups_kw.derated_each, ds.UNVERIFIED_PLACEHOLDER, "Rating x derating factors (06_UPS_SIZING)", "MANUFACTURER")
    inp.add("gen_kva", "Generator derated rating (each)", "kVA", sizing.generator.derated_each, ds.UNVERIFIED_PLACEHOLDER, "Rating x derating factors (05_GENERATOR_SIZING)", "MANUFACTURER")
    f = 1 + est.growth_pct / 100
    tx_tot = next(s for s in sizing.transformer.scenarios if s.id == "TX-PATH-OUT").load / f
    gen_tot = next(s for s in sizing.generator.scenarios if s.id == "GEN-PATH-OUT").load / f
    ups_tot = next(s for s in sizing.ups_kw.scenarios if s.id == "UPS-PATH-OUT").load / f
    inp.add("tx_load", "Whole facility load (kVA)", "kVA", tx_tot, ds.PRELIMINARY_ASSUMPTION, "Preliminary: from the load estimate", "SITE_DATA")
    inp.add("ups_load", "Whole critical load (kW)", "kW", ups_tot, ds.PRELIMINARY_ASSUMPTION, "Preliminary: from the load estimate", "SITE_DATA")
    inp.add("gen_load", "Whole load on the generators (kVA)", "kVA", gen_tot, ds.PRELIMINARY_ASSUMPTION, "Preliminary: from the load estimate", "SITE_DATA")
    inp.add("frac_a", "Share of the load on path A", "-", est.path_a.kw / est.facility_kw, ds.PRELIMINARY_ASSUMPTION, "Load estimate A/B allocation", "SITE_DATA")
    pol = sizing.transformer.policy
    inp.add("limit", "Maximum loading (all equipment)", "%", min(sizing.transformer.policy.limit_pct, sizing.ups_kw.policy.limit_pct, sizing.generator.policy.limit_pct), ds.PROJECT_INPUT, "Project owner decision", "SITE_DATA", "The lowest of the three limits.")
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Architecture: operating modes and load transfer", title
    calc["A2"].value, calc["A2"].font = "Each scenario shows the share of the load on one path and the units available there. Loading is against the derated capacity. Preliminary.", note
    _header(calc, 4, ["Scenario", "Load share on the path", "TX units", "UPS units", "Gen units", "Transformer loading %", "UPS loading %", "Generator loading %", "Worst %", "Result", "Judged", "UPS load share", "UPS units"],
            [48, 14, 9, 9, 9, 16, 14, 16, 10, 14, 10, 14, 10])
    nt, nu, ng = I("tx_n"), I("ups_n"), I("gen_n")
    ns = f"MAX({I('frac_a')},1-{I('frac_a')})"
    sc = [("Normal operation (the more loaded path)", f"MAX({I('frac_a')},1-{I('frac_a')})", nt, nu, ng, 1),
          ("Path A out: path B carries everything", "1", nt, nu, ng, 1), ("Path B out: path A carries everything", "1", nt, nu, ng, 1),
          ("One UPS out for maintenance (with one UPS per path the critical load moves to the other path's UPS)", f"MAX({I('frac_a')},1-{I('frac_a')})", nt, f"IF({nu}>=2,{nu}-1,{nu})", ng, 1),
          ("One generator out (N+1), normal load share", f"MAX({I('frac_a')},1-{I('frac_a')})", nt, nu, f"{ng}-1", 1),
          ("Path out and one generator out (beyond N+1: informational)", "1", nt, nu, f"{ng}-1", 0)]
    for k, (name, share, a, b, c, judged) in enumerate(sc):
        r = 5 + k
        _put(calc, f"A{r}", name)
        _put(calc, f"B{r}", f"={share}", base, None, "0.000")
        _put(calc, f"C{r}", f"={a}")
        _put(calc, f"D{r}", f"={b}")
        _put(calc, f"E{r}", f"={c}")
        _put(calc, f"F{r}", f'=IF(C{r}<=0,"NO CAPACITY",{I("tx_load")}*B{r}/(C{r}*{I("tx_kva")})*100)', base, FILL_RESULT, "0.0")
        ups_share = f"IF({nu}<2,1,B{r})" if k == 3 else f"B{r}"
        _put(calc, f"L{r}", f"={ups_share}", base, None, "0.000")
        _put(calc, f"M{r}", f"=D{r}")
        _put(calc, f"G{r}", f'=IF(M{r}<=0,"NO CAPACITY",{I("ups_load")}*L{r}/(M{r}*{I("ups_kw")})*100)', base, FILL_RESULT, "0.0")
        _put(calc, f"H{r}", f'=IF(E{r}<=0,"NO CAPACITY",{I("gen_load")}*B{r}/(E{r}*{I("gen_kva")})*100)', base, FILL_RESULT, "0.0")
        _put(calc, f"I{r}", f'=IF(COUNT(F{r}:H{r})<3,"NO CAPACITY",MAX(F{r}:H{r}))', bold, FILL_RESULT, "0.0")
        _put(calc, f"J{r}", f'=IF(K{r}=0,"INFORMATIONAL",IF(I{r}="NO CAPACITY","FAIL",IF(I{r}>{I("limit")}+0.000000001,"FAIL","PASS")))', bold)
        _put(calc, f"K{r}", judged)
    colour_statuses(calc, "J5:J10")
    _put(calc, "A12", "Redundancy checks", title, border=None)
    rc = [("Units divide evenly between paths (always true for integer inputs; confirm the design)", f'=IF(AND({nt}=INT({nt}),{nu}=INT({nu}),{ng}=INT({ng})),"PASS","FAIL")'),
          ("At least two independent paths", f'=IF({I("paths")}>=2,"PASS","FAIL")'),
          ("UPS: each path can carry the whole critical load alone (2N)", f'=IF({I("ups_load")}<={nu}*{I("ups_kw")},"PASS","FAIL")'),
          ("Transformer: each path can carry the whole facility load alone", f'=IF({I("tx_load")}<={nt}*{I("tx_kva")},"PASS","FAIL")'),
          ("Generators: N+1 (a spare unit in each path)", f'=IF({ng}>=2,"PASS","FAIL")'),
          ("Generators: the whole load is carried with one unit out", f'=IF({I("gen_load")}<=({ng}-1)*{I("gen_kva")},"PASS","FAIL")')]
    for k, (name, f_) in enumerate(rc):
        _put(calc, f"A{13+k}", name)
        _put(calc, f"B{13+k}", f_, bold)
    colour_statuses(calc, "B13:B18")
    _put(calc, "A20", "Equipment dependency summary", title, border=None)
    _header(calc, 21, ["Equipment", "Fed from", "Feeds", "Lost if this path fails"], [48, 30, 40, 30])
    for k, (a, b, c, d) in enumerate([("MV switchgear (per path)", "Utility", "Transformer", "Path"), ("Transformer", "MV switchgear", "LV main switchboard", "Path"),
                                      ("LV main switchboard", "Transformer or generators (transfer)", "UPS input, mechanical plant, essential loads", "Path"), ("Generators (N+1)", "Fuel", "LV main switchboard on utility failure", "One unit"),
                                      ("UPS", "LV main switchboard", "IT distribution of that path", "Path"), ("Battery", "UPS DC bus", "UPS (autonomy)", "Autonomy on that path")]):
        for col, v in zip("ABCD", (a, b, c, d)):
            _put(calc, f"{col}{22+k}", v)
    res["A1"].value, res["A1"].font = "Power architecture: results", title
    _header(res, 3, ["Result", "Value", "Python (04/05/06 engine)", "Agreement"], [58, 22, 26, 18])
    py = [("Path-out transformer loading (%)", "=CALCULATIONS!F6", next(s for s in sizing.transformer.scenarios if s.id == "TX-PATH-OUT").loading * 100),
          ("Path-out UPS loading, kW (%)", "=CALCULATIONS!G6", next(s for s in sizing.ups_kw.scenarios if s.id == "UPS-PATH-OUT").loading * 100),
          ("Path-out generator loading, kVA (%)", "=CALCULATIONS!H6", next(s for s in sizing.generator.scenarios if s.id == "GEN-PATH-OUT").loading * 100)]
    for k, (a, f_, pv) in enumerate(py):
        r = 4 + k
        _put(res, f"A{r}", a)
        _put(res, f"B{r}", f_, bold, FILL_RESULT, "0.00")
        _put(res, f"C{r}", pv, base, None, "0.00")
        _put(res, f"D{r}", f'=IF(ABS(B{r}-C{r})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
    fn["A1"].value, fn["A1"].font = "Architecture functions shown on the single-line diagram (concept only)", title
    fn["A2"].value, fn["A2"].font = "None of these is designed. They are shown so a reviewer can see what is missing. Utility A/B independence is NOT claimed.", note
    _header(fn, 4, ["Ref", "Function", "Drawing tags", "Shown as", "Status", "Needed before it can be designed"], [10, 44, 34, 44, 34, 90])
    for k, a_ in enumerate(ARCHITECTURE_FUNCTIONS):
        for col, v in zip("ABCDEF", (a_.id, a_.function, a_.drawing_tags, a_.shown_as, a_.status, a_.needed)):
            _put(fn, f"{col}{5 + k}", v)
    agg = agg_status(inp.status_range())
    _put(res, "A8", "Scenario results (judged scenarios)")
    _put(res, "B8", '=IF(COUNTIF(CALCULATIONS!J5:J10,"FAIL")>0,"FAIL","PASS")', bold)
    _put(res, "A9", "Input-data status (worst input)")
    _put(res, "B9", f"={agg}", bold)
    _put(res, "A10", "OVERALL DESIGN STATUS", bold)
    _put(res, "B10", '=IF(B8="FAIL","FAIL",IF(B9="VERIFIED_OR_ACCEPTED","PASS","NOT VERIFIED"))', bold)
    colour_statuses(res, "B8:B10")
    readme(ws0, "Power architecture: " + cfg.project.name, FILES["arch"], cfg, stamp,
           "Normal and maintenance operating modes, load transfer on loss of a path, a UPS or a generator, redundancy checks for the dual-path concept, and the equipment dependency summary.",
           "Loads are preliminary. Static transfer, switching sequences, generator transfer and interlocking, paralleling and synchronising, PMS and load sharing, load shedding, UPS bypass, battery isolation, protection and metering, and the transfer times are not "
           "modelled; the FUNCTIONS sheet lists them as concept symbols that are NOT designed. Independence of utility supply A and B is NOT claimed.", ["README", "INPUTS", "CALCULATIONS", "RESULTS", "FUNCTIONS", "REVISION_LOG"])
    revision_sheet(rev, cfg, stamp, FILES["arch"])
    return _save(wb, path)


# ------------------------------------------------------------------ 09
def build_voltage_drop_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "voltage drop")
    ws0, cases, rev = _sheets(wb, ["README", "CASES", "REVISION_LOG"])
    est = estimate_loads(cfg)
    dist = assess_distribution(cfg, est, size_power_system(cfg, est))
    feeders = {f["tag"]: f for f in (cfg.distribution or {}).get("feeders") or []}
    cases["A1"].value, cases["A1"].font = "Voltage drop: cases (edit the blue cells; add cases in the empty rows)", title
    cases["A2"].value, cases["A2"].font = "Three-phase: dV = sqrt3 x I x L x (R cos phi + X sin phi). Single-phase: dV = 2 x I x L x (R cos phi + X sin phi). R and X per km, I per run. Operating and starting cases use the same method with different current and power factor.", note
    heads = ["Case", "Type", "Method (3 or 1)", "Current per run (A)", "Length (m)", "R (ohm/km)", "X (ohm/km)", "Power factor", "Voltage (V)", "Limit (%)", "Voltage drop (V)", "Voltage drop (%)", "Result", "Data source / assumption (REQUIRED)"]
    _header(cases, 4, heads, [20, 12, 12, 14, 10, 12, 12, 10, 11, 9, 14, 14, 16, 60])
    temp = cfg.value("cable_data.conductor_operating_temperature")
    lim = cfg.value("design_criteria.voltage_drop_limit_pct")
    r_ = 5
    for c in dist.cables:
        f = feeders[c.tag]
        rho, alpha = {"copper": (0.017241, 0.00393), "aluminium": (0.028264, 0.00403)}[f["conductor"].lower()]
        rkm = rho * (1 + alpha * (temp - 20)) / f["cross_section_mm2"] * 1000
        vals = [c.tag, "Operating", 3, c.design_current_a / c.runs, f["length_m"], rkm, cfg.value(f["reactance_ref"]), f["power_factor"], c.voltage_v, lim,
                None, None, None, "Preliminary: illustrative cable, resistance from resistivity at the stated temperature, placeholder reactance."]
        for col, v in zip("ABCDEFGHIJKLMN", vals):
            if col in "KLM":
                continue
            _edit(cases, f"{col}{r_}", v, "General") if col not in "AB" else _put(cases, f"{col}{r_}", v)
        r_ += 1
    for k in range(4):                                 # empty rows, including starting cases
        _edit(cases, f"A{r_}", f"Case {k+1}")
        _edit(cases, f"B{r_}", "Starting" if k < 2 else "Operating")
        for col in "CDEFGHIJN":
            _edit(cases, f"{col}{r_}", 3 if col == "C" else None)
        r_ += 1
    last = r_ - 1
    for r in range(5, last + 1):
        need = f"COUNT(C{r}:J{r})<8"
        _put(cases, f"K{r}", f'=IF({need},{NC},IF(C{r}=1,2,SQRT(3))*D{r}*E{r}*(F{r}/1000*H{r}+G{r}/1000*SQRT(1-H{r}^2)))', base, FILL_RESULT, "0.000")
        _put(cases, f"L{r}", f'=IF(ISNUMBER(K{r}),K{r}/I{r}*100,{NC})', base, FILL_RESULT, "0.000")
        _put(cases, f"M{r}", f'=IF(NOT(ISNUMBER(L{r})),"NOT VERIFIED",IF(L{r}>J{r}+0.000000001,"FAIL",IF(N{r}="","NOT VERIFIED","PASS")))', bold)
    _put(cases, f"A{last+2}", "A case reads PASS only when it calculates within the limit AND a data source is stated. Preliminary inputs remain preliminary: PASS here means the arithmetic is within the limit.", note, border=None)
    dv = DataValidation(type="list", formula1='"1,3"', allow_blank=True)
    cases.add_data_validation(dv)
    dv.add(f"C5:C{last}")
    colour_statuses(cases, f"M5:M{last}")
    cases.freeze_panes = "B5"
    readme(ws0, "Voltage drop: " + cfg.project.name, FILES["vdrop"], cfg, stamp,
           "Voltage drop in volts and percent for operating and starting cases, three-phase and single-phase, from conductor resistance and reactance.",
           "Resistance and reactance are inputs: reactance depends on the cable and its layout. The motor starting current and power factor are your inputs. Voltage regulation of the supply and tap settings are not modelled. "
           "Prefilled operating cases come from the illustrative distribution schedule.", ["README", "CASES", "REVISION_LOG"])
    revision_sheet(rev, cfg, stamp, FILES["vdrop"])
    return _save(wb, path)


# ------------------------------------------------------------------ 20
def build_equipment_schedule(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "master equipment schedule")
    ws0, sch, rev = _sheets(wb, ["README", "SCHEDULE", "REVISION_LOG"])
    est = estimate_loads(cfg)
    sizing = size_power_system(cfg, est)
    dist = assess_distribution(cfg, est, sizing)
    V = cfg.value("electrical_system.lv_line_voltage")
    MV = cfg.value("electrical_system.mv_supply_voltage")
    g = cfg.value
    rows: list[tuple] = []     # tag, description, system, qty, duty, voltage, current A, power, fault kA
    for p in "AB":
        rows.append((f"MV-SWG-{p}", f"Path {p} MV switchgear", "MV distribution", 1, "Duty", f"{MV} kV", next((x.design_current_a for x in dist.switchgear if x.tag.startswith("MV")), None), None, None))
        rows.append((f"TX-{p}1", f"Path {p} transformer", "Transformation", 1, "Duty", f"{MV} kV / {V} V", None, f"{g('equipment.transformer_rating')} kVA", None))
        rows.append((f"BD-TX-{p}", f"Path {p} transformer busduct", "LV distribution", 1, "Duty", f"{V} V", next((x.design_current_a for x in dist.busducts), None), None, None))
        rows.append((f"LV-MSB-{p}", f"Path {p} LV main switchboard", "LV distribution", 1, "Duty", f"{V} V", next((x.design_current_a for x in dist.switchgear if x.tag.startswith("LV")), None), None, None))
        for i in range(1, int(g("equipment.generator_quantity_per_path")) + 1):
            rows.append((f"GEN-{p}{i}", f"Path {p} generator {i}", "Standby generation", 1, "Duty" if i < int(g("equipment.generator_quantity_per_path")) else "Standby (N+1)", f"{V} V", None, f"{g('equipment.generator_rating')} kVA (assumed PRP)", None))
        rows.append((f"UPS-{p}1", f"Path {p} UPS", "Critical power", 1, "Duty", f"{V} V", None, f"{g('equipment.ups_rating')} kW / {g('equipment.ups_rating_kva')} kVA", None))
        rows.append((f"BAT-{p}1", f"Path {p} battery", "Critical power", 1, "Duty", "DC", None, "Not sized: no discharge data", None))
    for d in (cfg.distribution or {}).get("protection_devices") or []:
        rows.append((d["tag"], d["description"], "Protection", 1, "Duty", f"{MV} kV" if d["bus"] == "MV" else f"{V} V", None, None, None))
    for c in dist.cables:
        rows.append((c.tag, c.description, "Cables", c.runs, "Duty", f"{c.voltage_v:g} V", c.design_current_a, None, None))
    heads = ["Equipment tag", "Description", "System", "Quantity", "Duty / standby", "Voltage", "Design current (A)", "Power", "Fault rating (kA)", "Manufacturer", "Model", "Datasheet reference", "Datasheet revision",
             "Reviewer attestation (name; organisation; date; evidence reference; scope. Self-declared, not authenticated)", "Technical status", "Procurement status", "Remarks"]
    sch["A1"].value, sch["A1"].font = "Master equipment schedule", title
    sch["A2"].value, sch["A2"].font = "Values are preliminary. Technical status: NOT VERIFIED until a manufacturer, model, datasheet and revision are entered AND a reviewer is recorded. No equipment is selected.", note
    _header(sch, 4, heads, [14, 40, 20, 9, 14, 16, 14, 30, 12, 20, 18, 22, 12, 16, 26, 18, 40])
    for i, (tag, desc, sysn, q, duty, volt, cur, pw, fk) in enumerate(rows):
        r = 5 + i
        for col, v in zip("ABCDEFGHI", (tag, desc, sysn, q, duty, volt, cur, pw, fk)):
            _put(sch, f"{col}{r}", v, base, FILL_RESULT if col == "G" and v is not None else None, "#,##0" if col == "G" else "General")
        for col in "IJKLMNPQ":
            _edit(sch, f"{col}{r}", "NOT STARTED" if col == "P" else None)
        _put(sch, f"O{r}", f'=IF(OR(J{r}="",K{r}="",L{r}="",M{r}=""),"NOT VERIFIED: no datasheet",IF(N{r}="","DATA ENTERED: REVIEW REQUIRED",IF({attested(f"N{r}")},"DATASHEET REVIEWED (attested, not authenticated)","DATA ENTERED: ATTESTATION INCOMPLETE")))', bold)
    last = 4 + len(rows)
    dv = DataValidation(type="list", formula1='"NOT STARTED,RFQ ISSUED,QUOTED,ORDERED,DELIVERED,INSTALLED"', allow_blank=True)
    sch.add_data_validation(dv)
    dv.add(f"P5:P{last}")
    sch.auto_filter.ref = f"A4:Q{last}"
    sch.freeze_panes = "C5"
    sch.conditional_formatting.add(f"O5:O{last}", __import__("openpyxl").formatting.rule.FormulaRule(formula=[f'LEFT(O5,12)="NOT VERIFIED"'], fill=__import__("openpyxl").styles.PatternFill("solid", bgColor="E4DCF2", fgColor="E4DCF2")))
    readme(ws0, "Master equipment schedule: " + cfg.project.name, FILES["equip"], cfg, stamp,
           "One row per equipment tag with description, system, quantity, duty, voltage, design current, power and fault rating, and fields for manufacturer, model, datasheet reference and revision, reviewer, technical status "
           "and procurement status.",
           "Currents and powers are preliminary. Fault ratings are blank until the short-circuit study can be calculated and a manufacturer rating is entered. A row never reads verified without a datasheet and a reviewer. "
           "Path B is listed as identical to path A.", ["README", "SCHEDULE", "REVISION_LOG"])
    revision_sheet(rev, cfg, stamp, FILES["equip"])
    return _save(wb, path)
