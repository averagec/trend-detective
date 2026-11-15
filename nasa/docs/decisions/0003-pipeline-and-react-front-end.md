# 0003 — Pipeline in Python, static JSON, React front end

- Status: **superseded by 0004** (2026-11-14). The pipeline and static-JSON parts still stand. The
  React front end was removed on the team's request: the app is now a dynamic Flask app.
- Date: 2026-11-14

## Context
- The data is MERRA-2 (see `docs/data-sources.md`), downloaded as Harmony subsets to
  `data/raw/merra2/`.
- The trend maths is in Python (ADR 0002) and is tested with golden tests.
- The team wants a React web app for students and the public, with a plain-language result for
  each question.
- AGENTS.md rule 5: every demo case must run offline from `data/demo/`. The live NASA
  connection must not be needed on demo day.

## Decision (proposed)
1. **Process (Python).** `process/merra2_clean.py` cleans and aggregates the raw subsets into
   `data/processed/merra2/monthly_regional.csv`. `process/analyse_trends.py` calls `core/summary.py`
   and writes one JSON file per (region, variable) plus `index.json`.
2. **Contract = JSON files.** The web app reads `data/processed/json/`. The schema is
   the `build()` output in `process/analyse_trends.py` (region, variable, unit, series with
   value and anomaly, statistics, sentence, warnings).
3. **Front end (React).** A Vite + React app in `web/`. It has no statistics code. It
   shows: the question flow (what, where), the time series with the trend line, the per-decade
   value with its CI, both test results, the sentence, and any warnings. It can compare two
   regions side by side.
4. **Demo cases** are copied from the processed JSON into `data/demo/` and committed, so the app
   runs offline.
5. **Python `app/nasa_view.py`** stays as an internal inspection tool. It is not the judges' UI.

## Why
- Keeps the validated statistics in one place, which NASA reviewers can read.
- A static JSON contract lets the pipeline and the UI be built and tested separately.
- No server is needed for the demo, which matches the offline rule.

## Alternatives considered
- **Streamlit (Python only).** Fastest to build, but it limits the storytelling and styling the
  award criteria reward.
- **FastAPI back end + React.** A live API works, but it adds a failure point on demo day and
  needs hosting. Only worth it if users must choose any region on the fly.

## Consequences
- The web build can start once the team agrees the JSON schema and the regions
  (`catalog/regions.py` is a proposal).
- Any new statistic is added to `core/` with a golden test, then passed through to the JSON.
  The web app does not compute it.

## Open questions for the team
1. Regions: the three in `catalog/regions.py`, or others?
2. Which variables form the demo cases (`docs/product-sense.md` needs ≥2)?
3. Hosting for the live link, or a static build only?
