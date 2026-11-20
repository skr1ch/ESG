# Product backlog and sprint log

**Product goal.** Meera can answer "what is our business exposure to climate events today and by 2040?" from one link, with every number traceable.

**Definition of done (every story).** Code merged; tests written and passing; `python scripts/verify.py` build checks all PASS; any made-up number is in `config/assumptions.yaml` and tagged on screen.

**Cadence.** One-day build, so sprints are 60 to 150 minutes. Each ends with the verification loop, a review of the rendered pages, and a short retro. Findings from the loop go back into the backlog.

## Sprint log

| Sprint | Goal | Stories | Status |
|---|---|---|---|
| 0 | Something loads | Repo layout; data contract; assumptions file; labelled sample hazard data | Done |
| 1 | The numbers are right | S1 clinker network and allocation; S2 hazard bands and exposure; S3 carbon cost | Done, 50 tests |
| 2 | Real data can flow | S4 resumable fetcher; S5 indicators; S6 hazards builder | Done; run on 20 November 2026 (gate G1 closed) |
| 3 | Meera can read it | S7 overview; S8 plant page; S9 carbon page; S10 method page; S11 provenance tags | Done |
| 4 | It checks itself | S12 `verify.py`; S13 checklist; fix cycle | Done |
| 5 | An engineer can build it | S14 ticket; S15 process note | Done (gate G4 closed) |
| 6 | It is live | S16 real data; S17 Aqueduct lookups; S18 Vercel deploy | S16 and S17 done (gates G1, G2, G3 closed); S18 waiting on owner (gate G5) |
| 7 | It looks like what it is | S19 redesign: a new look and layout, with every figure, statement, tag and URL kept | Done |
| 8 | It reads cleanly | S20 grammar and capitalisation pass on every page; S21 docs brought in line with the build | Done, 100 tests |

**Where it stands on 20 November 2026.** Build checks all pass and both hazard datasets are real. The one open item is S18: deploy to Vercel and close gate G5.

## Stories and acceptance criteria

- **S1** As Meera, I want emissions counted where clinker is ground, so plant comparisons are fair. *Allocated total equals reported total; Baloda Bazar is 557 kg/t, not 969.*
- **S2** As Meera, I want each plant rated on five bands per hazard for today and 2040. *Edges inclusive at the lower bound; coastal plants use 37 °C.*
- **S3** As Meera, I want the do-nothing carbon cost at a price I choose. *Rs 2,500 in 2040 gives Rs 714 cr; bad input never errors.*
- **S4-S6** As the developer, I want a pipeline I can re-run safely. *Cached downloads are skipped; under three models stops the build.*
- **S7** As a board member, I want the answer in the first screen. *Headline sentence states rupees and share, today and 2040.*
- **S8** As Meera, I want to see the spread between models. *Median dot, minimum-to-maximum whisker, band edges drawn.*
- **S11** As an auditor, I want to know which numbers are assumptions. *Every assumption id appears beside a figure and links to its row.*
- **S12** As the owner, I want one command that tells me what is left. *Build checks and release gates listed by id.*
- **S19** As a board member, I want the register to read on a projector, on a phone and on paper. *Reads at 400 px wide; prints on A4 with the band colours kept; no JavaScript.*
- **S20** As a reader, I want band names to look like names. *"Rated High or worse", never "rated high or worse"; a test fails on a lower-case band name.*

## Retro: what the loops caught

| Sprint | Caught by | Finding | Action |
|---|---|---|---|
| 1 | Code review | A range check in the hazard loader never ran (reused loop variable) | Fixed; regression test added |
| 2 | Reading API docs | Data ends 2050-01-01, so a 2031-2050 window has a one-day final year | Window set to 2030-2049 (A02); years under 330 days dropped |
| 3 | Page test | The leak check flagged the word "None" in body copy | Copy reworded; check kept strict |
| 3 | Screenshot review | Duplicate "Sample data" tags; "Integrated in Baloda Bazar" read oddly; tables squeezed on a phone | All three fixed |
| 4 | `verify.py` A1 | Assumption A14 was never shown beside a figure: the FY2026-27 carbon page was not in the audited set | Page added to the freeze and audit |
| 4 | `verify.py` G4 | Gate passed vacuously when the note did not exist | Gate now requires the file |
| 6 | First real fetch | The run stopped at download 22 of 36. Each download weighs about 230 against the free tier's 5,000 an hour, so the default pace could never finish in one go | Fetcher paces to two a minute and waits out the hourly limit; six tests added |
| 6 | Cross-check against WRI's service | The water file was marked real but still held the placeholder categories; 7 of 9 plants differed from Aqueduct | Replaced with WRI's values; gate G2 now stays open while "real" rows equal the placeholders |
| 6 | First look at real output | The heat and heavy-rain band edges (A05, A07) had been chosen before any real output existed | Edges reset against the spread across the nine plants: 10, 25, 45, 70 hot days and 0.5, 1, 2, 4 heavy-rain days; test fixtures pin the earlier edges |
| 8 | Proofreading the rendered pages | Band names were lower-case in sentences but capitalised in the assumptions; "2 kilns" opened a sentence; lists read "P08, P09"; the Method page showed "deg C", "INR" and a raw timestamp | All fixed; two tests added |

## Next up (not in v1)

1. Cyclone and storm-surge layer for Mundra and Paradip.
2. Notified CCTS targets and Scope 2, replacing A12.
3. Aqueduct point-in-basin lookup in the pipeline, replacing the manual CSV.
4. Humid-heat indicator (wet-bulb) for coastal and eastern plants.
5. Clinker stock days per grinding unit, replacing A11.
