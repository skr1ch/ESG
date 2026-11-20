"""Loads and validates every input file. Standard library plus PyYAML only (no pandas at runtime)."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .models import HORIZONS, DataError, Flow, Plant

ROOT = Path(__file__).resolve().parents[2]

PLANT_COLUMNS = [
    "plant_id", "plant_name", "town", "state", "latitude", "longitude", "plant_type",
    "cement_capacity_mtpa", "cement_output_fy2025_26_mt", "clinker_produced_fy2025_26_mt",
    "clinker_shipped_fy2025_26_mt", "scope1_co2_fy2025_26_kt", "water_source", "coastal",
    "asset_value_inr_cr", "revenue_fy2025_26_inr_cr", "employees", "notes",
]
CLIMATE_KEYS = ("heat_days", "heavy_rain_days", "rx1day_mm")


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        raise DataError(f"{path.name}: file not found at {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _num(row: dict, col: str, path: Path, line: int, minimum: float = 0.0) -> float:
    raw = (row.get(col) or "").strip()
    try:
        value = float(raw)
    except ValueError:
        raise DataError(f"{path.name} row {line}: '{col}' must be a number, got '{raw}'") from None
    if value < minimum:
        raise DataError(f"{path.name} row {line}: '{col}' must be >= {minimum}, got {value}")
    return value


def load_plants(path: Path | None = None) -> list[Plant]:
    path = path or ROOT / "data" / "plants.csv"
    rows = _rows(path)
    if not rows:
        raise DataError(f"{path.name}: no plant rows")
    missing = [c for c in PLANT_COLUMNS if c not in rows[0]]
    if missing:
        raise DataError(f"{path.name}: missing columns {missing}")
    plants, seen = [], set()
    for i, r in enumerate(rows, start=2):
        pid = r["plant_id"].strip().upper()
        if not pid or pid in seen:
            raise DataError(f"{path.name} row {i}: plant_id empty or duplicated ('{pid}')")
        seen.add(pid)
        coastal = r["coastal"].strip().upper()
        if coastal not in ("Y", "N"):
            raise DataError(f"{path.name} row {i}: 'coastal' must be Y or N")
        lat, lon = float(r["latitude"]), float(r["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise DataError(f"{path.name} row {i}: latitude/longitude out of range")
        p = Plant(
            id=pid, name=r["plant_name"].strip(), town=r["town"].strip(), state=r["state"].strip(),
            lat=lat, lon=lon, plant_type=r["plant_type"].strip(),
            capacity_mtpa=_num(r, "cement_capacity_mtpa", path, i),
            cement_mt=_num(r, "cement_output_fy2025_26_mt", path, i),
            clinker_produced_mt=_num(r, "clinker_produced_fy2025_26_mt", path, i),
            clinker_shipped_mt=_num(r, "clinker_shipped_fy2025_26_mt", path, i),
            scope1_kt=_num(r, "scope1_co2_fy2025_26_kt", path, i),
            water_source=r["water_source"].strip(), coastal=coastal == "Y",
            asset_value_cr=_num(r, "asset_value_inr_cr", path, i),
            revenue_cr=_num(r, "revenue_fy2025_26_inr_cr", path, i),
            employees=int(_num(r, "employees", path, i)), notes=(r.get("notes") or "").strip(),
        )
        if p.cement_mt <= 0:
            raise DataError(f"{path.name} row {i}: cement output must be above zero")
        if p.clinker_shipped_mt > p.clinker_produced_mt + 1e-9:
            raise DataError(f"{path.name} row {i}: ships more clinker than it produces")
        plants.append(p)
    return plants


def load_flows(path: Path | None = None) -> list[Flow]:
    path = path or ROOT / "data" / "clinker_flows.csv"
    return [
        Flow(r["from_plant"].strip().upper(), r["to_plant"].strip().upper(),
             _num(r, "clinker_mt", path, i, minimum=1e-9))
        for i, r in enumerate(_rows(path), start=2)
    ]


def load_assumptions(path: Path | None = None) -> dict:
    path = path or ROOT / "config" / "assumptions.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = doc.get("assumptions") or {}
    for aid, a in items.items():
        for key in ("name", "value", "unit", "kind", "used_in", "rationale"):
            if key not in a:
                raise DataError(f"{path.name}: {aid} is missing '{key}'")
        if a["kind"] not in ("assumption", "sourced"):
            raise DataError(f"{path.name}: {aid} kind must be 'assumption' or 'sourced'")
    return items


def load_hazards(path: Path | None = None) -> dict:
    """Climate indicators written by pipeline/build_hazards.py (or the labelled sample file)."""
    path = path or ROOT / "data" / "derived" / "hazards.json"
    if not path.exists():
        raise DataError(f"{path.name}: not found. Run the pipeline or restore the sample file.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    meta = doc.get("meta") or {}
    if meta.get("status") not in ("real", "sample"):
        raise DataError(f"{path.name}: meta.status must be 'real' or 'sample'")
    for pid, rec in (doc.get("plants") or {}).items():
        for key in CLIMATE_KEYS:
            for h in HORIZONS:
                cell = (rec.get(key) or {}).get(h)
                if not cell or any(k not in cell for k in ("median", "min", "max")):
                    raise DataError(f"{path.name}: {pid}.{key}.{h} needs median, min and max")
                if not (0 <= cell["min"] <= cell["median"] <= cell["max"]):
                    raise DataError(f"{path.name}: {pid}.{key}.{h} must satisfy 0 <= min <= median <= max")
        for key in ("heat_days", "heavy_rain_days"):
            if max(rec[key][h]["max"] for h in HORIZONS) > 366:
                raise DataError(f"{path.name}: {pid}.{key} exceeds 366 days a year")
    return doc


def load_aqueduct(path: Path | None = None) -> dict[str, dict]:
    """Water-stress categories per plant. -1 = 'Arid and low water use' (not rated), 0-4 = Low..Extremely high."""
    path = path or ROOT / "data" / "manual" / "aqueduct_plants.csv"
    out = {}
    for i, r in enumerate(_rows(path), start=2):
        pid = r["plant_id"].strip().upper()
        rec = {"status": r["status"].strip().lower(), "source": (r.get("source") or "").strip(),
               "looked_up_on": (r.get("looked_up_on") or "").strip()}
        if rec["status"] not in ("real", "sample"):
            raise DataError(f"{path.name} row {i}: status must be 'real' or 'sample'")
        for col in ("baseline_cat", "bau30_cat", "bau50_cat"):
            try:
                cat = int(r[col])
            except (KeyError, ValueError):
                raise DataError(f"{path.name} row {i}: '{col}' must be an integer from -1 to 4") from None
            if not -1 <= cat <= 4:
                raise DataError(f"{path.name} row {i}: '{col}' must be between -1 and 4")
            rec[col] = cat
        out[pid] = rec
    return out


@dataclass(frozen=True)
class Dataset:
    plants: list[Plant]
    flows: list[Flow]
    assumptions: dict
    hazards: dict
    aqueduct: dict

    @property
    def climate_status(self) -> str:
        return self.hazards["meta"]["status"]

    @property
    def water_status(self) -> str:
        return "real" if all(r["status"] == "real" for r in self.aqueduct.values()) else "sample"

    def plant(self, pid: str) -> Plant | None:
        return next((p for p in self.plants if p.id == pid.upper()), None)

    def a(self, aid: str):
        """Value of an assumption by id."""
        return self.assumptions[aid]["value"]


def load_dataset(root: Path | None = None) -> Dataset:
    root = root or ROOT
    ds = Dataset(
        plants=load_plants(root / "data" / "plants.csv"),
        flows=load_flows(root / "data" / "clinker_flows.csv"),
        assumptions=load_assumptions(root / "config" / "assumptions.yaml"),
        hazards=load_hazards(root / "data" / "derived" / "hazards.json"),
        aqueduct=load_aqueduct(root / "data" / "manual" / "aqueduct_plants.csv"),
    )
    ids = {p.id for p in ds.plants}
    for name, keys in (("hazards.json", set(ds.hazards["plants"])), ("aqueduct_plants.csv", set(ds.aqueduct))):
        if keys != ids:
            raise DataError(f"{name}: plant ids differ from plants.csv (missing {sorted(ids - keys)}, extra {sorted(keys - ids)})")
    return ds


@lru_cache(maxsize=1)
def dataset() -> Dataset:
    return load_dataset()
