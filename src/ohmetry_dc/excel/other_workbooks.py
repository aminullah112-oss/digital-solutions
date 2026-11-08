"""07_BATTERY_SIZING (interface), 11_LV_SWITCHGEAR, 12_MV_SWITCHGEAR, 13_BUSDUCT_SIZING and 15_EARTHING_BONDING (screening).

Same rules as the other workbooks: retained preliminary values, a datasheet value cell that needs a source, a reviewer cell, live input status,
NOT CALCULATED where inputs are missing, and an overall PASS only when the calculation passes and every input is verified.
"""
from __future__ import annotations

from pathlib import Path

from ohmetry_dc.calculations import assess_distribution, assess_earthing, assess_short_circuit, estimate_loads, size_power_system
from ohmetry_dc.calculations.sizing import size_battery
from ohmetry_dc.calculations.earthing import MissingInputs
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds
from ohmetry_dc.validation import CheckResult

from .common import (FILL_RESULT, Inputs, _header, _page, _put, agg_status, base, bold, colour_statuses, new_workbook, note, readme, revision_sheet, status_block, title)

SHEETS = ["README", "INPUTS", "CALCULATIONS", "RESULTS", "REVISION_LOG"]
FILES = {"battery": "07_BATTERY_SIZING.xlsx", "lv": "11_LV_SWITCHGEAR.xlsx", "mv": "12_MV_SWITCHGEAR.xlsx", "busduct": "13_BUSDUCT_SIZING.xlsx", "earthing": "15_EARTHING_BONDING.xlsx"}
NC = '"NOT CALCULATED"'


def _open(cfg, stamp, heading):
    wb, _ = new_workbook(cfg, stamp, heading)
    ws0 = wb.active
    ws0.title = "README"
    iw, calc, res, rev = (wb.create_sheet(n) for n in SHEETS[1:])
    for w in wb.worksheets:
        _page(w)
    return wb, ws0, iw, calc, res, rev


def _save(wb, path):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def _P(cfg, pid):
    p = cfg.get(pid)
    return p.value, ds.data_status(p), p.source


def build_rating_workbook(cfg: ProjectConfig, kind: str, path: str | Path, stamp: str) -> Path:
    """kind: 'busduct', 'lv' or 'mv'. One row group per item: current rating, short-circuit rating, evidence, and (busduct) voltage drop."""
    heading = {"busduct": "Busduct sizing", "lv": "LV switchgear", "mv": "MV switchgear"}[kind]
    file = FILES[kind]
    wb, ws0, iw, calc, res, rev = _open(cfg, stamp, heading)
    est = estimate_loads(cfg)
    sizing = size_power_system(cfg, est)
    dist = assess_distribution(cfg, est, sizing)
    sc = assess_short_circuit(cfg)
    items = dist.busducts if kind == "busduct" else [x for x in dist.switchgear if x.tag.startswith("LV" if kind == "lv" else "MV")]
    raw = {x["tag"]: x for g in ("busducts", "switchgear") for x in (cfg.distribution or {}).get(g) or []}
    limit_pid = "design_criteria.busduct_max_loading" if kind == "busduct" else "design_criteria.switchgear_max_loading"
    inp = Inputs(iw, f"{heading}: inputs", "Design currents come from the load estimate and sizing results (preliminary). Ratings and evidence are manufacturer data and are never assumed.")
    v, s_, src = _P(cfg, limit_pid)
    inp.add("max_loading", "Maximum loading of the rating", "%", v, s_, src, "SITE_DATA")
    if kind == "busduct":
        v, s_, src = _P(cfg, "design_criteria.voltage_drop_limit_pct")
        inp.add("vd_limit", "Voltage drop limit", "%", v, s_, src, "SITE_DATA")
    is_mv = kind == "mv"
    d_ = sc.mv_case if is_mv else sc.design_lv
    inp.add("req_ik", "Fault level the rating must exceed (initial symmetrical)", "kA", None if d_ is None else d_.ik_ka, ds.PRELIMINARY_ASSUMPTION,
            "From 10_SHORT_CIRCUIT. Pending until the utility, transformer and generator data are supplied", "SITE_DATA", "Blank until the short-circuit study can be calculated.")
    for it in items:
        r = raw[it.tag]
        sw = it.kind == "switchgear"
        inp.add(f"{it.tag}.I", f"{it.tag}: design current", "A", it.design_current_a, ds.PRELIMINARY_ASSUMPTION, f"Load model and sizing, basis {it.basis}", "SITE_DATA")
        k = 1.0
        for x in (r.get("derating") or {}).values():
            k *= x
        inp.add(f"{it.tag}.k", f"{it.tag}: derating factors (ambient x installation)", "-", k, ds.UNVERIFIED_PLACEHOLDER,
                "PLACEHOLDER 1.00 (no derating applied): NOT a verified value. Take it from the manufacturer's data for the site ambient and the installation.", "MANUFACTURER",
                "The required rating is a minimum until the real factors are entered.")
        inp.add(f"{it.tag}.rated", f"{it.tag}: rated current", "A", r.get("rated_current_a"), ds.UNVERIFIED_PLACEHOLDER, "Manufacturer data pending", "MANUFACTURER", "Never assumed.")
        inp.add(f"{it.tag}.sc", f"{it.tag}: short-circuit " + ("rating" if sw else "withstand"), "kA", r.get("short_circuit_rating_ka" if sw else "short_circuit_withstand_ka"), ds.UNVERIFIED_PLACEHOLDER,
                "Manufacturer data pending", "MANUFACTURER", "With the type-test evidence.")
        if sw:
            for f_, lab in (("form_of_separation", "form of separation"), ("ip_rating", "IP rating"), ("verification_evidence", "IEC 61439 / IEC 62271 verification evidence")):
                inp.add(f"{it.tag}.{f_}", f"{it.tag}: {lab}", "text", r.get(f_), ds.UNVERIFIED_PLACEHOLDER, "Manufacturer data pending", "MANUFACTURER", text=True)
        else:
            inp.add(f"{it.tag}.L", f"{it.tag}: length", "m", r["length_m"], ds.UNVERIFIED_PLACEHOLDER, "Illustrative distribution schedule", "SITE_DATA")
            inp.add(f"{it.tag}.V", f"{it.tag}: voltage", "V", it.voltage_v, ds.PRELIMINARY_ASSUMPTION, "Master configuration", "SITE_DATA")
            inp.add(f"{it.tag}.pf", f"{it.tag}: load power factor", "-", r["power_factor"], ds.UNVERIFIED_PLACEHOLDER, "Illustrative distribution schedule", "SITE_DATA")
            inp.add(f"{it.tag}.R", f"{it.tag}: resistance", "ohm/km", r.get("resistance_ohm_per_km"), ds.UNVERIFIED_PLACEHOLDER, "Manufacturer data pending", "MANUFACTURER")
            inp.add(f"{it.tag}.X", f"{it.tag}: reactance", "ohm/km", r.get("reactance_ohm_per_km"), ds.UNVERIFIED_PLACEHOLDER, "Manufacturer data pending", "MANUFACTURER")
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = f"{heading}: calculations", title
    cols = ["Item", "Required rated current (A)", "Loading vs rating (%)", "Current rating result", "Required short-circuit (kA)", "Short-circuit result", "Evidence complete (1/0)", "Voltage drop (%)", "Voltage drop result", "Overall design status"]
    _header(calc, 4, cols, [16, 18, 16, 16, 18, 16, 14, 14, 16, 18])
    agg = agg_status(inp.status_range())
    for n_, it in enumerate(items):
        r = 5 + n_
        t, sw = it.tag, it.kind == "switchgear"
        _put(calc, f"A{r}", t, bold)
        _put(calc, f"B{r}", f"={I(f'{t}.I')}/{I(f'{t}.k')}", base, FILL_RESULT, "#,##0.0")
        _put(calc, f"C{r}", f'=IF({I(f"{t}.rated")}="","",{I(f"{t}.I")}/({I(f"{t}.rated")}*{I(f"{t}.k")})*100)', base, FILL_RESULT, "0.0")
        _put(calc, f"D{r}", f'=IF(C{r}="","NOT VERIFIED",IF(C{r}>{I("max_loading")}+0.000000001,"FAIL","PASS"))', bold)
        _put(calc, f"E{r}", f'=IF({I("req_ik")}="",{NC},{I("req_ik")})', base, FILL_RESULT, "0.000")
        _put(calc, f"F{r}", f'=IF(OR(E{r}={NC},{I(f"{t}.sc")}=""),"NOT VERIFIED",IF({I(f"{t}.sc")}>=E{r},"PASS","FAIL"))', bold)
        if sw:
            ev = "*".join(f'({I(f"{t}.{f_}")}<>"")' for f_ in ("form_of_separation", "ip_rating", "verification_evidence"))
            _put(calc, f"G{r}", f"=IF({ev}=1,1,0)")
            _put(calc, f"H{r}", "n/a")
            _put(calc, f"I{r}", "n/a")
            parts_ok = f'AND(D{r}="PASS",F{r}="PASS",G{r}=1)'
            any_fail = f'OR(D{r}="FAIL",F{r}="FAIL")'
        else:
            _put(calc, f"G{r}", "n/a")
            _put(calc, f"H{r}", f'=IF(COUNT({I(f"{t}.R")},{I(f"{t}.X")})<2,{NC},SQRT(3)*{I(f"{t}.I")}*{I(f"{t}.L")}*({I(f"{t}.R")}/1000*{I(f"{t}.pf")}+{I(f"{t}.X")}/1000*SQRT(1-{I(f"{t}.pf")}^2))/{I(f"{t}.V")}*100)', base, FILL_RESULT, "0.000")
            _put(calc, f"I{r}", f'=IF(H{r}={NC},"NOT VERIFIED",IF(H{r}>{I("vd_limit")}+0.000000001,"FAIL","PASS"))', bold)
            parts_ok = f'AND(D{r}="PASS",F{r}="PASS",I{r}="PASS")'
            any_fail = f'OR(D{r}="FAIL",F{r}="FAIL",I{r}="FAIL")'
        _put(calc, f"J{r}", f'=IF({any_fail},"FAIL",IF(AND({parts_ok},{agg}="VERIFIED_OR_ACCEPTED"),"PASS","NOT VERIFIED"))', bold)
    colour_statuses(calc, f"D5:J{4+len(items)}")
    res["A1"].value, res["A1"].font = f"{heading}: results", title
    res["A2"].value, res["A2"].font = "Calculation results and the overall design status are separate. Python values at generation are shown for agreement.", note
    _header(res, 4, ["Item", "Required rated current (A)", "Python (A)", "Agreement", "Input-data status", "Overall design status"], [18, 24, 14, 18, 28, 22])
    for n_, it in enumerate(items):
        r = 5 + n_
        _put(res, f"A{r}", it.tag, bold)
        _put(res, f"B{r}", f"=CALCULATIONS!B{r}", bold, FILL_RESULT, "#,##0.0")
        _put(res, f"C{r}", it.required_rating_a, base, None, "#,##0.0")
        _put(res, f"D{r}", f'=IF(ABS(B{r}-C{r})<=0.0001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
        _put(res, f"E{r}", f"={agg}", bold)
        _put(res, f"F{r}", f"=CALCULATIONS!J{r}", bold)
    colour_statuses(res, f"E5:F{4+len(items)}")
    what = {"busduct": "Required rated current after derating, loading against the manufacturer's rating, voltage drop from the manufacturer's impedance, and short-circuit withstand against the fault level.",
            "lv": "Busbar required rated current after derating, loading against the rated current, short-circuit rating against the fault level, and completeness of the assembly data (separation, IP, IEC 61439 verification).",
            "mv": "Busbar required rated current, loading against the rated current, short-circuit rating against the MV fault level, and completeness of the assembly data (IEC 62271 evidence)."}[kind]
    readme(ws0, f"{heading}: " + cfg.project.name, file, cfg, stamp, what,
           "Ratings, impedance and type-test evidence are manufacturer data and are never assumed: without them the checks read NOT VERIFIED. The required fault level is blank until the short-circuit study can be calculated. "
           "Peak withstand, temperature rise and clearances are not assessed.", SHEETS)
    revision_sheet(rev, cfg, stamp, file)
    return _save(wb, path)


def build_earthing_workbook(cfg: ProjectConfig, checks: list[CheckResult], path: str | Path, stamp: str) -> Path:
    wb, ws0, iw, calc, res, rev = _open(cfg, stamp, "earthing")
    inp = Inputs(iw, "Earthing screening: inputs", "Soil resistivity and grid geometry are pending site and design data. Nothing is assumed.")
    spec = [("rho", "earthing.soil_resistivity", "SITE_DATA"), ("area", "earthing_study.grid_area_m2", "SITE_DATA"), ("length", "earthing_study.grid_conductor_length_m", "SITE_DATA"),
            ("depth", "earthing_study.grid_burial_depth_m", "SITE_DATA"), ("ig", "earthing_study.earth_fault_current_ka", "SITE_DATA"), ("ts", "earthing_study.fault_clearing_time_s", "SITE_DATA"),
            ("rho_s", "earthing_study.surface_layer_resistivity_ohm_m", "SITE_DATA"), ("hs", "earthing_study.surface_layer_thickness_m", "SITE_DATA")]
    for key, pid, sup in spec:
        p = cfg.get(pid)
        inp.add(key, p.name, p.unit, p.value, ds.data_status(p), p.source, sup, p.notes)
    p = cfg.get("earthing.earthing_system_type")
    inp.add("system", p.name, "-", p.value, ds.data_status(p), p.source, "SITE_DATA", "Earth-fault loop and disconnection need the device data and are not assessed.", text=True)
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Earthing screening: calculations (IEEE 80 equations)", title
    _header(calc, 4, ["Step", "Value", "Unit"], [64, 18, 10])
    lines = [("rg", "Grid resistance Rg = rho [1/LT + 1/sqrt(20A) (1 + 1/(1 + h sqrt(20/A)))]", f'IF(COUNT({I("rho")},{I("area")},{I("length")},{I("depth")})<4,{NC},{I("rho")}*(1/{I("length")}+1/SQRT(20*{I("area")})*(1+1/(1+{I("depth")}*SQRT(20/{I("area")})))))', "ohm", "0.0000"),
             ("gpr", "Ground potential rise GPR = Ig x Rg", f'IF(AND(ISNUMBER(B5),ISNUMBER({I("ig")})),{I("ig")}*1000*B5,{NC})', "V", "#,##0"),
             ("cs", "Surface layer factor Cs = 1 - 0.09 (1 - rho/rho_s) / (2 hs + 0.09)", f'IF(COUNT({I("rho")},{I("rho_s")},{I("hs")})<3,{NC},1-0.09*(1-{I("rho")}/{I("rho_s")})/(2*{I("hs")}+0.09))', "-", "0.0000"),
             ("touch", "Tolerable touch voltage (70 kg) = (1000 + 1.5 Cs rho_s) x 0.157 / sqrt(ts)", f'IF(AND(ISNUMBER(B7),COUNT({I("rho_s")},{I("ts")})=2),(1000+1.5*B7*{I("rho_s")})*0.157/SQRT({I("ts")}),{NC})', "V", "#,##0"),
             ("step", "Tolerable step voltage (70 kg) = (1000 + 6 Cs rho_s) x 0.157 / sqrt(ts)", f'IF(AND(ISNUMBER(B7),COUNT({I("rho_s")},{I("ts")})=2),(1000+6*B7*{I("rho_s")})*0.157/SQRT({I("ts")}),{NC})', "V", "#,##0")]
    for k, (_, label, f, unit, fmt) in enumerate(lines):
        r = 5 + k
        _put(calc, f"A{r}", label)
        _put(calc, f"B{r}", f"={f}", bold, FILL_RESULT, fmt)
        _put(calc, f"C{r}", unit)
    _put(calc, "A11", "Screening: a GPR at or below the tolerable touch voltage is a screening pass only. A higher value needs a detailed mesh and step analysis.", note, border=None)
    res["A1"].value, res["A1"].font = "Earthing screening: results and statuses", title
    for c, w in zip("ABCD", (58, 26, 26, 22)):
        res.column_dimensions[c].width = w
    py = None
    try:
        py = assess_earthing(cfg)
    except MissingInputs:
        pass
    _put(res, "B3", "Excel", bold)
    _put(res, "C3", "Python at generation", bold)
    _put(res, "D3", "Agreement", bold)
    for k, (label, cell, pv) in enumerate((("Grid resistance (ohm)", "B5", None if py is None else py.grid_resistance_ohm), ("Ground potential rise (V)", "B6", None if py is None or py.gpr_v is None else py.gpr_v),
                                            ("Tolerable touch voltage (V)", "B8", None if py is None or py.tolerable_touch_v is None else py.tolerable_touch_v))):
        r = 4 + k
        _put(res, f"A{r}", label)
        _put(res, f"B{r}", f"=CALCULATIONS!{cell}", bold, FILL_RESULT, "#,##0.000")
        _put(res, f"C{r}", NC.strip('"') if pv is None else pv, base, None, "#,##0.000")
        _put(res, f"D{r}", f'=IF(AND(ISNUMBER(B{r}),ISNUMBER(C{r})),IF(ABS(B{r}-C{r})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)"),IF(B{r}=C{r},"MATCH","DIFFERENT (inputs changed since generation)"))', note)
    refs = status_block(res, 9, "Statuses: touch voltage screening", [I("rho"), I("area"), I("length"), I("depth"), I("ig"), I("ts"), I("rho_s"), I("hs")], 'IF(CALCULATIONS!B6<=CALCULATIONS!B8,"PASS","WARNING")', inp.status_range())
    pyc = {c.id: c for c in checks}.get("earthing_framework")
    _put(res, "C14", pyc.status.value if pyc else None)
    _put(res, "D14", '=IF(B14=C14,"MATCH","DIFFERENT (inputs changed since generation)")', note)
    readme(ws0, "Earthing screening: " + cfg.project.name, FILES["earthing"], cfg, stamp,
           "Grid resistance (IEEE 80 Sverak equation), ground potential rise from the earth-fault current, and the tolerable touch and step voltages for a 70 kg person, compared as a screening.",
           "Soil resistivity, grid geometry, earth-fault current, clearing time and surface layer are pending and are not assumed. Uniform soil, grid current split factor of 1, no mesh or step voltage calculation, "
           "no earth-fault loop impedance, bonding conductor sizing or lightning protection.", SHEETS)
    revision_sheet(rev, cfg, stamp, FILES["earthing"])
    return _save(wb, path)


def build_battery_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, ws0, iw, calc, res, rev = _open(cfg, stamp, "battery sizing")
    est = estimate_loads(cfg)
    b = size_battery(cfg, est)
    inp = Inputs(iw, "Battery sizing interface: inputs", "The battery itself cannot be sized without the manufacturer's constant-power discharge data. This workbook gives the energy requirement and an indicative nominal energy.")
    f = 1 + (cfg.value("general.future_expansion_allowance") or 0) / 100.0
    inp.add("load_kw", "Critical load carried by one UPS (worst credible: the other path lost)", "kW", b.ups_output_kw / f, ds.PRELIMINARY_ASSUMPTION, "Preliminary: from the load estimate", "SITE_DATA")
    inp.add("growth", "Future expansion allowance", "%", cfg.value("general.future_expansion_allowance"), *(_P(cfg, "general.future_expansion_allowance")[1:]), "SITE_DATA")
    v, s_, src = _P(cfg, "redundancy.battery_autonomy")
    inp.add("autonomy", "Autonomy time", "min", v, s_, src, "SITE_DATA")
    for key, pid, sup in (("eta", "battery.inverter_efficiency_pct", "MANUFACTURER"), ("eol", "battery.end_of_life_capacity_factor", "MANUFACTURER"), ("temp", "battery.temperature_correction_factor", "MANUFACTURER"),
                          ("margin", "battery.design_margin_factor", "SITE_DATA"), ("vdc", "battery.dc_bus_voltage_v", "MANUFACTURER")):
        p = cfg.get(pid)
        inp.add(key, p.name, p.unit, p.value, ds.data_status(p), p.source, sup, p.notes)
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Battery sizing interface: calculations", title
    _header(calc, 4, ["Step", "Value", "Unit"], [70, 18, 10])
    rows = [("Energy at the UPS output = load x autonomy", f'IF(COUNT({I("load_kw")},{I("autonomy")})<2,{NC},{I("load_kw")}*(1+{I("growth")}/100)*{I("autonomy")}/60)', "kWh", "#,##0.0"),
            ("Indicative nominal energy = E / eta / (EOL x temperature) x margin (ignores discharge-rate effects; NOT a battery selection)", f'IF(OR(NOT(ISNUMBER(B5)),COUNT({I("eta")},{I("eol")},{I("temp")},{I("margin")})<4),{NC},B5/({I("eta")}/100)/({I("eol")}*{I("temp")})*{I("margin")})', "kWh", "#,##0.0")]
    for k, (label, f_, unit, fmt) in enumerate(rows):
        r = 5 + k
        _put(calc, f"A{r}", label, base)
        _put(calc, f"B{r}", f"={f_}", bold, FILL_RESULT, fmt)
        _put(calc, f"C{r}", unit)
    _put(calc, "A8", "String configuration, cell count and battery selection need the manufacturer's constant-power discharge table (W per cell to the end voltage at the autonomy time), at end of life and the room temperature. It is not assumed.", note, border=None)
    res["A1"].value, res["A1"].font = "Battery sizing interface: results and statuses", title
    for c, w in zip("ABCD", (58, 26, 26, 22)):
        res.column_dimensions[c].width = w
    _put(res, "B3", "Excel", bold)
    _put(res, "C3", "Python at generation", bold)
    _put(res, "D3", "Agreement", bold)
    for k, (label, cell, pv) in enumerate((("Energy at the UPS output (kWh)", "B5", b.energy_at_ups_output_kwh), ("Indicative nominal energy (kWh)", "B6", b.indicative_nominal_energy_kwh))):
        r = 4 + k
        _put(res, f"A{r}", label)
        _put(res, f"B{r}", f"=CALCULATIONS!{cell}", bold, FILL_RESULT, "#,##0.0")
        _put(res, f"C{r}", "NOT CALCULATED" if pv is None else pv, base, None, "#,##0.0")
        _put(res, f"D{r}", f'=IF(AND(ISNUMBER(B{r}),ISNUMBER(C{r})),IF(ABS(B{r}-C{r})<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)"),IF(B{r}=C{r},"MATCH","DIFFERENT (inputs changed since generation)"))', note)
    _put(res, "A8", "Battery selected", bold)
    _put(res, "B8", "NOT VERIFIED: no discharge data", bold)
    agg = agg_status(inp.status_range())
    _put(res, "A9", "Input-data status (worst input)")
    _put(res, "B9", f"={agg}", bold)
    colour_statuses(res, "B9:B9")
    readme(ws0, "Battery sizing interface: " + cfg.project.name, FILES["battery"], cfg, stamp,
           "The energy the battery must deliver at the UPS output for the autonomy time, and an indicative nominal energy once the inverter efficiency and correction factors are supplied.",
           "This is not a battery selection. A battery is sized from the manufacturer's constant-power discharge data, which is never assumed. The workbook does not choose cells, strings or a DC bus voltage.", SHEETS)
    revision_sheet(rev, cfg, stamp, FILES["battery"])
    return _save(wb, path)
