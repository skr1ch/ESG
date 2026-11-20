"""Hazard banding and revenue exposure, on the pinned sample fixture."""
import dataclasses

import pytest

from app.core import physical
from app.core.models import HAZARDS, HORIZONS


@pytest.mark.parametrize("value,band", [(0, 0), (9.99, 0), (10, 1), (29.9, 1), (30, 2), (60, 3), (89.9, 3), (90, 4), (400, 4)])
def test_band_edges_are_inclusive_at_the_lower_bound(value, band):
    assert physical.band_from_edges(value, [10, 30, 60, 90]) == band


def test_band_edges_must_be_four_ascending():
    with pytest.raises(ValueError):
        physical.band_from_edges(5, [10, 30, 60])
    with pytest.raises(ValueError):
        physical.band_from_edges(5, [30, 10, 60, 90])


def test_every_plant_has_every_hazard_and_horizon(ds):
    r = physical.plant_readings(ds)
    assert set(r) == {p.id for p in ds.plants}
    for pid in r:
        for hz in HAZARDS:
            for h in HORIZONS:
                assert r[pid][hz][h].band in (None, 0, 1, 2, 3, 4)


def test_coastal_plants_use_the_37_degree_threshold(ds):
    r = physical.plant_readings(ds)
    assert "37" in r["P07"]["heat"]["today"].unit and "37" in r["P08"]["heat"]["today"].unit
    assert "40" in r["P01"]["heat"]["today"].unit


def test_desalinated_plant_is_rated_low_for_water(ds):
    r = physical.plant_readings(ds)
    assert ds.aqueduct["P07"]["baseline_cat"] == 4          # the basin itself is extremely stressed
    assert r["P07"]["water"]["today"].band == 0             # but the plant does not draw on it (A09)
    assert "Desalinated" in r["P07"]["water"]["today"].note


def test_water_2040_takes_the_worse_of_2030_and_2050(ds):
    r = physical.plant_readings(ds)
    assert (ds.aqueduct["P06"]["bau30_cat"], ds.aqueduct["P06"]["bau50_cat"]) == (2, 3)
    assert r["P06"]["water"]["2040"].band == 3


def test_arid_category_is_not_rated_and_not_counted(ds):
    aq = dict(ds.aqueduct)
    aq["P02"] = {**aq["P02"], "baseline_cat": -1}
    ds2 = dataclasses.replace(ds, aqueduct=aq)
    r = physical.plant_readings(ds2)
    assert r["P02"]["water"]["today"].band is None and r["P02"]["water"]["today"].label == "Not rated"
    e = physical.exposure(ds2, r, "water", "today")
    assert "P02" not in e.direct_ids and e.unrated_cr == pytest.approx(1511)


def test_heat_exposure_today(ds):
    e = physical.exposure(ds, physical.plant_readings(ds), "heat", "today")
    assert e.direct_ids == ("P02", "P03", "P06")
    assert e.direct_cr == pytest.approx(4034)
    assert set(e.indirect_ids) == {"P08", "P09"} and e.indirect_cr == pytest.approx(1160)
    assert e.total_cr == pytest.approx(5194) and e.share == pytest.approx(5194 / 9658)
    assert e.assets_cr == pytest.approx(2700 + 2300 + 2350)


def test_heat_exposure_2040(ds):
    e = physical.exposure(ds, physical.plant_readings(ds), "heat", "2040")
    assert e.direct_ids == ("P01", "P02", "P03", "P04", "P06")
    assert e.total_cr == pytest.approx(6782 + 848 + 1160)


def test_water_exposure_includes_the_grinding_unit_fed_by_a_stressed_kiln(ds):
    e = physical.exposure(ds, physical.plant_readings(ds), "water", "today")
    assert e.direct_ids == ("P01", "P02", "P04", "P05")
    assert e.indirect_ids == ("P07",)                       # low itself, but P01 feeds it
    assert e.total_cr == pytest.approx(5127 + 848)


def test_revenue_by_band_adds_up_to_group_revenue(ds):
    r = physical.plant_readings(ds)
    for hz in HAZARDS:
        for h in HORIZONS:
            e = physical.exposure(ds, r, hz, h)
            assert sum(e.revenue_by_band) + e.unrated_cr == pytest.approx(9658)
            assert 0 <= e.share <= 1
            assert not set(e.direct_ids) & set(e.indirect_ids)
