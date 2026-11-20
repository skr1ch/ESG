"""Pure functions that turn a daily series into climate indicators. No I/O, so they are easy to test."""
from __future__ import annotations

from collections import defaultdict
from statistics import median

MIN_DAYS_PER_YEAR = 330  # a model-year with fewer valid days is dropped, not scaled


def _by_year(dates: list[str], values: list, first: int, last: int) -> dict[int, list[float]]:
    if len(dates) != len(values):
        raise ValueError("dates and values differ in length")
    years: dict[int, list[float]] = defaultdict(list)
    for d, v in zip(dates, values):
        y = int(d[:4])
        if first <= y <= last and v is not None:
            years[y].append(float(v))
    return {y: vs for y, vs in years.items() if len(vs) >= MIN_DAYS_PER_YEAR}


def days_at_or_above(dates: list[str], values: list, threshold: float, first: int, last: int) -> float | None:
    """Mean number of days a year at or above the threshold. None when no year has enough data."""
    years = _by_year(dates, values, first, last)
    if not years:
        return None
    return sum(sum(v >= threshold for v in vs) for vs in years.values()) / len(years)


def mean_annual_max(dates: list[str], values: list, first: int, last: int) -> float | None:
    """Mean of each year's largest daily value (Rx1day when the values are daily rainfall)."""
    years = _by_year(dates, values, first, last)
    if not years:
        return None
    return sum(max(vs) for vs in years.values()) / len(years)


def summarise(per_model: list[float | None]) -> dict | None:
    """Median and range across climate models. None when no model produced a value."""
    vals = [v for v in per_model if v is not None]
    if not vals:
        return None
    return {"median": round(median(vals), 2), "min": round(min(vals), 2), "max": round(max(vals), 2),
            "n_models": len(vals)}
