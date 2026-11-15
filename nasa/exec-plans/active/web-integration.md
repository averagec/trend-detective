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
- [x] 2. (done on feature/trend-exe-api-integration; ADR 0008) Serve the build from Flask (`/` -> `web/dist/index.html`, static assets). Dev: Vite proxy
      `/api` -> Flask. Add the web build to `scripts/check.sh` when `web/` exists.
- [x] 3. (TREND.EXE, then SETUP/PLOT/LINEUP on branch feature/case-flow-on-engine; MAP reads the engine already) Adapter `web/src/data/api.js` (fetch `/api/meta`, `/api/trend`) replacing
      `DATASETS`/`makeSeries`/`analyse` in `desktop.js` (SETUP, PLOT). Use `catalog/` text for
      labels. Units come from the API (K, mm day-1): convert for display in the adapter only.
- [x] 4. (done: `core/lineup.py`, `POST /api/lineup`, ADR 0010) Move the LINEUP and verdict logic into `core/` (new `core/lineup.py`): AR(1) surrogates
      (seeded), later-start-year check, leave-one-year-out check, instrument-gap flag, verdict
      (DETECTED / NOT YET DETECTABLE / SUSPECT). Golden tests with known answers; update
      `docs/statistics.md`. Expose `POST /api/lineup`. UI only draws the histogram it gets back.
- [ ] 5. Map: add `core` functions for Benjamini-Hochberg across regions and "years needed"
      (Weatherhead). Expose `/api/map?variable&from&to`. Port the map window to read it.
- [x] 6. (done on feature/case-flow-on-engine; `check.sh` rule added; synthetic map statistics removed) Delete `web/src/stats/` and the stats in `region-map.js` (`compute`, `ncdf`, `demoMonthly`).
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
- 2026-11-15 — case-flow-on-engine: steps 3, 4, 6 done. CASES call `/api/lineup` (`core/lineup.py`, ADR 0010); `web/src/stats/` deleted; synthetic per-country map statistics and the year slider removed from `region-map.js` (unreachable); `check.sh` fails if browser statistics return. Left: step 5 (`/api/map` for the 11-country map; the box layers already read the engine), steps 7 to 10.

## Decisions & surprises
- The web `tws` / `sst` / `ndvi` / `aod` layers have no data in this repo (only t2m and precip for 3
  regions, plus ocean SSH). Those buttons must be locked or removed, not left on synthetic data.
- Web flow guesses before plotting and flags EXPLORATORY after setup changes: keep this, it is a
  strong fit with the science rules.
- Python's Mann-Kendall p is unadjusted; the web's is autocorrelation-adjusted. Do not show both
  labels for one number: pick one in `docs/statistics.md` and use it everywhere.
- 2026-11-15 — ui-update: limited to the team's 31 cities (23 coastal, 14 clear rises); 10m coastline for coast distance; grid-cell focus, CITIES dropdown, GIBS SAT toggle, animated flood sprite, click-to-enlarge charts. CASES now real-data only (`cases_data.json`: ECCO per city + MERRA-2 regional t2m/precip), synthetic case datasets removed, lineup shows the PYTHON CORE result beside its own. ABOUT.TXT and title ABOUT panel (mission, references, Team SanSong). Next: per-province MERRA-2 (Jacob's raw grids) to replace the SAMPLE layers.
- 2026-11-15 — bug-fixes: TEMP/RAIN/WATER are real box layers from regional_data.json (sample per-country data no longer shown); GRACE added to cases_data.json and CASE_005 WETTER_GROUND; pixel pin markers with larger hit area; SKIP for the intro, boot and dialogue (Esc too); MAP.EXE / CASES glow and a CLICK THE COMPUTER beacon; dragged windows keep their size; CIRCLE hidden when no analysis server; box charts use seasonal anomalies so partial years are not biased.
- 2026-11-15 — circle-tool: city pins and per-city grid view removed (small dots again, click zooms); Earthdata-style CIRCLE (press and drag) reads per-cell core trends from indonesia_cells.json (scripts/export_cells.py) offline, with pop-ups for too small / too big / no sea data. Replaces the server-only circle in MAP.EXE (the Flask /map page keeps its own).
- 2026-11-15 — circle per layer: export_cells.py exports per-layer cell trends (ssl now; t2m/precip once data/processed/cells/merra2_idn.npz is committed; tws needs a GRACE cube). The circle re-reads on layer switch. Verified with a synthetic cube in /tmp (not committed).
- 2026-11-15 — tutorial: TUTORIAL ? icon on the desktop (yellow ? sprite, `scripts/assets/make_question_icon.py`) opens TUTORIAL.EXE, 9 plain steps (map, layers, circle, trend, cases, setup, guess and evidence, lineup, verdict). Each step lights its icon. Room poster now shows the pixel Earth (`make_textures.py` poster, model rebuilt; text TRENDSEN). Next: check the step copy with the team; TREND.EXE needs the local server.
