"""Carbon cost under the CCTS, do-nothing case."""
import pytest

from app.core import transition


def test_gap_share():
    assert transition.gap_share(0.02, 0) == 0
    assert transition.gap_share(0.02, 1) == pytest.approx(0.02)
    assert transition.gap_share(0.02, 15) == pytest.approx(0.2614, abs=1e-4)
    with pytest.raises(ValueError):
        transition.gap_share(1.2, 3)


@pytest.mark.parametrize("raw,expected", [(600, 600), ("2500", 2500), (-5, 0), (10**9, 10_000), ("abc", 0), (None, 0), (12.9, 12)])
def test_price_is_clamped(raw, expected):
    assert transition.clamp_price(raw) == expected


def test_gross_bill_is_every_scope1_tonne_times_price(ds):
    c = transition.carbon_cost(ds, 1000, "2040")
    assert c.gross_cost_cr == pytest.approx(1093.2)
    assert c.gross_pct_revenue == pytest.approx(0.1132, abs=1e-4)


def test_2040_central_case(ds):
    c = transition.carbon_cost(ds, 2500, "2040")
    assert c.priced_kt == pytest.approx(10932 * 0.2614, rel=1e-3)
    assert c.cost_cr == pytest.approx(714.5, abs=1.0)
    assert sum(r.cost_cr for r in c.rows) == pytest.approx(c.cost_cr)
    assert c.cost_cr < c.gross_cost_cr


def test_today_case_is_small(ds):
    c = transition.carbon_cost(ds, 600, "today")
    assert c.gap == pytest.approx(0.02)
    assert c.cost_cr == pytest.approx(10932 * 0.02 * 600 / 1e4)


def test_grinding_units_carry_the_clinker_they_grind(ds):
    rows = {r.plant_id: r for r in transition.carbon_cost(ds, 2500, "2040").rows}
    assert rows["P07"].allocated_kt == pytest.approx(1052, abs=0.6)   # 32 kt reported, 1,052 kt after allocation
    assert rows["P07"].cost_cr > 0


def test_zero_price_costs_nothing_and_bad_horizon_fails(ds):
    assert transition.carbon_cost(ds, 0, "2040").cost_cr == 0
    with pytest.raises(ValueError):
        transition.carbon_cost(ds, 100, "2035")
