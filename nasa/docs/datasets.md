# Datasets

Status as of 2026-11-15. Counts are files on disk under `data/raw/`, which is git-ignored and
about 7.3 GB. Raw files are not committed. The regional tables, QC reports and GeoJSON files in
`data/processed/` are committed (about 9 MB). The per-cell cubes are local only.

## Project scope: 1980 to 2018

Every analysis output is limited to **1980 to 2018**, the window in `src/trend_detective/catalog/scope.py`.
The regional map, the city and circle analysis, and the flood and drought routes clamp requested years to
this window. The reason: the GDIS disaster records end in 2018, so flood and drought counts can only be
compared with climate data for the same years. A dataset that starts later than 1980 is used from its own
first year, and one that ends later is cut at 2018.

## Status at a glance

| Group | Dataset | Files on disk | Download | Cleaned |
|---|---|---|---|---|
| MERRA-2 | T2MMAX (daily max 2 m air temperature) | 17,076 | Complete | Yes (monthly regional means) |
| MERRA-2 | T2M, QV2M, PS (monthly temperature, humidity, pressure) | 561 | Complete | Yes |
| MERRA-2 | EVAP, PRECTOTCORR (monthly evaporation, rainfall) | 561 | Complete | Yes |
| MERRA-2 | TSURF (monthly land surface temperature) | 561 | Complete | Yes (land cells only) |
| Witness | GLDAS Noah 2.1 monthly soil moisture and rainfall | 319 | Complete | Yes (regional monthly means, land cells only) |
| Witness | GPCP v3.3 monthly rainfall | 516 | Complete | Yes (regional monthly means) |
| Witness | GRACE / GRACE-FO mascon water storage | 1 | Complete | Yes (regional monthly means; 2 duplicate months resolved) |
| Ocean | ECCO sea level 0.5° (V4R4 and V4R4B) | 312 each | Complete | Yes (regional monthly CSV) |
| Ocean | ECCO sea level, native LLC90 grid (V4R4, V4R4B) | 312 each | Complete | Yes (regional monthly CSV and GeoJSON) |
| Ocean | NASA SSH indices (ENSO, IOD, PDO, GMSL) | 4 text files | Complete | Yes (GeoJSON, time series, no regions) |
| SAR | Sentinel-1 scene list and browse images | see `data/raw/sar/` | Earlier download | Partly |

Download manifests: `data/raw/merra2/manifest.csv` (702 jobs ok, 1 skipped, 0 failed) and
`data/raw/witness/manifest.csv` (71 jobs ok or skipped, 0 failed).

## Processed outputs

Regional tables are in `data/processed/<group>/` and are committed. The per-cell cubes in
`data/processed/cells/` are local only (about 40 MB, not committed).

### Regional monthly tables (committed)

| File | Rows | Variables | Regions | Period | Made by |
|---|---|---|---|---|---|
| `merra2/monthly_regional.csv` | 13,467 | t2m, t2mmax, qv2m, ps, vpd, precip, evap, tsurf | 3 | 1980-01 to 2026-10 | `process/merra2_clean.py` |
| `witness/witness_regional.csv` | 7,110 | gldas_sm_0_10cm, gldas_sm_10_40cm, gldas_sm_40_100cm, gldas_sm_100_200cm, gldas_rain, gpcp_precip, grace_lwe | 3 | GLDAS 2000-01 to 2026-07; GPCP 1983-01 to 2025-12; GRACE 2002-04 to 2026-09 | `process/witness_clean.py` |
| `ocean/ocean_regional.csv` | 3,744 | ssh (metres), 4 products: ECCO 0.5° and LLC90, each V4R4 and V4R4B | 3 | 1992-01 to 2017-12 | `process/ocean_clean.py` |
| `ocean/ecco_cell_stats.json` | 2,478 cells | each ECCO 0.5° ocean cell's own test results (OLS, Mann-Kendall, Sen), **not corrected**; the server corrects the cells inside a drawn circle (`POST /api/ocean-circle`) | Indonesia box | 1992-2017 | `scripts/export_cells.py` |

The regions are `se_asia_maritime`, `east_asia_land` and `north_asia_siberia` (`catalog/regions.py`).
North Asia has no ocean cells, so its ocean rows are blank. The t2mmax rows are monthly means of the
daily regional maxima. A daily-resolution file is not saved yet.

### QC reports (committed)

| File | What it records | Made by |
|---|---|---|
| `merra2/qc_report.json` | Files read, rows written, fill and out-of-range counts per variable | `process/merra2_clean.py` |
| `witness/qc_report.json` | Masked counts per variable and the GRACE duplicate-month count | `process/witness_clean.py` |
| `ocean/qc_report.json` | Masked counts per ECCO product | `process/ocean_clean.py` |

### Other processed files (committed)

| File | Contents | Made by |
|---|---|---|
| `geojson/*.geojson` (8 files) | ECCO sea surface height for all four products (one polygon for the box per month), and the NASA SSH ENSO, IOD, PDO and GMSL indices (null geometry, one feature per time step) | `scripts/raw_to_json.py` |
| `ocean_se_asia/*.npz` (625 files) | Monthly ECCO sea surface height for the Southeast Asia box, 1992 to 2017 | `ingest/ocean_download.py` |

### Per-cell cubes (local only, not committed)

These are not from this session's pipeline. They were created on 15 November in the local folder,
and their owner should confirm them before any commit.

| File | Contents | Size | Made by |
|---|---|---|---|
| `cells/merra2_idn.npz` (+ manifest) | MERRA-2 monthly values for each grid cell of the Indonesia box (94°E to 142°E, 12°S to 7°N): 39 × 77 cells, 561 months, with t2m, qv2m, ps, precip, evap, tsurf, vpd | 35 MB | `process/cell_cube.py` |
| `cells/gpcp_idn.npz` (+ manifest) | GPCP monthly rainfall for each cell of the same box: 38 × 96 cells, 516 months, 1983-01 to 2025-12 | 6.8 MB | `process/cell_cube.py` |

Other local files that read these outputs: `process/event_series.py` (monthly series for the flood and
drought flow, using the cubes and the ENSO, IOD and PDO indices), and `process/cities.py` and
`process/selection.py`. These were added in the same local folder and are not committed.

### GDIS flood and drought (committed)

Made by `process/gdis.py` from the GDIS disaster-location records (SEDAC, 1960 to 2018), kept for
1980 to 2018 and placed on the MERRA-2 cells of the Indonesia box.

| File | Rows | Columns | Made by |
|---|---|---|---|
| `gdis/gdis_events_1980_2018.csv` | 1,139 | year, hazard, country, adm1, latitude, longitude, cell_lat, cell_lon | `process/gdis.py` |
| `gdis/gdis_yearly_counts_idn.csv` | 839 | year, cell_lat, cell_lon, flood, drought (cells with no event left out) | `process/gdis.py` |
| `gdis/gdis_counts_idn.npz` | arrays | the same counts for the engine | `process/gdis.py` |

## MERRA-2 (NASA GMAO reanalysis)

Source: NASA GES DISC, version 5.12.4. Model output that assimilates observations, not a direct
measurement. Downloaded as Harmony subsets to the Asia-Pacific box (60°E to 179.4°E, 50°S to 60°N).
Script: `src/trend_detective/ingest/merra2_download.py`.

| Collection | Product | Variables | Grid | Time step | Raw units | Fill value | Coverage |
|---|---|---|---|---|---|---|---|
| M2SDNXSLV | Daily statistics, single level | T2MMAX | 0.5° × 0.625° (221 × 192) | daily, one file per day | K | 1e15 | 1980 to 2026 |
| M2TMNXSLV | Monthly mean, single level | T2M, QV2M, PS | 0.5° × 0.625° | monthly | K, kg kg⁻¹, Pa | 1e15 | 1980 to 2026 |
| M2TMNXFLX | Monthly mean, fluxes | EVAP, PRECTOTCORR | 0.5° × 0.625° | monthly | kg m⁻² s⁻¹ | 1e15 | 1980 to 2026 |
| M2TMNXLND | Monthly mean, land | TSURF | 0.5° × 0.625° | monthly | K | 1e15 | 1980 to 2026 |

Cleaning rules (`docs/statistics.md`): fill and out-of-range values masked; units converted to
mm day⁻¹ (fluxes), g kg⁻¹ (humidity). VPD is derived from T2M, QV2M and PS.

Checks on the cleaned output (`qc_report.json`): no fill or out-of-range values for the atmospheric
variables. TSURF has 63% of cells masked because they are ocean cells, which is expected.

## Witness datasets (checks against MERRA-2)

### GLDAS Noah 2.1, monthly (`GLDAS_NOAH025_M`)
- Source: NASA GES DISC, concept `C1342986036-GES_DISC`, version 2.1.
- Grid: 0.25° (440 × 476 in the box). Coverage: 2000 to July 2026 (open-ended in CMR).
- Variables: `SoilMoi0_10cm_inst`, `SoilMoi10_40cm_inst`, `SoilMoi40_100cm_inst`,
  `SoilMoi100_200cm_inst` (soil moisture, kg m⁻²), `Rainf_tavg` (rainfall rate, kg m⁻² s⁻¹).
- Fill value: −9999 (not 1e15). Cleaned: masked over ocean (70% of box cells), so regional values are land-only.
- Script: `src/trend_detective/ingest/witness_download.py` (group `gldas`).

### GPCP Precipitation, monthly v3.3 (`GPCPMON`)
- Source: NASA GES DISC, concept `C3405935516-GES_DISC`, version 3.3.
- Grid: 0.5° (220 × 238 in the box), not the 2.5° in the first plan. Coverage: 1983-01 to 2025-12.
- Variable used: `sat_gauge_precip` (combined satellite and gauge rainfall, mm day⁻¹).
  `gauge_precip` is not used: it holds values below the fill value.
- Fill value: −99999. Cleaned: no fill values inside the box.
- Script: `src/trend_detective/ingest/witness_download.py` (group `gpcp`).

### GRACE / GRACE-FO mascon, RL06.3 V04 (`TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4`)
- Source: JPL, PO.DAAC, concept `C3195502222-POCLOUD`.
- Grid: 0.5° (360 × 720), global single file (39 MB). Coverage: 2002-04 to 2026-09.
- Variables: `lwe_thickness` (water storage anomaly, cm), `uncertainty` (cm).
- Fill value: −99999. Coarse signal (about 3° effective); use for large regions only. Cleaned: the
  box is cut from the global file, longitudes are wrapped to −180…180, and two months that have two
  time steps keep the step nearest the 15th (2012-01 and 2015-04). Result: 259 months, 2002-04 to 2026-09,
  with gaps where GRACE had no solution.
- Script: `src/trend_detective/ingest/witness_download.py` (group `grace`).

## Other data (earlier downloads)
- `ocean/`: ECCO L4 sea surface height (0.5° and LLC90 grids, V4R4 and V4R4B) and four NASA SSH
  indicators (ENSO, IOD, PDO, GMSL). ECCO runs to December 2017. Script: `ingest/ocean_download.py`.
- `sar/`: Sentinel-1 scene list and browse images for coastal sites. Script: `ingest/sar.py`.

## Not downloaded
- GPM IMERG half-hourly rainfall: not downloaded. Candidate for event-scale flood analysis.


## Date ranges (project window 1980 to 2018)

Available is what the file covers. Used is the part inside the project window.

| Dataset | Available | Used in the project | Notes |
|---|---|---|---|
| MERRA-2 monthly and daily (T2M, QV2M, PS, PRECTOTCORR, EVAP, TSURF, VPD, T2MMAX) | 1980-01 to 2026-09 (T2MMAX to 2026-10) | 1980-01 to 2018-12 | Cell cubes and regional CSVs |
| GPCP v3.3 rainfall | 1983-01 to 2025-12 | 1983-01 to 2018-12 | Starts in 1983 |
| GLDAS Noah 2.1 soil moisture and rain | 2000-01 to 2026-07 | 2000-01 to 2018-12 | Cell cube for 0 to 10 cm soil moisture; regional rows for all layers |
| GRACE / GRACE-FO water storage | 2002-04 to 2026-09 (259 months, with gaps) | 2002-04 to 2018-12 | About 12% of months are missing in the full record |
| ECCO sea level (ocean) | 1992-01 to 2017-12 | 1992-01 to 2017-12 | Ends in 2017 |
| NASA SSH indices (ENSO, IOD, PDO) | 1993-01 to 2026-11 | 1993-01 to 2018-12 | Global, one series each |
| GDIS disaster locations (floods, droughts) | 1960-01 to 2018-12 | 1980-01 to 2018-12 | 1,139 flood and drought records in the Indonesia box (1,104 floods, 35 droughts) |
| SEDAC flood hazard frequency | 1985 to 2003 (static map) | Not used yet | Not downloaded |
| SEDAC drought hazard frequency | 1980 to 2000 (static map) | Not used yet | Not downloaded |
| GPM IMERG daily rainfall (V07 Final) | 1998-06 to 2025-09 | Not used yet | Not downloaded |

Notes: GDIS records are placed on MERRA-2 cells by location. The Indonesia box also covers parts of
Malaysia, the Philippines, Thailand, Timor-Leste and Papua New Guinea. Of the 1,139 placed records, 656 are
in Indonesia, 204 Malaysia, 149 Philippines, 88 Thailand, 39 Timor-Leste and 3 Papua New Guinea. The CSV
keeps the country column, so an Indonesia-only count can be made from it.
