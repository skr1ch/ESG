"""Pipeline logic on synthetic series (the real API is not called in tests)."""
import datetime as dt
import json

import pytest

from pipeline import build_hazards, fetch_climate, indicators


def daily(first_year, last_year, fn):
    d, end = dt.date(first_year, 1, 1), dt.date(last_year, 12, 31)
    dates, vals = [], []
    while d <= end:
        dates.append(d.isoformat())
        vals.append(fn(d))
        d += dt.timedelta(days=1)
    return dates, vals


def test_days_at_or_above_counts_whole_years():
    dates, vals = daily(2006, 2007, lambda d: 41.0 if d.month == 5 else 30.0)
    assert indicators.days_at_or_above(dates, vals, 40, 2006, 2007) == pytest.approx(31)
    assert indicators.days_at_or_above(dates, vals, 41, 2006, 2007) == pytest.approx(31)   # inclusive
    assert indicators.days_at_or_above(dates, vals, 41.1, 2006, 2007) == 0


def test_window_is_respected_and_thin_years_are_dropped():
    dates, vals = daily(2006, 2008, lambda d: 45.0 if d.year == 2008 else 20.0)
    assert indicators.days_at_or_above(dates, vals, 40, 2006, 2007) == 0
    vals_with_gap = [None if d.startswith("2007") else v for d, v in zip(dates, vals)]
    assert indicators.days_at_or_above(dates, vals_with_gap, 40, 2007, 2007) is None
    assert indicators.days_at_or_above(dates, vals_with_gap, 40, 2006, 2008) == pytest.approx(366 / 2)


def test_mean_annual_max():
    dates, vals = daily(2030, 2031, lambda d: (120.0 if d.year == 2030 else 80.0) if (d.month, d.day) == (7, 15) else 1.0)
    assert indicators.mean_annual_max(dates, vals, 2030, 2031) == pytest.approx(100.0)


def test_summarise_ignores_missing_models():
    assert indicators.summarise([10, None, 30, 20]) == {"median": 20, "min": 10, "max": 30, "n_models": 3}
    assert indicators.summarise([None, None]) is None


def test_length_mismatch_is_an_error():
    with pytest.raises(ValueError):
        indicators.days_at_or_above(["2006-01-01"], [1, 2], 0, 2006, 2006)


def test_parse_daily_accepts_plain_and_model_suffixed_keys():
    plain = {"daily": {"time": ["2040-01-01"], "temperature_2m_max": [31.0], "precipitation_sum": [0.0]}}
    suffixed = {"daily": {"time": ["2040-01-01"], "temperature_2m_max_EC_Earth3P_HR": [31.0], "precipitation_sum_EC_Earth3P_HR": [0.0]}}
    assert fetch_climate.parse_daily(plain, "EC_Earth3P_HR") == fetch_climate.parse_daily(suffixed, "EC_Earth3P_HR")
    with pytest.raises(ValueError, match="missing"):
        fetch_climate.parse_daily({"daily": {"time": ["2040-01-01"]}}, "EC_Earth3P_HR")
    with pytest.raises(ValueError):
        fetch_climate.parse_daily({"error": True, "reason": "bad"}, "EC_Earth3P_HR")


def test_url_requests_the_planned_window():
    url = fetch_climate.build_url(24.8887, 74.6269, "MRI_AGCM3_2_S")
    assert url.startswith("https://climate-api.open-meteo.com/v1/climate?")
    assert "start_date=2006-01-01" in url and "end_date=2049-12-31" in url and "models=MRI_AGCM3_2_S" in url


def _write_model(raw, pid, model, hot_today, hot_2040):
    dates, tmax = daily(2006, 2049, lambda d: 42.0 if d.timetuple().tm_yday <= (hot_today if d.year <= 2025 else hot_2040) else 30.0)
    rain = [70.0 if d.endswith("-07-01") else 0.0 for d in dates]
    (raw / f"{pid}_{model}.json").write_text(json.dumps(
        {"plant_id": pid, "model": model, "time": dates, "temperature_2m_max": tmax, "precipitation_sum": rain}))


def test_build_hazards_end_to_end(tmp_path, ds):
    for i, model in enumerate(["A", "B", "C"]):
        _write_model(tmp_path, "P01", model, 50 + 10 * i, 70 + 10 * i)
    doc = build_hazards.build(tmp_path, [{"id": "P01", "coastal": False}], ds.assumptions)
    rec = doc["plants"]["P01"]
    assert doc["meta"]["status"] == "real" and doc["meta"]["models"] == ["A", "B", "C"]
    assert rec["heat_days"]["today"] == {"median": 60, "min": 50, "max": 70, "n_models": 3}
    assert rec["heat_days"]["2040"]["median"] == 80
    assert rec["heavy_rain_days"]["today"]["median"] == 1 and rec["rx1day_mm"]["2040"]["median"] == 70


def test_build_hazards_refuses_thin_data(tmp_path, ds):
    _write_model(tmp_path, "P01", "A", 50, 70)
    with pytest.raises(ValueError, match="need 3"):
        build_hazards.build(tmp_path, [{"id": "P01", "coastal": False}], ds.assumptions)
