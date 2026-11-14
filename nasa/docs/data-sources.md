# Data sources

One entry per source. Read the entry before touching that source; add quirks you
discover. Use the `data-scout` subagent to explore a new source (keeps raw data out of context).
Prefer **monthly** (then daily) products: these are the easiest according to the brief.

## Candidate sources (from the challenge brief; access details unverified)
| Source | What it gives | Link |
|---|---|---|
| Giovanni (GES DISC) | Variable menus; area-averaged time series, downloadable | https://giovanni.gsfc.nasa.gov/ |
| Hydrology Time Series (GES DISC) | Point time series for hydrology models (e.g. GLDAS) | https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series |
| AppEEARS | Subset/transform land products (e.g. MODIS) to point/area time series | https://appeears.earthdatacloud.nasa.gov/ |
| NOAA Climate Data Online | Station observations for validation | https://www.ncei.noaa.gov/cdo-web/ |
| KNMI Climate Explorer | Reference trend analyses to cross-check our numbers | https://climexp.knmi.nl/ |
| CSA RCM / SWOT | SAR and water-surface data (advanced, probably out of scope) | https://donnees-data.asc-csa.gc.ca/en/dataset/rcm |

Most NASA Earthdata access needs a free Earthdata Login: store it as `EARTHDATA_USERNAME`
/ `EARTHDATA_PASSWORD` in `.env`, never in code.

## Hackathon fallback
Before the demo, cache every demo-case series to `data/demo/` (small CSVs, committed)
so the demo never depends on a live API.

## Entry template
### <Dataset name>
- Provider / link:
- Variable(s), units:
- Access: (env vars) / download
- Resolution (time, space), time range:
- Known quirks:
- Fetched by: `src/trend_detective/ingest/<name>.py` → cached at `data/raw/<name>/`

### Ocean collections (NASA CMR + Earthdata), Asia-Pacific 1992–2022
- Provider / link: NASA CMR search (https://cmr.earthdata.nasa.gov/search); downloads via Earthdata Login.
- Variable(s), units: per collection (discover with the catalog command; no variable list is pinned yet).
- Access: `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in `.env` for downloads; search is public. `NASA_API_KEY` is not used for these archives.
- Resolution (time, space), time range: per collection; window and box are CLI args (default 1992–2022, 60,-50,180,60).
- Known quirks: granules are global tiles; the bbox filters which granules are fetched, not the pixels inside them. Clip in the viewer or the analysis step. Downloads are not yet verified against live NASA.
- Fetched by: `src/trend_detective/ingest/ocean_download.py` → cached at `data/raw/ocean/<short_name>/`
- Viewed by: `src/trend_detective/app/nasa_view.py`
- GeoJSON export: `scripts/raw_to_json.py` → `data/processed/geojson/<short_name>.geojson` (one Feature per valid record; gridded records carry the SE Asia box as their Polygon, indicator records have null geometry; rejected files listed under `excluded` with a reason).
- Quirks found in the export: ECCO V4r4 granules end Dec 2017 (312 months, 1992–2017), not 2022 as the window says. The LLC90 native grid mean is about 8 mm higher than the 0.5° product on average (different valid-cell mask), so use the 0.5° product for the demo. Indicator text files: the undated file matches the newest dated snapshot; older dated copies are shorter.

### MERRA-2 reanalysis (NASA GES DISC, version 5.12.4)
- Provider / link: GES DISC via NASA CMR search (https://cmr.earthdata.nasa.gov/search); downloads via Earthdata Login.
- Variable(s), units: T2M (K, 2 m air temp, monthly mean), T2MMAX (K, daily max, collection M2SDNXSLV), QV2M (kg/kg, 2 m specific humidity), PS (Pa), EVAP (kg m-2 s-1, surface evaporation), PRECTOTCORR (kg m-2 s-1, bias-corrected precipitation), TSURF (K, land surface temperature incl. snow). VPD is not a MERRA-2 variable: derive it from T2M, QV2M and PS.
- Collections: M2TMNXSLV (monthly, single-level), M2SDNXSLV (daily stats), M2TMNXFLX (monthly fluxes), M2TMNXLND (monthly land). Stream file names change by year (MERRA2_100/200/300/400).
- Access: `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in `.env` for downloads; search is public.
- Resolution (time, space), time range: monthly files 1980-01 to present (561 files per monthly collection as of 2026-11-14); daily statD 1980-01-01 onward (17,076 files). Grid about 0.625 x 0.5 degrees, global.
- Size: whole files are about 108 GB for the full record (18,759 files; monthly files about 75 MB, daily statD about 1.7 MB). Harmony subsets to the Asia-Pacific box (lon 60–180, lat −50–60) and the chosen variables: estimated 3.5 GB (42,653 grid cells per variable, 4 bytes each).
- Known quirks: every whole file holds about 100 variables, so we subset with Harmony (harmony-py, one job per collection and year). The direct GES DISC OPeNDAP path is not usable: goldsmr4 returns 410 and the data.gesdisc path returns 404 (checked without login). CMR page-number paging stops at 10,000 results, so discovery runs one year at a time. Variable names for the monthly and daily collections were not verified against the spec PDF (unreadable from the build sandbox); check on the first Harmony output file. Land and flux names confirmed only on the hourly EE catalog pages (EVAP, PRECTOT, EVLAND, TSURF).
- Fetched by: `src/trend_detective/ingest/merra2_download.py` (`plan` = dry run, `download --confirm` = real run via Harmony) → cached at `data/raw/merra2/subset/<collection>/<year>/`
