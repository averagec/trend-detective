# Datasets

Status as of 2026-11-15. Counts are files on disk under `data/raw/`, which is git-ignored and
about 7.3 GB. Raw files are not committed. The cleaned outputs in `data/processed/` are committed
(about 9 MB).

## Status at a glance

| Group | Dataset | Files on disk | Download | Cleaned |
|---|---|---|---|---|
| MERRA-2 | T2MMAX (daily max 2 m air temperature) | 17,076 | Complete | Yes (monthly regional means) |
| MERRA-2 | T2M, QV2M, PS (monthly temperature, humidity, pressure) | 561 | Complete | Yes |
| MERRA-2 | EVAP, PRECTOTCORR (monthly evaporation, rainfall) | 561 | Complete | Yes |
| MERRA-2 | TSURF (monthly land surface temperature) | 561 | Complete | Yes (land cells only) |
| Witness | GLDAS Noah 2.1 monthly soil moisture and rainfall | 319 | Complete | No |
| Witness | GPCP v3.3 monthly rainfall | 516 | Complete | No |
| Witness | GRACE / GRACE-FO mascon water storage | 1 | Complete | No |
| Ocean | ECCO sea level (0.5° and LLC90), NASA SSH indicators | see `data/raw/ocean/` | Earlier download | Yes (GeoJSON) |
| SAR | Sentinel-1 scene list and browse images | see `data/raw/sar/` | Earlier download | Partly |

Download manifests: `data/raw/merra2/manifest.csv` (702 jobs ok, 1 skipped, 0 failed) and
`data/raw/witness/manifest.csv` (71 jobs ok or skipped, 0 failed).

## Processed outputs (committed)

| File | Contents | Made by |
|---|---|---|
| `data/processed/merra2/monthly_regional.csv` | 13,467 rows: 3 regions × 8 variables × months, with area-weighted values and cell counts | `process/merra2_clean.py` |
| `data/processed/merra2/qc_report.json` | Files read, rows written, fill and out-of-range counts per variable | `process/merra2_clean.py` |
| `data/processed/geojson/*.geojson` | Ocean and sea-level series as GeoJSON (one polygon per month for the box, or null geometry for indices) | `scripts/raw_to_json.py` |
| `data/processed/ocean_se_asia/*.npz` | Monthly Southeast Asia sea-surface height, 1992 to 2017 | `ingest/ocean_download.py` |

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
- Fill value: −9999 (not 1e15). Not yet cleaned.
- Script: `src/trend_detective/ingest/witness_download.py` (group `gldas`).

### GPCP Precipitation, monthly v3.3 (`GPCPMON`)
- Source: NASA GES DISC, concept `C3405935516-GES_DISC`, version 3.3.
- Grid: 0.5° (220 × 238 in the box), not the 2.5° in the first plan. Coverage: 1983-01 to 2025-12.
- Variable used: `sat_gauge_precip` (combined satellite and gauge rainfall, mm day⁻¹).
  `gauge_precip` is not used: it holds values below the fill value.
- Fill value: −99999. Not yet cleaned.
- Script: `src/trend_detective/ingest/witness_download.py` (group `gpcp`).

### GRACE / GRACE-FO mascon, RL06.3 V04 (`TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4`)
- Source: JPL, PO.DAAC, concept `C3195502222-POCLOUD`.
- Grid: 0.5° (360 × 720), global single file (39 MB). Coverage: 2002-04 to 2026-09.
- Variables: `lwe_thickness` (water storage anomaly, cm), `uncertainty` (cm).
- Fill value: −99999. Coarse signal (about 3° effective); use for large regions only. Not yet cleaned.
- Script: `src/trend_detective/ingest/witness_download.py` (group `grace`).

## Other data (earlier downloads)
- `ocean/`: ECCO L4 sea surface height (0.5° and LLC90 grids, V4R4 and V4R4B) and four NASA SSH
  indicators (ENSO, IOD, PDO, GMSL). ECCO runs to December 2017. Script: `ingest/ocean_download.py`.
- `sar/`: Sentinel-1 scene list and browse images for coastal sites. Script: `ingest/sar.py`.

## Not downloaded
- Atmospheric composition (ozone, NO2, CO, CO2, aerosol optical depth): no files yet.
  See `ingest/atmos_download.py --group composition`.
- GPM IMERG half-hourly rainfall: not downloaded. Candidate for event-scale flood analysis.
