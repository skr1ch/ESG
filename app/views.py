"""Builds each page as an HTML string. No web framework in here, so pages are testable and freezable."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .core import data, network, physical, transition
from .core.models import BAND_LABELS, HAZARD_NAMES, HAZARDS, HORIZONS

TEMPLATES = Path(__file__).parent / "templates"

HAZARD_HELP = {
    "heat": "Days a year hot enough to meet the weather service's heat-wave threshold.",
    "rain": "Days a year with at least 64.5 mm of rain, a proxy for flood-prone days.",
    "water": "How much of the local basin's renewable water is already withdrawn.",
}
NOT_ASSESSED = [
    ("Cyclone and storm surge", "Mundra and Paradip are on cyclone-prone coasts. No open dataset gave a 2040 view we could defend in a day."),
    ("River flood depth", "Open river-discharge data stops at a seven-month forecast. Heavy-rain days stand in as a proxy."),
    ("Humid heat", "Air temperature alone understates heat stress at humid sites such as Paradip and Durgapur."),
    ("Loss estimates", "This register shows where revenue sits against each hazard. It does not predict rupees lost."),
    ("Scope 2 and Scope 3 emissions", "The plant file holds Scope 1 only, so grinding units' electricity is missing from the carbon cost."),
    ("Suppliers, customers and logistics routes", "Only the nine plants and the clinker moved between them are covered."),
]
SOURCES = [
    ("Nimbus plant file (FY2025-26)", "", "Plant locations, output, clinker, Scope 1, revenue and asset values. Invented for the exercise."),
    ("Open-Meteo Climate API", "https://open-meteo.com/en/docs/climate-api", "Daily maximum temperature and rainfall from CMIP6 high-resolution models, 1950 to 2050."),
    ("WRI Aqueduct 4.0", "https://www.wri.org/data/aqueduct-global-maps-40-data", "Baseline water stress and business-as-usual projections for 2030 and 2050."),
    ("India Meteorological Department criteria", "https://mausam.imd.gov.in/", "Heat-wave thresholds (40 °C plains, 37 °C coast) and the heavy-rainfall category (64.5 mm)."),
    ("ICAP: India's Carbon Credit Trading Scheme", "https://icapcarbonaction.com/en/ets/indian-carbon-credit-trading-scheme", "Scheme design: intensity targets, FY2023-24 baseline, coverage."),
]


def _cr(v: float) -> str:
    return f"₹{v:,.0f} cr"


def _pct(v: float, digits: int = 0) -> str:
    return f"{v * 100:.{digits}f}%"


def _num(v: float, digits: int = 0) -> str:
    return f"{v:,.{digits}f}"


_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")


def _words(n: int) -> str:
    """Counts under ten as a word, for running text: 'two kilns', but '12 plants'."""
    return _NUMBER_WORDS[n] if 0 <= n < len(_NUMBER_WORDS) else f"{n:,}"


def _listing(items) -> str:
    """'A', 'A and B', 'A, B and C'."""
    items = [str(i) for i in items]
    return " and ".join(items) if len(items) < 3 else f"{', '.join(items[:-1])} and {items[-1]}"


def _day(iso: str) -> str:
    """'2026-11-20' or '2026-11-20T08:22:11Z' as '20 November 2026'. Anything else is shown as it is."""
    try:
        year, month, day = (int(part) for part in str(iso)[:10].split("-"))
        return f"{day} {_MONTHS[month - 1]} {year}"
    except (ValueError, IndexError):
        return str(iso)


env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]),
                  undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
env.filters.update(cr=_cr, pct=_pct, num=_num, words=_words, listing=_listing, day=_day)


def _base(ds: data.Dataset, active: str) -> dict:
    return {
        "active": active,
        "climate_status": ds.climate_status,
        "water_status": ds.water_status,
        "any_sample": "sample" in (ds.climate_status, ds.water_status),
        "band_labels": BAND_LABELS,
        "hazards": HAZARDS,
        "hazard_names": HAZARD_NAMES,
        "hazard_help": HAZARD_HELP,
        "horizons": HORIZONS,
        "assumptions": ds.assumptions,
        "meta": ds.hazards["meta"],
        "group": {
            "revenue_cr": sum(p.revenue_cr for p in ds.plants),
            "assets_cr": sum(p.asset_value_cr for p in ds.plants),
            "cement_mt": sum(p.cement_mt for p in ds.plants),
            "scope1_kt": sum(p.scope1_kt for p in ds.plants),
            "plants": len(ds.plants),
        },
    }


def _nice_max(v: float) -> float:
    """Smallest 1-2-5 step at or above v, so axes end on a round number."""
    step = 1.0
    while True:
        for m in (1, 2, 5):
            if m * step >= v:
                return m * step
        step *= 10


def range_plot(today, y2040, edges: list[float], digits: int = 0) -> dict:
    """Geometry for the today-versus-2040 plot: a dot at the model median, a whisker over the model range."""
    width, left, right = 600, 64, 84
    axis_max = _nice_max(max(today.high, y2040.high, edges[1]) * 1.05)
    span = width - left - right

    def x(v: float) -> float:
        return round(left + min(v, axis_max) / axis_max * span, 1)

    rows = [
        {"label": name, "cls": cls, "y": y, "x_lo": x(r.low), "x_hi": x(r.high), "x_med": x(r.value),
         "text": _num(r.value, digits), "band": r.label,
         "tip": f"{name}: {_num(r.value, digits)} (models {_num(r.low, digits)} to {_num(r.high, digits)}), {r.label}"}
        for name, cls, y, r in (("Today", "t0", 30, today), ("2040", "t1", 62, y2040))
    ]
    return {
        "width": width, "height": 112, "x0": left, "x1": left + span, "rows": rows,
        "edges": [{"x": x(e), "label": _num(e)} for e in edges if e <= axis_max],
        "axis_max_label": _num(axis_max),
    }


def render_overview() -> str:
    ds = data.dataset()
    readings = physical.plant_readings(ds)
    exposures = physical.all_exposures(ds, readings)
    stakes = network.revenue_at_stake(ds.plants, ds.flows, ds.a("A11"))
    by_id = {p.id: p for p in ds.plants}
    cutoff = ds.a("A10")
    group_rev = sum(p.revenue_cr for p in ds.plants)

    bars = {}
    for hz in HAZARDS:
        bars[hz] = {}
        for h in HORIZONS:
            e = exposures[hz][h]
            segs = [{"band": i, "label": BAND_LABELS[i], "cr": cr, "w": round(cr / group_rev * 100, 2)}
                    for i, cr in enumerate(e.revenue_by_band) if cr > 0]
            if e.unrated_cr > 0:
                segs.append({"band": "na", "label": "Not rated", "cr": e.unrated_cr, "w": round(e.unrated_cr / group_rev * 100, 2)})
            bars[hz][h] = segs

    rows = []
    for p in ds.plants:
        r = readings[p.id]
        high_2040 = sum(1 for hz in HAZARDS if r[hz]["2040"].band is not None and r[hz]["2040"].band >= cutoff)
        rows.append({
            "plant": p, "readings": r, "high_2040": high_2040,
            "feeds": [by_id[i] for i in stakes[p.id].downstream_ids] if p.id in stakes else [],
            "fed_by": [by_id[s] for s, _ in network.suppliers(p.id, ds.plants, ds.flows)],
        })
    rows.sort(key=lambda x: (-x["high_2040"], -x["plant"].revenue_cr))

    chains = [{"kiln": by_id[k], "stake": s, "units": [
                  {"plant": by_id[f.target], "mt": f.clinker_mt} for f in ds.flows if f.source == k]}
              for k, s in stakes.items() if s.downstream_ids]
    lead_hz = max(HAZARDS, key=lambda hz: exposures[hz]["2040"].total_cr)

    return env.get_template("overview.html").render(
        **_base(ds, "overview"), exposures=exposures, bars=bars, rows=rows, chains=chains,
        chain_share=sum(c["stake"].share_of_group for c in chains), lead_hz=lead_hz,
        n_units=sum(len(c["units"]) for c in chains),
        not_assessed=NOT_ASSESSED, cutoff_label=BAND_LABELS[cutoff],
    )


def render_plant(plant_id: str) -> str | None:
    ds = data.dataset()
    p = ds.plant(plant_id)
    if p is None:
        return None
    r = physical.plant_readings(ds)[p.id]
    rec = ds.hazards["plants"][p.id]
    by_id = {x.id: x for x in ds.plants}
    stakes = network.revenue_at_stake(ds.plants, ds.flows, ds.a("A11"))
    emissions = network.allocate_emissions(ds.plants, ds.flows)[p.id]

    plots = {
        "heat": range_plot(r["heat"]["today"], r["heat"]["2040"], ds.a("A05")),
        "rain": range_plot(r["rain"]["today"], r["rain"]["2040"], ds.a("A07"), digits=1),
    }
    rx = {h: rec["rx1day_mm"][h] for h in HORIZONS}
    aq = ds.aqueduct[p.id]
    return env.get_template("plant.html").render(
        **_base(ds, "overview"), plant=p, readings=r, plots=plots, rx=rx,
        rx_change=(rx["2040"]["median"] / rx["today"]["median"] - 1) if rx["today"]["median"] else 0,
        aqueduct=aq, aq_labels={k: ("Arid and low water use" if aq[k] < 0 else BAND_LABELS[aq[k]])
                                for k in ("baseline_cat", "bau30_cat", "bau50_cat")},
        emissions=emissions, stake=stakes.get(p.id),
        feeds=[(by_id[f.target], f.clinker_mt) for f in ds.flows if f.source == p.id],
        fed_by=[(by_id[s], share) for s, share in network.suppliers(p.id, ds.plants, ds.flows)],
        heat_threshold=ds.a("A04") if p.coastal else ds.a("A03"),
        all_plants=ds.plants,
    )


def render_carbon(price=None, horizon: str = "2040") -> str:
    ds = data.dataset()
    horizon = horizon if horizon in HORIZONS else "2040"
    paths = ds.a("A15")
    presets = ([("Estimate for the first trading cycle", ds.a("A14"))] if horizon == "today"
               else [("Low", paths["low"]), ("Central", paths["central"]), ("High", paths["high"])])
    default = ds.a("A14") if horizon == "today" else paths["central"]
    price = transition.clamp_price(default if price in (None, "") else price)
    cost = transition.carbon_cost(ds, price, horizon)
    alloc = network.allocate_emissions(ds.plants, ds.flows)
    by_id = {p.id: p for p in ds.plants}
    top = max((r.cost_cr for r in cost.rows), default=0) or 1
    rows = [{"plant": by_id[r.plant_id], "row": r, "em": alloc[r.plant_id], "w": round(r.cost_cr / top * 100, 1)}
            for r in sorted(cost.rows, key=lambda r: -r.cost_cr)]
    return env.get_template("carbon.html").render(
        **_base(ds, "carbon"), cost=cost, rows=rows, presets=presets, horizon=horizon, price=price,
        years=ds.a("A17")[horizon], rate=ds.a("A12"),
        group_kg_per_t=sum(p.scope1_kt for p in ds.plants) / sum(p.cement_mt for p in ds.plants),
        price_max=transition.PRICE_MAX,
    )


def render_method() -> str:
    ds = data.dataset()
    return env.get_template("method.html").render(
        **_base(ds, "method"), not_assessed=NOT_ASSESSED, sources=SOURCES,
        aqueduct_dates=sorted({r["looked_up_on"] for r in ds.aqueduct.values() if r["looked_up_on"]}),
    )


def render_not_found(what: str = "That page") -> str:
    ds = data.dataset()
    return env.get_template("not_found.html").render(**_base(ds, ""), what=what, all_plants=ds.plants)


def health() -> dict:
    ds = data.dataset()
    return {"ok": True, "plants": len(ds.plants), "climate_data": ds.climate_status, "water_data": ds.water_status}
