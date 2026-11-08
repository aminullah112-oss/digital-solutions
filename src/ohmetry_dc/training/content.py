"""The twelve training modules. Worked examples use the project configuration through the calculation engine, so the numbers cannot drift from the workbooks.

Exercise answers are computed in code by independent formulas and are checked against the engine in the tests. Standards are named, never quoted: clause numbers and
limits must be taken from the current edition. Exercise inputs are teaching values, not project data and not manufacturer data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ohmetry_dc.calculations import assess_distribution, assess_short_circuit, estimate_loads, size_power_system
from ohmetry_dc.calculations.sizing import size_battery
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.validation import run_all_checks, summarise

SQ3 = math.sqrt(3)


@dataclass
class Exercise:
    id: str
    prompt: str
    answer: float | str
    unit: str
    working: str
    tolerance: float = 0.005       # relative tolerance for a numeric answer


@dataclass
class Module:
    no: int
    title: str
    objectives: list[str]
    explanation: list[str]
    formulas: list[tuple[str, str, str]]          # name, formula, units
    example: list[str]
    mistakes: list[str]
    checklist: list[str]
    exercises: list[Exercise]
    references: list[str]
    limits: list[str]


def _with(cfg: ProjectConfig, **values) -> ProjectConfig:
    """A copy of the configuration with parameter values replaced (keys use '__' for '.')."""
    params = dict(cfg.parameters)
    for k, v in values.items():
        pid = k.replace("__", ".")
        params[pid] = params[pid].model_copy(update={"value": v})
    return cfg.model_copy(update={"parameters": params})


REFS_COMMON = ["IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), "
               "IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), "
               "IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).",
               "Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each."]
GEN_LIMITS = ["Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.",
              "Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.",
              "Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations."]


def build_modules(cfg: ProjectConfig) -> list[Module]:
    v = cfg.value
    est = estimate_loads(cfg)
    sz = size_power_system(cfg, est)
    dist = assess_distribution(cfg, est, sz)
    sc = assess_short_circuit(cfg)
    bat = size_battery(cfg, est)
    checks = run_all_checks(cfg)
    st = summarise(checks)
    tx_kva, lv, mv = v("equipment.transformer_rating"), v("electrical_system.lv_line_voltage"), v("electrical_system.mv_supply_voltage")
    i_tx = tx_kva * 1000 / (SQ3 * lv)
    tx_w = next(s for s in sz.transformer.scenarios if s.id == "TX-PATH-OUT")
    gen = sz.generator
    gen_kw = sz.generator_kw
    ups_kw, ups_kva = sz.ups_kw, sz.ups_kva
    cab = {c.tag: c for c in dist.cables}
    gcab = cab["CAB-GEN-A"]
    bound = next((c for c in sc.lv_cases if c.name.startswith("Transformer-limited")), None)
    uk = v("equipment.transformer_impedance")
    M: list[Module] = []

    # ---------------------------------------------------------------- 01
    ex1 = i_tx
    unit_out = next(x for x in sz.generator.scenarios if x.id == "GEN-UNIT-OUT")
    dbl = next(x for x in sz.generator.scenarios if x.id == "GEN-PATH-OUT-UNIT-OUT")
    M.append(Module(1, "Introduction to Data Centre Electrical Design",
        ["Describe the power chain of a data centre from utility to IT load.", "List the design stages in order and say what each stage decides.", "Distinguish a preliminary assumption from manufacturer-confirmed data.",
         "Calculate a three-phase current from apparent power and line voltage."],
        ["A data centre converts utility power into clean, continuous power for IT equipment. The chain is: utility supply, medium-voltage switchgear, transformers, low-voltage switchgear, UPS with batteries, distribution to the IT rooms, "
         "with generators and fuel as the long-duration backup and mechanical plant (cooling) as the other large load. Availability is bought with redundancy: duplicate paths, spare units, and the ability to maintain one part while the rest runs.",
         "Design proceeds in stages. The design basis fixes voltages, loads, redundancy and criteria. The load estimate gives real and reactive power. The architecture decides how many paths and units there are. Sizing checks each unit against "
         "its derated rating in the worst credible contingency. Distribution sizes cables, busducts and switchgear. The short-circuit study gives the fault levels the equipment must withstand. Protection and earthing follow. "
         "Documents, schedules and commissioning close the loop.",
         "The most important habit is to keep three kinds of information apart: standard methods (equations), reference data (published constants), and project data. Project data is further divided into preliminary assumptions and "
         "values confirmed by a manufacturer or a survey. A calculation can be correct arithmetic and still say nothing about whether the design works, if its inputs are unconfirmed."],
        [("Apparent power", "S = sqrt(P^2 + Q^2)", "P in kW, Q in kvar, S in kVA"), ("Three-phase current", "I = S / (sqrt(3) x V)", "S in VA, V line-to-line in V, I in A")],
        [f"Reference project: {v('general.it_critical_load'):,} kW of IT load, dual A/B paths, {v('equipment.transformer_quantity'):.0f} x {tx_kva:,.0f} kVA transformers at {lv:g} V.",
         f"Full-load secondary current of one transformer: I = {tx_kva * 1000:,.0f} / ({SQ3:.4f} x {lv:g}) = {i_tx:,.1f} A.",
         f"That current is the reason LV switchgear, busduct and the fault level become demanding at this size. The project's check on it reads {next(c for c in checks if c.id == 'transformer_secondary_current').status.value}: "
         "the arithmetic is right, but whether the equipment exists is a manufacturer question."],
        ["Mixing kW and kVA in one comparison.", "Sizing from the nameplate rating instead of the derated rating.", "Treating the first estimate as a result instead of a hypothesis to test.",
         "Quoting a calculated value without saying which inputs were assumed."],
        ["Is every input labelled assumption, reference, manufacturer or site data?", "Are voltages, frequency and redundancy written down before sizing starts?", "Is the worst credible contingency named for each unit?"],
        [Exercise("1.1", "A transformer is rated 2,500 kVA at 400 V line-to-line. What is its full-load secondary current?", 2500 * 1000 / (SQ3 * 400), "A", "I = 2,500,000 / (sqrt3 x 400)"),
         Exercise("1.2", "A load draws P = 1,800 kW and Q = 600 kvar. What is the apparent power?", math.hypot(1800, 600), "kVA", "S = sqrt(1800^2 + 600^2)")],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 02
    def pue_for(eta):
        c = _with(cfg, equipment__ups_efficiency=eta)
        e = estimate_loads(c)
        return e.pue, e.ups_loss.kw
    pue94, loss94 = pue_for(94.0)
    M.append(Module(2, "IT Load, Facility Load and PUE",
        ["Build a facility load from IT, cooling, lighting and losses.", "Explain why real and reactive power are added separately.", "Calculate UPS losses from efficiency and the PUE of a design point.", "State why a design-point PUE is not an annual PUE."],
        ["The IT load is the reason the facility exists. Everything else supports it: mechanical cooling, lighting and small power, auxiliaries, and the losses in the UPS and the distribution. Each item has a quantity, a unit rating, a demand "
         "factor and a power factor. Demand is connected load times demand factor. Real power adds directly. Reactive power also adds directly. Apparent power is then the square root of the sum of squares, never the sum of the apparent powers.",
         "UPS losses follow from efficiency: if the UPS delivers P_IT at efficiency eta, it draws P_IT / eta, so the loss is P_IT x (100/eta - 1) with eta in percent. Distribution losses are taken here as a single percentage of the load supplied, "
         "which is a placeholder for the transformer and cable loss data.",
         "PUE is facility energy over IT energy. The workbook value is a design-point power ratio: facility kW over IT kW at the design point. An annual PUE needs annual load profiles and ambient conditions and is a different number."],
        [("Demand", "P = N x P_unit x DF", "kW"), ("UPS loss", "P_loss = P_IT x (100 / eta - 1)", "eta in %"), ("PUE (design point)", "PUE = P_facility / P_IT", "-")],
        [f"IT load {est.it_demand_kw:,.0f} kW; UPS efficiency {v('equipment.ups_efficiency'):g} % gives UPS losses {est.ups_loss.kw:,.1f} kW; distribution losses {est.distribution_loss.kw:,.1f} kW.",
         f"Facility load {est.facility_kw:,.1f} kW, {est.facility_kvar:,.1f} kvar, {est.facility_kva:,.1f} kVA; power factor {est.power_factor:.3f}.", f"Design-point PUE = {est.facility_kw:,.1f} / {est.it_demand_kw:,.0f} = {est.pue:.3f} against a target of {v('general.target_pue')}."],
        ["Adding kVA figures arithmetically.", "Forgetting the UPS losses, which understates the load and the PUE.", "Quoting a design-point PUE as an annual figure."],
        ["Is every load item flagged with its basis (estimated or measured)?", "Are losses included in the facility load?", "Is the PUE labelled design point or annual?"],
        [Exercise("2.1", "A UPS delivers 2,000 kW and its efficiency is 94 %. What are its losses?", 2000 * (100 / 94 - 1), "kW", "P_loss = 2000 x (100/94 - 1)"),
         Exercise("2.2", "Using the reference project with the UPS efficiency changed to 94 % (everything else unchanged), what is the design-point PUE? Answer to 3 decimals.", pue94, "-", "Re-run the load model with efficiency 94 %: the UPS loss rises and the distribution losses rise with it.", 0.0005)],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 03
    cfg_t4 = _with(cfg, equipment__transformer_rating=4000)
    tx4 = next(s for s in size_power_system(cfg_t4, estimate_loads(cfg_t4)).transformer.scenarios if s.id == "TX-PATH-OUT")
    M.append(Module(3, "Electrical Architecture, A/B Paths and Redundancy",
        ["Explain 2N, N+1 and dual-corded loads.", "List the credible contingencies for a dual-path design.", "Calculate loading of the surviving equipment after loss of a path or a unit.", "Say what a redundancy check does and does not prove."],
        ["In a 2N arrangement there are two complete, independent paths and each can carry the whole critical load. In N+1 there is one spare unit beyond what the load needs. A common data centre concept is 2N for the UPS and transformer path and "
         "N+1 for the generators inside each path. IT equipment with two power supplies (dual-corded) is fed from both paths, so losing one path moves its load to the other.",
         "The sizing question is therefore always: what does the surviving equipment carry after the credible failure, and is that within its derated continuous rating and the project's loading limits. Loss of one path doubles the share on the other. "
         "Loss of a path and a unit at the same time is a double contingency: it is shown for information unless the project decides it is credible.",
         "Redundancy arithmetic does not prove independence. Two paths fed from one upstream busbar, one fuel tank or one control system are not independent. That is a design review item, not a formula."],
        [("Loading", "loading = load / (units x rating x derating)", "same unit throughout"), ("N+1 test", "load <= (n - 1) x rating", "n units per path")],
        [f"Reference project: path-out loads one transformer with {tx_w.load:,.0f} kVA against a derated {tx_w.capacity_total:,.0f} kVA: {tx_w.loading * 100:.1f} % (preliminary).",
         f"Normal operation loads each path at about half: {next(s for s in sz.transformer.scenarios if s.id == 'TX-NORMAL').loading * 100:.1f} %.",
         f"Generators: {gen.units_per_path} units per path. Worst credible case ({gen.worst_credible.id}) {gen.worst_credible.loading * 100:.1f} % of kVA; with one unit out in normal operation {unit_out.loading * 100:.1f} %. Workbook 03_POWER_ARCHITECTURE shows all the scenarios."],
        ["Calling a design N+1 without checking the load is carried with one unit out.", "Assuming two paths are independent because there are two of everything.", "Ignoring the maintenance case."],
        ["Is each contingency named and its loading calculated?", "Is the double contingency decision recorded?", "Are common points of failure listed?"],
        [Exercise("3.1", f"With the reference load ({tx_w.load:,.0f} kVA on one path after loss of the other), the transformers are changed to 4,000 kVA each. What is the path-out loading, in percent of the derated rating?", tx4.loading * 100, "%",
                  "loading = load / (1 x 4000 x 1.0)", 0.002),
         Exercise("3.2", "A path has 3 generators of 2,000 kVA (derating 1.0). What is the largest load it can carry with one unit out at 80 % of the remaining capacity?", 2 * 2000 * 0.8, "kVA", "(3 - 1) x 2000 x 0.8")],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 04
    req_t = sz.transformer.required_rating_each_for_target
    M.append(Module(4, "MV Distribution and Transformer Sizing",
        ["Size a transformer against the worst credible contingency with derating applied first.", "Explain the difference between a preferred loading target and a maximum.", "Describe what the impedance does to the fault level.",
         "State what must come from the transformer manufacturer."],
        ["Transformer loading is the load divided by the derated continuous rating. Derating comes first: ambient temperature, altitude and installation reduce what the transformer can carry continuously, and the factors come from the manufacturer's loading guide. "
         "Short-duration emergency overload may exist, but it is not used to justify continuous loading.",
         "A project may set a preferred target (here 90 %) and a hard maximum (100 %). A result between them is a WARNING: it needs a decision, not necessarily a change. Such a decision is recorded as an exception with a ceiling and a verification action. "
         "An exception never turns a warning into a pass.",
         "The impedance of the transformer sets the fault level downstream: a lower impedance passes more fault current. The LV fault level is limited by the transformer impedance whatever the utility's fault level, which gives a useful upper bound before any utility data exists."],
        [("Derated rating", "S_derated = S x k_amb x k_alt x k_inst", "kVA"), ("Rating for a target", "S_needed = S_load / (units x target x k)", "kVA"), ("Transformer-limited fault current", "I_k'' = c x U / (sqrt3 x K_T x z x U^2 / S_r)", "z per unit")],
        [f"Path-out: {tx_w.load:,.0f} kVA on one {tx_kva:,.0f} kVA transformer (derating 1.00 placeholders) = {tx_w.loading * 100:.2f} % against a 90 % target: WARNING.",
         f"A rating of {req_t:,.0f} kVA each would meet the 90 % target; the owner accepted the exception up to 91.0 % pending verification." if req_t else "",
         (f"With a {uk:g} % impedance the transformer-limited LV figure is {bound.ik_ka:,.1f} kA: the most the utility can contribute through that transformer. It excludes generators and motors, so it is not the bus fault level." if bound else "The transformer-limited fault level needs the transformer impedance.")],
        ["Applying the loading limit to the nameplate instead of the derated rating.", "Using overload capability to make a continuous load fit.", "Picking a larger transformer without checking what it does to the fault level."],
        ["Are the derating factors from the manufacturer's curve at the site conditions?", "Is the contingency case the one that governs?", "Is the exception, if any, recorded with a ceiling?"],
        [Exercise("4.1", "A path-out load of 2,866 kVA must be carried by one transformer at no more than 90 % of its derated rating, with a combined derating factor of 0.95. What nameplate rating is needed?", 2866 / (0.9 * 0.95), "kVA", "S = 2866 / (0.90 x 0.95)"),
         Exercise("4.2", "For a 2,500 kVA, 6 % transformer at 400 V with a voltage factor c = 1.05, what is the transformer-limited fault level in kA? Use the correction factor K_T = 0.95 c / (1 + 0.6 x 0.06).", 
                  1.05 * 400 / (SQ3 * 0.06 * 400 ** 2 / 2.5e6 * (0.95 * 1.05 / (1 + 0.6 * 0.06))) / 1000, "kA", "Z_T = K_T x 0.06 x 400^2 / 2.5e6; I = 1.05 x 400 / (sqrt3 x Z_T)", 0.002)],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 05
    M.append(Module(5, "Generator Sizing and Transient Performance",
        ["Distinguish prime power (PRP), emergency standby power (ESP) and continuous power (COP) ratings.", "Size N+1 generators in kVA and kW.", "Explain why load steps and the UPS rectifier matter.", "List the manufacturer data a generator study needs."],
        ["Generator ratings are defined in ISO 8528 and the three bases are not interchangeable. PRP allows unlimited running at variable load with a limit on the average load; ESP is for emergency standby with limited hours and is a poor basis for long outages; COP is for constant load. "
         "A rating quoted without its basis is not usable for sizing. The reference project assumes PRP and says that it is not confirmed.",
         "A generator has two limits: the alternator in kVA and the engine in kW. The engine kW is the kVA rating times the rated power factor (0.8 here is a placeholder). Both are checked. N+1 means the load must be carried with the largest unit out.",
         "Steady-state loading is not enough. A UPS rectifier or a large motor applies a step; the generator's frequency and voltage dip depend on the step size, the engine, the alternator and the controls. UPS rectifiers also draw harmonic current that "
         "loads the alternator. These need manufacturer data, so the engine reports an upper bound on the step and marks the result NOT VERIFIED."],
        [("Engine rating", "P_engine = S_rated x pf_rated", "kW"), ("N+1 loading", "loading = load / ((n - 1) x rating x derating)", "")],
        [f"{gen.units_per_path} x {v('equipment.generator_rating'):,.0f} kVA per path. Worst credible case (loss of the other path, all units available): {gen.worst_credible.loading * 100:.1f} % of kVA and {gen_kw.worst_credible.loading * 100:.1f} % of kW.",
         f"With one unit out in normal operation: {unit_out.loading * 100:.1f} % of kVA. Path out and one unit out together is beyond N+1 and is shown for information only: {dbl.loading * 100:.1f} % of kVA.", "The step-load check, prime-power load factor and hours restriction all read NOT VERIFIED because the manufacturer data is missing."],
        ["Using an ESP rating as if it were prime power.", "Checking kVA only and missing the engine kW limit.", "Reading a low loading percentage as good: light load needs the manufacturer's minimum-load guidance."],
        ["Is the rating basis stated and confirmed?", "Are kW and kVA both checked?", "Is the largest-unit-out case calculated?", "Are step loads and harmonics covered by manufacturer data?"],
        [Exercise("5.1", "A generator is rated 2,000 kVA at power factor 0.8. What is its engine kW rating?", 1600.0, "kW", "2000 x 0.8"),
         Exercise("5.2", "A path must carry 2,687 kW. Each generator is rated 1,600 kW and the target is 80 % of the remaining capacity with one unit out. What is the smallest number of generators per path?", float(math.ceil(2687 / (1600 * 0.8)) + 1), "units",
                  "Needed running units = ceil(2687 / (1600 x 0.8)) = 3; add one spare for N+1.", 0.0)],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 06
    ex6 = 2000 * 15 / 60
    M.append(Module(6, "UPS Architecture and Battery Sizing",
        ["Check a UPS in both kW and kVA.", "Explain why a battery cannot be sized from energy alone.", "Calculate the energy a battery must deliver.", "List the manufacturer data a battery calculation needs."],
        ["A UPS has an active power rating in kW and an apparent power rating in kVA. A load with power factor below unity can reach the kVA limit before the kW limit. The reference UPS is 2,500 kW and 2,500 kVA, so a 0.95 power factor load is kVA-limited.",
         "In a 2N design each UPS must carry the whole critical load when the other path is lost. The battery bridges the time until the generators accept load. The energy at the UPS output is the critical load times the autonomy. That is arithmetic, not a battery selection: "
         "batteries are sized from the manufacturer's constant-power discharge table at end of life and the room temperature, because capacity falls as the discharge rate rises.",
         "Ageing, temperature and design margin factors convert the energy into a nameplate energy. They are battery-specific and are never assumed in the Ohmetry package."],
        [("Energy at the UPS output", "E = P x t / 60", "P in kW, t in min, E in kWh"), ("Indicative nominal energy", "E_nom = E / eta_inv / (k_EOL x k_temp) x k_margin", "kWh")],
        [f"Critical load {bat.ups_output_kw:,.0f} kW for {bat.autonomy_min:g} min = {bat.energy_at_ups_output_kwh:,.1f} kWh at the UPS output.",
         f"UPS kW loading {ups_kw.worst_credible.loading * 100:.1f} % and kVA loading {ups_kva.worst_credible.loading * 100:.1f} %: the kVA limit governs (check {next(c for c in checks if c.id == 'ups_loading_kva').status.value}).",
         "No battery is selected: the discharge data and correction factors are pending."],
        ["Sizing a battery from nameplate ampere-hours without the discharge table.", "Checking the UPS in kW only.", "Forgetting the inverter efficiency between the battery and the load."],
        ["Is the autonomy time tied to the generator start and transfer time?", "Are end-of-life and temperature factors from the manufacturer?", "Are kW and kVA both within limits?"],
        [Exercise("6.1", "A UPS must supply 1,800 kW for 12 minutes. What energy must the battery deliver at the UPS output?", 1800 * 12 / 60, "kWh", "E = 1800 x 12 / 60"),
         Exercise("6.2", "Teaching values (not data): the energy is 360 kWh, inverter efficiency 96 %, end-of-life factor 0.8, temperature factor 0.95, margin 1.1. What is the indicative nominal energy?", 360 / 0.96 / (0.8 * 0.95) * 1.1, "kWh",
                  "E_nom = 360 / 0.96 / (0.8 x 0.95) x 1.1")],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 07
    lvsw = next(x for x in dist.switchgear if x.tag.startswith("LV"))
    M.append(Module(7, "LV Distribution and Switchgear Selection",
        ["Calculate the rated current a busbar or busduct must have.", "Explain verification evidence for assemblies.", "Link the short-circuit rating to the fault level.", "Describe the data a switchgear specification needs."],
        ["Low-voltage assemblies are specified by rated current, short-circuit withstand, form of separation, ingress protection and evidence that the design was verified (IEC 61439). Medium-voltage switchgear follows IEC 62271. The assembly's ratings come from the manufacturer's "
         "verification, not from the project. The designer states the requirement and checks the evidence.",
         "The required rated current is the design current divided by the derating factors. The short-circuit rating must exceed the prospective fault level at the busbars, including the peak current, and the breaking capacity of each breaker must exceed the fault level at its location.",
         "In the reference project the required busbar current is large, which is why busduct and a well-designed switchboard layout matter. Ratings are not assumed: the workbook reads NOT VERIFIED until a rating and its evidence are entered."],
        [("Required rated current", "I_rated = I_design / k", "A"), ("Short-circuit test", "I_cw >= I_k''", "kA")],
        [f"LV main switchboard design current {lvsw.design_current_a:,.0f} A (path-out). Required rated current with derating 1.0: {lvsw.required_rating_a:,.0f} A.",
         "The short-circuit rating needed is the LV fault level, which is NOT CALCULATED until utility data exists; the transformer-limited bound is the first available number."],
        ["Selecting a rating from a catalogue before the fault level is known.", "Accepting a rating without the verification evidence.", "Forgetting that derating applies to busbars as well as cables."],
        ["Are rated current, short-circuit rating, separation and IP rating all specified?", "Is the verification evidence listed?", "Is the peak withstand checked?"],
        [Exercise("7.1", "A switchboard carries a design current of 4,136 A with a combined derating factor of 0.9. What rated current is required?", 4136 / 0.9, "A", "I = 4136 / 0.9"),
         Exercise("7.2", "A switchboard is rated 65 kA for 1 s and the fault level is 74 kA. Does it pass? Answer PASS or FAIL.", "FAIL", "", "65 < 74")],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 08
    from ohmetry_dc.calculations.distribution import resistance_ohm_per_m
    r630 = resistance_ohm_per_m("copper", 630, 90.0)
    ex8 = SQ3 * 400 * 30 * (0.0000349 * 0.8 + 0.00008 * 0.6) / 400 * 100
    M.append(Module(8, "Cable Sizing, Ampacity and Voltage Drop",
        ["Calculate conductor resistance at an operating temperature.", "Calculate three-phase voltage drop.", "Explain why a tabulated current rating is never assumed.", "Check thermal withstand against a fault."],
        ["A cable must carry the design current within its tabulated rating (after grouping, ambient and installation derating), keep the voltage drop within the project limit, and survive the fault current for the clearing time. The tabulated rating comes from the standard "
         "for the installation method or from the manufacturer; it depends on the cable construction and layout and is not assumed.",
         "Resistance rises with temperature: R = rho20 x (1 + alpha x (T - 20)) / A. Voltage drop in a three-phase circuit is sqrt3 x I x L x (R cos phi + X sin phi). Reactance depends on the layout (trefoil, flat, spacing) and is an input.",
         "The adiabatic equation S >= I x sqrt(t) / k gives the smallest conductor that survives a fault of I for t seconds. With parallel cables the fault current divides between runs. The clearing time comes from the protection study."],
        [("Resistance", "R = rho20 (1 + alpha (T - 20)) / A", "ohm per m with A in mm2"), ("Voltage drop", "dV = sqrt3 I L (R cos phi + X sin phi)", "V"), ("Thermal withstand", "S >= I sqrt(t) / k", "mm2")],
        [f"630 mm2 copper at 90 C: R = {r630 * 1e6:.2f} micro-ohm per metre.", f"Generator cables CAB-GEN-A: {gcab.design_current_a:,.0f} A on {gcab.runs} runs ({gcab.design_current_a / gcab.runs:,.0f} A per run), voltage drop {gcab.voltage_drop_pct:.3f} % against a 3 % limit.",
         "The tabulated rating is missing, so the ampacity reads NOT VERIFIED while the required rating per run is shown."],
        ["Assuming a rating from memory instead of the table for the installation method.", "Using the 20 C resistance for a hot cable.", "Applying the whole fault current to one run of a parallel group."],
        ["Is the installation method stated and the table from the matching standard?", "Are grouping and ambient factors applied?", "Is the clearing time from the protection study?"],
        [Exercise("8.1", "A 120 mm2 copper conductor operates at 90 C (rho20 = 0.017241 ohm.mm2/m, alpha = 0.00393). What is its resistance in milliohm per metre?", 0.017241 * (1 + 0.00393 * 70) / 120 * 1000, "mohm/m", "R = 0.017241 x (1 + 0.00393 x 70) / 120"),
         Exercise("8.2", "A circuit carries 300 A per run over 40 m at 400 V, power factor 0.9, R = 0.07 mohm/m, X = 0.08 mohm/m. What is the three-phase voltage drop in percent?", SQ3 * 300 * 40 * (0.00007 * 0.9 + 0.00008 * math.sqrt(1 - 0.81)) / 400 * 100, "%",
                  "dV = sqrt3 x 300 x 40 x (0.00007 x 0.9 + 0.00008 x 0.4359); divide by 400", 0.002)],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 09
    M.append(Module(9, "Short-Circuit Fundamentals and Protection Coordination",
        ["Describe the IEC 60909 steps for a maximum fault level.", "Explain peak and thermal equivalent currents.", "Say what selectivity is and what it needs.", "List the data a coordination study cannot do without."],
        ["The initial symmetrical short-circuit current is Ik'' = c x U / (sqrt3 x |Z|), where Z is the total impedance from the sources to the fault and c is a voltage factor. Sources are the utility, the transformer and the generators, each converted to an impedance at the "
         "fault voltage. The peak current is kappa x sqrt2 x Ik'', and the thermal effect of a fault of duration t is the thermal equivalent current. Equipment must withstand all three.",
         "The utility's fault level and X/R ratio are written statements from the utility. Transformer impedance and generator reactance are manufacturer data. Until they exist the engine reports NOT CALCULATED and does not substitute defaults. "
         "The transformer-limited bound, which needs only the transformer data, is a legitimate first number.",
         "Selectivity (discrimination) means only the device nearest the fault trips. It needs the time-current curves of every device and a study at the relevant fault levels. Without curves it cannot be asserted, so the protection workbook never reports a coordination pass."],
        [("Initial fault current", "Ik'' = c U / (sqrt3 |Z|)", "kA"), ("Peak current", "ip = kappa sqrt2 Ik''", "kA"), ("Peak factor", "kappa = 1.02 + 0.98 exp(-3 R/X)", "-")],
        [(f"Reference project: transformer-limited LV bound {bound.ik_ka:,.1f} kA with the {uk:g} % preliminary impedance." if bound else "Transformer impedance is pending."),
         "Utility, generator and parallel cases read NOT CALCULATED: the utility fault level and generator reactance are not supplied.", "Protection coordination reads NOT VERIFIED: no device curves, no network study."],
        ["Selecting equipment ratings before the fault level exists.", "Adding the generator and utility contributions when they never run in parallel (or forgetting to when they do).", "Calling a coordination chart a study without the manufacturers' curves."],
        ["Is the maximum and the minimum fault level calculated?", "Is the operating arrangement (open or closed transition) decided?", "Are device curves and a study reference recorded?"],
        [Exercise("9.1", "A source has R/X = 0.1 (X/R = 10) and Ik'' = 40 kA. What is the peak current?", (1.02 + 0.98 * math.exp(-3 / 10)) * math.sqrt(2) * 40, "kA", "kappa = 1.02 + 0.98 exp(-0.3); ip = kappa sqrt2 x 40", 0.002),
         Exercise("9.2", "A utility has S''kQ = 250 MVA at 13.8 kV with c = 1.10. What is the initial fault current at the MV bus in kA?", 250e6 / (SQ3 * 13800) / 1000, "kA", "Ik'' = S / (sqrt3 U) because Z = c U^2 / S", 0.002)],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 10
    from ohmetry_dc.calculations.earthing import grid_resistance
    rg = grid_resistance(100, 2500, 1200, 0.5)
    M.append(Module(10, "Earthing, Bonding, Lightning and Power Quality",
        ["Estimate a grid resistance and ground potential rise.", "Explain touch and step voltage and why a screening is not a design.", "Say what a lightning risk assessment decides.", "Calculate voltage unbalance and THD from measurements."],
        ["Earthing serves safety (touch and step voltages), protection (a low-impedance path for fault current) and function. The grid resistance depends on the soil resistivity and the grid geometry. The ground potential rise is the earth-fault current into the grid times "
         "that resistance. If it is below the tolerable touch voltage, a screening passes; if not, a detailed mesh and step calculation is needed.",
         "Lightning protection starts with a risk assessment (IEC 62305-2). The equivalent collection area and the flash density give the expected number of dangerous events, one input to the risk. Compliance cannot be claimed without a complete assessment.",
         "Power quality is measured, not designed from a formula: voltage unbalance, harmonic distortion, flicker and frequency are compared with limits taken from the project requirements. The measurement instrument and conditions are part of the evidence."],
        [("Grid resistance (Sverak)", "Rg = rho [1/L + 1/sqrt(20 A) (1 + 1/(1 + h sqrt(20/A)))]", "ohm"), ("Ground potential rise", "GPR = Ig x Rg", "V"), ("THD", "THD = sqrt(sum Vh^2) / V1", "%"),
         ("Unbalance", "max deviation from the mean / mean", "%")],
        ["Soil resistivity, grid geometry and earth-fault current are pending site data in the reference project; the earthing workbook reads NOT CALCULATED.",
         f"Teaching inputs only (not project data): 100 ohm.m soil, 2,500 m2, 1,200 m of conductor, 0.5 m depth give Rg = {rg:.3f} ohm.", "Power quality and lightning workbooks are input registers: they calculate only from the measurements and site data you enter."],
        ["Assuming soil resistivity instead of surveying it.", "Treating a screening pass as an earthing design.", "Claiming lightning compliance from a collection area."],
        ["Is there a soil survey with the method stated?", "Is the clearing time from the protection study?", "Are the PQ limits taken from the project requirements, with the instrument stated?"],
        [Exercise("10.1", "Teaching inputs: soil 100 ohm.m, grid area 2,500 m2, buried conductor 1,200 m, depth 0.5 m. What is the grid resistance in ohm?", rg, "ohm", "Rg = 100 [1/1200 + 1/sqrt(50000) (1 + 1/(1 + 0.5 sqrt(20/2500)))]", 0.002),
         Exercise("10.2", "Line voltages measured 400, 404 and 396 V. What is the voltage unbalance (maximum deviation from the mean divided by the mean) in percent?", 1.0, "%", "mean = 400; max deviation = 4; 4/400 = 1 %", 0.001)],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 11
    n_status = {k: v_ for k, v_ in st.items() if v_}
    M.append(Module(11, "Single-Line Diagrams, Schedules and Engineering Reports",
        ["Read a single-line diagram and trace a load back to its source.", "Keep tags consistent across drawings, schedules and calculations.", "Read the four-status result table.", "Write a limitation statement."],
        ["A single-line diagram shows how the power flows and where the protection sits. Every item has a tag, and the tag is the key that joins the drawing, the equipment schedule, the calculations and the specifications. A diagram that cannot be traced to a calculation is a sketch.",
         "Results are reported with four separate statuses. The calculation status says whether the arithmetic ran on complete inputs. The calculation result says what the numbers show against the criterion. The input-data status says what the inputs are (assumption, placeholder, "
         "manufacturer data supplied, verified). The overall design status can be PASS only when the calculation passes and the inputs are verified. A preliminary pass reads NOT VERIFIED.",
         "A report states its scope, its inputs and their status, its limitations, and what it does not cover. Approval fields are filled by the people who approve, never by the software."],
        [("Overall status rule", "PASS only if the calculation passes AND every input is verified, reference data or an owner decision", "")],
        [f"Reference project at this revision: {n_status.get('PASS', 0)} checks PASS (all arithmetic or consistency checks), {n_status.get('WARNING', 0)} WARNING, {n_status.get('FAIL', 0)} FAIL, {n_status.get('NOT VERIFIED', 0)} NOT VERIFIED.",
         "The single-line diagram OHM-DC-2000-SLD-001 and the equipment schedule use the same tags as the workbooks."],
        ["Inventing tags in each document.", "Showing ratings on a diagram that were never calculated.", "Filling approval fields on behalf of reviewers."],
        ["Do all documents share one tag list?", "Does every rating on a diagram trace to a calculation or a datasheet?", "Is the status of each rating visible?"],
        [Exercise("11.1", "A check's calculation result is PASS and its input status is UNVERIFIED_PLACEHOLDER. What is the overall design status?", "NOT VERIFIED", "", "A pass on unverified inputs is not evidence the design works."),
         Exercise("11.2", "A check's calculation result is WARNING on preliminary inputs. What is the overall design status?", "WARNING", "", "A preliminary exceedance is still reported.")],
        REFS_COMMON, GEN_LIMITS))

    # ---------------------------------------------------------------- 12
    gen_rating_kw = v("equipment.generator_rating") * v("equipment.generator_rating_power_factor")
    M.append(Module(12, "Commissioning, FAT, SAT and Integrated Systems Testing",
        ["Distinguish factory acceptance, site acceptance and integrated systems testing.", "Plan a failure test sequence.", "Calculate load bank sizes and test energy.", "Describe what records a test must leave."],
        ["Factory acceptance tests (FAT) prove a unit against its specification at the factory. Site acceptance tests (SAT) prove installation and function on site. Integrated systems testing (IST) proves the whole chain under failure: utility loss, generator start and transfer, "
         "UPS and battery behaviour, loss of a path, and return to normal. The acceptance criteria come from the specification and the manufacturer data, not from this course.",
         "Tests are planned with prerequisites, a step sequence, expected results and abort criteria. A load bank supplies a known load so that the generator and UPS can be loaded without the IT load. Records must name the instrument, the calibration, the date and the person.",
         "Commissioning is where a design's assumptions are tested. Every NOT VERIFIED item in the design record should either be closed by a test or carried forward as a stated risk."],
        [("Load bank size", "P_bank = target % x P_rated - P_existing", "kW"), ("Autonomy test energy", "E = P x t / 60", "kWh")],
        [f"Generator engine rating {gen_rating_kw:,.0f} kW (placeholder). To test one unit at 80 % with no other load needs a {0.8 * gen_rating_kw:,.0f} kW load bank.",
         f"A battery autonomy test at the critical load ({bat.ups_output_kw:,.0f} kW) for {bat.autonomy_min:g} min removes {bat.energy_at_ups_output_kwh:,.0f} kWh from the batteries.",
         "Typical IST steps: simulate utility loss; confirm generator start, transfer and UPS behaviour; lose a path; restore. Each step has an expected result written beforehand."],
        ["Testing before the prerequisites (protection settings, interlocks) are verified.", "Not recording instrument calibration.", "Treating a test passed on a load bank as proof of behaviour under the real, non-linear IT load."],
        ["Is there a written test procedure with expected results?", "Are safety isolations and abort criteria defined?", "Does every open NOT VERIFIED item map to a test or a stated risk?"],
        [Exercise("12.1", "A generator has an engine rating of 1,600 kW. Its existing load is 400 kW. What load bank is needed to test it at 75 % of its rating?", 0.75 * 1600 - 400, "kW", "0.75 x 1600 - 400"),
         Exercise("12.2", "An autonomy test runs a 1,500 kW load for 9 minutes. How much energy leaves the batteries at the UPS output?", 1500 * 9 / 60, "kWh", "E = 1500 x 9 / 60")],
        REFS_COMMON, GEN_LIMITS))
    return M


def build_question_bank(modules: list[Module]) -> list[dict]:
    """Multiple-choice questions, four per module. Each has the correct option index, an explanation, and the module number."""
    Q = {
        1: [("Which statement about a data centre power chain is correct?", ["Generators carry the load in normal operation", "The UPS bridges the time until generators accept load", "Transformers store energy", "Switchgear sets the IT load"], 1, "The UPS and battery carry the load during the gap."),
            ("What does 'worst credible contingency' mean?", ["The largest load in normal operation", "The most onerous failure the design is required to survive", "Any failure that can be imagined", "The first failure in the schedule"], 1, "It is the most onerous failure the project has decided is credible."),
            ("Which of these is manufacturer data?", ["Target PUE", "Transformer short-circuit impedance", "Number of power paths", "Loading target"], 1, "Impedance comes from the test report."),
            ("Apparent power for P = 300 kW and Q = 400 kvar is:", ["700 kVA", "500 kVA", "100 kVA", "350 kVA"], 1, "sqrt(300^2 + 400^2) = 500.")],
        2: [("Why are kvar added separately from kW?", ["They are different units of the same thing", "Reactive and real power are different quantities; apparent power is the vector sum", "Because kvar is smaller", "It is a convention only"], 1, "S = sqrt(P^2 + Q^2)."),
            ("UPS losses increase when:", ["Efficiency rises", "Efficiency falls", "IT load is constant and efficiency constant", "PUE is below 1"], 1, "Loss = P x (100/eta - 1)."),
            ("A design-point PUE is:", ["The annual PUE", "A power ratio at the design point", "Always below 1.2", "Measured"], 1, "It is a ratio of power, not annual energy."),
            ("PUE below 1.0 is:", ["Possible with free cooling", "Not possible: facility power cannot be below IT power", "Normal for large sites", "A sign of good design"], 1, "Facility power includes the IT load plus overhead.")],
        3: [("2N means:", ["One spare unit", "Two complete independent paths, each able to carry the whole load", "Two generators", "Two UPS in series"], 1, "Each path can carry the whole critical load."),
            ("N+1 for generators means:", ["Load carried with the largest unit out", "Load carried only with all units", "Two generators per path", "One generator per two paths"], 0, "The load must be carried with one unit out."),
            ("Two paths fed from one upstream busbar are:", ["Independent", "Not independent at that point", "Always acceptable", "2N+1"], 1, "A shared point is a common failure."),
            ("Loss of a path and a unit together is:", ["Always judged against limits", "A double contingency, informational unless the project decides it is credible", "Impossible", "Normal operation"], 1, "It is beyond N+1.")],
        4: [("Transformer loading is calculated against:", ["The nameplate rating", "The derated continuous rating", "The short-time rating", "The fault rating"], 1, "Derating first."),
            ("A result between the target and the maximum is:", ["PASS", "WARNING needing a decision", "FAIL", "Not applicable"], 1, "It needs a recorded decision."),
            ("A lower transformer impedance gives:", ["A lower fault level", "A higher fault level", "No change", "A lower voltage"], 1, "Less impedance passes more fault current."),
            ("Emergency overload capability may be used to:", ["Justify continuous loading", "Nothing in continuous sizing", "Replace derating", "Raise the target"], 1, "It is not used for continuous loading.")],
        5: [("PRP, ESP and COP are:", ["The same rating", "Different ISO 8528 rating bases", "Brands", "Fuel types"], 1, "They are not interchangeable."),
            ("Engine kW for 2,000 kVA at 0.8 power factor is:", ["2,000", "1,600", "2,500", "1,200"], 1, "kVA x pf."),
            ("Why are generator load steps assessed?", ["Steps cause frequency and voltage dips that depend on the unit", "Steps change the fuel", "Steps change the rating basis", "They are not relevant"], 0, "Needs manufacturer data."),
            ("A very low generator loading percentage is:", ["Always good", "Not automatically good: minimum-load guidance applies", "A FAIL", "Impossible"], 1, "Light running has its own limits.")],
        6: [("A battery is sized from:", ["Ampere-hours on the nameplate", "The manufacturer's constant-power discharge data at end of life", "The UPS kVA", "The generator rating"], 1, "Capacity depends on discharge rate."),
            ("Energy for 2,000 kW over 10 min is:", ["333 kWh", "200 kWh", "20,000 kWh", "3.3 kWh"], 0, "2000 x 10 / 60."),
            ("A load with power factor 0.95 on a UPS rated 2,500 kW / 2,500 kVA is limited by:", ["kW first", "kVA first", "Neither", "Both equally"], 1, "kVA = kW / 0.95 is larger."),
            ("In 2N each UPS carries, after the other path is lost:", ["Half the load", "The whole critical load", "Nothing", "The mechanical load"], 1, "That is the point of 2N.")],
        7: [("Required rated current is:", ["Design current times derating", "Design current divided by derating", "Fault current", "Nameplate current"], 1, "I / k."),
            ("A switchboard short-circuit rating must exceed:", ["The load current", "The prospective fault level at the busbars", "The transformer rating", "The cable rating"], 1, "Including the peak current."),
            ("IEC 61439 verification evidence comes from:", ["The project designer", "The assembly manufacturer's verification", "The utility", "The cable maker"], 1, "The designer checks the evidence."),
            ("Ratings in the Ohmetry workbooks without entered data read:", ["PASS", "NOT VERIFIED", "FAIL", "Assumed"], 1, "They are never assumed.")],
        8: [("Conductor resistance at 90 C compared with 20 C is:", ["Lower", "Higher", "The same", "Zero"], 1, "Resistance rises with temperature."),
            ("A tabulated current rating comes from:", ["Memory", "The standard for the installation method or the manufacturer", "The voltage drop", "The fault level"], 1, "It depends on construction and layout."),
            ("Fault current in a parallel cable group:", ["Goes through one run", "Divides between runs", "Is zero", "Doubles"], 1, "Per-run share."),
            ("The adiabatic equation gives:", ["Voltage drop", "Minimum conductor area for a fault of given duration", "Ampacity", "Resistance"], 1, "S >= I sqrt(t) / k.")],
        9: [("The utility fault level comes from:", ["A default table", "The utility's written statement", "The transformer", "The generator"], 1, "It is a site/utility input."),
            ("The peak current factor kappa depends on:", ["X/R", "Voltage", "Frequency only", "Cable length"], 0, "kappa = 1.02 + 0.98 exp(-3 R/X)."),
            ("Selectivity can be asserted from:", ["The number of breakers", "Device time-current curves and a study", "Rated currents", "Colour codes"], 1, "Curves and a validated study."),
            ("The transformer-limited bound needs:", ["The utility fault level", "Only the transformer rating and impedance", "Generator data", "Soil data"], 1, "It assumes an infinite source.")],
        10: [("Ground potential rise is:", ["Earth-fault current times grid resistance", "Grid resistance times voltage", "Soil resistivity times area", "Touch voltage"], 0, "GPR = Ig x Rg."),
             ("A screening pass for touch voltage means:", ["The earthing is designed", "No further study is needed", "A detailed mesh and step calculation may still be required", "Lightning is protected"], 2, "It is only a screening."),
             ("Lightning compliance can be claimed with:", ["A collection area", "A complete verified risk assessment and design", "A flash density", "A catalogue"], 1, "Not otherwise."),
             ("Voltage unbalance for 400, 404, 396 V is:", ["0.5 %", "1 %", "2 %", "4 %"], 1, "4/400.")],
        11: [("Tags are used to:", ["Decorate drawings", "Join drawings, schedules and calculations", "Number pages", "Replace revision control"], 1, "The shared key."),
             ("A preliminary PASS on unverified inputs reads overall:", ["PASS", "NOT VERIFIED", "FAIL", "WARNING"], 1, "A pass is not evidence."),
             ("Approval fields are filled by:", ["The software", "The people who approve", "The author", "Nobody"], 1, "Never by the software."),
             ("A drawing rating without a calculation or datasheet is:", ["Acceptable", "A sketch, not evidence", "Verified", "Approved"], 1, "It must trace to something.")],
        12: [("FAT stands for:", ["Final assembly test", "Factory acceptance test", "Fault analysis test", "Field alarm test"], 1, "A unit test at the factory."),
             ("Integrated systems testing proves:", ["A single unit", "The whole chain under failure", "Only the UPS", "Cable insulation"], 1, "The chain under failure."),
             ("A load bank result proves:", ["Behaviour under real non-linear IT load", "Capacity at a known resistive load, not the full behaviour", "Nothing", "Harmonics"], 1, "It is a different load."),
             ("Acceptance criteria come from:", ["This course", "The specification and manufacturer data", "A random choice", "The load bank"], 1, "Not from training material.")],
    }
    out = []
    for m in modules:
        for i, (q, opts, ans, why) in enumerate(Q[m.no], start=1):
            out.append({"id": f"Q{m.no:02d}.{i}", "module": m.no, "question": q, "options": opts, "answer_index": ans, "answer": opts[ans], "explanation": why})
    return out
