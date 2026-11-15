# CASES run on the engine (steps 3, 4 and 6 of web-integration)

- Owner: agent (with Jacob)
- Started: 2026-11-15
- Status: done, awaiting review and merge

## Goal
The CASES flow (SETUP, PLOT, LINEUP) shows only numbers that `core/` computed, the same engine that
TREND.EXE and MAP.EXE read, so one variable and window can never get two different answers. Done when:
`web/src/stats/` is gone, a `check.sh` rule keeps it gone, `POST /api/lineup` returns the lineup and the
case verdict, `bash scripts/check.sh` passes with ruff and pytest on PATH, and a browser run of the open cases
reaches a verdict (only CASE_005 WETTER_GROUND was run so far: 001 to 004 still to check).

## Context
- Why: ADR 0008 ("the browser still computes statistics elsewhere"), `web-integration.md` steps 3, 4, 6.
- Browser engine to retire: `web/src/stats/trend-analysis.js` (Sen slope, own Mann-Kendall, 1,000
  surrogates, checks, DETECTED / NOT YET DETECTABLE / SUSPECT). Used by `os/desktop.js` and `os/region-map.js`.
- Engine to build on: `core/significance.py` (`assess_single`), `core/summary.py`, `core/detect.py`
  (`years_needed`), `process/analyse_trends.py` (`build_custom`), `/api/analyse-series` (series as sent,
  outside the 1980-2018 window).
- Cases need series the server's Store lacks (ECCO per city, GRACE, 1980-2025), so the page sends the
  window's series, like `/api/analyse-series`. `cases_data.json` stays as data only.

## Steps
- [x] 1. `core/lineup.py` + `tests/core/test_lineup.py`: seeded AR(1) lineup, later-start-year check,
      leave-one-year-out check, instrument-gap check, case verdict on top of `assess_single`.
- [x] 2. `POST /api/lineup` in `app/web.py`, `process/analyse_trends.py` builder, `docs/api.md`,
      `tests/app` shape test, ADR 0010 (case verdict on the engine).
- [x] 3. Web: `data/case-data.js` (data only), `data/api.js` `getLineup` (PLOT reuses `analyseOwn` for the seasons-removed series), rewrite
      SETUP / PLOT / LINEUP in `desktop.js` to call the server, chart through `trendSpec`.
- [x] 4. `region-map.js` stops importing `stats/`; delete `web/src/stats/`; add the `check.sh` rule.
- [x] 5. Fixtures + web tests; ruff, pytest, `npm test`, `npm run build`; browser check of each open case.
- [x] 6. Update `web-integration.md`, `ARCHITECTURE.md`, `docs/statistics.md`; progress log.

## Progress log
<!-- Append one line per session: date — what changed — what's next. -->
- 2026-11-15 — branch feature/case-flow-on-engine from main (677aee9); venv outside the repo, baseline 352 pytest passed. Next: step 1.
- 2026-11-15 — steps 1 to 6 done: `core/lineup.py` (14 tests), `/api/lineup` (13 tests), SETUP/PLOT/LINEUP on the server, `stats/` deleted, `check.sh` rule, ADR 0010, docs. Full gate passes (379 pytest, 23 web tests, build). Browser-checked WETTER_GROUND end to end (SUSPECT across the GRACE gap), MAP.EXE on every layer, and the map to SETUP hand-off, no console errors. Not committed. Next: review, rebase on feature/circle-grid-layers if it merges first.
- 2026-11-15 — merged origin/main (1445fe9) into the branch (one conflict in `region-map.js` `toolbar()`, resolved). Two reports from the user: (1) CASES did not open on main: `cases_data.json` (b2b3f27) gained yearly flood and drought sets and the old browser loader threw on `reg.monthly.forEach`; `case-data.js` now tolerates them and SETUP offers monthly sets only. (2) Only SEA LVL could start a case from a city; the city card on the other layers offered "draw a circle". Now it offers INVESTIGATE AS A CASE for the layer and city (`areaCard`), fed by new per-city series for HUMID, LAND T, VPD, EVAP (`process/city_cases.py`, `scripts/export_city_cases.py`; nearest MERRA-2 cell, same rule as the TEMP and RAIN city series). Also fixed the cp1252 bug: `indonesia_cells.json` was invalid UTF-8 (degree sign) and the export scripts now write UTF-8. Browser-checked: CASES opens; every layer shows the case button on two cities; HUMID at Bengkulu runs to DETECTED; box card case on EVAP.

## Decisions & surprises
- `cases_data.json` on main was produced by a generator that is not in the repo (`export_indonesia.py` still writes tws and one place for TEMP and RAIN, no flood or drought). Regenerating with it would drop the 31 city series and the new datasets. `export_city_cases.py` only adds its four datasets to the committed file.
- The city card on the map reads the 4 or so cells within 75 km; the case reads the one nearest cell. Numbers differ slightly (Bengkulu humidity: card +0.21, case +0.19 g/kg per decade). The card shows which cell the case uses.
- Yearly event datasets (flood, drought) are in the data but have no engine path in CASES yet (ADR 0006 / `/api/event`).
- The one-year check almost never fires on real-looking data: one odd year is absorbed by the monthly means. Kept as a safeguard and unit-tested directly.
- `bash scripts/check.sh` only runs ruff and pytest when they are on PATH: use a venv (see memory note).
- Seen, not changed: a guess of "increase" on a `suspect` rise reads "DIDN'T MATCH" (old rule: only `detected` counts as a real direction).
- The old LINEUP verdict used its own Sen slope and an own Mann-Kendall. The new case verdict is the
  engine's ladder (both tests, same sign) AND the noise lineup AND the robustness checks. Three labels
  stay (the game uses them); they are computed in Python.
- `cases_data.json` has no `gap` key, so the old GRACE-to-GRACE-FO check never fired for WATER. The page
  now sends `gap_years: [2017, 2018]` for `tws`.
- The old page compared its own result with a "PYTHON CORE" line. That line goes: there is one result now.
- Teammate is working on `feature/circle-grid-layers` (`region-map.js`, `export_cells.py`): keep my edits
  to `region-map.js` small and rebase before merging.
