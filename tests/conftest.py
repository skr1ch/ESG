"""Shared fixtures. Domain tests run on pinned SAMPLE hazard fixtures so they keep passing
after the real pipeline replaces data/derived/hazards.json."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import data  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


# The band edges the sample hazard fixtures were written against. They are pinned here for the same
# reason the hazard values are: so recalibrating A05 or A07 in config/assumptions.yaml to real model
# output does not change what the domain tests assert.
SAMPLE_BAND_EDGES = {"A05": [10, 30, 60, 90], "A07": [1, 3, 6, 10]}


@pytest.fixture(scope="session")
def ds() -> data.Dataset:
    assumptions = data.load_assumptions()
    for aid, edges in SAMPLE_BAND_EDGES.items():
        assumptions[aid] = {**assumptions[aid], "value": edges}
    return data.Dataset(
        plants=data.load_plants(),
        flows=data.load_flows(),
        assumptions=assumptions,
        hazards=data.load_hazards(FIXTURES / "hazards_sample.json"),
        aqueduct=data.load_aqueduct(FIXTURES / "aqueduct_sample.csv"),
    )


@pytest.fixture(scope="session")
def by_id(ds):
    return {p.id: p for p in ds.plants}
