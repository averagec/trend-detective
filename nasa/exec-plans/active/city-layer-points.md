# City points follow the layer filter

- Owner: agent (with averagec)
- Started: 2026-11-15
- Status: active

## Goal
Clicking a city dot on MAP.EXE (or picking it from the CITIES list) shows that city's data for the layer chosen in the top bar. On SEA LVL it still shows the ECCO sea-level card. On TEMP, RAIN, HUMID, LAND T, VPD and EVAP it shows the city's air/land/rain trend read from the grid cells around the city, the same test CIRCLE uses. The layer stays where the user put it (clicking a city no longer switches it to SEA LVL). Verified by a browser click on Bengkulu on each layer, `npm run build`, `npm test` in `nasa/web`, and `scripts/check.sh`.

## Context
- Root cause: `pickCity()` in `nasa/web/src/os/region-map.js` forces `st.v` back to the sea-level layer; `card()` only draws the city card for real (sea-level) layers; the layer buttons clear `st.city` when a non-sea-level layer is chosen.
- Per-city numbers reuse `POST /api/cell-circle` (`src/trend_detective/app/web.py`, `process/cell_circle.py`, ADR 0009) with a circle centred on the city. No statistic is computed in the page. Radius starts at 75 km (the engine minimum, `MIN_CELLS` = 4) and grows to 150 and 250 km only when too few cells have data.
- Sea-level city data stays in `web/public/data/indonesia_sea_level.json` (unchanged).
- The circle card renderer (`circleCard`) is shared with the city card through `areaCard`.

## Steps
- [x] 1. `pickCity()`: keep the current layer; sea-level talk lines only for SEA LVL.
- [x] 2. Layer buttons: keep the selected city when switching layers.
- [x] 3. `card()`: non-sea-level layers show the city card when a city is selected.
- [x] 4. `cityLayerCard()` + `loadCityArea()`: judge the cells around the city per layer, cached per city and layer, re-render when ready.
- [x] 5. Split `circleResult()` into `areaResult()` (shared) and `areaCard()` (shared renderer for circle and city).
- [x] 6. Build, `npm test`, `scripts/check.sh`; browser-check Bengkulu on TEMP, RAIN and SEA LVL.

## Progress log
<!-- Append one line per session: date — what changed — what's next. -->
- 2026-11-15 — City card follows the layer (TEMP, RAIN checked on Bengkulu: 75 km area, 4 cells; SEA LVL unchanged). Also guarded the `[data-lock]` handler in `toolbar()`, which threw when no layer is locked and stopped CIRCLE/FX/search from binding after a layer click. Build, `npm test` (16 pass) and check.sh pass. Next: check the 150/250 km fallback on a city with few cells; the CITIES dropdown rows still show sea-level mm/yr on other layers.

## Decisions & surprises
- A city's trend is an area: the grid cells within 75 km of it (4 to 6 cells for the cities checked). The card says so. It is not a point measurement.
- The dropdown rows in the CITIES list still show sea-level mm/yr under other layers. Left for a follow-up.
- The case button ("INVESTIGATE AS A CASE") stays on the sea-level card only; the cases are sea-level cases.
