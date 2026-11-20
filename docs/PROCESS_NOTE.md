# Process note

## The problem I chose

Meera is asked one question by three audiences: what is our business exposure to climate events, today and by 2040? V1 answers it as a register she can put in front of her board: where revenue sits against three physical hazards, today and in 2040, plus one page on carbon cost.

## What I researched

- **The plant file.** Clinker balances exactly (12.61 Mt made, 12.61 Mt used). Reported Scope 1 includes clinker shipped out, so emissions per tonne of cement mislead unless reallocated. Two kilns feed all three grinding units and carry 52% of revenue.
- **Physical data.** The Open-Meteo Climate API gives daily output from seven models, on one pathway close to RCP8.5, ending in 2050. Its flood API has no 2040 view. Aqueduct 4.0 projects water stress for 2030 and 2050 only. Thresholds come from the India Meteorological Department.
- **Transition.** Cement received CCTS intensity targets in October 2025. As of October 2026 sources, no certificate had traded; estimates were Rs 400-900 a tonne.
- **What exists.** XDI's public material describes ten hazards, five rating bands and value-at-risk. Shree Cement's climate report assesses heat, water stress and urban flooding plant by plant, close to the three I chose.

## Assumptions

All 17 are in `config/assumptions.yaml` and on the Method page, each tagged beside the figures it affects. Those that move the answer most:

- "Exposed" means rated high or worse (A10).
- The band edges for heat and rain are mine (A05, A07).
- Grinding units have no clinker stock or second supplier (A11).
- Targets tighten 2% a year and Nimbus abates nothing (A12, A13).
- The 2040 carbon prices are illustrative (A15).

## What I cut, and why

- **Rupees lost.** It needs damage functions I could not defend. Revenue at exposed plants is a fact; a loss figure would be a guess.
- **Cyclone and storm surge.** The biggest gap, for Mundra and Paradip. No open source gave a 2040 view in the time, so the product says "not assessed" on the page.
- **Flood depth and humid heat.** Heavy-rain days stand in for the first; the second is flagged as a gap.
- **A map.** Open map tiles draw India's boundaries in a way an Indian board pack should not carry. The clinker diagram says more.
- **A scenario switch.** The source has one pathway, so plant pages show the spread between models instead.
- **Most of transition risk.** "Climate events" is a physical question. I kept carbon cost because it is the larger rupee figure.

Any dataset still on sample values is flagged on every page, and `scripts/verify.py --release` blocks submission until both are real.

## How I used AI

**Tools.** Claude and Gemini, working as coding agents with web search: research, architecture, core business logic, Jinja templates, 92 test cases, and drafts of the ticket and process note. I paired them with local Python REPL runs to independently verify calculations.

**How.** It planned first, then built in sprints. Each ended with a script that recomputes totals from the plant file, audits every page and lists the steps only I can do.

**Where it was wrong.** Its first plan defined "2040" as 2031-2050. The API documentation says the data ends on 2050-01-01, so the last year would have held one day. Reading the API response during verification caught it: the window became 2030-2049, and the pipeline drops any year with under 330 days. It also initially overlooked grinding unit clinker dependencies, treating grinding units as near zero-emission; I caught this during data reconciliation and enforced emissions reallocation from kilns.
