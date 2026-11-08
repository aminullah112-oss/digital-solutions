"""Equipment options shown side by side so the engineer can select (A5 review items 2 and 3).

The package selects nothing. It re-applies the same scenarios, derating and loading policy as the sizing module to the retained rating and to an illustrative alternative
(a 4,000 kVA transformer; a 3,000 kVA UPS). The alternatives share the retained equipment's derating factors and impedance percentage, which a real unit would not have to.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ohmetry_dc.models import ProjectConfig

from .sizing import LoadingStatus, PowerSystemSizing, Sizing, classify


@dataclass
class OptionRow:
    equipment: str                      # transformer or ups
    label: str
    rating: dict                        # {"kVA": 3150} or {"kW": 2500, "kVA": 2500}
    retained: bool
    loadings_pct: dict                  # metric -> worst credible loading in %
    statuses: dict                      # metric -> LoadingStatus value
    worst_scenario: dict                # metric -> scenario id
    overall: str                        # the worst of the statuses
    extra: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _worst(block: Sizing, ratio: float) -> tuple[float, str, LoadingStatus]:
    cred = [s for s in block.scenarios if s.credible and s.units_available > 0]
    if not cred:
        return math.nan, "", LoadingStatus.NOT_VERIFIED
    w = max(cred, key=lambda s: s.load / (s.units_available * s.capacity_each * ratio))
    loading = w.load / (w.units_available * w.capacity_each * ratio)
    return loading, w.id, classify(loading, block.policy)


def _overall(statuses) -> str:
    order = [LoadingStatus.FAIL, LoadingStatus.WARNING, LoadingStatus.NOT_VERIFIED, LoadingStatus.PASS]
    vals = {s for s in statuses}
    return next((o.value for o in order if o in vals), LoadingStatus.NOT_VERIFIED.value)


def equipment_options(cfg: ProjectConfig, sizing: PowerSystemSizing) -> list[OptionRow]:
    rows: list[OptionRow] = []
    tx = sizing.transformer
    if tx.rating_each:
        opt = cfg.optional_value("design_options.transformer_option_kva")
        z = cfg.optional_value("equipment.transformer_impedance")
        v = cfg.value("electrical_system.lv_line_voltage")
        c = cfg.optional_value("short_circuit.voltage_factor_c_max_lv")
        bound_ref = None
        if z and c:
            kt = 0.95 * c / (1 + 0.6 * z / 100.0)
            bound_ref = c * v / (math.sqrt(3) * (z / 100.0) * v ** 2 / (tx.rating_each * 1000.0) * kt) / 1000.0
        for label, rating, kept in (("Retained (preliminary)", tx.rating_each, True), ("Illustrative option", opt, False)):
            if rating is None:
                continue
            ratio = rating / tx.rating_each
            lo, sid, st = _worst(tx, ratio)
            notes = []
            extra = {"full_load_current_a": rating * 1000 / (math.sqrt(3) * v)}
            if bound_ref is not None:
                extra["transformer_limited_ka"] = bound_ref * ratio
                lim = cfg.optional_value("short_circuit.lv_fault_level_limit_ka")
                if lim is not None and bound_ref * ratio > lim:
                    notes.append(f"EXCEEDS the {lim:g} kA practical limit (an Ohmetry preliminary policy, not a standard limit): a larger transformer at the same impedance raises the LV fault level, so a higher impedance, a split LV bus or a different arrangement would need to be considered with it.")
                notes.append("The transformer-limited figure scales with the rating at the same impedance. It is the utility contribution through one transformer only: not the bus fault level and not a design value.")
            rows.append(OptionRow("transformer", label, {"kVA": rating}, kept, {"kVA": lo * 100}, {"kVA": st.value}, {"kVA": sid}, st.value, extra, notes))
    kw, kva = sizing.ups_kw, sizing.ups_kva
    if kw.rating_each and kva.rating_each:
        opt = cfg.optional_value("design_options.ups_option_kva")
        pf = kw.rating_each / kva.rating_each
        for label, r_kva, kept in (("Retained (preliminary)", kva.rating_each, True), ("Illustrative option", opt, False)):
            if r_kva is None:
                continue
            ratio = r_kva / kva.rating_each
            l_kw, s_kw, st_kw = _worst(kw, ratio)
            l_kva, s_kva, st_kva = _worst(kva, ratio)
            rows.append(OptionRow("ups", label, {"kW": r_kva * pf, "kVA": r_kva}, kept, {"kW": l_kw * 100, "kVA": l_kva * 100}, {"kW": st_kw.value, "kVA": st_kva.value}, {"kW": s_kw, "kVA": s_kva},
                                  _overall([st_kw, st_kva]), {}, [] if kept else ["The kW rating is scaled by the retained kW/kVA ratio. Real UPS ratings and output power factor come from the manufacturer."]))
    return rows


def options_markdown(rows: list[OptionRow]) -> list[str]:
    L = ["Both ratings are shown against the same worst credible contingency, derating (1.00 placeholders) and loading policy (target 90 / 100 % transformers, 80 / 100 % UPS). **The package does not select between them: the engineer does.**", "",
         "| Equipment | Option | Rating | Loading, worst credible case | Status | Notes |", "|---|---|---|---|---|---|"]
    for r in rows:
        rating = ", ".join(f"{v:,.0f} {k}" for k, v in r.rating.items())
        load = "; ".join(f"{k} {v:.2f} % ({r.worst_scenario[k]})" for k, v in r.loadings_pct.items())
        extra = "; ".join([f"full-load LV current {r.extra['full_load_current_a']:,.0f} A"] + ([f"transformer-limited figure {r.extra['transformer_limited_ka']:.1f} kA (not a bus fault level)"] if "transformer_limited_ka" in r.extra else [])) if r.extra else ""
        L.append(f"| {r.equipment} | {r.label} | {rating} | {load} | {r.overall} | {extra}{' ' + ' '.join(r.notes) if r.notes else ''} |")
    return L
