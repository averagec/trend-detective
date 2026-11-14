# Datasets we are downloading

Status as of 2026-11-15, 01:06 MPST. Counts are files on disk under `data/raw/`, which is git-ignored.
Downloads run from the scripts named under each group. Raw files are not committed.

## Status at a glance

| Group | Dataset | Files on disk | Status |
|---|---|---|---|
| MERRA-2 | T2MMAX (daily max 2 m air temperature) | 17,076 | Downloading (MERRA-2 run, 682 of 703 jobs done, 0 failed) |
| MERRA-2 | T2M, PS, QV2M (monthly 2 m temperature, pressure, humidity) | 426 | Downloading (2008 reached) |
| MERRA-2 | EVAP, PRECTOTCORR (monthly evaporation, rainfall) | 561 | Complete |
| MERRA-2 | TSURF (monthly land surface temperature) | 561 | Complete |
| Witness | GLDAS Noah 2.1 monthly soil moisture and rainfall | 252 of 319 | Downloading (2012 reached) |
| Witness | GPCP v3.3 monthly rainfall | 12 (test year only) | Waiting for the full run |
| Witness | GRACE / GRACE-FO mascon water storage | 1 | Complete |

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

## Witness datasets (checks against MERRA-2)

### GLDAS Noah 2.1, monthly (`GLDAS_NOAH025_M`)
- Source: NASA GES DISC, concept `C1342986036-GES_DISC`, version 2.1.
- Grid: 0.25° (440 × 476 in the box). Coverage: 2000 to present (CMR open-ended).
- Variables: `SoilMoi0_10cm_inst`, `SoilMoi10_40cm_inst`, `SoilMoi40_100cm_inst`,
  `SoilMoi100_200cm_inst` (soil moisture, kg m⁻²), `Rainf_tavg` (rainfall rate, kg m⁻² s⁻¹).
- Fill value: −9999 (not 1e15).
- Script: `src/trend_detective/ingest/witness_download.py` (group `gldas`).

### GPCP Precipitation, monthly v3.3 (`GPCPMON`)
- Source: NASA GES DISC, concept `C3405935516-GES_DISC`, version 3.3.
- Grid: 0.5° (220 × 238 in the box), not the 2.5° in the first plan. Coverage: 1983-01 to 2025-12.
- Variable used: `sat_gauge_precip` (combined satellite and gauge rainfall, mm day⁻¹).
  `gauge_precip` is not used: it holds values below the fill value.
- Fill value: −99999.

### GRACE / GRACE-FO mascon, RL06.3 V04 (`TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4`)
- Source: JPL, PO.DAAC, concept `C3195502222-POCLOUD`.
- Grid: 0.5° (360 × 720), global single file (39 MB). Coverage: 2002-04 to 2026-09.
- Variables: `lwe_thickness` (water storage anomaly, cm), `uncertainty` (cm).
- Fill value: −99999. Coarse signal (about 3° effective); use for large regions only.
- Script: `src/trend_detective/ingest/witness_download.py` (group `grace`).

## Other data in `data/raw/` (earlier downloads, not part of the current run)
- `ocean/`: ECCO L4 sea surface height (0.5° and LLC90 grids, V4R4 and V4R4B) and four NASA SSH
  indicators (ENSO, IOD, PDO, GMSL). Script: `ingest/ocean_download.py`.
- `sar/`: Sentinel-1 scene list and browse images for coastal sites. Script: `ingest/sar.py`.

## Not downloaded
- Atmospheric composition (ozone, NO2, CO, CO2, aerosol optical depth): no files yet.
  See `ingest/atmos_download.py --group composition`.
