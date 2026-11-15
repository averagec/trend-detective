# Hackathon 48h build

- Owner: team
- Started: 2026-11-14
- Status: active

## Goal
A submitted entry that meets full scope (visualisation + significance analysis) with ≥2
demo case studies that pass `./scripts/check.sh`, plus the project page and demo video,
submitted before the official deadline (TODO: confirm time, SGT).

## Context
`docs/product-sense.md`, `docs/science-rules.md`, `ARCHITECTURE.md`, claude.ai project doc
`claude/project-context.md`.

## Steps
- [x] 0. Harness + validated stats core (`core/trend.py`, golden tests)
- [ ] 1. Combine the 3 reviews → pick the concept → update product-sense.md "Status"
- [ ] 2. ADR 0003: UI framework
- [ ] 3. Pick 2–3 demo cases (variable + region + why it's interesting) → `docs/demo-cases.md`
- [ ] 3b. Demo case: SAR coastal change (Singapore east / Ca Mau / Jakarta; `catalog/sites.py`)
- [ ] 4. Ingest for the demo variables → cache to `data/demo/`
- [ ] 5. App: question flow → plot → trend + verdict sentence
- [ ] 6. Regional comparison (opposite trends) view
- [ ] 7. Verifier subagent pass on every demo case
- [ ] 8. Freeze features at T-8h: write-up, video, submission

## Progress log
- 2026-11-14 10:20 SGT — harness and stats core in place; waiting on reviews.

- 2026-11-14 15:30 SGT — added core/shoreline.py (+golden tests), catalog/sites.py, ingest/sar.py (one scene/month, pinned orbit). Not run on real ASF data yet: build sandbox has no NASA network access.

- 2026-11-14 15:40 SGT — added ingest/ocean_download.py (CMR search + Earthdata download to data/raw/ocean/, manifest + provenance) and app/nasa_view.py (catalog / local / plot; display only). Lint clean (ruff). Not run against live NASA: build sandbox is blocked (403 from proxy) and the laptop returned no connection.

- 2026-11-14 — added scripts/raw_to_json.py: raw ocean downloads → data/processed/geojson/*.geojson (GeoJSON FeatureCollections, valid records only, rejects listed with reasons). Replaced the earlier .json outputs. Four datasets converted (ECCO 0.5° V4R4 and V4R4B, ECCO LLC90 V4R4, and the four SSH indicators), 312 or 1755 valid records each, nothing excluded. The 0.5° V4R4 and V4R4B means match data/processed/ocean_se_asia CSV to 5e-6 m. ECCO LLC90 V4R4B has no manifest.csv yet (download still running when checked, 82 files); rerun the script when it finishes. Added h5py to pyproject.

- 2026-11-14 — added ingest/merra2_download.py (MERRA-2 T2M monthly and T2MMAX daily, QV2M, PS for VPD, EVAP, PRECTOTCORR, TSURF). `plan` is a dry run: 18,759 unique files, 108.3 GB whole-file, nothing downloaded. Switched to Harmony subsetting (harmony-py added to pyproject) for the Asia-Pacific box (60,-50,179.375,60; east edge set to the grid max, because 180.0 left longitude unsubset): estimated 3.5 GB. Test: 2000 VPD inputs (M2TMNXSLV), 12 files, 5.1 MB, lat 221 / lon 192 as expected; T2M, QV2M, PS confirmed. Full run (`download --confirm`) not run: waiting for user approval. Variable names for the daily T2MMAX and the flux/land files not yet checked against a real Harmony output.
- 2026-11-14 — pipeline proposal and first build: catalog/regions.py (3 proposed regions), process/merra2_clean.py (QC, units, VPD, regional means; tested on the 2000 files), core/summary.py (OLS + Mann-Kendall sentence, warnings), process/analyse_trends.py (JSON for the web app), docs/statistics.md, ADR 0003 (proposed: React + Vite over static JSON). Fixed core/trend.py: a flat series with zero residual spread now gives p = 1 (was p = 0, a false "significant"). The full-download retry (monthly daily chunks, 2 jobs at a time) is still running in the background; the web app is not started.
- 2026-11-14 — ADR 0003 accepted. Built web/ (React 19 + Vite 8): question chips, region choice, compare mode, SVG chart with trend line, stats panel with warnings. Checked in the browser on synthetic sample JSON (not committed; web/public/data is git-ignored). Phone width: no horizontal scroll after a fix to the compare dropdown. Not yet run on real pipeline output, which waits for the full download.

- 2026-11-14 — React app removed at the team's request. Added the dynamic app: app/web.py (Flask) computes the trend for the chosen region, variable and year window on each request through process.analyse_trends.build() and core/summary.py (ADR 0004). Text moved to catalog/variables.py. analyse_trends.build() takes an optional year window. Tests: tests/app/test_web.py (7). Checked in the browser on synthetic sample data: the year window recomputes the trend. Flask added to pyproject.

- 2026-11-14 — ocean and radar pictures for the web app. scripts/render_demo_images.py writes data/demo/images/ocean_ssh_mean.png (average SSH over 312 ECCO months, shown as above or below the box average, with the three sites and the 20 radar scene outlines) and sar_browse_scenes.png (5 of the 20 Sentinel-1 previews). New /ocean page and /demo/<name> route in app/web.py; tests/app/test_ocean_page.py (4 tests). Finding: the SAR scenes cover lon 94.7–103.2, lat 2.1–32.2, so none of the three study sites (Singapore, Ca Mau, North Jakarta) is covered; the previews are context only. Site imagery needs scenes over the sites. Display only: no trend or p-value is computed in the script. check.sh passes; checked in the browser at phone and desktop widths.
- 2026-11-15 — web chart: 95% confidence band around the OLS line. core/trend.py `ols_band` (+ golden tests), passed through core/summary.py and analyse_trends.build() as `band` in /api/trend, drawn as a shaded path in app.js (no statistics in the browser). Method in docs/statistics.md 4.2a; the level-term convention is an open question for the team.
- 2026-11-15 — scripts/build_processed.py: one region + variable through ingest (only with --confirm-download), clean (merged into monthly_regional.csv, other series kept), analyse, and a demo copy to data/demo/ (6 proposed cases: t2m and precip in each region, 188 KB CSV + 440 KB JSON). `--dry-run` checks the plan and that the app can read the CSV. Real run of the demo step done offline from the committed CSV; ingest and clean not run (data/raw/ is not on this machine). The 6 demo cases are a proposal: the team has not picked them (step 3).
- 2026-11-15 — AppEEARS: public product list has none of the MERRA-2 variables (nor GLDAS/GPCP/GRACE), so scripts/appeears_submit.py was not built (docs/data-sources.md). check.sh: pytest never ran (the `tests/*.py` guard missed tests/core and tests/app); fixed. Ruff failed on two older scripts: import fixes applied, style rules ignored for just those two files in pyproject.toml. Demo checked in the browser on data/demo (band shows on both compared regions, only local requests).
- 2026-11-15 — API for series analysis: JSON errors on every /api route; docs/api.md freezes /api/trend (+ n_eff, r1); new POST /api/analyse (user series, validated, padded to January) and GET /api/scan (BH q-values across region x variable); core `mann_kendall_ar1` with ADR 0007 and golden tests (tests/core/test_trend_additions.py); page shows n_eff, both MK p-values, q-value and a paste box. Found: `mann_kendall` computes Sen's slope per valid value when months are missing (+25% at 14% missing); not fixed, xfail test marks it. Next: team decisions listed in ADR 0007 and statistics.md section 8.
- 2026-11-15 — branch feature/trend-exe-api-integration: Flask serves web/dist at / (plain page at /classic), web/src/data/api.js + to-chart.js, chart-view.js renderChart, TREND.EXE window reading /api/trend + /api/scan; web tests (npm test) and a fixture-shape test keep site and API in step; check.sh builds the site. Checked in the browser (chart, analysis, error and server-down paths). Merge with the teammate's trend-engine branch is pending; not pushed. Open: sentence (p) vs q verdict can disagree (ADR 0008).

- 2026-11-15 — city and circle selection (plan approved; ADR 0005). `process/cell_cube.py` builds per-cell MERRA-2 (7 variables) and GPCP cubes for the Indonesia box, reproducing the hand-checked Jakarta trends (T2M +0.1645 K/decade, PRECTOTCORR +0.3276 mm/day/decade). `process/selection.py`: city cell, 75 to 250 km circle with the centre rule, 4-cell minimum, static cell mask, per-cell trends with the mixed-sign warning, combined average as reference. Routes `/map`, `/api/cities`, `/api/cell`, `/api/variables`, `/api/analyse`. Checked in the browser on a test city list (the team's list is not yet supplied). Not yet done: GLDAS and ECCO cubes, T2MMAX cube, step 4 (cause analysis, deferred), merge with the other dashboard repo (its stack not yet inspected). `scripts/check.sh` now runs ruff and pytest (it had been skipping both silently).

- 2026-11-15 — review of the next step (monthly or yearly view, flood and drought variables, one output shape for the external app). No build yet: waiting for the user's decisions. Finding: the mixed-signal warning in `analyse_circle` fires on about half of null 50-cell circles (simulation with independent cells, `summarise` at 5%), so it needs a multiple-testing guard before the demo. Tests: 72 pass.

- 2026-11-15 — flood and drought flow for one city (ADR 0006, proposed; not yet committed). Core: `core/events.py` (percentiles against the same calendar month or annual totals, extreme at the 10th or 90th percentile, trend significance, one-time event vs in-trend call, amount and percent) and `core/comovement.py` (factor co-movement with rainfall, autocorrelation-adjusted). Process: `process/event_series.py` (alignment, monthly totals, ENSO/IOD/PDO monthly means), city list gains a `rainfall_source` column. App: `/event` page and `POST /api/event` (`app/event_api.py`). Factors are shown as co-movement, never as causes. Checked on real data: Jakarta 1997 annual drought is a one-time event against a wetting trend; Feb 2007 flood sits at the 89th percentile, just under the 90th. Tests: 106 pass; ruff clean. Open: the circle mixed-signal warning fires on 52% of null 50-cell circles (confirmed by simulation), so it needs a multiple-testing guard; co-movement p-values are not corrected for the number of factors.

- 2026-11-15 — user decisions. The trend engine uses its own statistics, proposed in `docs/stats_trend.md` (not `docs/statistics.md`): Mann-Kendall after pre-whitening as the headline, Sen's slope for size, OLS kept as a secondary check, Benjamini-Hochberg across circle cells. Changes to `docs/science-rules.md` listed there for decision. Map tiles use the internet; "local" means the data is read from local files. The city and circle engine in `selection.py` is a test of the logic; the new engine replaces it. City list will be in the GitHub repo later; city-to-cell mapping proposed in chat. Nothing committed.

- 2026-11-15 — conflicts cleared (user decisions): (1) JS stats in `web/src/stats/` stay for now; the core-only rule is bypassed until the replacement is built. (2) Both OLS and Mann-Kendall are shown; no single headline. (6) Keep Flask; the API adds the regional CSVs (GLDAS, GPCP, GRACE, ECCO) and serves the regional map (spec in chat, not built). (9) City cell is a MERRA-2 land cell. (11) Soil moisture included, from the GLDAS regional rows. (13) GRACE is already in `witness_regional.csv`; NASA POWER is MERRA-2-based and is a cross-check only. Not yet built: yearly view, BH on cell p-values, the regional route, the 31-city table. Merge plan after all conflicts are cleared. Deadline still to confirm.

- 2026-11-15 — built the core parts: `summarise(..., steps_per_year=1)` for yearly series (no seasonal removal, slope x 10); `process/frequency.py` `to_yearly` (year needs 10 valid months); `core/trend.benjamini_hochberg` (same as origin/main). Tests: 117 pass (new: tests/core/test_yearly.py, tests/core/test_bh.py, tests/process/test_frequency.py). Not built yet: the `/api/map` route, the `freq` parameter in the API, the circle tool in the dashboard, the locks, the 31-city table, the merge. Weatherhead "years needed" not implemented: formula to confirm first.

- 2026-11-15 — `GET /api/map` (process/regional_map.py, both tests, BH across regions per test; 8 tests). Web: CIRCLE.EXE (`web/src/os/circle-tool.js`): click the map, radius 75 to 250 km, variable, RUN calls `POST api/analyse` circle mode; the page draws cells and text only. SST layer locked (no real series). Vite dev proxy `/api` to 127.0.0.1:5000. `npm run build` passes. Not done: TEMP, RAIN and WATER still synthetic (the 11-country map has no real values until country masks or a 3-region panel exist); Flask does not serve `web/dist` yet; no browser check of CIRCLE.EXE; Weatherhead years-needed; the 31-city table; the merge.

## Decisions & surprises

