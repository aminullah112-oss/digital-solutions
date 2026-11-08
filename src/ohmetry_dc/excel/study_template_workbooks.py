"""14_PROTECTION_COORDINATION, 16_LIGHTNING_PROTECTION, 17_POWER_QUALITY, 18_ENERGY_EFFICIENCY and 19_GENERATOR_FUEL.

These are mostly structured input registers: the studies they support need data that does not exist in this package (device curves, a lightning risk
assessment, measurements, a fuel curve). Each calculation that can be done from what is entered is live; everything else reads NOT CALCULATED or
NOT VERIFIED, and no status ever reads PASS without the evidence the master prompt requires.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from ohmetry_dc.calculations import assess_short_circuit, estimate_loads, size_power_system
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds

from .architecture_workbooks import _edit, _sheets
from .common import FILL_RESULT, Inputs, _header, _put, agg_status, base, bold, colour_statuses, note, new_workbook, readme, revision_sheet, status_block, title
from .other_workbooks import _P, _save

FILES = {"protection": "14_PROTECTION_COORDINATION.xlsx", "lightning": "16_LIGHTNING_PROTECTION.xlsx", "pq": "17_POWER_QUALITY.xlsx", "energy": "18_ENERGY_EFFICIENCY.xlsx", "fuel": "19_GENERATOR_FUEL.xlsx"}
NC = '"NOT CALCULATED"'
VIOLET = PatternFill("solid", bgColor="E4DCF2", fgColor="E4DCF2")


# ------------------------------------------------------------------ 14
def build_protection_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "protection coordination")
    ws0, dev, ctvt, relay, zones, sel, rev = _sheets(wb, ["README", "DEVICE_SCHEDULE", "CT_VT", "RELAY_SETTINGS", "ZONES", "SELECTIVITY", "REVISION_LOG"])
    sc = assess_short_circuit(cfg)
    devs = (cfg.distribution or {}).get("protection_devices") or []
    dev["A1"].value, dev["A1"].font = "Protective device schedule", title
    dev["A2"].value, dev["A2"].font = "Breaking and making capacity and curve references are manufacturer data and are never assumed. The required fault level is blank until the short-circuit study can be calculated.", note
    _header(dev, 4, ["Tag", "Description", "Bus", "Function", "Required breaking (kA)", "Required making peak (kA)", "Breaking capacity (kA)", "Making capacity (kA)", "TCC / curve reference", "Datasheet source and revision", "Reviewed by", "Rating check", "Device status"],
            [14, 44, 7, 40, 14, 14, 14, 14, 24, 30, 16, 16, 28])
    for i, d in enumerate(devs):
        r = 5 + i
        mv = d["bus"] == "MV"
        ik = (sc.mv_case.ik_ka if sc.mv_case else None) if mv else (sc.design_lv.ik_ka if sc.design_lv else None)
        ip = (sc.mv_case.ip_ka if sc.mv_case else None) if mv else (sc.design_lv.ip_ka if sc.design_lv else None)
        for col, v in zip("ABCD", (d["tag"], d["description"], d["bus"], d["function"])):
            _put(dev, f"{col}{r}", v)
        _edit(dev, f"E{r}", ik, "0.000")
        _edit(dev, f"F{r}", ip, "0.000")
        for col in "GHIJK":
            _edit(dev, f"{col}{r}", d.get("breaking_capacity_ka") if col == "G" else None)
        _put(dev, f"L{r}", f'=IF(OR(E{r}="",G{r}="",J{r}=""),"NOT VERIFIED",IF(G{r}>=E{r},"PASS","FAIL"))', bold)
        _put(dev, f"M{r}", f'=IF(L{r}="FAIL","FAIL",IF(AND(L{r}="PASS",I{r}<>"",K{r}<>""),"RATING VERIFIED (coordination separate)","NOT VERIFIED"))', bold)
    last = 4 + len(devs)
    colour_statuses(dev, f"L5:L{last}")
    dev.conditional_formatting.add(f"M5:M{last}", FormulaRule(formula=['LEFT(M5,12)="NOT VERIFIED"'], fill=VIOLET))
    ctvt["A1"].value, ctvt["A1"].font = "CT and VT data register", title
    _header(ctvt, 3, ["Tag", "Type (CT/VT)", "Location", "Ratio", "Class", "Burden (VA)", "Knee-point / saturation data", "Datasheet source and revision", "Notes"], [14, 12, 24, 14, 10, 12, 30, 30, 30])
    for r in range(4, 14):
        for col in "ABCDEFGHI":
            _edit(ctvt, f"{col}{r}")
    relay["A1"].value, relay["A1"].font = "Relay settings input register", title
    relay["A2"].value, relay["A2"].font = "Settings come from the coordination study. None are suggested here.", note
    _header(relay, 3, ["Relay / device tag", "Function", "Setting", "Value", "Unit", "Time (s)", "Source (study, curve)", "Study reference", "Reviewed by"], [20, 22, 24, 12, 8, 10, 40, 24, 16])
    for r in range(4, 24):
        for col in "ABCDEFGHI":
            _edit(relay, f"{col}{r}")
    zones["A1"].value, zones["A1"].font = "Protection zones", title
    _header(zones, 3, ["Zone", "Equipment in the zone", "Primary protection (device tag)", "Backup protection (device tag)", "Status"], [30, 44, 28, 28, 28])
    for i, (z, eq) in enumerate([("MV incomer", "MV switchgear, MV cable"), ("Transformer", "TX-A1, TX-B1"), ("LV main switchboard", "LV-MSB-A, LV-MSB-B, BD-TX-A"), ("Generator", "GEN-A1..A3, GEN-B1..B3, generator cables"),
                                  ("UPS feeder", "UPS-A1, UPS-B1, input cables"), ("Mechanical feeder", "Mechanical plant feeder")]):
        r = 4 + i
        _put(zones, f"A{r}", z)
        _put(zones, f"B{r}", eq)
        _edit(zones, f"C{r}")
        _edit(zones, f"D{r}")
        _put(zones, f"E{r}", f'=IF(C{r}="","NOT VERIFIED: no primary protection assigned","DEVICES ASSIGNED: coordination not verified")', bold)
    sel["A1"].value, sel["A1"].font = "Selectivity matrix and coordination evidence", title
    sel["A2"].value, sel["A2"].font = "Coordination reads NOT VERIFIED without the actual device curves and a validated network study. This workbook never reports a coordination PASS.", bold
    _header(sel, 4, ["Upstream device", "Downstream device", "Upstream TCC reference", "Downstream TCC reference", "Network study reference", "Selective up to (kA)", "Result recorded", "Reviewed by", "Coordination status"], [16, 16, 28, 28, 28, 14, 20, 16, 40])
    pairs = [("MV-CB-A", "ACB-TX-A"), ("ACB-TX-A", "ACB-UPS-IN-A"), ("ACB-GEN-A", "ACB-UPS-IN-A")] + [("", "")] * 5
    for i, (u, d_) in enumerate(pairs):
        r = 5 + i
        _edit(sel, f"A{r}", u or None)
        _edit(sel, f"B{r}", d_ or None)
        for col in "CDEFGH":
            _edit(sel, f"{col}{r}")
        _put(sel, f"I{r}", f'=IF(A{r}="","",IF(OR(C{r}="",D{r}="",E{r}=""),"NOT VERIFIED: curves or study missing",IF(H{r}="","EVIDENCE ENTERED: REVIEW REQUIRED","EVIDENCE REVIEWED (not a PASS)")))', bold)
    dv = DataValidation(type="list", formula1='"SELECTIVE,PARTIAL,NOT SELECTIVE,NOT ASSESSED"', allow_blank=True)
    sel.add_data_validation(dv)
    dv.add("G5:G12")
    _put(sel, "A14", "Overall coordination status", bold)
    _put(sel, "B14", '=IF(COUNTIF(I5:I12,"NOT VERIFIED*")>0,"NOT VERIFIED",IF(COUNTIF(I5:I12,"EVIDENCE ENTERED*")>0,"EVIDENCE ENTERED: REVIEW REQUIRED","EVIDENCE REVIEWED (not a PASS)"))', bold)
    sel.conditional_formatting.add("I5:I12", FormulaRule(formula=['LEFT(I5,12)="NOT VERIFIED"'], fill=VIOLET))
    readme(ws0, "Protection coordination: " + cfg.project.name, FILES["protection"], cfg, stamp,
           "A schedule of protective devices with the fault level each must handle, registers for CT and VT data, relay settings and protection zones, a selectivity matrix and coordination evidence fields.",
           "No curve, setting or coordination result is supplied or suggested. Discrimination needs the manufacturers' time-current curves and a validated network study. Arc-flash and minimum fault sensitivity are not assessed. "
           "Coordination never reads PASS here.", ["README", "DEVICE_SCHEDULE", "CT_VT", "RELAY_SETTINGS", "ZONES", "SELECTIVITY", "REVISION_LOG"])
    revision_sheet(rev, cfg, stamp, FILES["protection"])
    return _save(wb, path)


# ------------------------------------------------------------------ 16
def build_lightning_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "lightning protection")
    ws0, iw, calc, rev = _sheets(wb, ["README", "INPUTS", "RESULTS", "REVISION_LOG"])
    inp = Inputs(iw, "Lightning protection: inputs", "Every input is pending site and design data. Nothing is assumed.")
    pend = "Pending: site and design data"
    for key, lab, unit in (("L", "Structure length", "m"), ("W", "Structure width", "m"), ("H", "Structure height", "m"), ("Ng", "Ground flash density", "flashes/km2/year"), ("Cd", "Location factor (IEC 62305-2)", "-")):
        inp.add(key, lab, unit, None, ds.MISSING, pend, "SITE_DATA")
    for key, lab in (("level", "Protection level selected (I to IV) and basis"), ("air", "Air termination arrangement"), ("down", "Down conductor arrangement (number, spacing)"), ("earth", "Earth termination"),
                     ("spd", "Surge protection coordination (SPD types and positions)"), ("risk", "Risk assessment reference (complete IEC 62305-2 assessment)")):
        inp.add(key, lab, "text", None, ds.MISSING, pend, "SITE_DATA", text=True)
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Lightning protection: calculations and status", title
    for c, w in zip("ABCD", (66, 22, 14, 60)):
        calc.column_dimensions[c].width = w
    _put(calc, "A3", "Equivalent collection area Ad (isolated structure) = L W + 2 (3H)(L + W) + pi (3H)^2", base)
    _put(calc, "B3", f'=IF(COUNT({I("L")},{I("W")},{I("H")})<3,{NC},{I("L")}*{I("W")}+2*(3*{I("H")})*({I("L")}+{I("W")})+PI()*(3*{I("H")})^2)', bold, FILL_RESULT, "#,##0")
    _put(calc, "C3", "m2")
    _put(calc, "A4", "Expected annual dangerous events ND = Ng x Ad x Cd x 1e-6", base)
    _put(calc, "B4", f'=IF(AND(ISNUMBER(B3),COUNT({I("Ng")},{I("Cd")})=2),{I("Ng")}*B3*{I("Cd")}*0.000001,{NC})', bold, FILL_RESULT, "0.0000")
    _put(calc, "C4", "per year")
    _put(calc, "D3", "Reference equation from IEC 62305-2 (verify the edition). ND is one input to the risk assessment, not the risk.", note)
    _put(calc, "A6", "Design arrangement fields complete (1/0)", base)
    _put(calc, "B6", f'=IF(AND({I("level")}<>"",{I("air")}<>"",{I("down")}<>"",{I("earth")}<>"",{I("spd")}<>""),1,0)', bold)
    _put(calc, "A7", "Risk assessment reference entered (1/0)", base)
    _put(calc, "B7", f'=IF({I("risk")}<>"",1,0)', bold)
    _put(calc, "A9", "OVERALL DESIGN STATUS", bold)
    _put(calc, "B9", '=IF(B7=0,"NOT VERIFIED: no risk assessment",IF(B6=0,"NOT VERIFIED: arrangement incomplete","EVIDENCE ENTERED: REVIEW REQUIRED"))', bold)
    _put(calc, "A10", "Compliance with IEC 62305 is not claimed. It needs a complete, verified risk assessment.", note, border=None)
    calc.conditional_formatting.add("B9", FormulaRule(formula=['LEFT(B9,12)="NOT VERIFIED"'], fill=VIOLET))
    readme(ws0, "Lightning protection: " + cfg.project.name, FILES["lightning"], cfg, stamp,
           "Input fields for the risk assessment and protection design (structure dimensions, protection level, air termination, down conductors, earth termination, SPD coordination), and the equivalent collection area and expected number of dangerous events.",
           "Not a lightning protection design and not a risk assessment. Compliance is not claimed without a complete verified IEC 62305-2 risk assessment and a specialist design.", ["README", "INPUTS", "RESULTS", "REVISION_LOG"])
    calc.title = "RESULTS"
    revision_sheet(rev, cfg, stamp, FILES["lightning"])
    return _save(wb, path)


# ------------------------------------------------------------------ 17
def build_power_quality_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "power quality")
    ws0, iw, harm, res, rev = _sheets(wb, ["README", "INPUTS", "HARMONICS", "RESULTS", "REVISION_LOG"])
    inp = Inputs(iw, "Power quality: inputs", "Measurement data only. Nothing is assumed. Limits are entered from the applicable project requirements.")
    pend = "Pending: measurement"
    for key, lab, unit in (("vab", "Line voltage AB", "V"), ("vbc", "Line voltage BC", "V"), ("vca", "Line voltage CA", "V"), ("v1", "Fundamental voltage (for THD)", "V"), ("f", "Measured frequency", "Hz")):
        inp.add(key, lab, unit, None, ds.MISSING, pend, "SITE_DATA")
    inp.add("fnom", "Nominal frequency", "Hz", cfg.value("electrical_system.frequency"), ds.data_status(cfg.get("electrical_system.frequency")), cfg.get("electrical_system.frequency").source, "SITE_DATA")
    inp.add("pf", "Measured power factor", "-", None, ds.MISSING, pend, "SITE_DATA")
    inp.add("flicker", "Flicker severity Plt (measured)", "-", None, ds.MISSING, pend, "SITE_DATA")
    inp.add("thd_limit", "THD limit (from the applicable project requirement)", "%", None, ds.MISSING, "Pending: applicable limits to be verified from current project requirements", "SITE_DATA")
    inp.add("vuf_limit", "Voltage unbalance limit (from the applicable project requirement)", "%", None, ds.MISSING, "Pending: applicable limits to be verified", "SITE_DATA")
    inp.add("freq_limit", "Frequency deviation limit", "%", None, ds.MISSING, "Pending: applicable limits to be verified", "SITE_DATA")
    inp.add("instrument", "Measurement instrument, class and test conditions", "text", None, ds.MISSING, pend, "SITE_DATA", text=True)
    inp.add("basis", "Basis of the values (MEASURED or ESTIMATED)", "text", None, ds.MISSING, pend, "SITE_DATA", text=True)
    inp.finish()
    I = inp.eff
    harm["A1"].value, harm["A1"].font = "Individual harmonic voltages (enter measured RMS voltages)", title
    _header(harm, 3, ["Harmonic order", "Voltage (V)", "Percent of fundamental"], [16, 16, 22])
    for h in range(2, 26):
        r = 2 + h
        _put(harm, f"A{r}", h)
        _edit(harm, f"B{r}", None, "0.000")
        _put(harm, f"C{r}", f'=IF(OR(B{r}="",NOT(ISNUMBER({I("v1")}))),"",B{r}/{I("v1")}*100)', base, FILL_RESULT, "0.000")
    res["A1"].value, res["A1"].font = "Power quality: results and statuses", title
    for c, w in zip("ABCD", (58, 20, 22, 40)):
        res.column_dimensions[c].width = w
    _header(res, 3, ["Quantity", "Value", "Limit", "Result"], [58, 20, 22, 40])
    rows = [("Voltage unbalance (max deviation from the mean / mean)", f'IF(COUNT({I("vab")},{I("vbc")},{I("vca")})<3,{NC},MAX(ABS({I("vab")}-AVERAGE({I("vab")},{I("vbc")},{I("vca")})),ABS({I("vbc")}-AVERAGE({I("vab")},{I("vbc")},{I("vca")})),ABS({I("vca")}-AVERAGE({I("vab")},{I("vbc")},{I("vca")})))/AVERAGE({I("vab")},{I("vbc")},{I("vca")})*100)', "%", "vuf_limit"),
            ("Total harmonic distortion THD (orders 2 to 25)", f'IF(OR(COUNT(HARMONICS!B4:B27)=0,NOT(ISNUMBER({I("v1")}))),{NC},SQRT(SUMSQ(HARMONICS!B4:B27))/{I("v1")}*100)', "%", "thd_limit"),
            ("Frequency deviation", f'IF(COUNT({I("f")},{I("fnom")})<2,{NC},ABS({I("f")}-{I("fnom")})/{I("fnom")}*100)', "%", "freq_limit")]
    for k, (lab, f_, unit, lim) in enumerate(rows):
        r = 4 + k
        _put(res, f"A{r}", lab)
        _put(res, f"B{r}", f"={f_}", bold, FILL_RESULT, "0.000")
        _put(res, f"C{r}", f'=IF({I(lim)}="","(limit not entered)",{I(lim)})')
        _put(res, f"D{r}", f'=IF(NOT(ISNUMBER(B{r})),"NOT CALCULATED",IF(NOT(ISNUMBER(C{r})),"NOT VERIFIED: no limit entered",IF(B{r}>C{r}+0.000000001,"FAIL",IF(AND({I("instrument")}<>"",{agg_status(inp.status_range())}="VERIFIED_OR_ACCEPTED"),"PASS","NOT VERIFIED: inputs unreviewed"))))', bold)
    res.conditional_formatting.add("D4:D6", FormulaRule(formula=['LEFT(D4,3)="NOT"'], fill=VIOLET))
    res.conditional_formatting.add("D4:D6", FormulaRule(formula=['D4="FAIL"'], fill=PatternFill("solid", bgColor="F8C9C4", fgColor="F8C9C4")))
    _put(res, "A8", "Power factor / flicker: recorded values", base)
    _put(res, "B8", f'=IF({I("pf")}="","(not entered)",{I("pf")})')
    _put(res, "C8", f'=IF({I("flicker")}="","(not entered)",{I("flicker")})')
    readme(ws0, "Power quality: " + cfg.project.name, FILES["pq"], cfg, stamp,
           "Voltage unbalance, total and individual harmonic distortion and frequency deviation from the measurements you enter, with the measurement instrument and conditions, compared with limits you enter.",
           "No measurement or limit is supplied. Applicable limits must be verified from the current project requirements. A PASS needs a measurement, a limit, a named instrument and reviewed inputs. "
           "Flicker, interharmonics and current harmonics are recorded, not assessed.", ["README", "INPUTS", "HARMONICS", "RESULTS", "REVISION_LOG"])
    revision_sheet(rev, cfg, stamp, FILES["pq"])
    return _save(wb, path)


# ------------------------------------------------------------------ 18
def build_energy_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "energy efficiency")
    ws0, iw, calc, rev = _sheets(wb, ["README", "INPUTS", "RESULTS", "REVISION_LOG"])
    est = estimate_loads(cfg)
    from ohmetry_dc.models import Category
    inp = Inputs(iw, "Energy efficiency: inputs", "Loads from the load estimate (preliminary). Load factors of 1.00 make this a design-point (peak) energy, an upper bound, not an annual estimate.")
    cat = lambda c: sum(r.demand_kw for r in est.items if r.category == c.value)
    cats = [("it", "IT energy", Category.IT_CRITICAL), ("cool", "Mechanical cooling", Category.MECHANICAL_COOLING)]
    others = [r for r in est.items if r.category not in (Category.IT_CRITICAL.value, Category.MECHANICAL_COOLING.value)]
    inp.add("hours", "Hours per year", "h", 8760, ds.REFERENCE_DATA, "Calendar", "SITE_DATA")
    for key, lab, c in cats:
        inp.add(f"{key}_kw", f"{lab}: demand load", "kW", cat(c), ds.PRELIMINARY_ASSUMPTION, "Preliminary: from the load estimate", "SITE_DATA")
        inp.add(f"{key}_lf", f"{lab}: annual average load factor", "-", 1.0, ds.PRELIMINARY_ASSUMPTION, "Design-point basis (peak all year): an upper bound", "SITE_DATA", "Replace with measured or modelled annual load factors.")
    inp.add("oth_kw", "Lighting, small power and auxiliary: demand load", "kW", sum(r.demand_kw for r in others), ds.PRELIMINARY_ASSUMPTION, "Preliminary: from the load estimate", "SITE_DATA")
    inp.add("oth_lf", "Lighting, small power and auxiliary: annual average load factor", "-", 1.0, ds.PRELIMINARY_ASSUMPTION, "Design-point basis: an upper bound", "SITE_DATA")
    inp.add("ups_eff", "UPS efficiency (design point)", "%", cfg.value("equipment.ups_efficiency"), ds.data_status(cfg.get("equipment.ups_efficiency")), cfg.get("equipment.ups_efficiency").source, "MANUFACTURER", "A single point; the efficiency curve varies with load.")
    inp.add("dist_loss", "Distribution losses (percentage of the load supplied)", "%", cfg.value("losses.distribution_loss_fraction"), ds.data_status(cfg.get("losses.distribution_loss_fraction")), cfg.get("losses.distribution_loss_fraction").source, "MANUFACTURER")
    inp.add("tx_nl", "Transformer no-load losses (total, all units)", "kW", None, ds.MISSING, "Pending: transformer test report", "MANUFACTURER", "If entered, replaces the single distribution loss percentage for the transformers only when you set 1 below.")
    inp.add("tx_ll", "Transformer load losses at full load (total, all units)", "kW", None, ds.MISSING, "Pending: transformer test report", "MANUFACTURER")
    inp.add("gen_eff", "Generator operating efficiency", "%", None, ds.MISSING, "Pending: generator data sheet", "MANUFACTURER", "Not used in the annual figure: generators run only on outage and test.")
    inp.add("basis", "Basis of the figures (MEASURED or ESTIMATED)", "text", "ESTIMATED", ds.PRELIMINARY_ASSUMPTION, "Preliminary", "SITE_DATA", text=True)
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Energy efficiency: results", title
    _header(calc, 3, ["Quantity", "Value", "Unit", "Python (design point)", "Agreement"], [62, 18, 10, 20, 18])
    L = [("IT energy", f'{I("it_kw")}*{I("it_lf")}*{I("hours")}', "kWh"), ("Mechanical cooling energy", f'{I("cool_kw")}*{I("cool_lf")}*{I("hours")}', "kWh"),
         ("Lighting, small power and auxiliary energy", f'{I("oth_kw")}*{I("oth_lf")}*{I("hours")}', "kWh"),
         ("UPS losses", f'B4*(100/{I("ups_eff")}-1)', "kWh"), ("Distribution losses", f'{I("dist_loss")}/100*(B4+B5+B6+B7)', "kWh")]
    for k, (lab, f_, u) in enumerate(L):
        r = 4 + k
        _put(calc, f"A{r}", lab)
        _put(calc, f"B{r}", f"={f_}", base, FILL_RESULT, "#,##0")
        _put(calc, f"C{r}", u)
    _put(calc, "A9", "Facility energy", bold)
    _put(calc, "B9", "=SUM(B4:B8)", bold, FILL_RESULT, "#,##0")
    _put(calc, "C9", "kWh")
    _put(calc, "A10", "Energy-based PUE = facility energy / IT energy", bold)
    _put(calc, "B10", "=B9/B4", bold, FILL_RESULT, "0.000")
    _put(calc, "D10", est.pue, base, None, "0.000")
    _put(calc, "E10", '=IF(ABS(B10-D10)<=0.000001,"MATCH","DIFFERENT (inputs changed since generation)")', note)
    _put(calc, "A11", "Basis", base)
    _put(calc, "B11", f"={I('basis')}", bold)
    _put(calc, "A12", "Transformer losses (separately), when data is entered", base)
    _put(calc, "B12", f'=IF(COUNT({I("tx_nl")},{I("tx_ll")})<2,{NC},({I("tx_nl")}+{I("tx_ll")})*{I("hours")})', base, FILL_RESULT, "#,##0")
    _put(calc, "C12", "kWh")
    _put(calc, "A13", "Input-data status (worst input)")
    _put(calc, "B13", f"={agg_status(inp.status_range())}", bold)
    _put(calc, "A14", "OVERALL STATUS", bold)
    _put(calc, "B14", '=IF(B13="VERIFIED_OR_ACCEPTED","CALCULATED FROM VERIFIED DATA","NOT VERIFIED: estimate on unverified inputs")', bold)
    _put(calc, "A15", "The annual PUE here is a design-point estimate, not a measured annual PUE. Do not publish it as a measured figure.", note, border=None)
    calc.conditional_formatting.add("B14", FormulaRule(formula=['LEFT(B14,12)="NOT VERIFIED"'], fill=VIOLET))
    readme(ws0, "Energy efficiency: " + cfg.project.name, FILES["energy"], cfg, stamp,
           "IT, cooling, auxiliary, UPS and distribution energy over a year from demand loads and annual load factors, the facility energy and an energy-based PUE, with the transformer losses taken separately when data is entered.",
           "With load factors of 1.00 this is a design-point upper bound, not an annual estimate. Measured and estimated values must be told apart: set the basis cell. Cooling energy needs a cooling model. "
           "Generator efficiency and fuel are not included in the annual figure.", ["README", "INPUTS", "RESULTS", "REVISION_LOG"])
    calc.title = "RESULTS"
    revision_sheet(rev, cfg, stamp, FILES["energy"])
    return _save(wb, path)


# ------------------------------------------------------------------ 19
def build_fuel_workbook(cfg: ProjectConfig, path: str | Path, stamp: str) -> Path:
    wb, _ = new_workbook(cfg, stamp, "generator fuel")
    ws0, iw, calc, rev = _sheets(wb, ["README", "INPUTS", "RESULTS", "REVISION_LOG"])
    sizing = size_power_system(cfg, estimate_loads(cfg))
    inp = Inputs(iw, "Generator fuel: inputs", "No fuel consumption is estimated without the manufacturer's fuel curve.")
    inp.add("model", "Generator model (manufacturer and model)", "text", None, ds.MISSING, "Pending: manufacturer data", "MANUFACTURER", text=True)
    w = sizing.generator_kw.worst_credible
    inp.add("load_pct", "Generator load for the runtime case (percent of the rated kW)", "%", None if w is None else w.loading * 100, ds.PRELIMINARY_ASSUMPTION, "Preliminary: worst credible loading from 05_GENERATOR_SIZING", "SITE_DATA")
    inp.add("running", "Generators running in the case", "-", sizing.generator.units_per_path, ds.PRELIMINARY_ASSUMPTION, "Preliminary: the units of one path", "SITE_DATA")
    for i in range(1, 5):
        inp.add(f"x{i}", f"Fuel curve point {i}: load", "%", None, ds.MISSING, "Pending: manufacturer fuel consumption curve", "MANUFACTURER", "Ascending load points.")
        inp.add(f"y{i}", f"Fuel curve point {i}: fuel consumption (each generator)", "L/h", None, ds.MISSING, "Pending: manufacturer fuel consumption curve", "MANUFACTURER")
    inp.add("tank", "Tank usable capacity (total for the running generators)", "L", None, ds.MISSING, "Pending: fuel system design", "SITE_DATA")
    inp.add("reserve", "Reserve not counted as usable", "%", None, ds.MISSING, "Pending: fuel policy", "SITE_DATA")
    inp.add("refill", "Refill assumptions (delivery time, quantity)", "text", None, ds.MISSING, "Pending: fuel supply agreement", "SITE_DATA", text=True)
    inp.finish()
    I = inp.eff
    calc["A1"].value, calc["A1"].font = "Generator fuel: results", title
    for c, w_ in zip("ABC", (66, 22, 12)):
        calc.column_dimensions[c].width = w_
    x = [I(f"x{i}") for i in range(1, 5)]
    y = [I(f"y{i}") for i in range(1, 5)]
    L = I("load_pct")
    seg = lambda a, b: f"{y[a]}+({y[b]}-{y[a]})*({L}-{x[a]})/({x[b]}-{x[a]})"
    _put(calc, "A3", "Fuel consumption of one generator at the load (piecewise-linear on the manufacturer curve)", base)
    _put(calc, "B3", f'=IF(COUNT({",".join(x + y)},{L})<9,{NC},IF(OR({L}<{x[0]},{L}>{x[3]}),"OUTSIDE CURVE",IF({L}<={x[1]},{seg(0,1)},IF({L}<={x[2]},{seg(1,2)},{seg(2,3)}))))', bold, FILL_RESULT, "0.00")
    _put(calc, "C3", "L/h")
    _put(calc, "A4", "Total consumption of the running generators", base)
    _put(calc, "B4", f'=IF(ISNUMBER(B3),B3*{I("running")},{NC})', bold, FILL_RESULT, "0.00")
    _put(calc, "C4", "L/h")
    _put(calc, "A5", "Usable fuel after the reserve", base)
    _put(calc, "B5", f'=IF(COUNT({I("tank")},{I("reserve")})<2,{NC},{I("tank")}*(1-{I("reserve")}/100))', bold, FILL_RESULT, "#,##0")
    _put(calc, "C5", "L")
    _put(calc, "A6", "Runtime at that load", bold)
    _put(calc, "B6", '=IF(AND(ISNUMBER(B4),ISNUMBER(B5)),IF(B4>0,B5/B4,"NOT CALCULATED"),"NOT CALCULATED")', bold, FILL_RESULT, "0.0")
    _put(calc, "C6", "h")
    _put(calc, "A8", "Input-data status (worst input)")
    _put(calc, "B8", f"={agg_status(inp.status_range())}", bold)
    _put(calc, "A9", "OVERALL STATUS", bold)
    _put(calc, "B9", '=IF(B6="NOT CALCULATED","NOT VERIFIED: no fuel curve or tank data",IF(B8="VERIFIED_OR_ACCEPTED","CALCULATED FROM VERIFIED DATA","NOT VERIFIED: calculated on unverified inputs"))', bold)
    calc.conditional_formatting.add("B9", FormulaRule(formula=['LEFT(B9,12)="NOT VERIFIED"'], fill=VIOLET))
    readme(ws0, "Generator fuel: " + cfg.project.name, FILES["fuel"], cfg, stamp,
           "Fuel consumption at the runtime load from the manufacturer's fuel curve, total consumption of the running generators, usable tank capacity and runtime.",
           "No consumption is estimated without the manufacturer's curve: the case reads NOT CALCULATED. The curve is interpolated linearly between four points and is not extrapolated. Fuel quality, tank "
           "temperature effects, transfer pump losses and refill logistics are not modelled.", ["README", "INPUTS", "RESULTS", "REVISION_LOG"])
    calc.title = "RESULTS"
    revision_sheet(rev, cfg, stamp, FILES["fuel"])
    return _save(wb, path)
