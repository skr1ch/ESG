"""Physical hazards: turn indicators into bands, then bands into revenue exposure."""
from __future__ import annotations

from dataclasses import dataclass

from .data import Dataset
from .models import HAZARDS, HORIZONS, Plant, Reading
from .network import suppliers


def band_from_edges(value: float, edges: list[float]) -> int:
    """edges = four ascending cut points; a value equal to an edge falls in the higher band."""
    if len(edges) != 4 or sorted(edges) != list(edges):
        raise ValueError("band edges must be four ascending numbers")
    return sum(value >= e for e in edges)


def _climate(cell: dict, edges: list[float], unit: str, note: str = "") -> Reading:
    return Reading(band_from_edges(cell["median"], edges), cell["median"], cell["min"], cell["max"], unit, note)


def _water(plant: Plant, row: dict, horizon: str, ds: Dataset) -> Reading:
    cat = row["baseline_cat"] if horizon == "today" else max(row["bau30_cat"], row["bau50_cat"])  # A08
    if plant.desalinated:
        return Reading(int(ds.a("A09")), cat, unit="Aqueduct category",
                       note="Desalinated supply: rated Low because it does not draw on the basin")
    if cat < 0:
        return Reading(None, cat, unit="Aqueduct category", note="Arid and low water use: Aqueduct does not rate it")
    return Reading(cat, cat, unit="Aqueduct category")


def plant_readings(ds: Dataset) -> dict[str, dict[str, dict[str, Reading]]]:
    """readings[plant_id][hazard][horizon]"""
    out = {}
    for p in ds.plants:
        rec = ds.hazards["plants"][p.id]
        threshold = ds.a("A04") if p.coastal else ds.a("A03")
        out[p.id] = {
            "heat": {h: _climate(rec["heat_days"][h], ds.a("A05"), f"days a year at or above {threshold} °C")
                     for h in HORIZONS},
            "rain": {h: _climate(rec["heavy_rain_days"][h], ds.a("A07"), f"days a year at or above {ds.a('A06')} mm")
                     for h in HORIZONS},
            "water": {h: _water(p, ds.aqueduct[p.id], h, ds) for h in HORIZONS},
        }
    return out


@dataclass(frozen=True)
class Exposure:
    hazard: str
    horizon: str
    direct_ids: tuple[str, ...]     # plants rated High or worse
    indirect_ids: tuple[str, ...]   # not rated High themselves, but fed by a plant that is
    direct_cr: float
    indirect_cr: float
    total_cr: float
    share: float                    # of group revenue
    assets_cr: float                # gross block at directly exposed plants
    revenue_by_band: tuple[float, ...]  # five numbers, direct revenue per band
    unrated_cr: float


def exposure(ds: Dataset, readings: dict, hazard: str, horizon: str) -> Exposure:
    cutoff, dependency = ds.a("A10"), ds.a("A11")
    group = sum(p.revenue_cr for p in ds.plants)
    band = {p.id: readings[p.id][hazard][horizon].band for p in ds.plants}
    direct = [p for p in ds.plants if band[p.id] is not None and band[p.id] >= cutoff]
    direct_ids = {p.id for p in direct}
    indirect_cr, indirect_ids = 0.0, []
    for p in ds.plants:
        if p.id in direct_ids:
            continue
        share = sum(s for src, s in suppliers(p.id, ds.plants, ds.flows) if src in direct_ids)
        if share > 0:
            indirect_cr += p.revenue_cr * share * dependency
            indirect_ids.append(p.id)
    by_band = [0.0] * 5
    for p in ds.plants:
        if band[p.id] is not None:
            by_band[band[p.id]] += p.revenue_cr
    direct_cr = sum(p.revenue_cr for p in direct)
    return Exposure(
        hazard, horizon, tuple(sorted(direct_ids)), tuple(indirect_ids), direct_cr, indirect_cr,
        direct_cr + indirect_cr, (direct_cr + indirect_cr) / group,
        sum(p.asset_value_cr for p in direct), tuple(by_band),
        sum(p.revenue_cr for p in ds.plants if band[p.id] is None),
    )


def all_exposures(ds: Dataset, readings: dict) -> dict[str, dict[str, Exposure]]:
    return {hz: {h: exposure(ds, readings, hz, h) for h in HORIZONS} for hz in HAZARDS}
