# Trend Detective

An interactive detective game for the NASA Space Apps Challenge 2026 (Earth System Trend Detective). You walk into a 3D office, log in to a retro computer, and test whether climate trends in Southeast Asia are real or just noise.

## Running it

```bash
npm install
npm run dev
```

Build for production with `npm run build`. The output goes to `dist/`.

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

MAP.EXE opens on Indonesia with the **SEA LVL** layer: sea level next to 62 coastal cities, from
ECCO V4r4 (1992-2017). Every number on it is computed by the Python core, not the browser:

```bash
python scripts/build_indonesia_geo.py --ne-dir /path/to/natural-earth   # only if cities change
python scripts/export_indonesia.py                                     # writes web/public/data/indonesia_sea_level.json
```

Search a city or province from the toolbar. Inland cities (more than 20 km from the sea) show
no sea level. TEMP / RAIN / WATER / SEA are still synthetic and labelled SAMPLE DATA.
