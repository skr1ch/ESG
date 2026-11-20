"""Page rendering on whatever data is live (sample or real). No web framework needed."""
import re

import pytest

from app import views
from app.core import data, transition

BAD_TOKENS = ("None", "nan", "Undefined", "{{", "}}", "{%", "Traceback")


def pages() -> dict[str, str]:
    ds = data.dataset()
    out = {"/": views.render_overview(), "/carbon": views.render_carbon(), "/method": views.render_method(),
           "/carbon?horizon=today": views.render_carbon(None, "today")}
    out.update({f"/plants/{p.id}": views.render_plant(p.id) for p in ds.plants})
    return out


@pytest.fixture(scope="module")
def rendered():
    return pages()


def visible_text(html: str) -> str:
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def test_all_pages_render_without_template_leaks(rendered):
    assert len(rendered) == 13
    for path, html in rendered.items():
        assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>"), path
        text = visible_text(html)
        for token in BAD_TOKENS:
            assert token not in text, f"{path} shows '{token}'"


def test_internal_links_resolve(rendered):
    ds = data.dataset()
    valid = {"/", "/carbon", "/method"} | {f"/plants/{p.id}" for p in ds.plants}
    for path, html in rendered.items():
        for href in re.findall(r'href="(/[^"]*)"', html):
            target = href.split("#")[0].split("?")[0]
            assert target in valid, f"{path} links to unknown {href}"


def test_every_assumption_tag_points_at_a_row_on_the_method_page(rendered):
    anchors = set(re.findall(r'<tr id="(A\d+)"', rendered["/method"]))
    assert anchors == set(data.dataset().assumptions)
    used = set()
    for html in rendered.values():
        used |= set(re.findall(r'href="/method#(A\d+)"', html))
    assert used <= anchors
    assert used == anchors, f"assumptions never shown next to a figure: {sorted(anchors - used)}"


def test_sample_data_is_flagged_everywhere_and_only_when_sample(rendered):
    ds = data.dataset()
    is_sample = "sample" in (ds.climate_status, ds.water_status)
    for path, html in rendered.items():
        assert ('class="flag"' in html) == is_sample, path
    assert ("tag-sample" in visible_text(rendered["/"]) or 'class="tag tag-sample"' in rendered["/"]) == is_sample


def test_overview_reconciles_to_the_plant_file(rendered):
    text = visible_text(rendered["/"])
    assert "₹9,658 cr" in text                     # group revenue
    assert "₹2,597 cr" in text and "₹2,435 cr" in text   # revenue riding on the two shipping kilns
    assert "52%" in text
    for town in ("Chittorgarh", "Satna", "Chandrapur", "Nalgonda", "Ariyalur", "Baloda Bazar", "Mundra", "Paradip", "Durgapur"):
        assert town in text


def test_carbon_page_matches_the_domain_calculation():
    ds = data.dataset()
    cost = transition.carbon_cost(ds, 2500, "2040")
    text = visible_text(views.render_carbon(2500, "2040"))
    assert f"₹{cost.cost_cr:,.0f} cr" in text and f"₹{cost.gross_cost_cr:,.0f} cr" in text
    assert "1,052 kt" in text                      # Mundra after clinker allocation


@pytest.mark.parametrize("price,horizon", [("abc", "2040"), ("-50", "today"), ("99999999", "2040"), ("", "1999"), (None, None)])
def test_carbon_page_survives_bad_input(price, horizon):
    html = views.render_carbon(price, horizon)
    assert "Traceback" not in html and "₹" in html


def test_unknown_plant_and_not_found_page_escape_input():
    assert views.render_plant("P99") is None
    assert views.render_plant("p01") is not None   # case-insensitive
    html = views.render_not_found("Plant '<script>alert(1)</script>'")
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_health_reports_data_status():
    h = views.health()
    assert h["ok"] and h["plants"] == 9 and h["climate_data"] in ("real", "sample")


def test_range_plot_geometry_stays_inside_the_canvas():
    class R:
        def __init__(self, v, lo, hi):
            self.value, self.low, self.high, self.label = v, lo, hi, "High"
    p = views.range_plot(R(55, 46, 63), R(400, 61, 999), [10, 30, 60, 90])
    for row in p["rows"]:
        assert p["x0"] <= row["x_lo"] <= row["x_med"] <= p["x1"] and row["x_hi"] <= p["x1"]
    assert views._nice_max(87) == 100 and views._nice_max(101) == 200 and views._nice_max(4.3) == 5
