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


@pytest.fixture(scope="session")
def ds() -> data.Dataset:
    return data.Dataset(
        plants=data.load_plants(),
        flows=data.load_flows(),
        assumptions=data.load_assumptions(),
        hazards=data.load_hazards(FIXTURES / "hazards_sample.json"),
        aqueduct=data.load_aqueduct(FIXTURES / "aqueduct_sample.csv"),
    )


@pytest.fixture(scope="session")
def by_id(ds):
    return {p.id: p for p in ds.plants}
