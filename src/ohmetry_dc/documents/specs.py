"""Technical specification templates for the main equipment (DOCX and PDF).

These are EDITABLE TEMPLATES, not issued specifications. Ratings are read from the master configuration and labelled with their data status. Every item the project
must decide is shown in [square brackets]. Standards are named, never quoted: clause numbers, limits and editions must be taken from the current documents and
confirmed by the project. Requirements are written in general terms; numbers appear only where they come from the configuration or are left for the project.
"""
from __future__ import annotations

from pathlib import Path

from ohmetry_dc import __version__
from ohmetry_dc.models import ProjectConfig
from ohmetry_dc.models import data_status as ds
from ohmetry_dc.reporting.manufacturer_register import build_rows, load_register_meta

from . import docx_tools as dx

TBD = "[To be determined by the project]"
DRAFT = "DRAFT TEMPLATE. NOT AN ISSUED SPECIFICATION. NOT FOR PROCUREMENT. PRELIMINARY VALUES ARE NOT MANUFACTURER-CONFIRMED."
SPEC_REV = "P1"

COMMON_TESTING = ["Routine tests on every unit as required by the applicable standard and this specification.", "Type-test reports or evidence for the design, issued by an accredited or recognised laboratory [project to define acceptable evidence].",
                  "Inspection and test plan (ITP) approved before manufacture, naming witness and hold points.", "Calibration certificates for test instruments."]


VENDOR = "[vendor to complete]"

COMMON_SAT = ["A SAT procedure shall be submitted for approval before the tests. It states the test, the method, the instrument, the acceptance criterion and the witness, with the criteria taken from the applicable standard and this specification [project to define].",
              "SAT is carried out on the installed equipment with its final connections, after the installation inspection and before commissioning loads are applied.",
              "Results are recorded on signed sheets. Any deviation, retest and concession is listed with its disposition. A SAT is not passed while a deviation is open.",
              "SAT results are compared with the FAT results; a significant difference is investigated and recorded."]

SAT = {
    "Transformers": ["Inspection for transport damage, nameplate and accessories; insulation resistance and ratio on site; confirmation of tap position, protection settings and alarm functions."],
    "Generators": ["Inspection of mountings, fuel and cooling connections; start tests; a load-bank test at the site conditions for the duration and steps in the approved procedure; control and protection function tests; paralleling and load-sharing tests where specified."],
    "UPS": ["Input and output checks; transfer to and from battery and bypass; maintenance bypass operation and interlocking; alarm and communications checks; a load test with the site load or load banks as approved."],
    "Batteries": ["Inspection, polarity and connection checks; insulation and voltage checks; an acceptance discharge test to the approved procedure; temperature and ventilation checks."],
    "MV_Switchgear": ["Insulation resistance and the tests of the approved procedure on the installed assemblies; mechanical operation and interlock checks; protection relay secondary injection; trip and close circuit checks."],
    "LV_Switchgear": ["Insulation resistance; mechanical operation and interlocking (including the utility-to-generator interlock); protection settings as set by the approved study; metering and communications checks."],
    "Cables": ["Visual check of routing, bending radius and glands; insulation resistance and the specified electrical test on every cable after installation; phase and sequence checks."],
    "Busduct": ["Visual and alignment check; joint torque verification; insulation resistance; continuity of the protective conductor; thermographic check under load [project to define]."],
    "Protection": ["Secondary injection of every relay function used; primary injection where specified; checks of CT and VT polarity, ratio and wiring; trip circuit supervision; settings read back and compared with the approved settings study."],
    "Earthing": ["Continuity of all bonds; earth resistance measurement by the specified method; comparison with the design values [project to define]."],
}

SUBMITTALS = [("Completed vendor data schedule (section 6) and compliance schedule (section 7)", "With the tender"), ("Datasheets and general arrangement drawings", "With the tender, final before manufacture"),
              ("Type-test reports and certificates for the offered design", "With the tender"), ("Inspection and test plan (ITP)", "Before manufacture"), ("FAT procedure and report", "Before and after the FAT"),
              ("Installation instructions and SAT procedure", "Before delivery"), ("Operation and maintenance manuals, as-built drawings and final data", "Before commissioning; as-built at handover"),
              ("Recommended spare parts and special tools lists", "With the tender and at handover"), ("Training plan and materials [project to define]", "Before commissioning"), ("Warranty terms [project to define]", "With the tender")]


def _p(cfg, pid):
    p = cfg.parameters[pid]
    return p.value, ds.data_status(p), p.unit


def _row(cfg, label, pid, note=""):
    v, s, u = _p(cfg, pid)
    if v is None:
        shown = TBD
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        shown = f"{v:,} {u}".replace(" -", "").strip()
    else:
        shown = str(v)
    return [label, shown, s + (f". {note}" if note else "")]


def _common_rows(cfg):
    return [["Nominal LV system", f"{cfg.value('electrical_system.lv_line_voltage'):g} V line-to-line, {cfg.value('electrical_system.frequency'):g} Hz, 3-phase", "PRELIMINARY_ASSUMPTION. Utility confirmation is the owner's statement, not independently verified"],
            ["MV supply", f"{cfg.value('electrical_system.mv_supply_voltage'):g} kV", "PRELIMINARY_ASSUMPTION. To be confirmed with the utility"],
            ["Design ambient temperature", f"{cfg.value('environment.design_ambient_temperature'):g} degC", "PRELIMINARY_ASSUMPTION. Site data to be confirmed"],
            ["Site altitude", f"{cfg.value('environment.site_altitude'):g} m", "PRELIMINARY_ASSUMPTION. Site data to be confirmed"],
            ["Prospective fault level", "[To be calculated: short-circuit study pending utility, transformer and generator data]", "NOT CALCULATED"]]


def _specs(cfg: ProjectConfig) -> list[dict]:
    from ohmetry_dc.calculations import assess_distribution, estimate_loads, size_power_system

    est = estimate_loads(cfg)
    dist = assess_distribution(cfg, est, size_power_system(cfg, est))
    lv_i = next(x for x in dist.switchgear if x.tag.startswith("LV")).required_rating_a
    bd = dist.busducts[0]
    R = lambda label, pid, note="": _row(cfg, label, pid, note)
    q = cfg.value("equipment.transformer_quantity")
    return [
        dict(id="01", slug="Transformers", title="Power Transformers", tags=("TX",), standards=["IEC 60076 series (power transformers)", "IEC 60076-7 (loading guide, mineral-oil-immersed)", "IEC 60076-11 (dry-type), if dry-type is selected", "IEC 60076-5 (ability to withstand short circuit)", "Local utility and authority requirements [project to add]"],
             ratings=[R("Quantity (total)", "equipment.transformer_quantity"), R("Rated power (each)", "equipment.transformer_rating", "Loading limits are applied to the derated rating"), R("Short-circuit impedance", "equipment.transformer_impedance", "Guaranteed value and tolerance from the manufacturer"),
                      ["Primary / secondary voltage", f"{cfg.value('electrical_system.mv_supply_voltage'):g} kV / {cfg.value('electrical_system.lv_line_voltage'):g} V", "PRELIMINARY_ASSUMPTION"], ["Type and cooling", "[Dry-type or liquid-immersed; cooling class: project to select]", "Project decision"],
                      ["Vector group, tap changer", "[Project to select]", "Project decision"], R("Derating (ambient, altitude, installation)", "derating.transformer_ambient_factor", "1.00 is a placeholder. Manufacturer's loading guide governs")],
             requirements=["The transformer shall carry its rated power continuously at the site conditions in the service-conditions table without exceeding the temperature-rise limits of the applicable standard.", "The manufacturer shall state the continuous rating at the site conditions and any derating for ambient temperature, altitude and enclosure.",
                           "The manufacturer shall not rely on short-duration emergency overload to meet the continuous loading requirement.", "The short-circuit impedance, tolerance, no-load and load losses shall be guaranteed values supplied in the tender and confirmed by test.",
                           "The transformer shall withstand the thermal and dynamic effects of the specified through-fault level for the specified duration; evidence by test or calculation per the applicable standard.", "Losses evaluation basis: [project to define].",
                           "Noise level, enclosure protection rating, temperature monitoring and protection accessories: [project to define].", f"Number of transformers per power path: {int(q) // int(cfg.value('redundancy.power_paths')) if q else TBD}; each path is to carry the whole facility load after loss of the other path."],
             inspection=["Review of design calculations, drawings and the inspection and test plan before manufacture.", "Inspection of materials certificates and core and winding processing at hold points defined in the ITP [project to define].", "Dimensional and nameplate check before shipment."],
             fat=["Routine tests per the standard: ratio and vector group, winding resistance, no-load loss and current, load loss and impedance voltage, applied voltage, induced voltage, insulation resistance.", "Temperature-rise test or evidence on a duplicate unit [project to define].", "Witnessing: [owner / independent inspector to attend]. Results recorded against the guaranteed values."],
             commissioning=["Visual and mechanical inspection, torque checks, insulation resistance, ratio and polarity.", "Protection and temperature-alarm function tests.", "Energisation sequence and thermography under load [project to define]."]),
        dict(id="02", slug="Generators", title="Standby Generator Sets", tags=("GEN",), standards=["ISO 8528 series (reciprocating engine driven generating sets)", "IEC 60034 series (rotating electrical machines)", "Local emissions, noise and fuel storage regulations [project to add]"],
             ratings=[R("Generators per power path", "equipment.generator_quantity_per_path", "N+1: the load is carried with the largest unit out"), R("Rated apparent power (each)", "equipment.generator_rating", "ASSUMED to be a PRP rating. NOT confirmed. ISO 8528: PRP, ESP and COP are different ratings"),
                      R("Rated power factor", "equipment.generator_rating_power_factor", "Engine kW is the kVA rating times this factor"), ["Rating basis required", "PRP (prime power) per ISO 8528-1, at the site conditions", "Project decision. ESP is not a basis for prolonged outages"],
                      R("Derating (ambient, altitude, installation)", "derating.generator_ambient_factor", "1.00 is a placeholder"), ["Load acceptance and transient limits", "[Frequency dip, voltage dip, recovery time: project to specify]", "Pending manufacturer data"]],
             requirements=["The generating set shall be rated for prime power (PRP) at the site conditions; the rating basis shall be stated on the datasheet and the nameplate.", "The manufacturer shall state kW and kVA ratings, the allowed average load factor and any hours restriction for the stated basis.",
                           "The set shall accept the stated load steps, including the UPS rectifier input with its walk-in, within the specified frequency and voltage limits; the manufacturer shall provide transient response data.", "The alternator shall be rated for the harmonic current of the UPS rectifier load [project to specify the harmonic data].",
                           "Minimum-load and light-load operation requirements shall be stated by the manufacturer.", "Control system, paralleling, synchronising, protection, fuel system, cooling, exhaust, starting system and enclosure: [project to define].", "Black-start capability and start-to-load time: [project to define]."],
             inspection=["Review of the set data sheet, alternator and engine data and the paralleling scheme.", "Inspection of the base frame, enclosure and fuel system components."],
             fat=["Factory test per ISO 8528 for performance class [project to define]: load runs at agreed steps, regulation, load acceptance and transient response.", "Protection and control function tests; paralleling and load sharing if applicable.", "Witnessing: [owner / independent inspector to attend]."],
             commissioning=["Pre-start checks, fuel and coolant, protection settings.", "Load bank test to rated load; transient tests with the real UPS load where possible.", "Utility-failure transfer and return tests with the switchgear; fuel runtime verification against the design basis."]),
        dict(id="03", slug="UPS", title="Uninterruptible Power Supply Systems", tags=("UPS",), standards=["IEC 62040 series (uninterruptible power systems), including performance classification", "IEC 61000 series (EMC and harmonics)", "IEEE 519 (harmonic limits), if adopted by the project"],
             ratings=[R("UPS per power path", "equipment.ups_quantity", "2N: each UPS carries the whole critical load after loss of the other path"), R("Rated active power (each)", "equipment.ups_rating"), R("Rated apparent power (each)", "equipment.ups_rating_kva", "Both kW and kVA limits apply"),
                      R("Efficiency (design point)", "equipment.ups_efficiency", "A single point. The manufacturer shall declare the efficiency curve"), R("Input power factor", "equipment.ups_input_power_factor"), ["Autonomy", f"{cfg.value('redundancy.battery_autonomy'):g} min at the design load", "PRELIMINARY_ASSUMPTION"],
                      ["Topology, bypass, paralleling", "[Project to select]", "Project decision"]],
             requirements=["The UPS shall deliver its rated kW and kVA continuously at the site conditions; overload capability shall be declared but shall not be used to meet continuous loading.", "The manufacturer shall declare efficiency at 25, 50, 75 and 100 per cent load [project to confirm the points].",
                           "The input current harmonic distortion, input power factor, rectifier walk-in time and generator compatibility shall be declared.", "Output voltage and frequency regulation, short-circuit contribution and fault clearing capability shall be declared.", "Battery interface, monitoring, alarms, communication and maintenance bypass: [project to define]."],
             inspection=["Review of the datasheet, single-line and control philosophy.", "Inspection of enclosures and power components."],
             fat=["Functional tests: transfer to and from battery and bypass, load steps, overload behaviour within declared limits, efficiency measurement at the declared points.", "Input harmonics and walk-in verification [project to define].", "Witnessing: [owner / independent inspector to attend]."],
             commissioning=["Installation checks, battery connection checks, parameter and alarm checks.", "Load bank and autonomy test together with the battery; generator interaction test.", "Failure tests as part of integrated systems testing."]),
        dict(id="04", slug="Batteries", title="UPS Batteries", tags=("BAT",), standards=["IEC 60896 series (stationary lead-acid), if lead-acid is selected", "IEC 62619 (secondary lithium cells and batteries, safety), if lithium-ion is selected", "IEC 62485-2 (safety requirements for stationary batteries)", "IEEE 485 (sizing lead-acid batteries) as a method reference", "Local fire and ventilation regulations [project to add]"],
             ratings=[["Autonomy to be provided", f"{cfg.value('redundancy.battery_autonomy'):g} min at the critical load", "PRELIMINARY_ASSUMPTION"], ["Energy at the UPS output", f"{cfg.value('general.it_critical_load') * cfg.value('redundancy.battery_autonomy') / 60:,.0f} kWh (arithmetic, not a battery size)", "Preliminary"],
                      ["DC bus voltage, cell count, strings", TBD, "Pending manufacturer constant-power discharge data"], ["Chemistry and design life", "[Project to select]", "Project decision"], ["End-of-life capacity, temperature and design margin factors", TBD, "Pending manufacturer data"]],
             requirements=["The battery shall deliver the stated autonomy at the stated constant power to the end-of-discharge voltage at end of life and at the minimum room temperature.", "The manufacturer shall provide the constant-power discharge table (power per cell against time to the end voltage) for the offered cell.",
                           "The manufacturer shall state ageing, temperature correction and expected life and shall declare the capacity at the design discharge rate.", "Battery management, monitoring, protection, racks, seismic requirements and ventilation or gas management: [project to define].", "Thermal runaway and fire safety measures: [project to define with the authority]."],
             inspection=["Review of the cell datasheet, rack drawings and safety documentation.", "Inspection of delivery condition, cell voltages and torque."],
             fat=["Cell and module routine tests per the standard.", "Capacity and discharge tests on a sample [project to define]."],
             commissioning=["Installation checks, polarity, torque, insulation resistance.", "Initial charge per the manufacturer.", "Capacity or autonomy test with the UPS at the design load; records retained as the baseline."]),
        dict(id="05", slug="MV_Switchgear", title="Medium-Voltage Switchgear", tags=("MV-SWG", "MV-CB"), standards=["IEC 62271 series (high-voltage switchgear and controlgear), including metal-enclosed switchgear and circuit-breakers", "IEC 61869 series (instrument transformers)", "IEC 60255 series (measuring relays and protection equipment)", "Local utility requirements [project to add]"],
             ratings=[["Rated voltage", f"[Class for the {cfg.value('electrical_system.mv_supply_voltage'):g} kV system: project to select]", "Project decision"], ["Rated current", "[At least the required current; busbars need at least the incomer design current]", "Pending manufacturer data"],
                      ["Short-circuit rating (kA, duration) and peak", "[To be at least the calculated MV fault level]", "NOT CALCULATED: utility fault level pending"], ["Internal arc classification", "[Project to define]", "Project decision"], ["Protection and metering", "[Relay, CT and VT data: project to define]", "Pending"]],
             requirements=["The switchgear shall be type tested per the applicable standard; type-test reports shall be supplied.", "The short-circuit rating shall exceed the prospective fault level including the peak current, evidenced by test reports.", "Interlocking, earthing switches, operating mechanisms, auxiliary supplies and control voltage: [project to define].",
                           "Protection relays shall be programmable, with settings from the approved coordination study; the manufacturer shall supply device curves.", "Cable terminations, partial-discharge performance and arc-fault containment: [project to define]."],
             inspection=["Review of drawings, bill of materials, type-test reports and the ITP.", "Inspection of busbar insulation, clearances, interlocks and wiring at hold points [project to define]."],
             fat=["Routine tests: power-frequency voltage withstand, main circuit resistance, mechanical operation, interlock and wiring checks, protection secondary injection.", "Witnessing: [owner / independent inspector to attend]."],
             commissioning=["Insulation resistance and contact resistance, circuit-breaker timing, CT and VT checks.", "Protection secondary and primary injection as specified; settings verified against the approved study.", "Interlock and transfer scheme tests; energisation procedure."]),
        dict(id="06", slug="LV_Switchgear", title="Low-Voltage Switchgear and Assemblies", tags=("LV-MSB", "ACB-"), standards=["IEC 61439-1 and IEC 61439-2 (low-voltage switchgear and controlgear assemblies), design verification", "IEC 60947-2 (circuit-breakers)", "IEC 61869 series (instrument transformers)", "Local regulations [project to add]"],
             ratings=[["Rated voltage and frequency", f"{cfg.value('electrical_system.lv_line_voltage'):g} V, {cfg.value('electrical_system.frequency'):g} Hz", "PRELIMINARY_ASSUMPTION"], ["Busbar rated current", f"[At least the incomer design current after derating; preliminary {lv_i:,.0f} A (path-out)]", "Preliminary requirement, pending manufacturer data"],
                      ["Rated short-time withstand (kA, 1 s) and peak", "[To be at least the calculated LV fault level]", "NOT CALCULATED: utility, transformer impedance and generator data pending"], ["Form of separation, IP rating", "[Project to select]", "Project decision"], ["Circuit-breaker breaking and making capacity", "[At least the fault level at each location]", "Pending manufacturer data"]],
             requirements=["The assembly shall be design verified per IEC 61439-1 and -2; the verification evidence (test, calculation or design rule) shall be supplied for each rating, with the assembly manufacturer identified.", "The short-circuit withstand shall exceed the prospective fault level including the peak, at the busbars and at each outgoing device.",
                           "Circuit-breakers shall have breaking capacity above the fault level at their location; time-current characteristics shall be supplied for the coordination study.", "Temperature rise at the rated current and the site ambient shall be evidenced; derating of busbars at altitude and ambient shall be stated.", "Metering, monitoring, interlocking, transfer scheme and arc-fault mitigation: [project to define]."],
             inspection=["Review of design verification evidence, drawings and the ITP.", "Inspection of busbar supports, clearances, wiring and labelling."],
             fat=["Routine verification per IEC 61439: wiring, operation, dielectric, protective circuit continuity, mechanical function.", "Breaker functional tests and settings checks; transfer scheme simulation.", "Witnessing: [owner / independent inspector to attend]."],
             commissioning=["Torque and insulation resistance, phase sequence, protection tests, interlock and transfer tests.", "Load and thermography checks [project to define]."]),
        dict(id="07", slug="Cables", title="Power Cables", tags=("CAB-",), standards=["IEC 60502 series (power cables with extruded insulation)", "IEC 60287 series (cable current rating calculation)", "IEC 60364 series (installations), including current-carrying capacity", "Local fire performance requirements [project to add]"],
             ratings=[["Installation method (basis of the rating)", cfg.value("installation.cable_installation_method"), "PRELIMINARY_ASSUMPTION"], R("Conductor operating temperature", "cable_data.conductor_operating_temperature", "Of the chosen insulation"), R("Voltage drop limit", "design_criteria.voltage_drop_limit_pct", "Project criterion"),
                      ["Cable sizes and runs", "See the cable sizing workbook: illustrative selections only", "UNVERIFIED_PLACEHOLDER"], ["Tabulated current rating per run", "[From the cable standard or manufacturer for the installation method; never assumed]", "Pending"], ["Fault withstand", "[Conductor area to survive the calculated fault for the clearing time]", "NOT CALCULATED"]],
             requirements=["Each cable shall carry its design current after applying the grouping, ambient and installation derating factors, using a tabulated rating for the actual installation method.", "The cable shall keep the voltage drop within the project limit at the design current.",
                           "The conductor shall withstand the calculated fault current for the protection clearing time (adiabatic or manufacturer data).", "Insulation, sheath, armour, fire performance (flame propagation, smoke and halogen emission) and identification: [project to define].", "Parallel runs shall be of equal length and layout with the current sharing verified; bending radius and pulling tensions per the manufacturer."],
             inspection=["Review of type-test certificates and drum test records.", "Inspection of drum condition, markings and length."],
             fat=["Routine tests per the standard: conductor resistance, voltage test, partial discharge for MV cables.", "Witnessing: [project to define]."],
             commissioning=["Insulation resistance and continuity; phasing.", "MV cable test per the specification [project to define: very low frequency or DC withstand and partial discharge].", "Verification of installed layout against the rating basis (spacing, grouping, burial or tray)."]),
        dict(id="08", slug="Busduct", title="Busbar Trunking (Busduct)", tags=("BD-",), standards=["IEC 61439-6 (busbar trunking systems)", "IEC 61439-1 (general rules)", "Local fire barrier and building requirements [project to add]"],
             ratings=[["Rated current", f"[At least the design current after derating; preliminary {bd.required_rating_a:,.0f} A on the path-out case]", "Pending manufacturer data"], ["Rated short-time withstand and peak", "[At least the calculated LV fault level]", "NOT CALCULATED"], ["Impedance (resistance and reactance per km)", TBD, "Pending manufacturer data, needed for voltage drop"],
                      ["Length and routing", f"{(cfg.distribution or {}).get('busducts', [{}])[0].get('length_m', 0):g} m (illustrative)", "UNVERIFIED_PLACEHOLDER"], ["Ingress protection, material", "[Project to select]", "Project decision"]],
             requirements=["The busduct shall be design verified per IEC 61439-6 with evidence supplied.", "Rated current shall account for ambient temperature, altitude and mounting orientation.", "The manufacturer shall declare resistance and reactance per length, expansion provisions, fire barrier arrangements and tap-off units.",
                           "Short-circuit withstand shall exceed the prospective fault level including the peak at the busduct location."],
             inspection=["Review of verification evidence, shop drawings and the ITP.", "Inspection of joints, insulation and supports."],
             fat=["Routine verification per the standard: dielectric test, continuity, mechanical checks.", "Witnessing: [project to define]."],
             commissioning=["Joint torque and insulation resistance, phase sequence.", "Thermography under load."]),
        dict(id="09", slug="Protection", title="Protection Relays, Instrument Transformers and Coordination", tags=("MV-CB", "ACB-"), standards=["IEC 60255 series (measuring relays and protection equipment)", "IEC 61869 series (instrument transformers)", "IEC 61850 series (communication), if adopted", "IEC 60947-2 (LV circuit-breakers)"],
             ratings=[["Protective devices in scope", "MV-CB-A/B, ACB-TX-A/B, ACB-GEN-A/B, ACB-UPS-IN-A/B (illustrative list)", "Illustrative. Confirm with the design"], ["Required breaking capacity", "[At least the fault level at each location]", "NOT CALCULATED"], ["CT and VT ratios, classes, burdens", TBD, "Pending"], ["Settings", "[From the approved coordination study]", "NOT STARTED: needs device curves and a validated network study"]],
             requirements=["A protection coordination study shall be performed by the project with the manufacturers' device curves and a validated network model; the study, the settings schedule and the time-current characteristics shall be issued for review.", "The study shall demonstrate selectivity where the project requires it and report where it is not achieved.",
                           "Minimum fault current sensitivity, earth-fault protection and the effect of generator fault contribution shall be assessed.", "Arc-flash assessment: [project to define].", "Relay functions, communication, time synchronisation and cyber security: [project to define]."],
             inspection=["Review of relay datasheets, firmware versions and the settings schedule.", "Inspection of panel wiring and test blocks."],
             fat=["Relay functional and secondary injection tests against the settings schedule.", "Scheme and interlock tests.", "Witnessing: [owner / independent inspector to attend]."],
             commissioning=["Secondary injection of every protection function; primary injection where specified.", "Trip tests through the circuit-breakers; settings verified against the approved study and recorded.", "Coordination evidence retained with the commissioning records."]),
        dict(id="10", slug="Earthing", title="Earthing, Bonding and Lightning Protection Interface", tags=("EARTH",), standards=["IEEE 80 (substation grounding), as a method reference", "IEC 60364-5-54 (earthing arrangements and protective conductors)", "IEC 62305 series (lightning protection)", "Local utility and authority requirements [project to add]"],
             ratings=[R("Earthing system type", "earthing.earthing_system_type", "Assumed for the sample"), ["Soil resistivity", "[From a site soil resistivity survey, Wenner method]", "Pending site data"], ["Grid geometry", "[From the earthing design]", "Pending"], ["Earth-fault current and clearing time", "[From the fault and protection studies]", "Pending"], ["Touch and step voltage limits", "[Per the adopted method]", "Pending"]],
             requirements=["The earthing design shall be based on a soil resistivity survey and shall demonstrate that touch and step voltages and the ground potential rise are within the limits of the adopted method.", "The design shall state the earth-fault current, its split between the grid and other paths, and the clearing time used.",
                           "Bonding conductors, connections, test points and corrosion protection: [project to define].", "Interfaces with the lightning protection system, structural steel, the utility earth and IT equipment earthing: [project to define]."],
             inspection=["Review of the survey report, the grounding study and the drawings.", "Inspection of buried conductors and connections before backfill, with records."],
             fat=["Not applicable to the installation. Factory tests apply only to manufactured components (for example exothermic moulds and test links): [project to define]."],
             commissioning=["Continuity of all bonds; earth resistance measurement (fall-of-potential or the specified method).", "Verification of touch and step voltage against the design where specified; records retained."]),
    ]


def _manufacturer_rows(cfg: ProjectConfig, tags: tuple[str, ...]) -> list[list]:
    path = Path(cfg.base_dir) / "manufacturer_data_register.yaml"
    if not path.exists():
        return []
    rows = build_rows(cfg, load_register_meta(path))
    out = []
    for r in rows:
        if any(t.startswith(tags) for t in r.equipment_tags):
            out.append([r.parameter, r.name, r.required_datasheet.split(":")[0], r.data_class])
    return out


def build_spec_docx(cfg: ProjectConfig, spec: dict, path: Path, stamp: str, doc_no: str) -> Path:
    d = dx.new_document(spec["title"], doc_no, f"{cfg.project.revision}, Issue {SPEC_REV}", "Draft template", f"OHMETRY {cfg.project.code}: {spec['title']} (specification template)")
    dx.title(d, f"Technical specification template: {spec['title']}", f"{cfg.project.name}. Package revision {cfg.project.revision}. Generated {stamp}. Package version {__version__}.")
    dx.banner(d, DRAFT)
    d.add_heading("Document control", 2)
    dx.table(d, ["Field", "Value"], [["Document number", doc_no], ["Package revision", cfg.project.revision], ["Issue", SPEC_REV], ["Status", "DRAFT TEMPLATE"], ["Prepared by", "[name]"], ["Checked by", "[name]"], ["Approved by", "[name]"], ["Approval date", "[date]"]])
    d.add_heading("1. Scope", 2)
    d.add_paragraph(f"This template defines the technical requirements for {spec['title'].lower()} for the {cfg.project.name}. It is to be completed and issued by the project. Items in [square brackets] are decisions or data the project must supply. "
                    "Preliminary values from the Ohmetry reference configuration are shown with their data status and must be replaced or confirmed.")
    d.add_heading("2. Applicable standards", 2)
    dx.bullets(d, spec["standards"] + ["Editions and applicability of every standard above are NOT VERIFIED. The project shall confirm the current editions and any national deviations."])
    d.add_heading("3. Service conditions and system data", 2)
    dx.table(d, ["Item", "Requirement or preliminary value", "Data status"], _common_rows(cfg))
    d.add_heading("4. Equipment ratings", 2)
    d.add_paragraph("Ratings below are preliminary values from the master configuration unless marked otherwise. They are not manufacturer-confirmed and are not an equipment selection.")
    dx.table(d, ["Item", "Requirement or preliminary value", "Data status and note"], spec["ratings"])
    d.add_heading("5. Technical requirements", 2)
    dx.numbered(d, spec["requirements"], "5")
    d.add_heading("6. Vendor data schedule", 2)
    d.add_paragraph("The tenderer shall complete the schedule below with its offer: the value offered, its unit, and the name and revision of the document that states it. A value without a source document is not accepted. "
                    "The parameters are those in the manufacturer-data register; supplied values are imported into the calculations through the data override mechanism, and a value stays NOT VERIFIED until a reviewer records an attestation against its source (name, organisation, date, evidence reference, scope).")
    rows = _manufacturer_rows(cfg, spec["tags"])
    dx.table(d, ["Parameter id", "Parameter", "Datasheet required", "Current status", "Value offered", "Unit", "Document and revision"],
             [r + [VENDOR, VENDOR, VENDOR] for r in rows] or [["-", "See the manufacturer-data register", "-", "-", VENDOR, VENDOR, VENDOR]])
    d.add_paragraph("Model, manufacturer, country of manufacture, and the type-test reports for the offered design: [vendor to complete].")
    d.add_heading("7. Compliance schedule", 2)
    d.add_paragraph("The tenderer shall state, for every standard in section 2 and every technical requirement in section 5, whether the offer complies. 'Complies' needs an evidence reference (type-test report, certificate, calculation, drawing or data sheet with revision). "
                    "A statement without evidence is recorded as not demonstrated. The requirement references below are the numbered items of section 5 of this template; no clause of any standard is quoted.")
    dx.table(d, ["Standard named in section 2", "Edition offered", "Complies / complies with comment / does not comply", "Evidence reference", "Comment or deviation"], [[x, VENDOR, VENDOR, VENDOR, VENDOR] for x in spec["standards"] if not x.startswith("Local")] +
             [["Local requirements [project to add]", VENDOR, VENDOR, VENDOR, VENDOR]])
    dx.table(d, ["Requirement (section 5)", "Complies / complies with comment / does not comply", "Evidence reference", "Comment or deviation"], [[f"5.{i}", VENDOR, VENDOR, VENDOR] for i, _ in enumerate(spec["requirements"], 1)])
    d.add_heading("8. Inspection and quality requirements", 2)
    dx.numbered(d, spec["inspection"] + COMMON_TESTING, "8")
    d.add_heading("9. Factory acceptance test (FAT) requirements", 2)
    dx.numbered(d, spec["fat"] + ["A FAT procedure shall be submitted for approval before the test; the results shall be issued as a signed report, with deviations and their disposition recorded.",
                                  "Acceptance criteria are taken from the applicable standard and this specification [project to define]; a test passed against a criterion not stated in advance is not accepted.",
                                  "Equipment shall not be shipped until the FAT report is accepted or a concession is recorded and approved by the owner."], "9")
    d.add_heading("10. Site acceptance test (SAT) requirements", 2)
    dx.numbered(d, SAT.get(spec["slug"], []) + COMMON_SAT, "10")
    d.add_heading("11. Commissioning requirements", 2)
    dx.numbered(d, spec["commissioning"] + ["Commissioning records shall name the test, the instrument and its calibration, the date and the person, and shall be retained with the verification register.",
                                            "Integrated systems testing of the whole power chain (utility loss, generator start and transfer, UPS on battery, loss of one power path, return to normal) is carried out under a project procedure [project to define]. "
                                            "This equipment's commissioning is not complete until it has taken part in that test."], "11")
    d.add_heading("12. Submittals and documentation", 2)
    dx.table(d, ["Document", "When required", "Status"], [[a, b, "[vendor to complete]"] for a, b in SUBMITTALS])
    d.add_heading("13. Open items (NOT VERIFIED)", 2)
    dx.bullets(d, ["All ratings in section 4 marked PRELIMINARY or UNVERIFIED are open until confirmed from manufacturer data and the project studies.", "The prospective fault level is NOT CALCULATED until the utility, transformer and generator data are supplied.",
                   "Standards editions and local requirements are NOT VERIFIED.", "The vendor data schedule (section 6) and the compliance schedule (section 7) are blank until a tenderer completes them.",
                   "FAT, SAT and commissioning acceptance criteria are [project to define].", "This template has not been reviewed by an independent engineer."])
    d.save(path)
    return path


def build_specifications(cfg: ProjectConfig, out: Path, stamp: str, doc_numbers: dict[str, str] | None = None) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for s in _specs(cfg):
        no = (doc_numbers or {}).get(s["id"], f"{cfg.project.code}-SPEC-{s['id']}")
        p = build_spec_docx(cfg, s, out / f"{no}_{s['slug']}.docx", stamp, no)
        written.append(p)
        pdf = dx.to_pdf(p, out / "pdf")
        if pdf:
            written.append(pdf)
    return written


def spec_catalogue(cfg: ProjectConfig) -> list[tuple[str, str, str]]:
    return [(s["id"], s["slug"], s["title"]) for s in _specs(cfg)]
