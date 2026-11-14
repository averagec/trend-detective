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

## Decisions & surprises

