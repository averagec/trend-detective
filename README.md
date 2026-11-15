# trend-detective
NASA Space Apps 2026: Be An Earth System Trend Detective

# Trend Detective

An interactive detective game for the NASA Space Apps Challenge 2026 (Earth System Trend Detective). You walk into a 3D office, log in to a retro computer, and test whether climate trends in Southeast Asia are real or just noise.

## Project summary

**What we built.** Trend Detective is a browser-based detective game, built on NASA data, that tests whether a climate trend is real. The player logs in to a retro desktop, picks a variable, a place and a period, and gets a verdict: **Detected**, **Not yet detectable**, or **Suspect**. The main case is sea level along 31 Indonesian coastal cities, from the ECCO ocean model. MAP.EXE also shows air temperature, rainfall and water stored on land, and lets you draw a circle to average the grid cells inside it.

**How it addresses the challenge.** The challenge asks what is changing, where, how much, and whether the change is significant. Trend Detective answers each part:

- **Variables:** sea level, air temperature, rainfall and water storage on land, from ECCO, MERRA-2, GPCP and GRACE.
- **Where and how much:** a trend per year for each city or circle, with units and a 95% range.
- **Significance:** a trend test that adjusts for autocorrelation, a Mann-Kendall test with Sen's slope, and a comparison against 1,000 simulated trend-free records.
- **Opposite trends:** regions are shown side by side rather than averaged, and when many places are tested together, the Benjamini-Hochberg procedure controls false discoveries.

**Why it matters.** A trend line on its own invites over-reading. Monthly Earth data is autocorrelated, so a naive test claims more certainty than the data support, and a change in data source can look like a climate trend. Trend Detective marks those cases **Suspect** instead of reporting them as change. Sea level matters for places such as Jakarta, which floods partly because the ground is sinking. The sea-level data alone does not capture that, and the app says so on the case.

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

## References

Data citations, one per collection, are in [`docs/references.md`](docs/references.md).

Methods:

- Santer, B. D., et al. (2000). Statistical significance of trends and trend differences in layer-average atmospheric temperature time series. *Journal of Geophysical Research*, 105(D6), 7337–7356. https://doi.org/10.1029/1999JD901105
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13, 245–259.
- Kendall, M. G. (1975). *Rank Correlation Methods*. Charles Griffin.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the American Statistical Association*, 63(324), 1379–1389.
- Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society: Series B*, 57(1), 289–300.
