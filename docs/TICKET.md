# Ticket: Nimbus climate exposure register, v1

**For:** the engineer building v1 for production. **Reference build:** this repository; `app/core/` and `tests/` are the specification.

## Goal

Meera Iyer, Head of Sustainability at Nimbus Cement, opens one link and can tell her board, auditor and investors, with sources:

1. How much FY2025-26 revenue is earned at plants rated high or worse for extreme heat, heavy rain and water stress, today and in 2040, including grinding units that depend on those plants' clinker.
2. What a carbon price would cost per year if Nimbus changed nothing.

It shows exposure. It does not predict losses.

## Build in this order

1. **Data contract.** Load and validate `plants.csv`, `clinker_flows.csv`, `assumptions.yaml`. Bad input fails with the file, row and reason (`tests/test_data_contract.py`).
2. **Clinker network** (`app/core/network.py`). Move shipped-clinker emissions to the unit that grinds it. Must reproduce: allocated total 10,932 kt; Baloda Bazar 557 kg CO2/t cement; Chittorgarh plus Baloda Bazar carry 52.1% of revenue.
3. **Climate pipeline** (`pipeline/`). Per plant and model: daily maximum temperature and rainfall, 2006-2049. Indicators: hot days (40 °C inland, 37 °C coastal), heavy-rain days (64.5 mm), mean wettest day. Store median, minimum and maximum across at least three models for 2006-2025 and 2030-2049.
4. **Water stress.** Replace the hand-filled CSV with a point-in-basin lookup on the Aqueduct 4.0 file: baseline, 2030 and 2050 business-as-usual categories.
5. **Exposure and pages** (`app/core/physical.py`, `app/templates/`): overview, plant, method.
6. **Carbon cost** (`app/core/transition.py`): allocated emissions × gap to target × price.

## Done when

- `python scripts/verify.py --release` exits 0 (`docs/CHECKLIST.md` explains each id).
- Every figure shows where it came from: a dataset name or an assumption id that links to the Method page.
- A dataset on sample values shows the banner on every page. It never fails silently.
- Editing `assumptions.yaml` changes results with no code change.
- Pages are server-rendered, need no JavaScript, read at 400 px wide and print on A4.

## Edge cases

Covered by tests:

- A grinding unit with two suppliers: dependency splits by clinker share.
- Flows that disagree with `clinker_shipped`: reject, name the plant.
- Aqueduct "arid and low water use" (-1): show "Not rated", leave out of exposed revenue, report the unrated amount.
- Desalinated supply: rated low, with a note (A09).
- A model-year with under 330 valid days is dropped; under three models stops the build.
- A value exactly on a band edge takes the higher band.
- Carbon price that is text, negative or huge: clamp to 0-10,000.

Not covered, decide before building:

- A plant with zero output, or one commissioned mid-year (currently rejected).
- An integrated plant that also buys clinker (formula handles it; no real data to test).
- Coastal plants whose climate grid cell is mostly sea.

## Open questions (owner: product; none blocks steps 1-3)

1. Notified CCTS targets per plant, and Scope 2 data. Until then A12 is a placeholder and grinding units are understated.
2. Climate data licence: the keyless Open-Meteo endpoint is non-commercial. Buy a key, or move to NEX-GDDP-CMIP6, which also adds scenarios.
3. Band edges A05 and A07 are ours. Confirm with plant operations and safety heads.
4. Clinker stock days and alternative suppliers per grinding unit (A11 assumes none).
5. Whether v2 adds a loss model, and whose.
6. Login. The prototype is public by brief; production is not.

## Out of scope

Cyclone and storm surge, flood depth, humid heat, Scope 2 and 3, suppliers and logistics, file upload, PDF export, maps.

## Stack

Python 3.12, FastAPI, Jinja2, PyYAML. No database: the pipeline writes `data/derived/hazards.json`, which is committed. Hosted on Vercel; `scripts/freeze.py` gives a static fallback.
