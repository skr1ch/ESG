# Verification checklist

Run `python scripts/verify.py` after every change. It prints one line per id below.
Build checks must all say PASS. Release gates say NEEDS YOU until a person has done the step.

**Status on 20 November 2026:** every build check passes, gates G1 to G4 are closed, and G5 (deploy) is the one step left.

## Build checks (automatic)

| Id | What is checked | How |
|----|-----------------|-----|
| T1 | Unit and page tests pass | `pytest`, 100 tests: network, physical, transition, pipeline, data contract, views, HTTP routes |
| D1 | Group totals on screen equal the plant file | Totals recomputed from `data/plants.csv` and searched for in the rendered pages |
| D2 | Clinker balance closes | Produced = consumed, shipped = sum of flows, within 0.005 Mt |
| D3 | Emission allocation conserves the group total | Allocated kt = reported kt, within 0.5 kt |
| D4 | Exposure never exceeds group revenue | Revenue by band plus unrated = group revenue, for every hazard and horizon |
| V1 | Every page renders with no template leaks | 14 pages rendered; no `None`, `nan`, `{{` in visible text |
| V2 | Internal links resolve | Every `href="/..."` points at a real route |
| V3 | Sample data is flagged, and only when sample | Banner present on every page if and only if a dataset is sample |
| V4 | Pages work without JavaScript | No `<script>` tags |
| A1 | Assumptions are consistent | Every id used in code exists in `assumptions.yaml`; every assumption is shown beside a figure |
| P1 | Ticket and process note fit one page | Each exists and is at most 620 words |

## Release gates (need you)

| Id | Gate | Status | What you do | Why it cannot be automated here |
|----|------|--------|-------------|---------------------------------|
| G1 | Climate data is real | Closed, 20 November 2026 | Run the two pipeline commands below on a machine with internet | The build sandbox cannot reach the Open-Meteo API |
| G2 | Water data is real | Closed, 20 November 2026 | Look up nine points in the Aqueduct atlas and fill the CSV | Needs a person, or a browser session you approve |
| G3 | HTTP tests ran | Closed | `pip install -r requirements-dev.txt`, re-run verify | FastAPI could not be installed in the build sandbox |
| G4 | Process note is yours | Closed | Replace every `[YOUR WORDS ...]` line in `docs/PROCESS_NOTE.md` | It is your account of your process |
| G5 | Live link works | **Open** | Deploy to Vercel with your login; run verify with `--url` | Needs your Vercel account |

The sections below stay as the way to redo a step, for example to refresh the climate data.

### G1 and G3: install, fetch, build (about 75 minutes, nearly all waiting)

```
python -m venv .venv
.venv\Scripts\activate            (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
python -m pipeline.fetch_climate
python -m pipeline.build_hazards
python scripts/verify.py
```

`fetch_climate` makes 36 downloads, two a minute. The free tier allows about 21 of them an hour, so after the 21st it waits, for up to an hour, and then carries on by itself.
You can stop it at any time. Finished downloads are kept, and the same command picks up where it left off.
Then look at the numbers before trusting them: `uvicorn app.main:app --reload` and open http://127.0.0.1:8000.
Sanity check: Chandrapur and Chittorgarh should have far more hot days than Paradip. If they do not, stop: the fetch or the thresholds are wrong. On the committed data they have 60, 45 and 12 a year.

### G2: water stress (about 15 minutes)

1. Open the Aqueduct Water Risk Atlas: https://www.wri.org/applications/aqueduct/water-risk-atlas
2. For each plant, search the coordinates and read **Water Stress** for Baseline, then Future 2030 and 2050 under **Business as usual**. Menu labels may differ slightly.
3. Write the category number in `data/manual/aqueduct_plants.csv`, set `status` to `real`, put the date in `looked_up_on`.

| Category shown | Number |
|---|---|
| Arid and low water use | -1 |
| Low (under 10%) | 0 |
| Low to medium (10-20%) | 1 |
| Medium to high (20-40%) | 2 |
| High (40-80%) | 3 |
| Extremely high (over 80%) | 4 |

| Plant | Latitude, longitude |
|---|---|
| P01 Chittorgarh | 24.8887, 74.6269 |
| P02 Satna | 24.6005, 80.8322 |
| P03 Chandrapur | 19.9615, 79.2961 |
| P04 Nalgonda | 17.0575, 79.2671 |
| P05 Ariyalur | 11.1401, 79.0786 |
| P06 Baloda Bazar | 21.6566, 82.1606 |
| P07 Mundra | 22.8390, 69.7219 |
| P08 Paradip | 20.3165, 86.6114 |
| P09 Durgapur | 23.5204, 87.3119 |

The gate stays open if every row is marked `real` but still holds the placeholder categories from `pipeline/sample_data.py`.

The committed values were read on 20 November 2026 from the service behind the Atlas, not typed from the screen. The nine points were posted to `https://api.resourcewatch.org/v1/geostore`, then read from `/v1/aqueduct/analysis`: once with `analysis_type=annual` (field `bws_cat`), and with `analysis_type=projected`, `indicator=water_stress`, `scenario=business_as_usual`, `change_type=future_value` for `year=2030` and `year=2050` (field `label`). Spot-check two plants in the Atlas, using the steps above, before relying on them.

### G5: deploy (about 10 minutes)

```
npm i -g vercel
vercel login
vercel deploy --prod
python scripts/verify.py --release --url https://<your-project>.vercel.app
```

Use the production URL, not a preview URL: previews can sit behind Vercel's login. Open the link in a private window to confirm no login is asked.
If the Python function fails on Vercel: `python scripts/freeze.py` then `vercel deploy dist --prod` serves the same pages as static files.

## Manual review before sending (5 minutes)

- [ ] The headline sentence on the overview still reads sensibly with real data.
- [ ] No "Sample data" tag or banner anywhere.
- [ ] Each plant page: the two dots and whiskers look plausible, and 2040 is not below today for heat.
- [ ] Carbon page: try a price of 0 and of 10000.
- [ ] Print the overview to PDF; it fits and keeps its colours.
- [ ] Phone width: tables scroll sideways, nothing overlaps.
