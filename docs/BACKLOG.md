# Product backlog and sprint log

**Product goal.** Meera can answer "what is our business exposure to climate events today and by 2040?" from one link, with every number traceable.

**Definition of done (every story).** Code merged; tests written and passing; `python scripts/verify.py` build checks all PASS; any made-up number is in `config/assumptions.yaml` and tagged on screen.

**Cadence.** One-day build, so sprints are 60 to 150 minutes. Each ends with the verification loop, a review of the rendered pages, and a short retro. Findings from the loop go back into the backlog.

## Sprint log

| Sprint | Goal | Stories | Status |
|---|---|---|---|
| 0 | Something loads | Repo layout; data contract; assumptions file; labelled sample hazard data | Done |
| 1 | The numbers are right | S1 clinker network and allocation; S2 hazard bands and exposure; S3 carbon cost | Done, 50 tests |
| 2 | Real data can flow | S4 resumable fetcher; S5 indicators; S6 hazards builder | Done in code; run pending (gate G1) |
| 3 | Meera can read it | S7 overview; S8 plant page; S9 carbon page; S10 method page; S11 provenance tags | Done |
| 4 | It checks itself | S12 `verify.py`; S13 checklist; fix cycle | Done |
| 5 | An engineer can build it | S14 ticket; S15 process note | Drafted; note needs owner's words (gate G4) |
| 6 | It is live | S16 real data; S17 Aqueduct lookups; S18 Vercel deploy | Waiting on owner (gates G1, G2, G3, G5) |

## Stories and acceptance criteria

- **S1** As Meera, I want emissions counted where clinker is ground, so plant comparisons are fair. *Allocated total equals reported total; Baloda Bazar is 557 kg/t, not 969.*
- **S2** As Meera, I want each plant rated on five bands per hazard for today and 2040. *Edges inclusive at the lower bound; coastal plants use 37 °C.*
- **S3** As Meera, I want the do-nothing carbon cost at a price I choose. *Rs 2,500 in 2040 gives Rs 714 cr; bad input never errors.*
- **S4-S6** As the developer, I want a pipeline I can re-run safely. *Cached downloads are skipped; under three models stops the build.*
- **S7** As a board member, I want the answer in the first screen. *Headline sentence states rupees and share, today and 2040.*
- **S8** As Meera, I want to see the spread between models. *Median dot, minimum-to-maximum whisker, band edges drawn.*
- **S11** As an auditor, I want to know which numbers are assumptions. *Every assumption id appears beside a figure and links to its row.*
- **S12** As the owner, I want one command that tells me what is left. *Build checks and release gates listed by id.*

## Retro: what the loops caught

| Sprint | Caught by | Finding | Action |
|---|---|---|---|
| 1 | Code review | A range check in the hazard loader never ran (reused loop variable) | Fixed; regression test added |
| 2 | Reading API docs | Data ends 2050-01-01, so a 2031-2050 window has a one-day final year | Window set to 2030-2049 (A02); years under 330 days dropped |
| 3 | Page test | The leak check flagged the word "None" in body copy | Copy reworded; check kept strict |
| 3 | Screenshot review | Duplicate "Sample data" tags; "Integrated in Baloda Bazar" read oddly; tables squeezed on a phone | All three fixed |
| 4 | `verify.py` A1 | Assumption A14 was never shown beside a figure: the FY2026-27 carbon page was not in the audited set | Page added to the freeze and audit |
| 4 | `verify.py` G4 | Gate passed vacuously when the note did not exist | Gate now requires the file |

## Next up (not in v1)

1. Cyclone and storm-surge layer for Mundra and Paradip.
2. Notified CCTS targets and Scope 2, replacing A12.
3. Aqueduct point-in-basin lookup in the pipeline, replacing the hand-filled CSV.
4. Humid-heat indicator (wet-bulb) for coastal and eastern plants.
5. Clinker stock days per grinding unit, replacing A11.
