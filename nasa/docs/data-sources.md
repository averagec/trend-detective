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

**AppEEARS check (2026-11-15).** The public product list (`GET /api/product`, no login) returned 193
products from LP DAAC, NSIDC, OB.DAAC, USGS, ORNL and one GES DISC product (none is MERRA-2).
None of our MERRA-2 variables is offered: T2M, T2MMAX, QV2M, PS, EVAP, PRECTOTCORR, TSURF (VPD is
derived from the first three and PS). GLDAS, GPCP and GRACE are not offered either. So AppEEARS
cannot replace `merra2_download.py`. It only has different land products: for example MOD11A1/A2
land surface temperature (1 km), MOD16A2GF evapotranspiration (500 m), SMAP soil moisture, and
DAYMET (North America only). These are not the same quantities as the MERRA-2 variables.
`scripts/make_appeears_request.py` still works for those land products. `scripts/appeears_submit.py`
was not written for this reason.

Most NASA Earthdata access needs a free Earthdata Login: store it as `EARTHDATA_USERNAME`
/ `EARTHDATA_PASSWORD` in `.env`, never in code.

## Hackathon fallback
Before the demo, cache every demo-case series to `data/demo/` (small CSVs, committed)
so the demo never depends on a live API.
`scripts/build_processed.py --region R --variable V` does this: it runs the ingest, clean and analyse
steps once and copies the demo cases to `data/demo/` (`monthly_regional.csv`, `json/`, `cases.json`).
Run the app on it with `python src/trend_detective/app/web.py --input data/demo/monthly_regional.csv`.

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
- Cleaned output (committed): `src/trend_detective/process/merra2_clean.py` → `data/processed/merra2/monthly_regional.csv` (13,467 rows, 3 regions × 8 variables, columns `region,variable,period,value,unit,n_cells,n_valid,n_days`, 729 KB) and `qc_report.json` (1 KB). Periods 1980-01 to 2026-09 (T2MMAX to 2026-10). Cell counts per region: `east_asia_land` 1,155, `north_asia_siberia` 2,015, `se_asia_maritime` 3,034. Quirk: TSURF has 63% of cells masked (ocean cells), so `tsurf` is a land-only mean. Units after cleaning: K, Pa, g kg-1, kPa, mm day-1. Details: `docs/datasets.md`.

### GLDAS Noah 2.1, monthly (witness for MERRA-2 soil and rain)
- Provider / link: NASA GES DISC, short name `GLDAS_NOAH025_M`, version 2.1, CMR concept `C1342986036-GES_DISC` (https://cmr.earthdata.nasa.gov/search).
- Variable(s), units: `SoilMoi0_10cm_inst`, `SoilMoi10_40cm_inst`, `SoilMoi40_100cm_inst`, `SoilMoi100_200cm_inst` (soil moisture, kg m-2), `Rainf_tavg` (rainfall rate, kg m-2 s-1).
- Access: `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in `.env`; Harmony subset to the Asia-Pacific box (lon 60–179, lat −50–60).
- Resolution (time, space), time range: monthly, 0.25° (440 × 476 cells in the box), 2000-01 to 2026-07 (open-ended in CMR). 319 files on disk.
- Known quirks: fill value is −9999 (not 1e15 as in MERRA-2). Cleaned (2026-11-15): `process/witness_clean.py`. Per-dataset size not recorded; all of `data/raw/` is about 7.3 GB (`docs/datasets.md`).
- Cleaned output (committed): `process/witness_clean.py` → `data/processed/witness/witness_regional.csv` (7,110 rows for all three witness datasets, columns `dataset,region,variable,period,value,unit,n_cells,n_valid`) and `qc_report.json`. GLDAS is a land-only mean (about 62% of cells masked in `se_asia_maritime`).
- Fetched by: `src/trend_detective/ingest/witness_download.py` (group `gldas`) → cached at `data/raw/witness/`

### GPCP monthly precipitation v3.3 (witness for MERRA-2 rain)
- Provider / link: NASA GES DISC, short name `GPCPMON`, version 3.3, CMR concept `C3405935516-GES_DISC`.
- Variable(s), units: `sat_gauge_precip` (combined satellite and gauge rainfall, mm day-1).
- Access: `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in `.env`; Harmony subset to the same box.
- Resolution (time, space), time range: monthly, 0.5° (220 × 238 cells in the box), 1983-01 to 2025-12. 516 files on disk.
- Known quirks: fill value is −99999. Do not use `gauge_precip`: it holds values below the fill value. The first plan assumed a 2.5° grid; the real grid is 0.5°. Cleaned (2026-11-15): `process/witness_clean.py`. Per-dataset size not recorded.
- Fetched by: `src/trend_detective/ingest/witness_download.py` (group `gpcp`) → cached at `data/raw/witness/`

### GRACE / GRACE-FO mascon, JPL RL06.3 V04 (witness for water storage)
- Provider / link: JPL via PO.DAAC, short name `TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4`, CMR concept `C3195502222-POCLOUD`.
- Variable(s), units: `lwe_thickness` (liquid water equivalent thickness anomaly, cm), `uncertainty` (cm).
- Access: `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in `.env`.
- Resolution (time, space), time range: monthly, 0.5° grid (360 × 720, global), 2002-04 to 2026-09. One file, 39 MB.
- Known quirks: Harmony returned the whole global file, so the box is cut later in cleaning. Fill value −99999. The true resolution is about 3°, so use large regions only. Cleaned (2026-11-15): `process/witness_clean.py`; 2 duplicate months resolved.
- Fetched by: `src/trend_detective/ingest/witness_download.py` (group `grace`) → cached at `data/raw/witness/`

### Atmospheric temperature (checked 2026-11-15)
- Status: no separate atmospheric-temperature download is on this machine. `data/raw/` is not present here (git-ignored), and no `data/raw/temperature/` folder exists anywhere under the repo or home folder. `ingest/atmos_download.py --group temperature` (CMR keywords "atmospheric temperature", "air temperature") has no recorded run in the docs, manifests or progress log.
- What does exist is temperature from MERRA-2 (see its entry above), cleaned in `data/processed/merra2/monthly_regional.csv`: `t2m` (monthly mean 2 m air temperature), `t2mmax` (daily maximum, averaged per month) and `tsurf` (land surface temperature), 1980-01 to 2026-09 (`t2mmax` to 2026-10), K, 3 regions. `data/processed/geojson/M2SDNXSLV_T2MMAX_SEA_{DAILY,MONTHLY}.geojson` hold the Southeast Asia T2MMAX series but only to 1994 (a partial extract).
- Pressure-level temperature (MERRA-2 `M2IMNPASM` at 850 and 5 hPa, AIRS `AIRS3STM`) is listed in `scripts/pull_nasa.py`'s catalog as `verified=False`, with no data on disk.
- To confirm: ask the teammates which folder, product and machine they mean. If it is MERRA-2 T2M, it is already covered.

### Atmospheric composition
- Dropped (2026-11-15): the composition group (ozone, NO2, CO, CO2, aerosol optical depth) was removed from `ingest/atmos_download.py`, and `omi_no2` from `scripts/pull_nasa.py`. Nothing was downloaded. Not planned.
