# Merge the TD-OS website into trend-detective

- Owner: team
- Started: 2026-11-15
- Status: active (DRAFT: needs the decisions below before step 1)

## Goal
The website from `borkthecat/trenddetective` (3D office, TD-OS desktop, MAP.EXE) runs inside this
repo at `web/`, served by the Flask app, and every number on screen comes from `core/` through
`/api/*`. Done when: `./scripts/check.sh` passes (including the web build), a clean laptop with no
network runs all demo cases, and `web/` contains no statistics code.

## Context
- Review of the web repo: clone at `C:\Users\Jacob\Documents\trenddetective-web` (1 commit, `882bedf`).
- `ARCHITECTURE.md` invariant: every user-facing number comes from `core/`. The web repo breaks it
  (`src/stats/trend-analysis.js`, parts of `src/os/region-map.js`, all data synthetic).
- ADR 0004 (Flask, dynamic) is the current front-end decision. ADR 0003 used `web/` for a Vite app.

## Decisions needed first (blocking step 1)
1. **Front end = TD-OS, served by Flask?** Recommended: yes. Flask serves `web/dist/` and keeps
   `/api/meta`, `/api/trend`. The current `templates/index.html` page stays as `/classic` (internal
   check) or is removed. Write this as ADR 0005 (supersedes the UI part of 0004).
2. **How to import.** Recommended: `git subtree add --prefix=nasa/web <url> main` (keeps history,
   teammate can keep pushing to their repo and we `subtree pull`). Alternative: one-time copy,
   then the team works only here.
3. **Regions on the map.** The web map shows 11 countries; `catalog/regions.py` has 3 large boxes.
   Recommended for the deadline: show the 3 regions on the existing WORLD view first; countries
   later (needs country masks in `process/`, see step 8).
4. **Which headline estimator.** Python: OLS + autocorrelation-adjusted CI (science rule 3).
   Web: Sen's slope. Recommended: Python's, with Sen shown second, as the rules say.

## Steps
- [ ] 1. Import into `nasa/web/`. Leave out `assets/source/office_original.glb` (12 MB, rebuild-only)
      and keep `package-lock.json`. Add `node_modules/`, `dist/` to the ignore list. Verify
      `npm ci && npm run build` works (it did on the clone: 668 kB JS, 179 kB gzip).
- [ ] 2. Serve the build from Flask (`/` -> `web/dist/index.html`, static assets). Dev: Vite proxy
      `/api` -> Flask. Add the web build to `scripts/check.sh` when `web/` exists.
- [ ] 3. Adapter `web/src/data/api.js` (fetch `/api/meta`, `/api/trend`) replacing
      `DATASETS`/`makeSeries`/`analyse` in `desktop.js` (SETUP, PLOT). Use `catalog/` text for
      labels. Units come from the API (K, mm day-1): convert for display in the adapter only.
- [ ] 4. Move the LINEUP and verdict logic into `core/` (new `core/lineup.py`): AR(1) surrogates
      (seeded), later-start-year check, leave-one-year-out check, instrument-gap flag, verdict
      (DETECTED / NOT YET DETECTABLE / SUSPECT). Golden tests with known answers; update
      `docs/statistics.md`. Expose `POST /api/lineup`. UI only draws the histogram it gets back.
- [ ] 5. Map: add `core` functions for Benjamini-Hochberg across regions and "years needed"
      (Weatherhead). Expose `/api/map?variable&from&to`. Port the map window to read it.
- [ ] 6. Delete `web/src/stats/` and the stats in `region-map.js` (`compute`, `ncdf`, `demoMonthly`).
      Add a `check.sh` rule: no `web/src/stats/`, no `Math.sqrt` in `web/src/os/`.
      Migration check before deleting: run JS and Python on the same series, list the differences.
- [ ] 7. Offline demo safety: self-host the fonts (the ttf files exist in `scripts/fonts/`; convert
      to woff2), remove the Google Fonts `<link>` in `index.html`. Replace "DEMO DATA, SHAPED LIKE
      ..." and `TOOL FALSE ALARMS: [x.x]%` with real text. Test with the network off.
- [ ] 8. Data scripts (see table below). Country masks for the 11-country map if decision 3 says so.
- [ ] 9. Other panels as TD-OS apps: OCEAN.EXE (`/ocean` content, `ocean_ssh_mean.png`) and the SAR
      scenes. Optional; after the core flow works.
- [ ] 10. `verifier` subagent pass on each demo case in the browser (desktop width). Then freeze.

## How the scripts map onto the site
| Script (this repo) | Output | Used by the site |
|---|---|---|
| `process/merra2_clean.py` + `scripts/build_processed.py` | `data/processed/merra2/monthly_regional.csv`, `data/demo/` | Flask `Store` -> `/api/trend` -> SETUP/PLOT/LINEUP |
| `process/analyse_trends.py` | per-series JSON incl. `band` | Same shape as `/api/trend`; use as offline snapshot |
| `scripts/raw_to_json.py`, `render_demo_images.py` | GeoJSON, ocean/SAR PNGs | OCEAN.EXE (step 9) |
| `scripts/pull_nasa.py`, `ingest/*` | raw downloads | Not used by the site |

| Script (web repo) | Decision |
|---|---|
| `scripts/data/fetch_power.mjs` | Drop for the demo: NASA POWER is a second, different data path. Keep only if the 11-country map needs a stopgap. |
| `scripts/data/import_grace.py` | Keep for later: GRACE is not in the Python pipeline yet. Until it is, `tws` cases stay locked. |
| `scripts/data/sample_points.json` | Reuse for country masks (step 8), after checking the cells. |
| `scripts/assets/*`, `scripts/fonts/*` | Move under `web/scripts/`, unchanged. Not part of `check.sh`. |

## Progress log
<!-- Append one line per session: date — what changed — what's next. -->
- 2026-11-15 — cloned the web repo, built it, read both sides, drafted this plan. Nothing merged. Next: decisions 1-4.
- 2026-11-15 — ui-update: map-first MAP.EXE, fullscreen/scaling, Indonesia focus. New real layer SEA LVL: per-city ECCO sea level computed by `core` (`summarise` + new `benjamini_hochberg`), exported to `web/public/data/indonesia_sea_level.json` by `scripts/export_indonesia.py`; the page computes nothing for it. Province outlines and cities from Natural Earth (`scripts/build_indonesia_geo.py`). Other layers still synthetic and labelled SAMPLE DATA. Next: step 3 (API adapter) for t2m/precip; per-province MERRA-2 needs the raw grids (Jacob).

## Decisions & surprises
- The web `tws` / `sst` / `ndvi` / `aod` layers have no data in this repo (only t2m and precip for 3
  regions, plus ocean SSH). Those buttons must be locked or removed, not left on synthetic data.
- Web flow guesses before plotting and flags EXPLORATORY after setup changes: keep this, it is a
  strong fit with the science rules.
- Python's Mann-Kendall p is unadjusted; the web's is autocorrelation-adjusted. Do not show both
  labels for one number: pick one in `docs/statistics.md` and use it everywhere.
