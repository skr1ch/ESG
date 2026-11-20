"""Clinker network and emission allocation. Expected values were reconciled by hand against plants.csv."""
import dataclasses

import pytest

from app.core import network
from app.core.models import DataError, Flow


def test_group_totals_match_the_plant_file(ds):
    assert len(ds.plants) == 9
    assert sum(p.capacity_mtpa for p in ds.plants) == pytest.approx(23.0)
    assert sum(p.cement_mt for p in ds.plants) == pytest.approx(18.35)
    assert sum(p.revenue_cr for p in ds.plants) == pytest.approx(9658)
    assert sum(p.asset_value_cr for p in ds.plants) == pytest.approx(15450)
    assert sum(p.scope1_kt for p in ds.plants) == pytest.approx(10932)


def test_clinker_balance_closes(ds):
    produced = sum(p.clinker_produced_mt for p in ds.plants)
    consumed = sum(network.clinker_consumed(p, ds.flows) for p in ds.plants)
    assert produced == pytest.approx(12.61)
    assert consumed == pytest.approx(produced)
    assert sum(f.clinker_mt for f in ds.flows) == pytest.approx(sum(p.clinker_shipped_mt for p in ds.plants))


def test_allocation_conserves_total_emissions(ds):
    alloc = network.allocate_emissions(ds.plants, ds.flows)
    assert sum(e.allocated_kt for e in alloc.values()) == pytest.approx(10932)


@pytest.mark.parametrize("pid,kt,kg_per_t", [
    ("P01", 2105, 638), ("P02", 1720, 604), ("P03", 1510, 629), ("P04", 1025, 554), ("P05", 1005, 648),
    ("P06", 1420, 557), ("P07", 1052, 658), ("P08", 579, 551), ("P09", 516, 430),
])
def test_allocated_emissions_per_plant(ds, pid, kt, kg_per_t):
    e = network.allocate_emissions(ds.plants, ds.flows)[pid]
    assert e.allocated_kt == pytest.approx(kt, abs=0.6)
    assert e.allocated_kg_per_t == pytest.approx(kg_per_t, abs=0.6)


def test_naive_intensity_is_misleading_for_clinker_shippers(ds):
    """The trap: reported Scope 1 / cement output ranks P06 worst; after allocation it is among the best."""
    alloc = network.allocate_emissions(ds.plants, ds.flows)
    naive_worst = max(alloc, key=lambda k: alloc[k].naive_kg_per_t)
    assert naive_worst == "P06" and alloc["P06"].naive_kg_per_t == pytest.approx(969, abs=1)
    assert alloc["P07"].naive_kg_per_t == pytest.approx(20, abs=0.5)
    ranked = sorted(alloc, key=lambda k: alloc[k].allocated_kg_per_t)
    assert ranked.index("P06") <= 3


def test_clinker_factor(ds):
    alloc = network.allocate_emissions(ds.plants, ds.flows)
    assert alloc["P09"].clinker_factor == pytest.approx(0.50, abs=0.005)   # slag cement
    assert alloc["P01"].clinker_factor == pytest.approx(0.70, abs=0.005)
    assert alloc["P07"].clinker_ef_kg_per_t is None


def test_two_kilns_carry_half_of_revenue(ds):
    stake = network.revenue_at_stake(ds.plants, ds.flows)
    assert set(stake) == {"P01", "P02", "P03", "P04", "P05", "P06"}
    assert stake["P01"].total_cr == pytest.approx(2597) and stake["P01"].downstream_ids == ("P07",)
    assert stake["P06"].total_cr == pytest.approx(2435) and set(stake["P06"].downstream_ids) == {"P08", "P09"}
    assert stake["P01"].share_of_group + stake["P06"].share_of_group == pytest.approx(0.521, abs=0.001)
    assert stake["P02"].downstream_cr == 0


def test_flows_must_match_reported_shipments(ds):
    bad = [Flow("P01", "P07", 1.00)] + [f for f in ds.flows if f.source != "P01"]
    with pytest.raises(DataError, match="P01 flows total 1.00"):
        network.validate_flows(ds.plants, bad)


def test_grinding_unit_cannot_ship_and_needs_a_supplier(ds):
    with pytest.raises(DataError, match="no kiln but ships"):
        network.validate_flows(ds.plants, ds.flows + [Flow("P07", "P08", 0.1)])
    with pytest.raises(DataError):
        network.validate_flows(ds.plants, [f for f in ds.flows if f.target != "P09"])


def test_partial_dependency_when_a_unit_has_two_suppliers(ds):
    """Edge case for the ticket: split supply gives split dependency."""
    plants = [dataclasses.replace(p, clinker_shipped_mt=p.clinker_shipped_mt + 0.30) if p.id == "P02" else p for p in ds.plants]
    flows = [Flow("P06", "P09", 0.30) if f.target == "P09" else f for f in ds.flows] + [Flow("P02", "P09", 0.30)]
    plants = [dataclasses.replace(p, clinker_shipped_mt=0.98) if p.id == "P06" else p for p in plants]
    shares = dict(network.suppliers("P09", plants, flows))
    assert shares == pytest.approx({"P06": 0.5, "P02": 0.5})
    stake = network.revenue_at_stake(plants, flows)
    assert stake["P02"].downstream_cr == pytest.approx(624 * 0.5)
