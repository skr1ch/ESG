"""Transition risk, v1: the do-nothing carbon cost under India's Carbon Credit Trading Scheme (CCTS)."""
from __future__ import annotations

from dataclasses import dataclass

from .data import Dataset
from .network import allocate_emissions

PRICE_MIN, PRICE_MAX = 0, 10_000


def gap_share(rate: float, years: int) -> float:
    """Share of emissions above the target after `years` of tightening at `rate`, with no abatement (A12, A13)."""
    if not 0 <= rate < 1 or years < 0:
        raise ValueError("rate must be in [0, 1) and years >= 0")
    return 1 - (1 - rate) ** years


def clamp_price(price) -> int:
    try:
        return max(PRICE_MIN, min(PRICE_MAX, int(price)))
    except (TypeError, ValueError):
        return PRICE_MIN


@dataclass(frozen=True)
class CarbonRow:
    plant_id: str
    allocated_kt: float
    kg_per_t: float
    priced_kt: float
    cost_cr: float
    pct_revenue: float


@dataclass(frozen=True)
class CarbonCost:
    horizon: str
    price: int
    gap: float
    rows: tuple[CarbonRow, ...]
    priced_kt: float
    cost_cr: float
    pct_revenue: float
    gross_cost_cr: float      # every Scope 1 tonne priced: an upper bound, not a forecast
    gross_pct_revenue: float


def carbon_cost(ds: Dataset, price: int, horizon: str) -> CarbonCost:
    if horizon not in ("today", "2040"):
        raise ValueError("horizon must be 'today' or '2040'")
    price = clamp_price(price)
    gap = gap_share(ds.a("A12"), ds.a("A17")[horizon])
    alloc = allocate_emissions(ds.plants, ds.flows)
    rows = []
    for p in ds.plants:
        e = alloc[p.id]
        priced = e.allocated_kt * gap
        cost = priced * price / 1e4          # kt * 1000 t * INR / 1e7 INR per crore
        rows.append(CarbonRow(p.id, e.allocated_kt, e.allocated_kg_per_t, priced, cost, cost / p.revenue_cr))
    revenue = sum(p.revenue_cr for p in ds.plants)
    total_kt = sum(r.allocated_kt for r in rows)
    cost = sum(r.cost_cr for r in rows)
    gross = total_kt * price / 1e4
    return CarbonCost(horizon, price, gap, tuple(rows), sum(r.priced_kt for r in rows), cost,
                      cost / revenue, gross, gross / revenue)
