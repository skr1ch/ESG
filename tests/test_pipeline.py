"""Pipeline logic on synthetic series (the real API is not called in tests)."""
import datetime as dt
import io
import json
import urllib.error

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


def _limit(which):
    body = json.dumps({"error": True, "reason": f"{which} API request limit exceeded."}).encode()
    return urllib.error.HTTPError("https://example.invalid", 429, "Too Many Requests", {}, io.BytesIO(body))


def _api(monkeypatch, replies):
    """Make urlopen raise or return each reply in turn, and collect the waits fetch() asks for."""
    queue, waits = list(replies), []

    def urlopen(req, timeout=None):
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(fetch_climate.urllib.request, "urlopen", urlopen)
    return waits


def test_limit_kind_reads_the_limit_named_in_the_message():
    assert fetch_climate.limit_kind('{"reason":"Hourly API request limit exceeded."}') == "hourly"
    assert fetch_climate.limit_kind('{"reason":"Daily API request limit exceeded."}') == "daily"
    assert fetch_climate.limit_kind('{"reason":"Minutely API request limit exceeded."}') == "minutely"
    assert fetch_climate.limit_kind("") == "minutely"   # an unnamed 429 gets the short wait


def test_fetch_waits_out_the_minute_and_hour_limits(monkeypatch):
    waits = _api(monkeypatch, [_limit("Minutely"), _limit("Hourly"), _limit("Hourly"), {"daily": {}}])
    assert fetch_climate.fetch("https://example.invalid", sleep=waits.append) == {"daily": {}}
    assert waits == [65, 600, 600]


def test_fetch_stops_at_once_on_the_daily_limit(monkeypatch):
    waits = _api(monkeypatch, [_limit("Daily")])
    with pytest.raises(RuntimeError, match="Daily"):
        fetch_climate.fetch("https://example.invalid", sleep=waits.append)
    assert waits == []


def test_fetch_gives_up_when_a_limit_never_clears(monkeypatch):
    waits = _api(monkeypatch, [_limit("Hourly") for _ in range(8)])   # a fresh reply each time: a body reads once
    with pytest.raises(RuntimeError, match="HTTP 429"):
        fetch_climate.fetch("https://example.invalid", sleep=waits.append)
    assert waits == [600] * 7   # 70 minutes: longer than the hourly window


def test_fetch_retries_a_timeout_then_reports_it(monkeypatch):
    waits = _api(monkeypatch, [TimeoutError("timed out")] * 3 + [{"daily": {}}])
    assert fetch_climate.fetch("https://example.invalid", sleep=waits.append) == {"daily": {}}
    waits = _api(monkeypatch, [TimeoutError("timed out")] * 4)
    with pytest.raises(RuntimeError, match="network error: timed out"):
        fetch_climate.fetch("https://example.invalid", sleep=waits.append)
    assert waits == [10, 10, 10]


def test_default_pace_stays_inside_the_minute_limit():
    days = (dt.date.fromisoformat(fetch_climate.END) - dt.date.fromisoformat(fetch_climate.START)).days + 1
    weight = days / 14 * len(fetch_climate.VARIABLES) / 10   # Open-Meteo's published request weight
    assert weight == pytest.approx(229.6, abs=0.1)           # matches the X-RateLimit-Cost header it returns
    assert weight * 2 <= 600 < weight * 3                    # so two downloads a minute, never three


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
