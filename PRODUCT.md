# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **The real first reader is an assessment reviewer.** This is a v1 prototype submitted for the Oren
  product-manager assessment. A reviewer opens the link cold and forms an opinion in about the first
  minute, so the product thinking has to be legible in that minute. Confirmed by the owner on
  2026-11-20: "Assessors come first. Meera is the persona, not the real reader."
- **The persona the product is designed around is Meera Iyer**, Head of Sustainability at Nimbus Cement
  (a fictional company). Three audiences ask her one question: her board, her auditor and investors.
  She opens one link and takes them through it, with sources.
- Reading situations: a laptop or projector in a meeting, a phone, and a printed A4 board pack.

## Product Purpose

A climate exposure register. It answers "What is our business exposure to climate events, today and by
2040?" by showing where FY2025-26 revenue sits against extreme heat, heavy rain and water stress, plant
by plant, and what a carbon price would cost a year if Nimbus changed nothing.

It shows exposure, not predicted losses. Success: a reader can state the answer, see which plants drive
it, and trace any figure back to a dataset or a numbered assumption.

## Positioning

- **It follows the clinker.** Revenue is traced through the kiln to grinding-unit dependency, so a hazard
  at one kiln is counted wherever its clinker goes. Two kilns carry 52% of revenue.
- **Every figure admits where it came from**: a dataset name, or an assumption id (A01 to A17) that links
  to the Method page. Sample data is flagged on every page. Gaps are listed as "not assessed", never left
  blank.

## Operating Context

- Four page types, each a plain URL: overview (`/`), plant (`/plants/P01` to `/plants/P09`), carbon cost
  (`/carbon`, with `horizon` and `price` query parameters), and method (`/method`). Unknown paths get a
  helpful 404.
- Every view is a URL, so a board pack can link to an exact state.
- Built to be hosted on Vercel as a FastAPI app; not deployed yet (release gate G5). `scripts/freeze.py`
  renders the same pages to static HTML as a fallback.
- `python scripts/verify.py` is the self-check loop: tests, reconciliation to the plant file, a page
  audit, and the release gates.

## Capabilities and Constraints

- Server-rendered FastAPI and Jinja2, with the stylesheet inlined into every page.
- No JavaScript. The page audit fails on any `<script>` tag.
- No live API calls when a page loads. The pipeline runs ahead of time and commits
  `data/derived/hazards.json`.
- Pages must read at 400 px wide and print on A4.
- No map. Open map tiles draw India's boundaries in a way an Indian board pack should not carry
  (`docs/PROCESS_NOTE.md`).
- Five hazard bands: Low, Low to medium, Medium to high, High, Extremely high. "Exposed" means rated High
  or worse (assumption A10). Band names keep their capital wherever they name a rating; a test enforces it.
- Terms of the domain: clinker, kiln, integrated plant, grinding unit, gross block, Scope 1, CCTS (Carbon
  Credit Trading Scheme), crore (cr).
- The tests and `scripts/verify.py` read the rendered HTML, so the markup they look for is part of the
  contract.
- Redesign scope, confirmed by the owner on 2026-11-20: a new look and a new layout. Every figure,
  statement, tag and URL stays.
- Copy pass, asked for by the owner on 2026-11-20: grammar and capitalisation only. No figure, tag or URL
  changed.

## Brand Commitments

- Names: "Nimbus Cement" and "Climate exposure register" (sentence case in the masthead and page titles).
  Nimbus Cement Ltd is fictional and its plant data is invented; the footer says so on every page.
- Voice: plain, direct sentences that give the answer first and its limits second.
- No logo or other brand assets exist.

## Evidence on Hand

- `data/plants.csv` (nine plants, invented for the exercise) and `data/clinker_flows.csv`.
- `config/assumptions.yaml`: 17 assumptions, each with a value, a basis and a rationale.
- `data/derived/hazards.json`: Open-Meteo Climate API output (CMIP6, four models), real, built on
  2026-11-20.
- `data/manual/aqueduct_plants.csv`: WRI Aqueduct 4.0 categories, real, read on 2026-11-20.
- There is no photography, illustration, testimonial or customer. None may be invented.

## Product Principles

1. Answer first. The page states the answer before it shows the working.
2. Every number shows its source or its assumption.
3. Exposure, not loss. Never imply a forecast the data cannot support.
4. Gaps are stated, not hidden.
5. Every view is a URL, and it works on paper.

## Accessibility & Inclusion

- Must read at 400 px wide, work without JavaScript, and print on A4 with the hazard-band colours kept.
- Open decision: the owner has not set a formal accessibility standard.
