# CIRCLE for every map layer

- Owner: agent (with averagec)
- Started: 2026-11-15
- Status: active

## Goal
Drawing a CIRCLE on MAP.EXE gives a real answer for every layer that has grid data (SEA LVL, TEMP, RAIN now; WATER once its GRACE grid is built; the new MERRA-2, GPCP and GLDAS layers once they are exported). Layers without grid data say which layers do have it. Verified by a browser CIRCLE on each layer, `POST /api/cell-circle` returning 200 for each layer on the deployed site, and `scripts/check.sh` passing.

## Context
- Client gate: `nasa/web/src/os/region-map.js` `circleResult()` and `cellLayer()`, which read `web/public/data/indonesia_cells.json`.
- Export: `nasa/scripts/export_cells.py` writes that JSON and `data/processed/cell_stats/<layer>.json`. Its `CUBES` table maps web layers to cube files (only `t2m`, `precip`, `tws`).
- Server: `src/trend_detective/app/web.py` `/api/cell-circle` reads `cell_stats/<layer>.json`. Missing file: `missing_hint()` in `process/cell_circle.py`.
- Cubes: `data/processed/cells/{merra2,gpcp,gldas}_idn.npz`. No `grace_idn.npz` yet.

## Steps
- [x] 1. Re-run `scripts/export_cells.py` with the cubes present. `t2m` and `precip` written; `tws` skipped until its cube exists.
- [ ] 2. Build `grace_idn.npz` (`process/cell_cube.py`). WATER then gets grid data.
- [ ] 3. Extend `CUBES` with `qv2m`, `vpd`, `evap`, `tsurf`, `ps` (merra2 cube) and the gpcp and gldas cubes, using the web layer keys.
- [ ] 4. Daily max (`t2mmax`) needs the daily cube (M2SDNXSLV). Not built yet.
- [x] 5. The toast names the layers that have grid cells.
- [ ] 6. Make the deployed server serve the regenerated `cell_stats` (check the Vercel `nasa` service).
- [ ] 7. Browser-check CIRCLE on each layer; run `tests/process/`, `tests/app/`, `scripts/check.sh`.

## Progress log
<!-- Append one line per session: date — what changed — what's next. -->
- 2026-11-15 — RCA: `indonesia_cells.json` was exported when the cube was not found, so only SEA LVL had grid data. Re-export done (SEA LVL, TEMP, RAIN); toast updated; build, 12 web tests and check.sh pass; browser check shows the new message on SOIL 0-10. Next: step 2 (GRACE cube) and step 3 (extra layers).
- 2026-11-15 — Repo state changed under this session (branch switched to main, stash created, cubes moved to `data/processed/cells-backup-20261115/`). Cubes restored by copy from the backup; backup folder left in place.

## Decisions & surprises
- The cube folder `data/processed/cells/` was missing once during this session. Restored from `origin/main` and then from the backup folder by copy. Check it is present before re-exporting.
- The export only knows three layers, so the new map layers (humidity, VPD, evaporation, land temperature, GPCP, GLDAS) still have no CIRCLE grid. Step 3 covers them.
