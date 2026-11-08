"""Power system sizing summary (Markdown) and revision impact comparison."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from ohmetry_dc.calculations import PowerSystemSizing, Sizing, estimate_loads, size_power_system
from ohmetry_dc.models import ProjectConfig

NOTICE = ("PRELIMINARY. Not construction-ready and not verified. Every rating, derating factor and efficiency here is an illustrative assumption for the sample project at ideal conditions, "
          "except the loading policy, which is a preliminary Ohmetry design policy and not an IEC acceptance limit. Manufacturer data is outstanding. Engineering verification is required.")


def sizing_to_dict(s: Sizing) -> dict:
    d = {k: v for k, v in vars(s).items() if k not in ("scenarios", "worst_credible", "policy")}
    d["policy"] = vars(s.policy)
    d["status"] = s.status.value
    d["worst_credible"] = s.worst_credible.id if s.worst_credible else None
    d["scenarios"] = [{**{k: v for k, v in vars(x).items() if k != "status"}, "status": x.status.value} for x in s.scenarios]
    return d


def power_system_to_dict(r: PowerSystemSizing) -> dict:
    return {"transformer": sizing_to_dict(r.transformer), "ups_kw": sizing_to_dict(r.ups_kw), "ups_kva": sizing_to_dict(r.ups_kva), "generator": sizing_to_dict(r.generator), "generator_kw": sizing_to_dict(r.generator_kw),
            "generator_steps": {"blocks": [vars(b) for b in r.generator_steps.blocks], "running_capacity_kva": r.generator_steps.running_capacity_kva, "status": r.generator_steps.status.value,
                                "requirements": r.generator_steps.requirements, "note": r.generator_steps.note},
            "battery": {**vars(r.battery), "status": r.battery.status.value}}


def generator_verification_table(r: PowerSystemSizing, cfg: ProjectConfig) -> list[str]:
    """Loss of the largest generator and the remaining capacity, in kVA and kW, for every scenario whatever its credibility."""
    out = ["### Loss of the largest generator and remaining capacity", ""]
    confirmed = bool(cfg.optional_value("generators.rating_basis_confirmed"))
    out.append(f"Rating basis {cfg.value('generators.rating_basis')}: **{'confirmed by manufacturer documentation' if confirmed else 'ASSUMED, NOT confirmed. The 2,000 kVA rating must not be treated as PRP until the manufacturer confirms it'}**. "
               f"Derating: ambient, altitude and installation factors are placeholders unless the manufacturer's values are entered.")
    out += ["", "| Scenario | Units running | Remaining capacity (kVA) | Remaining capacity (kW) | Load (kVA) | Load (kW) | kVA loading | kW loading | Credible |", "|---|---|---|---|---|---|---|---|---|"]
    kw = {x.id: x for x in r.generator_kw.scenarios}
    for x in r.generator.scenarios:
        y = kw.get(x.id)
        out.append(f"| {x.id} | {x.units_available} | {x.capacity_total:,.0f} | {y.capacity_total:,.0f} | {x.load:,.0f} | {y.load:,.0f} | {x.loading * 100:.1f} % | {y.loading * 100:.1f} % | {'yes' if x.credible else 'no (informational)'} |" if y else
                   f"| {x.id} | {x.units_available} | {x.capacity_total:,.0f} | n/a | {x.load:,.0f} | n/a | {x.loading * 100:.1f} % | n/a | {'yes' if x.credible else 'no (informational)'} |")
    out += ["", "Still to be verified from manufacturer documentation: actual PRP rating in kW and kVA, site derating for ambient temperature and altitude, load-step capability and transient response, UPS rectifier interaction and harmonic loading, continuous operating limits and manufacturer restrictions.", ""]
    return out


def _table(s: Sizing, unit: str) -> list[str]:
    rows = ["| Scenario | Credible | Load | Units | Derated capacity | Loading | Status |", "|---|---|---|---|---|---|---|"]
    for x in s.scenarios:
        rows.append(f"| {x.id}: {x.description} | {'yes' if x.credible else 'no (informational)'} | {x.load:,.0f} {unit} | {x.units_available} | {x.capacity_total:,.0f} {unit} | {x.loading * 100:.1f} % | {x.status.value} |")
    return rows


def _section(title: str, s: Sizing, unit: str) -> list[str]:
    out = [f"## {title}", ""]
    if not s.scenarios:
        return out + [f"Not assessed. Missing: {'; '.join(s.missing_data)}", ""]
    d = s.derating
    out += [f"Policy: preferred target {s.policy.target_pct:g} %, maximum {s.policy.limit_pct:g} % of the derated continuous rating. Rating each {s.rating_each:,.0f} {unit}; derating factors ambient {d['ambient']:g}, altitude {d['altitude']:g}, installation {d['installation']:g} (combined {d['combined']:g}); derated {s.derated_each:,.0f} {unit}.", ""]
    out += _table(s, unit)
    w = s.worst_credible
    out += ["", f"**Worst credible case: {w.id}, {w.loading * 100:.1f} %, {s.status.value}.**", ""]
    if s.required_rating_each_for_target:
        out.append(f"Rating each needed to meet the preferred target: {s.required_rating_each_for_target:,.0f} {unit}" + (f" (next size in the configured list: {s.suggested_size_for_target:,.0f})" if s.suggested_size_for_target else "") + ".")
        out.append(f"Rating each needed to stay at the maximum: {s.required_rating_each_for_limit:,.0f} {unit}" + (f" (next size in the configured list: {s.suggested_size_for_limit:,.0f})" if s.suggested_size_for_limit else "") + ".")
    out += [""] + [f"- {n}" for n in s.notes] + [""]
    return out


def build_sizing_summary(cfg: ProjectConfig, generated: str | None = None) -> str:
    est = estimate_loads(cfg)
    r = size_power_system(cfg, est)
    generated = generated or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"# {cfg.project.code}: power system sizing summary (Stage 3)", "", f"Revision {cfg.project.revision}. Generated {generated}. Release state {cfg.project.release_state.value}.", "", f"**{NOTICE}**", "",
         "## Load basis", "", f"IT {est.it_demand_kw:,.0f} kW. Facility {est.facility_kw:,.1f} kW ({est.facility_kva:,.1f} kVA). Growth allowance {est.growth_pct:g} %. Source of the demand figures: {cfg.value('demand_data.demand_data_source')} ({cfg.value('demand_data.demand_data_date')}).", ""]
    L += _section("Transformers", r.transformer, "kVA") + _section("UPS: kW", r.ups_kw, "kW") + _section("UPS: kVA", r.ups_kva, "kVA")
    L += _section(f"Generators ({cfg.value('generators.rating_basis')} basis): alternator kVA", r.generator, "kVA")
    L += _section("Generators: engine kW (kVA rating x rated power factor, a placeholder)", r.generator_kw, "kW")
    L += generator_verification_table(r, cfg)
    st = r.generator_steps
    L += ["### Load steps and transient performance (generators)", "", st.note, "", "| Step | Block | Step size | Percent of running capacity |", "|---|---|---|---|"]
    L += [f"| {b.id} | {b.description} | {b.step_kva:,.0f} kVA | {b.percent_of_running_capacity:.1f} % |" for b in st.blocks]
    L += ["", f"Status: **{st.status.value}**. Data required for the transient verification:", ""] + [f"- {x}" for x in st.requirements] + [""]
    b = r.battery
    L += ["## Battery (interface only)", "", f"Critical load {b.ups_output_kw:,.0f} kW for {b.autonomy_min:g} min is {b.energy_at_ups_output_kwh:,.0f} kWh at the UPS output. Status: **{b.status.value}**.", ""] + [f"- {n}" for n in b.notes]
    L += ["", "Missing: " + (", ".join(b.missing_data) or "none"), ""]
    pend = [p for p in cfg.parameters.values() if p.status.value == "MANUFACTURER_DATA" and p.missing]
    L += ["## Outstanding manufacturer data", ""] + [f"- `{p.id}`: {p.name}" for p in pend] + [""]
    L += ["## Verification required before any use", "", "- Manufacturer sizing for each generator, UPS and transformer at the site conditions, including derating, load steps, UPS interaction, harmonics, altitude and ambient temperature.",
          "- Battery sizing from the manufacturer's constant-power discharge data.", "- Specialist studies where required: short-circuit, protection coordination, arc flash, harmonics, transients (Stages 4 and 5 and beyond).",
          "- Independent engineering review of every assumption in `config/assumptions_register.yaml`.", ""]
    return "\n".join(L)


# ---- revision impact -----------------------------------------------------------------------------------------------
def snapshot(cfg: ProjectConfig) -> dict:
    from ohmetry_dc.validation import run_all_checks

    est = estimate_loads(cfg)
    r = size_power_system(cfg, est)
    out = {"params": {pid: p.value for pid, p in cfg.parameters.items()},
           "load": {"it_kw": est.it_demand_kw, "facility_kw": est.facility_kw, "facility_kva": est.facility_kva, "pue": est.pue, "path_a_kw": est.path_a.kw},
           "sizing": {}, "checks": {c.id: c.status.value for c in run_all_checks(cfg)}}
    for key, s in (("transformer", r.transformer), ("ups_kw", r.ups_kw), ("ups_kva", r.ups_kva), ("generator", r.generator), ("generator_kw", r.generator_kw)):
        out["sizing"][key] = {"worst_loading_pct": s.worst_credible.loading * 100 if s.worst_credible else None, "status": s.status.value,
                              "required_rating_each_for_target": s.required_rating_each_for_target, "required_rating_each_for_limit": s.required_rating_each_for_limit,
                              "suggested_size_for_target": s.suggested_size_for_target, "suggested_size_for_limit": s.suggested_size_for_limit}
    return out


def compare(old: ProjectConfig, new: ProjectConfig) -> dict:
    a, b = snapshot(old), snapshot(new)
    params = {k: (a["params"].get(k), b["params"].get(k)) for k in sorted(set(a["params"]) | set(b["params"])) if a["params"].get(k) != b["params"].get(k)}
    load = {k: (a["load"][k], b["load"][k]) for k in a["load"] if abs(a["load"][k] - b["load"][k]) > 1e-9 * max(1.0, abs(a["load"][k]))}
    sizing = {}
    for eq in a["sizing"]:
        d = {k: (a["sizing"][eq][k], b["sizing"][eq][k]) for k in a["sizing"][eq]
             if a["sizing"][eq][k] != b["sizing"][eq][k] and not (isinstance(a["sizing"][eq][k], float) and isinstance(b["sizing"][eq][k], float) and abs(a["sizing"][eq][k] - b["sizing"][eq][k]) < 1e-9)}
        if d:
            sizing[eq] = d
    checks = {k: (a["checks"].get(k), b["checks"].get(k)) for k in sorted(set(a["checks"]) | set(b["checks"])) if a["checks"].get(k) != b["checks"].get(k)}
    return {"parameters": params, "load": load, "sizing": sizing, "checks": checks, "equipment_sizing_changed": bool(sizing)}


def compare_markdown(diff: dict, old_rev: str, new_rev: str) -> str:
    f = lambda v: f"{v:,.4g}" if isinstance(v, float) else str(v)
    L = [f"# Design basis revision impact: {old_rev} to {new_rev}", ""]
    L += ["## Changed inputs", ""] + ([f"- `{k}`: {f(a)} to {f(b)}" for k, (a, b) in diff["parameters"].items()] or ["- none"]) + [""]
    L += ["## Load results", ""] + ([f"- {k}: {f(a)} to {f(b)}" for k, (a, b) in diff["load"].items()] or ["- no change"]) + [""]
    L += ["## Equipment sizing changes", ""]
    if diff["sizing"]:
        for eq, d in diff["sizing"].items():
            L += [f"- **{eq}**: " + "; ".join(f"{k} {f(a)} to {f(b)}" for k, (a, b) in d.items())]
    else:
        L += ["- no equipment sizing change"]
    L += ["", "## Check status changes", ""] + ([f"- `{k}`: {a} to {b}" for k, (a, b) in diff["checks"].items()] or ["- none"]) + [""]
    return "\n".join(L)


def append_revision_log(path: Path, revision: str, description: str, diff: dict, date: str | None = None) -> None:
    path = Path(path)
    data = yaml.safe_load(path.read_text()) if path.exists() else {"schema_version": 1, "revisions": []}
    data["revisions"].append({"revision": revision, "date": date or dt.date.today().isoformat(), "description": description,
                              "changed_parameters": {k: [a, b] for k, (a, b) in diff["parameters"].items()}, "load_changes": {k: [a, b] for k, (a, b) in diff["load"].items()},
                              "equipment_sizing_changes": {eq: {k: [a, b] for k, (a, b) in d.items()} for eq, d in diff["sizing"].items()},
                              "check_status_changes": {k: [a, b] for k, (a, b) in diff["checks"].items()}, "reviewer": None, "review_status": "NOT REVIEWED"})
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
