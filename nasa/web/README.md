# Trend Detective

An interactive detective game for the NASA Space Apps Challenge 2026 (Earth System Trend Detective). You walk into a 3D office, log in to a retro computer, and test whether climate trends in Southeast Asia are real or just noise.

## Running it

```bash
npm install
npm run dev
```

Build for production with `npm run build`. The output goes to `dist/`.

### With the analysis engine (TREND.EXE)

TREND.EXE reads every number from the Python backend. From the project root (`nasa/`):

```bash
cd web && npm ci && npm run build && cd ..      # once, and after changing web/
python src/trend_detective/app/web.py           # serves the site and /api at http://127.0.0.1:5000
```

For live reload while editing the site, run the backend as above and `npm run dev` in `web/`
(Vite proxies `/api` to port 5000). `npm test` checks the response mapper against real API
responses in `tests/fixtures/`. Contract: `docs/api.md`; decision: `docs/decisions/0008-*.md`.

## How it works

1. **The office**: a 3D room built with three.js. Click the monitor to log in.
2. **TD-OS**: a pixel-art desktop. Every case goes through the same five steps:
   - pick a variable
   - pick a region
   - pick a time period
   - plot the time series
   - test its significance against 1,000 trend-free fake series
3. **MAP.EXE**: a trend map of 11 Southeast Asian countries.
   - It shows the trend per decade, adjusted for year-to-year autocorrelation and corrected for testing 11 countries at once (Benjamini-Hochberg).
   - It shows how many years of data a clear trend would need (Weatherhead et al., 1998).
   - It animates weather that matches each country's trend direction: rain, storms or drought.

## Project structure

```
index.html                 page markup
src/
  main.js                  entry point
  audio/sfx.js             sound effects
  ui/dialogue.js           detective dialogue box
  ui/menu.js               title screen
  scene/office.js          3D office, camera and interaction
  os/desktop.js            TD-OS desktop, windows and case flow
  os/region-map.js         MAP.EXE
  os/pixel-weather.js      pixel-grid rain, storm and drought
  stats/trend-analysis.js  trend tests and datasets
  styles/                  one stylesheet per part of the interface
  assets/sprites/          sprites used by the stylesheets
public/
  models/office.glb        retextured office model
  images/                  desktop icons, earth image, ID photo
  data/sea_map.json        country outlines and centre points
scripts/
  assets/                  scripts that rebuild every generated asset
  data/                    NASA data import scripts
  fonts/                   fonts used to render textures
assets/source/             original source files
```

## Real NASA data

Without a data file, the map uses sample series and labels them **SAMPLE DATA**.

**Temperature and rainfall** come from NASA POWER, which is based on MERRA-2. No login is needed:

```bash
npm run data:power
```

This writes `public/data/sea_data.json`, and the map picks it up automatically.

**Water storage** comes from GRACE / GRACE-FO.

1. Download the JPL mascon file (RL06.3 CRI, netCDF) from PO.DAAC. This needs a free Earthdata login.
2. Run:

```bash
pip install xarray netCDF4 numpy
npm run data:grace -- path/to/GRCTellus.JPL...CRI.nc
```

## Rebuilding assets

```bash
pip install pillow numpy
npm run build:assets
npm run build:map
```

## Credits

- 3D room: ["Detective's Office - True Detective Fan Art"](https://sketchfab.com/3d-models/detectives-office-true-detective-fan-art-a5d7f399d7694053affb63f069740c4a) by nickheitzman, licensed [CC BY 4.0](http://creativecommons.org/licenses/by/4.0/). Modified: retextured screen, mousepad, corkboard and poster; walls and ceiling added.
- Country outlines: Natural Earth, via world-atlas.
- Data: NASA POWER (MERRA-2), GRACE / GRACE-FO.

## Indonesia sea level (real data)

MAP.EXE opens on Indonesia with the **SEA LVL** layer: sea level next to the 23 coastal cities
of the team's 31 study cities, from
ECCO V4r4 (1992-2017). Every number on it is computed by the Python core, not the browser:

```bash
python scripts/build_indonesia_geo.py --ne-dir /path/to/natural-earth   # only if cities change
python scripts/export_indonesia.py                                     # writes indonesia_sea_level.json and cases_data.json
```

Pick a city from the CITIES dropdown (grouped by region, with search). Clicking a coastal city
zooms to its ECCO grid: every 0.5° cell within 120 km, the cells used (yellow), each cell's own
trend, and the dashed 120 km radius. Inland cities (more than 20 km from the sea) show no sea
level. SAT toggles NASA GIBS Blue Marble imagery (needs internet; the chip turns mustard when
offline). Every chart opens full size when clicked (`src/ui/chart-view.js`).

TEMP, RAIN and WATER are real: one value for the Maritime Southeast Asia box (95-141°E,
10°S-10°N) from `regional_data.json` (`scripts/export_regional.py`, core statistics, BH across the
3 boxes). Click the box for the card, chart and case. MERRA-2 for temperature and rain, GRACE /
GRACE-FO for water stored on land. SEA (sea surface temperature), NDVI and AOD stay locked: no
series in the pipeline. CIRCLE only appears in `npm run dev` with the Flask server running.

CASES now runs only on real data from `cases_data.json`: sea level per coastal city (ECCO) and
MERRA-2 temperature and rain over Maritime Southeast Asia. INVESTIGATE AS A CASE on a city card
starts a case for that city. TEMP / RAIN / WATER / SEA map layers are still synthetic and
labelled SAMPLE DATA; their cards link to the real regional case where one exists.
