"""Load estimation, losses and A/B path allocation.

All power is in kW, kvar and kVA. For each item: connected = quantity x unit rating; demand = connected x demand factor;
reactive power = demand kW x tan(acos(power factor)). Totals add real and reactive power separately; apparent power is
sqrt(P^2 + Q^2). UPS losses and distribution losses are added as explicit lines. They are never left out silently.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ohmetry_dc.models import Category, ConfigError, ProjectConfig

from .pue import pue as _pue


def _tan(pf: float) -> float:
    return math.tan(math.acos(pf))


@dataclass(frozen=True)
class ItemResult:
    id: str
    category: str
    description: str
    quantity: float
    unit_rating_kw: float
    connected_kw: float
    power_factor: float
    demand_factor: float
    demand_kw: float
    demand_kvar: float
    demand_kva: float
    path_a_fraction: float
    on_generator: bool = True


@dataclass(frozen=True)
class PathLoad:
    kw: float
    kvar: float

    @property
    def kva(self) -> float:
        return math.hypot(self.kw, self.kvar)


@dataclass
class LoadEstimate:
    items: list[ItemResult]
    category_demand_kw: dict[str, float]
    it_demand_kw: float
    items_demand_kw: float
    ups_efficiency_pct: float
    ups_loss: PathLoad
    distribution_loss_pct: float
    distribution_loss: PathLoad
    facility_kw: float
    facility_kvar: float
    facility_kva: float
    power_factor: float
    pue: float
    growth_pct: float
    design_demand_kw: float
    design_demand_kva: float
    path_a: PathLoad
    path_b: PathLoad
    scenarios: dict[str, PathLoad] = field(default_factory=dict)
    connected_kw: float = 0.0


def _param(cfg: ProjectConfig, pid: str) -> float:
    v = cfg.value(pid)
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise ConfigError(f"The load model needs '{pid}', which is missing or not a number")
    return float(v)


def estimate_loads(cfg: ProjectConfig) -> LoadEstimate:
    if not cfg.load_items:
        raise ConfigError("The load schedule has no load items")
    design_pf = _param(cfg, "general.design_power_factor")
    eta_pct = _param(cfg, "equipment.ups_efficiency")
    dist_pct = _param(cfg, "losses.distribution_loss_fraction")
    growth_pct = _param(cfg, "general.future_expansion_allowance")
    if not 0 < eta_pct <= 100:
        raise ConfigError("equipment.ups_efficiency must be above 0 and at most 100 %")
    if not 0 <= dist_pct < 100 or growth_pct < 0:
        raise ConfigError("Distribution losses must be 0 to 100 % and the growth allowance cannot be negative")

    items: list[ItemResult] = []
    for it in cfg.load_items:
        if it.unit_rating_kw is None:
            raise ConfigError(f"Load item {it.id} has no rating (check the referenced design-basis value)")
        connected = it.quantity * it.unit_rating_kw
        dkw = connected * it.demand_factor
        dkvar = dkw * _tan(it.power_factor)
        items.append(ItemResult(it.id, it.category.value, it.description, it.quantity, it.unit_rating_kw, connected, it.power_factor, it.demand_factor,
                                dkw, dkvar, math.hypot(dkw, dkvar), it.path_a_fraction, it.on_generator))

    cat: dict[str, float] = {c.value: 0.0 for c in Category}
    for r in items:
        cat[r.category] += r.demand_kw
    it_kw = cat[Category.IT_CRITICAL.value]
    if it_kw <= 0:
        raise ConfigError("The load schedule has no IT critical load")
    items_kw = sum(r.demand_kw for r in items)
    items_kvar = sum(r.demand_kvar for r in items)

    t = _tan(design_pf)  # losses are given the design power factor
    ups_kw = it_kw * (100.0 / eta_pct - 1.0)
    ups = PathLoad(ups_kw, ups_kw * t)
    dist_kw = dist_pct / 100.0 * (items_kw + ups_kw)
    dist = PathLoad(dist_kw, dist_kw * t)

    fac_kw = items_kw + ups.kw + dist.kw
    fac_kvar = items_kvar + ups.kvar + dist.kvar
    fac_kva = math.hypot(fac_kw, fac_kvar)

    # A/B allocation. UPS losses follow the IT split; distribution losses follow each path's own load (they are a fraction of it).
    share_a = sum(r.demand_kw * r.path_a_fraction for r in items if r.category == Category.IT_CRITICAL.value) / it_kw
    sub_a_kw = sum(r.demand_kw * r.path_a_fraction for r in items) + ups.kw * share_a
    sub_a_kvar = sum(r.demand_kvar * r.path_a_fraction for r in items) + ups.kvar * share_a
    dist_a_kw = dist_pct / 100.0 * sub_a_kw
    path_a = PathLoad(sub_a_kw + dist_a_kw, sub_a_kvar + dist_a_kw * t)
    path_b = PathLoad(fac_kw - path_a.kw, fac_kvar - path_a.kvar)

    full = PathLoad(fac_kw, fac_kvar)
    scenarios = {
        "NORMAL_PATH_A": path_a,
        "NORMAL_PATH_B": path_b,
        "PATH_B_OUT_PATH_A_CARRIES_ALL": full,
        "PATH_A_OUT_PATH_B_CARRIES_ALL": full,
    }
    return LoadEstimate(items=items, category_demand_kw=cat, it_demand_kw=it_kw, items_demand_kw=items_kw, ups_efficiency_pct=eta_pct, ups_loss=ups,
                        distribution_loss_pct=dist_pct, distribution_loss=dist, facility_kw=fac_kw, facility_kvar=fac_kvar, facility_kva=fac_kva,
                        power_factor=fac_kw / fac_kva, pue=_pue(fac_kw, it_kw), growth_pct=growth_pct,
                        design_demand_kw=fac_kw * (1 + growth_pct / 100.0), design_demand_kva=fac_kva * (1 + growth_pct / 100.0),
                        path_a=path_a, path_b=path_b, scenarios=scenarios, connected_kw=sum(r.connected_kw for r in items))
