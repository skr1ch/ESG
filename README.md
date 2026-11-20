# Nimbus climate exposure register

A v1 prototype for the Oren product-manager assessment. It answers one question for Meera Iyer,
Head of Sustainability at Nimbus Cement (a fictional company):

> What is our business exposure to climate events today and by 2040?

It shows where FY2025-26 revenue sits against extreme heat, heavy rain and water stress, plant by plant,
and what a carbon price would cost if nothing changed. It shows exposure, not predicted losses.

## Status

As of 20 November 2026:

- **Build checks all pass**: 100 tests, reconciliation to the plant file and an audit of 14 rendered pages.
- **The hazard data is real.** Heat and rain come from four CMIP6 models through the Open-Meteo Climate
  API; water stress comes from WRI Aqueduct 4.0. No page carries a sample-data flag.
- **Release gates G1 to G4 are closed.** G5, the live link, stays open until the app is deployed to Vercel
  and checked with `--url`.

Run `python scripts/verify.py` to see the current state. `docs/CHECKLIST.md` explains each id and has the
steps for G5.

## Quick start

```
python -m venv .venv
.venv\Scripts\activate                  # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/verify.py                # tests + reconciliation + page audit + release gates
uvicorn app.main:app --reload           # http://127.0.0.1:8000
```

## Real data

Both hazard datasets are committed, so the app runs without these steps. Run them only to refresh the data.

```
python -m pipeline.fetch_climate        # Open-Meteo, 36 downloads, resumable; waits out the hourly limit (about 75 min)
python -m pipeline.build_hazards        # writes data/derived/hazards.json (status: real)
python -m pipeline.sample_data          # puts the labelled sample files back, if ever needed
```

Water stress is a nine-row CSV, `data/manual/aqueduct_plants.csv`. Its values were read on
20 November 2026 from the service behind the Aqueduct Water Risk Atlas; `docs/CHECKLIST.md` records the
calls. If a dataset is ever back on sample values, every page says so.

## Deploy

```
vercel login
vercel deploy --prod
python scripts/verify.py --release --url https://<your-project>.vercel.app
```

Vercel detects FastAPI from `requirements.txt` and finds `app` in `app/main.py`. No configuration file is needed.
Fallback: `python scripts/freeze.py && vercel deploy dist --prod` serves the same pages as static HTML.

## Layout

```
app/
  main.py             FastAPI routes (thin: HTTP in, HTML out)
  views.py            builds each page; no framework, so pages are testable
  core/
    data.py           loads and validates every input file
    network.py        clinker flows, emission allocation, revenue riding on each kiln
    physical.py       hazard bands and revenue exposure
    transition.py     carbon cost under the CCTS
    models.py         shared data structures
  templates/          Jinja2 pages, macros and the stylesheet
pipeline/
  fetch_climate.py    step 1: download daily model output (needs internet)
  indicators.py       pure functions: hot days, heavy-rain days, wettest day
  build_hazards.py    step 2: write data/derived/hazards.json
  sample_data.py      labelled placeholder data for development
config/assumptions.yaml   every number that is not from a dataset, with its reason
data/
  plants.csv          the plant file, unchanged
  clinker_flows.csv   who ships clinker to whom (from the plant file's notes)
  manual/             hand-collected data (Aqueduct)
  derived/            pipeline output, committed
  raw/                downloads, not committed
scripts/
  verify.py           the self-check loop
  freeze.py           static export
tests/                pytest, 100 tests; fixtures pin sample data so tests survive real data
docs/
  TICKET.md           one-page ticket for the developer
  PROCESS_NOTE.md     one-page process note
  CHECKLIST.md        what verify.py checks, and the steps only a person can do
  BACKLOG.md          sprints, stories, acceptance criteria, retro
PRODUCT.md            product brief: users, purpose, constraints and principles
```

## Design rules

- Every figure is tagged: a dataset name, an assumption id (dashed, links to the Method page), or "Sample data".
- Band names (Low to Extremely high) keep their capital wherever they name a rating.
- No JavaScript. Every view is a URL, so a board pack can link to an exact state.
- No live API calls when a page loads. The pipeline runs ahead of time and commits a small JSON file.
- Anek Latin typeface (condensed for headings, normal width for reading) with a width-matched fallback,
  so text does not jump while the font loads.
- The look is a printed cement sack: sack-white ground and two inks. Blue is structure; the hot ink and
  hatching mean "counted as exposed". Light scheme only, because it has to project and print.

## Data and licences

Open-Meteo Climate API (CMIP6 data, CC BY 4.0; the keyless endpoint is for non-commercial use).
WRI Aqueduct 4.0 (CC BY 4.0). Thresholds: India Meteorological Department. Plant data is invented.
The code is under the MIT licence (`LICENSE`).
