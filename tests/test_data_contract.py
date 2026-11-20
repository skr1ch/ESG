"""The data contract: whatever is in data/ right now (sample or real) must load, and bad files must fail clearly."""
import json

import pytest

from app.core import data
from app.core.models import DataError


def test_live_dataset_loads():
    ds = data.load_dataset()
    assert ds.climate_status in ("real", "sample") and ds.water_status in ("real", "sample")
    assert ds.plant("p01").town == "Chittorgarh" and ds.plant("P99") is None


def test_real_climate_data_declares_its_models():
    meta = data.load_dataset().hazards["meta"]
    if meta["status"] == "real":
        assert len(meta["models"]) >= 3 and meta["windows"]["2040"][1] <= 2049


def test_hazards_file_must_declare_status(tmp_path):
    p = tmp_path / "hazards.json"
    p.write_text(json.dumps({"meta": {}, "plants": {}}))
    with pytest.raises(DataError, match="status"):
        data.load_hazards(p)


def test_hazards_cells_need_ordered_range(tmp_path):
    cell = {"median": 5, "min": 9, "max": 10}
    rec = {k: {"today": cell, "2040": cell} for k in data.CLIMATE_KEYS}
    p = tmp_path / "hazards.json"
    p.write_text(json.dumps({"meta": {"status": "sample"}, "plants": {"P01": rec}}))
    with pytest.raises(DataError, match="min <= median <= max"):
        data.load_hazards(p)


def test_plants_file_rejects_bad_rows(tmp_path):
    good = (data.ROOT / "data" / "plants.csv").read_text(encoding="utf-8").splitlines()
    for mutate, message in [
        (lambda r: r.replace(",N,3200,", ",maybe,3200,"), "coastal"),
        (lambda r: r.replace("P01,", "P02,", 1), "duplicated"),
        (lambda r: r.replace(",3.3,3.43,1.12,", ",3.3,1.00,1.12,"), "ships more clinker"),
    ]:
        p = tmp_path / "plants.csv"
        p.write_text("\n".join([good[0], mutate(good[1]), *good[2:]]), encoding="utf-8")
        with pytest.raises(DataError, match=message):
            data.load_plants(p)


def test_aqueduct_category_range(tmp_path):
    p = tmp_path / "aqueduct_plants.csv"
    p.write_text("plant_id,baseline_cat,bau30_cat,bau50_cat,status,source,looked_up_on\nP01,7,4,4,real,x,\n")
    with pytest.raises(DataError, match="between -1 and 4"):
        data.load_aqueduct(p)


def test_every_assumption_is_complete():
    for aid, a in data.load_assumptions().items():
        assert aid.startswith("A") and a["rationale"].strip() and a["name"].strip()
        if a["kind"] == "sourced":
            assert a.get("source"), f"{aid} is marked sourced but names no source"


def test_more_than_366_days_a_year_is_rejected(tmp_path):
    ok, silly = {"median": 5, "min": 4, "max": 6}, {"median": 300, "min": 200, "max": 400}
    rec = {k: {"today": ok, "2040": ok} for k in data.CLIMATE_KEYS}
    rec["heat_days"] = {"today": ok, "2040": silly}
    p = tmp_path / "hazards.json"
    p.write_text(json.dumps({"meta": {"status": "real"}, "plants": {"P01": rec}}))
    with pytest.raises(DataError, match="exceeds 366"):
        data.load_hazards(p)
