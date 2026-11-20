# Nimbus climate exposure register

A v1 prototype for the Oren product-manager assessment. It answers one question for Meera Iyer,
Head of Sustainability at Nimbus Cement (a fictional company):

> What is our business exposure to climate events today and by 2040?

It shows where FY2025-26 revenue sits against extreme heat, heavy rain and water stress, plant by plant,
and what a carbon price would cost if nothing changed. It shows exposure, not predicted losses.

## Status

Run `python scripts/verify.py`. Build checks must all PASS. Release gates G1 to G5 stay open until you
have fetched real climate data, filled in water stress, installed FastAPI locally, put the process note
in your own words and deployed. `docs/CHECKLIST.md` has the exact steps.

Until G1 and G2 are closed the hazard ratings are **labelled sample values** and every page says so.

## Quick start

```
python -m venv .venv
.venv\Scripts\activate                  # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/verify.py                # tests + reconciliation + page audit + release gates
uvicorn app.main:app --reload           # http://127.0.0.1:8000
```

## Real data

```
python -m pipeline.fetch_climate        # Open-Meteo, 36 downloads, resumable
python -m pipeline.build_hazards        # writes data/derived/hazards.json (status: real)
python -m pipeline.sample_data          # puts the labelled sample files back, if ever needed
```

Water stress is a nine-row CSV filled by hand from the Aqueduct atlas: `data/manual/aqueduct_plants.csv`.

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
tests/                pytest; fixtures pin sample data so tests survive real data
docs/
  TICKET.md           one-page ticket for the developer
  PROCESS_NOTE.md     one-page process note
  CHECKLIST.md        what verify.py checks, and the steps only a person can do
  BACKLOG.md          sprints, stories, acceptance criteria, retro
```

## Design rules

- Every figure is tagged: a dataset name, an assumption id (dashed, links to the Method page), or "Sample data".
- No JavaScript. Every view is a URL, so a board pack can link to an exact state.
- No live API calls when a page loads. The pipeline runs ahead of time and commits a small JSON file.
- Lato typeface with a metric-matched fallback, so text does not jump while the font loads.

## Data and licences

Open-Meteo Climate API (CMIP6 data, CC BY 4.0; the keyless endpoint is for non-commercial use).
WRI Aqueduct 4.0 (CC BY 4.0). Thresholds: India Meteorological Department. Plant data is invented.
