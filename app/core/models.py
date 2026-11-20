"""Plain data structures shared by the domain modules. No I/O here."""
from __future__ import annotations

from dataclasses import dataclass

BAND_LABELS = ["Low", "Low to medium", "Medium to high", "High", "Extremely high"]
HORIZONS = ("today", "2040")
HAZARDS = ("heat", "rain", "water")
HAZARD_NAMES = {"heat": "Extreme heat", "rain": "Heavy rain", "water": "Water stress"}


class DataError(ValueError):
    """Raised when an input file breaks the data contract. The message names the file and row."""


@dataclass(frozen=True)
class Plant:
    id: str
    name: str
    town: str
    state: str
    lat: float
    lon: float
    plant_type: str
    capacity_mtpa: float
    cement_mt: float
    clinker_produced_mt: float
    clinker_shipped_mt: float
    scope1_kt: float
    water_source: str
    coastal: bool
    asset_value_cr: float
    revenue_cr: float
    employees: int
    notes: str

    @property
    def has_kiln(self) -> bool:
        return self.clinker_produced_mt > 0

    @property
    def desalinated(self) -> bool:
        return "desalinat" in self.water_source.lower()


@dataclass(frozen=True)
class Flow:
    source: str
    target: str
    clinker_mt: float


@dataclass(frozen=True)
class Reading:
    """One hazard, one plant, one horizon."""

    band: int | None          # 0-4, or None when not rated
    value: float | None       # headline indicator (median across models, or Aqueduct category)
    low: float | None = None  # lowest model
    high: float | None = None # highest model
    unit: str = ""
    note: str = ""

    @property
    def label(self) -> str:
        return "Not rated" if self.band is None else BAND_LABELS[self.band]
