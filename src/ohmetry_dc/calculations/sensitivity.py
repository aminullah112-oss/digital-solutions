"""Sensitivity of the load model, and a review of how it is built (A5 review item 4).

PUE is an OUTPUT of the load model. Nothing here adjusts an input to reach a PUE target, and the 1.35 target in the design basis is context only.
The cases are the package's own illustrative variations (plus or minus 10 % IT load, as the review asked), not forecasts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ohmetry_dc.models import Category, ProjectConfig

from .load import estimate_loads
from .sizing import size_power_system


@dataclass
class Case:
    label: str
    it_kw: float
    facility_kw: float
    facility_kva: float
    pue: float
    transformer_pct: float
    transformer_status: str
    ups_kw_pct: float
    ups_kva_pct: float
    ups_status: str
    gen_kva_pct: float
    gen_kw_pct: float
    gen_status: str
    exception_covers: bool | None


def _copy(cfg: ProjectConfig) -> ProjectConfig:
    return cfg.model_copy(deep=True)


def _run(cfg: ProjectConfig, label: str) -> Case:
    est = estimate_loads(cfg)
    sz = size_power_system(cfg, est)
    tx = next(s for s in sz.transformer.scenarios if s.id == "TX-PATH-OUT")
    worst = lambda blk: blk.worst_credible
    ceiling = max((e.accepted_ceiling_pct for e in cfg.exceptions if e.check_id == "transformer_loading"), default=None)
    order = ["FAIL", "WARNING", "NOT VERIFIED", "PASS"]
    pick = lambda *s: next(o for o in order if o in {x.value for x in s})
    return Case(label, est.it_demand_kw, est.facility_kw, est.facility_kva, est.pue, tx.loading * 100, tx.status.value, worst(sz.ups_kw).loading * 100, worst(sz.ups_kva).loading * 100,
                pick(worst(sz.ups_kw).status, worst(sz.ups_kva).status), worst(sz.generator).loading * 100, worst(sz.generator_kw).loading * 100, pick(worst(sz.generator).status, worst(sz.generator_kw).status),
                None if ceiling is None or tx.status.value != "WARNING" else tx.loading * 100 <= ceiling + 1e-9)


def it_load_cases(cfg: ProjectConfig, steps=(-0.10, 0.0, 0.10)) -> list[Case]:
    """IT load varied. Two treatments of the cooling plant: held as scheduled (the plant is installed capacity) or scaled with the IT load (the plant follows the load)."""
    out: list[Case] = []
    for mode in ("plant held as scheduled", "cooling plant scaled with IT load"):
        for d in steps:
            c = _copy(cfg)
            for it in c.load_items:
                if it.category == Category.IT_CRITICAL:
                    it.unit_rating_kw = it.unit_rating_kw * (1 + d)
                elif mode.startswith("cooling") and it.category == Category.MECHANICAL_COOLING:
                    it.unit_rating_kw = it.unit_rating_kw * (1 + d)
            out.append(_run(c, f"IT {d * 100:+.0f} %, {mode}"))
    return out


def loss_cases(cfg: ProjectConfig) -> list[Case]:
    """UPS efficiency and distribution loss varied (the review asked whether the single flat values are reasonable)."""
    out = []
    eta = cfg.value("equipment.ups_efficiency")
    dist = cfg.value("losses.distribution_loss_fraction")
    for label, e, dl in (("As retained", eta, dist), (f"UPS efficiency {eta - 2:g} % (lighter-load efficiency is usually lower)", eta - 2, dist), (f"UPS efficiency {min(eta + 2, 99):g} %", min(eta + 2, 99), dist),
                         (f"Distribution loss {dist * 2:g} %", eta, dist * 2)):
        c = _copy(cfg)
        c.parameters["equipment.ups_efficiency"].value = e
        c.parameters["losses.distribution_loss_fraction"].value = dl
        out.append(_run(c, label))
    return out


def pue_range(cases: list[Case]) -> tuple[float, float]:
    return min(c.pue for c in cases), max(c.pue for c in cases)


@dataclass
class AllocationRow:
    item: str
    installed: float
    running: float
    unit_kw: float
    model_per_path_kw: float
    discrete_worst_path_kw: float | None
    note: str


def discrete_allocation_review(cfg: ProjectConfig) -> list[AllocationRow]:
    """The model splits every item 50 / 50 between paths. Equipment comes in whole units, so an odd number of running units cannot split evenly."""
    est = estimate_loads(cfg)
    out = []
    for it in est.items:
        if it.category != Category.MECHANICAL_COOLING.value:
            continue
        running = it.quantity * it.demand_factor
        unit_kw = it.demand_kw / running if running else 0.0
        model = it.demand_kw * it.path_a_fraction if it.path_a_fraction >= 0.5 else it.demand_kw * (1 - it.path_a_fraction)
        if abs(running - round(running)) > 0.05:
            out.append(AllocationRow(it.id, it.quantity, running, unit_kw, model, None, "The demand factor does not give a whole number of running units: the schedule treats it as a load fraction, not a unit count."))
            continue
        run = int(round(running))
        worst_units = math.ceil(run / 2)
        discrete = worst_units * unit_kw
        out.append(AllocationRow(it.id, it.quantity, run, unit_kw, model, discrete,
                                 "Running units split evenly between the paths." if run % 2 == 0 else f"{run} running units cannot split evenly: one path carries {worst_units}, so the worst path is {discrete - model:+,.0f} kW against the 50 % model."))
    return out


REVIEW_NOTES = [
    "Chillers: 4 installed, 3 running (N+1). The load schedule counts only running units (demand factor 0.75), which is the right basis for the load; the spare is not in the load. With 3 running over 2 paths one path carries 2, so the 50 / 50 split understates the worst path (see the allocation table).",
    "Chilled-water and condenser pumps: 6 installed, 4 running (demand factor 0.67 gives 4.02, read as 4). Two spare pumps (N+2). Splits 2 + 2.",
    "CRAH fan units: 20 installed, all counted as running (demand factor 1.0). Whether the 20 include spare units is not stated. If some are spare the load is overstated; if none are, there is no CRAH redundancy. A design decision, not decided here.",
    "A/B path split: every item is split 50 / 50 by `path_a_fraction`. That is an assumption, not a design: real feeders are allocated by whole units and by hall. In the path-out cases all load transfers to the surviving path (ER-006); mechanical plant behaviour after a path loss is not modelled.",
    "UPS losses use one efficiency (96 %) at every load. In a 2N arrangement each UPS normally runs at about 40 % of its rating, where efficiency is usually lower than at full load. The loss table shows the effect of 2 points. The real curve is manufacturer data.",
    "Distribution losses use one flat 1 % of the load, an assumption. The loss table shows the effect of doubling it.",
    "PUE is a design-point power ratio and an OUTPUT of this model. The 1.35 target is context only: no input has been, or will be, adjusted to reach it (ER-005 records that the early inputs were chosen with the target in view, so the 1.349 result is not independent evidence).",
]


def sensitivity_markdown(cfg: ProjectConfig) -> list[str]:
    cases = it_load_cases(cfg)
    loss = loss_cases(cfg)
    lo, hi = pue_range(cases + loss)
    fmt = lambda c: (f"| {c.label} | {c.it_kw:,.0f} | {c.facility_kw:,.1f} | {c.facility_kva:,.1f} | {c.pue:.3f} | {c.transformer_pct:.1f} % {c.transformer_status}" + (" (EX-001 covers)" if c.exception_covers else " (EX-001 does NOT cover)" if c.exception_covers is False else "") +
                     f" | {c.ups_kw_pct:.1f} / {c.ups_kva_pct:.1f} % {c.ups_status} | {c.gen_kva_pct:.1f} / {c.gen_kw_pct:.1f} % {c.gen_status} |")
    head = ["| Case | IT kW | Facility kW | Facility kVA | PUE | Transformer 3,150 kVA, path out | UPS kW / kVA | Generators kVA / kW, combined contingency |", "|---|---|---|---|---|---|---|---|"]
    L = ["Illustrative variations chosen by the package. They are not forecasts. Equipment ratings and derating (1.00 placeholders) are as retained.", ""] + head + [fmt(c) for c in cases] + ["", "Losses:", ""] + head + [fmt(c) for c in loss]
    L += ["", f"PUE across all cases above: {lo:.3f} to {hi:.3f}. PUE is an output of the model; no input was adjusted to reach a target.", "", "### Allocation of the mechanical plant between paths (whole units)", "",
          "| Item | Installed | Running | kW per unit | Model, worst path kW | Whole-unit worst path kW | Note |", "|---|---|---|---|---|---|---|"]
    for r in discrete_allocation_review(cfg):
        L.append(f"| {r.item} | {r.installed:g} | {r.running:g} | {r.unit_kw:,.1f} | {r.model_per_path_kw:,.1f} | {'' if r.discrete_worst_path_kw is None else format(r.discrete_worst_path_kw, ',.1f')} | {r.note} |")
    L += ["", "### Review notes on the load model", ""] + [f"- {n}" for n in REVIEW_NOTES]
    return L
