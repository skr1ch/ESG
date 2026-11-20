"""Clinker network: who feeds whom, where the emissions belong, and what revenue rides on each kiln."""
from __future__ import annotations

from dataclasses import dataclass

from .models import DataError, Flow, Plant

TOLERANCE_MT = 0.005


def validate_flows(plants: list[Plant], flows: list[Flow]) -> None:
    by_id = {p.id: p for p in plants}
    for f in flows:
        if f.source not in by_id or f.target not in by_id:
            raise DataError(f"clinker_flows.csv: unknown plant in flow {f.source}->{f.target}")
        if f.source == f.target:
            raise DataError(f"clinker_flows.csv: {f.source} ships to itself")
        if not by_id[f.source].has_kiln:
            raise DataError(f"clinker_flows.csv: {f.source} has no kiln but ships clinker")
    for p in plants:
        shipped = sum(f.clinker_mt for f in flows if f.source == p.id)
        if abs(shipped - p.clinker_shipped_mt) > TOLERANCE_MT:
            raise DataError(
                f"clinker_flows.csv: {p.id} flows total {shipped:.2f} Mt but plants.csv says "
                f"{p.clinker_shipped_mt:.2f} Mt shipped"
            )
        if not p.has_kiln and not any(f.target == p.id for f in flows):
            raise DataError(f"clinker_flows.csv: {p.id} has no kiln and no clinker supplier")


def received(pid: str, flows: list[Flow]) -> float:
    return sum(f.clinker_mt for f in flows if f.target == pid)


def clinker_consumed(p: Plant, flows: list[Flow]) -> float:
    return p.clinker_produced_mt - p.clinker_shipped_mt + received(p.id, flows)


@dataclass(frozen=True)
class Emissions:
    reported_kt: float           # Scope 1 as reported (includes clinker shipped out)
    allocated_kt: float          # after moving shipped-clinker emissions to the receiver
    naive_kg_per_t: float        # reported / cement output  (misleading for shippers and receivers)
    allocated_kg_per_t: float    # allocated / cement output (comparable across plants)
    clinker_factor: float        # clinker consumed per tonne of cement
    clinker_ef_kg_per_t: float | None  # kiln plants only


def allocate_emissions(plants: list[Plant], flows: list[Flow]) -> dict[str, Emissions]:
    """Move the emissions embodied in shipped clinker from the kiln to the grinding unit (assumption A16).

    kt / Mt is numerically kg per tonne, so no unit conversion is needed.
    """
    validate_flows(plants, flows)
    ef = {p.id: p.scope1_kt / p.clinker_produced_mt for p in plants if p.has_kiln}
    out = {}
    for p in plants:
        moved_out = p.clinker_shipped_mt * ef[p.id] if p.has_kiln else 0.0
        moved_in = sum(f.clinker_mt * ef[f.source] for f in flows if f.target == p.id)
        allocated = p.scope1_kt - moved_out + moved_in
        out[p.id] = Emissions(
            reported_kt=p.scope1_kt,
            allocated_kt=allocated,
            naive_kg_per_t=p.scope1_kt / p.cement_mt,
            allocated_kg_per_t=allocated / p.cement_mt,
            clinker_factor=clinker_consumed(p, flows) / p.cement_mt,
            clinker_ef_kg_per_t=ef.get(p.id),
        )
    return out


def suppliers(pid: str, plants: list[Plant], flows: list[Flow]) -> list[tuple[str, float]]:
    """(supplier id, share of this plant's clinker that comes from it)."""
    p = next(x for x in plants if x.id == pid)
    used = clinker_consumed(p, flows)
    return [(f.source, f.clinker_mt / used) for f in flows if f.target == pid and used > 0]


@dataclass(frozen=True)
class KilnStake:
    plant_id: str
    own_cr: float
    downstream_cr: float
    downstream_ids: tuple[str, ...]
    total_cr: float
    share_of_group: float


def revenue_at_stake(plants: list[Plant], flows: list[Flow], dependency: float = 1.0) -> dict[str, KilnStake]:
    """Revenue that stops if a kiln stops: its own plus the dependent share of the units it feeds (A11)."""
    by_id = {p.id: p for p in plants}
    group = sum(p.revenue_cr for p in plants)
    out = {}
    for p in plants:
        if not p.has_kiln:
            continue
        down, ids = 0.0, []
        for f in flows:
            if f.source != p.id:
                continue
            share = dict(suppliers(f.target, plants, flows))[p.id]
            down += by_id[f.target].revenue_cr * share * dependency
            ids.append(f.target)
        total = p.revenue_cr + down
        out[p.id] = KilnStake(p.id, p.revenue_cr, down, tuple(ids), total, total / group)
    return out
