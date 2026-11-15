# Statistical analysis: how the trends are computed

Status: **draft for team review**. The methods are implemented and tested; the region choice and
the wording of results are still open. Rules that the code must follow are in
`docs/science-rules.md`. This file explains the method and the reasons for it.

## 1. Pipeline at a glance

```
ingest/merra2_download.py   Harmony subsets  ->  data/raw/merra2/subset/<collection>/<year>/
process/merra2_clean.py     QC, units, VPD,   ->  data/processed/merra2/monthly_regional.csv
                            regional means
core/summary.py + core/trend.py                   (pure statistics, no files)
                            (includes the 95% band around the OLS line, 4.2a)
app/web.py (Flask)          per request: build() for the chosen region, variable and years
                            -> JSON to the page
(optional) process/analyse_trends.py  ->  data/processed/json/  (static export)
```

Only `core/` does statistics. `process/` cleans and aggregates and never computes a trend.
`app/` asks `core/` for the numbers each time. The browser draws them and recalculates nothing.

## 2. Data

- **Source:** NASA MERRA-2 reanalysis, GES DISC, version 5.12.4 (1980 to present).
- **Grid:** 0.625° longitude × 0.5° latitude. A region must cover several cells: see
  `catalog/regions.py`. Coastal sites a few km wide (`catalog/sites.py`) are smaller than
  one cell and must not be analysed with MERRA-2.
- **Subset:** Harmony cuts each file to the variables and the box, so each file is small.

| Output key | MERRA-2 variable | Collection | Unit after cleaning |
|---|---|---|---|
| `t2m` | T2M, monthly mean 2 m air temperature | M2TMNXSLV | K |
| `t2mmax` | T2MMAX, daily maximum 2 m air temperature | M2SDNXSLV | K |
| `qv2m` | QV2M, 2 m specific humidity | M2TMNXSLV | g kg⁻¹ |
| `ps` | PS, surface pressure | M2TMNXSLV | Pa |
| `vpd` | derived (see §3.3) | — | kPa |
| `precip` | PRECTOTCORR, bias-corrected precipitation | M2TMNXFLX | mm day⁻¹ |
| `evap` | EVAP, surface evaporation | M2TMNXFLX | mm day⁻¹ |
| `tsurf` | TSURF, land surface temperature incl. snow | M2TMNXLND | K |

## 3. Data cleaning (`process/merra2_clean.py`)

### 3.1 Masking
1. **Fill values.** MERRA-2 marks missing cells with 1×10¹⁵. Any value with |x| ≥ 10¹⁴, and
   any NaN or infinity, is masked.
2. **Physical range.** Values outside a plausible range are masked, not clipped. The ranges
   are in raw units: T in 180–340 K (345 K for the daily maximum and land surface), specific
   humidity 0–0.05 kg kg⁻¹, pressure 30,000–110,000 Pa, precipitation 0–0.05 kg m⁻² s⁻¹,
   evaporation −0.001 to 0.01 kg m⁻² s⁻¹.
3. Each run writes `qc_report.json` with the number of cells read, masked for fill, and masked
   for range, per variable. A large masked share is a warning sign, so check it before using
   a region.

### 3.2 Units
- Precipitation and evaporation: kg m⁻² s⁻¹ × 86,400 = mm day⁻¹ (1 kg of water on 1 m² is 1 mm).
- Humidity: kg kg⁻¹ × 1,000 = g kg⁻¹.
- Temperatures stay in K. A trend in K per decade equals a trend in °C per decade.

### 3.3 Vapour pressure deficit (VPD)
VPD is not a MERRA-2 variable. It is computed per grid cell from the monthly means of T2M,
QV2M and PS, then averaged over the region:

- Saturation vapour pressure (Tetens, over water), with T in °C:
  `es = 0.6108 · exp(17.27 · T / (T + 237.3))` kPa
- Actual vapour pressure from specific humidity q and pressure P, with ε = 0.622:
  `e = q · P / (ε + (1 − ε) · q)` (P in kPa after dividing Pa by 1,000)
- `VPD = max(es − e, 0)` kPa

**Caveat:** the monthly mean of VPD is not the VPD of the monthly means. The difference is
largest in months with large day-to-day swings. State this next to any VPD result.

### 3.4 Regional averages
- For each region, the cells whose centres lie inside the box are selected.
- Each cell is weighted by cos(latitude), so high-latitude cells count less (see
  `core/trend.py: area_weighted_mean`). Cells with no value are left out of both the
  sum and the weights.
- Daily T2MMAX: the regional mean is taken for each day, then averaged over the days of
  the month. The number of valid days is kept.

### 3.5 Cell-level series and circles (`process/cell_cube.py`, `process/selection.py`)
- The cube keeps every cell of the box, with the same cleaning as §3.1 to §3.3. Nothing is
  averaged in the cube.
- **City:** the series of the one cell that contains the point. No averaging.
- **Circle:** the cells whose centres lie within the radius (75 to 250 km, at least 4 cells; see
  `docs/decisions/0005-spatial-selection.md`). A cell with no value in any month is dropped, so
  the cell set is fixed. Each cell goes through `summarise` on its own. The area average of the
  used cells (cos-latitude weights, §3.4) goes through `summarise` as a reference.
- Gaps: a missing month is NaN on a full monthly timeline. Series start in January, as the
  seasonal removal in §4.1 needs.

### 4.5 Flood and drought events and co-movement (`core/events.py`, `core/comovement.py`)
- **Monthly totals:** rainfall rate (mm/day) × days in the month (mm). The trend is tested on
  the rate, the amounts on the totals.
- **Percentile:** the share of the same calendar month's values (monthly periods) or of the
  complete annual totals (yearly periods) at or below the period's value. Partial years are
  left out.
- **Extreme:** at or above the 90th percentile for a flood, at or below the 10th for a drought.
- **Trend:** the OLS trend of the deseasonalised rate (§4.2). Reported only when significant at
  95%, with the direction ("wetter" or "drier").
- **Call:** "not unusual" if not extreme; "extreme, in line with a trend" if extreme and the
  significant trend is in the same direction; otherwise "one-time event".
- **Amount:** observed minus the median of the same baseline (mm), and as a percent of the median.
- **Peak:** for a year, the month whose percentile is furthest toward the incident.
- **Co-movement:** Pearson correlation of the deseasonalised anomalies over the shared months.
  The effective sample size uses the lag-1 autocorrelation of both series, as in §4.2.
  The slope is the least-squares slope of rainfall on the factor. The implied rainfall change is
  that slope × the factor's average anomaly in the period.
- **Interpretation:** co-movement is not a cause (science rules 7 and 8). Several factors are
  tested at once, and the p-values are not corrected for that (§6, item 4).

## 4. Statistics (`core/`)

Every trend uses **monthly data** and its **deseasonalised anomalies**. Annual series are not
used for the main result (45 or so points give little power, and annual means hide the
seasonal shape of change).

### 4.1 Deseasonalising (science rule 1)
For each calendar month, subtract that month's mean over all years:
`a(t) = x(t) − mean{x(m) : m is the same calendar month as t}`. Without this step, the annual
cycle (about 10 K in mid-latitudes) dominates the trend.

### 4.2 OLS trend with an autocorrelation-adjusted confidence interval (`ols_trend`)
- Least-squares slope `b` of `a(t)` against time `t` (in months).
- Lag-1 autocorrelation `r1` of the residuals. Effective sample size (Santer et al., 2000):
  `n_eff = n · (1 − r1) / (1 + r1)`, bounded below by 3.
- Standard error from the residual variance with `n_eff − 2` degrees of freedom. The 95%
  confidence interval uses the t distribution with the same degrees of freedom.
- `p` is the two-sided t-test on `b / se`.

### 4.2a Confidence band around the OLS line (`ols_band`)
The chart shades a 95% band around the OLS line, one point per year (at month 6 of the year, the
same place as the yearly bar). It uses the same `n_eff` and `n_eff − 2` degrees of freedom as the
slope CI:

`var(line at t) = s² / n_eff + se_slope² · (t − t̄)²`, band = line ± t_crit · √var

- `s² = SSR / (n − 2)` is the residual variance; `se_slope` is the one from §4.2, so the band
  opens up away from the middle of the record at exactly the rate of the slope CI.
- It is a band for the **line** (where the true trend plausibly lies), not a prediction band
  for single months, so most dots lie outside it.
- Years whose position falls after the last month of the record are left out (no extrapolation).
  Records under two years have no band.
- This adds a number; it does not change the slope, CI or p-values. The `s² / n_eff` level term is
  a choice made for the band: see the open question in §8.

**Why:** monthly anomalies are usually positively autocorrelated. A naive test then finds
trends that are not there. The `n_eff` adjustment widens the interval to match.

### 4.3 Mann-Kendall test with Sen's slope (`mann_kendall`)
- **S** = sum over all pairs i < j of sign(a(j) − a(i)).
- **Variance** with the tie correction: `Var(S) = [n(n−1)(2n+5) − Σ t(t−1)(2t+5)] / 18`, where
  t is the size of each group of tied values.
- **z** = (S − 1)/√Var for S > 0, (S + 1)/√Var for S < 0, and 0 otherwise (continuity correction).
- **p** = 2·P(Z > |z|), normal approximation. The p-value is **not** adjusted for
  autocorrelation. It is labelled that way in the UI (science rule 4).
- **Sen's slope** = median of all pairwise slopes (a(j) − a(i))/(j − i). It is robust to
  outliers.

The test is rank-based, so it does not assume a normal distribution and is not pulled
by one extreme month.

### 4.4 Reporting (`core/summary.py`)
- Trends are reported **per decade**: the per-month slope × 120, in the data's unit
  (science rule 6). Example: "+0.21 K per decade".
- Significance uses p < 0.05 at 95% (science rule 7). The sentence is one of:
  - "*{region}: {variable} rose/fell by X per decade (95% CI a to b), statistically
    significant at 95%.*"
  - "*{region}: {variable}: no significant trend detected (yet). The estimated change is X per
    decade.*"
- **Record length:** under 10 years gives a warning; under 2 years gives no trend at all.
- **Gaps:** more than 10% of the months missing gives a warning.
- **Agreement:** if the OLS and Mann-Kendall tests disagree on sign or significance, the summary
  says so and asks the reader to check for outliers or non-linearity (science rule 3).

### 4.5 Many places at once: Benjamini-Hochberg (`benjamini_hochberg`)
The Indonesia map tests one trend per coastal city (62 tests). At p < 0.05 about 3 of them would
look significant by chance alone. `core.trend.benjamini_hochberg` turns the OLS p-values into
adjusted p-values that control the false discovery rate: among the cities shown as a clear trend,
the expected share of false alarms is at most 5%. A city is shown as a clear trend only when its
OLS test is significant **and** its adjusted p < 0.05.

### 4.6 Sea level next to Indonesian cities (`process/ocean_cities.py`, `scripts/export_indonesia.py`)
- Data: ECCO V4r4 dynamic sea surface height (`SSH`, inverse-barometer corrected), 0.5° monthly,
  1992-2017, from the processed `ocean_se_asia/*.npz` grids. V4r4b differs by < 0.02 mm.
- Cities: the team's 31 study cities across 7 regions (list in `scripts/build_indonesia_geo.py`).
  Positions from Natural Earth places; Batam and Prabumulih are missing there and come from the
  2020 census via Wikipedia. Coast distance uses Natural Earth's 1:10m coastline (includes small
  islands such as Ternate). A city further than 20 km from the coast is inland and gets no
  sea-level series (8 of 31: Medan 23 km, Samarinda, Padangsidimpuan, Tasikmalaya, Jambi,
  Prabumulih, Pekanbaru, Palangka Raya).
- Series: cos(latitude)-weighted mean of every ocean cell whose centre is within 120 km (the
  centre-inside rule of ADR 0005), in mm. Usually 3 to 12 cells.
  The export also lists every 0.5° cell whose centre is within 120 km, which cells were used,
  and each ocean cell's own OLS trend (not adjusted for multiple tests) for the map's grid view.
- Statistics: `core.summary.summarise` per city, then Benjamini-Hochberg across all tested
  cities. Result (2026-11-15 build): 23 coastal cities tested, 14 with a clear rise, trends
  +32.6 to +50.4 mm per decade. The eastern cities (Ambon, Sorong, Ternate, Kendari,
  Manado) rise fastest but are not yet significant: ENSO makes their records noisy. Cross-check:
  the whole Southeast Asia box rises +38.8 mm per decade (95% CI +7.6 to +69.9) with the same
  code, inside the city range.
- The CASES workflow uses the same monthly city series (`web/public/data/cases_data.json`) plus
  the MERRA-2 Maritime Southeast Asia temperature and rain series. Its lineup runs in the
  browser (Sen's slope, autocorrelation-adjusted Mann-Kendall, 1,000 AR(1) fakes) and always
  shows the core's full-record OLS result beside it, labelled PYTHON CORE.
- Limitation: ocean-model sea level next to the coast. It does not include land subsidence,
  which dominates relative sea-level rise in Jakarta and Semarang.

## 5. Interpretation rules
- Say "statistically significant at 95%", never "proves". Never say "caused by" unless a
  cited source does.
- A non-significant result may just need a longer record. Say so.
- Opposite trends in neighbouring regions are a result, not an error. Compare regions side by
  side and do not average them.
- Only linear trends are reported. Non-linear series are flagged, not fitted.

## 6. Limitations (say these in the write-up)
1. **Reanalysis, not observations.** MERRA-2 is a model combined with observations. It has
   known biases, especially for precipitation over land. Check the trend against an
   independent source where one exists (see `docs/data-sources.md`).
2. **Coarse grid.** One 0.5° cell is roughly 50 km. Small areas are averaged with their
   surroundings.
3. **VPD is approximate** (§3.3).
4. **Multiple tests.** Showing three regions and eight variables means about 24 tests. At
   5% some will look significant by chance. Say this on the page, or correct for it later
   (e.g. Benjamini-Hochberg). Done for the Indonesia city map (§4.5); not yet for regions.
5. **Seasonal structure.** Deseasonalising removes the mean seasonal cycle but not a change in
   the cycle itself (for example, a longer summer). A seasonal Mann-Kendall test would be
   needed for that. Not done yet.
6. **Record length.** MERRA-2 starts in 1980, so the longest trends run about 46 years.

## 7. Tests that protect this
- `tests/core/test_trend.py` (golden tests, never loosen): known trends are recovered, the
  seasonal cycle is removed, white noise is rarely significant, autocorrelation widens the CI,
  Mann-Kendall agrees with Kendall's tau, Sen's slope resists an outlier, opposite trends are
  both detected, and polar cells are down-weighted. Benjamini-Hochberg matches scipy's
  `false_discovery_control` on a textbook example and keeps false alarms near 5% on pure noise.
- `tests/process/test_ocean_cities.py`: land and far cells are never picked, cells are nearest
  first, the series is in millimetres and keeps missing months, inland cities get no series.
- Band (`ols_band`, same file): a hand-worked 5-point series gives the exact half-widths
  (0.9001, 1.5591, 2.7004 at t = 2, 0 or 4, 6); the band opens at the rate of the slope CI; it is
  wider for autocorrelated anomalies; it covers the true line about 95% of the time over 400
  simulated records; missing months keep their positions; an exact line has zero width.
- `tests/core/test_summary.py`: known warming gives the right per-decade value and sentence; no
  trend gives the "no significant trend" sentence; short records, gaps and one-year records
  give warnings, not false results.
- Change log: `ols_trend` previously reported p = 0 when the residual spread was exactly zero,
  even for a flat series. A flat series now gives p = 1. Found on the 2000 test data, where
  a one-year series produced a false "significant" result.
- Change log: `mann_kendall` previously dropped the missing months before computing Sen's slope,
  so with gaps the slope was per valid value, not per month, and too large by roughly the share
  of months missing (+25% in a test with 14% missing; OLS was not affected). It now computes the
  slope with the gaps kept in place, so it is per month. S, Var(S) and the p-value are unchanged.
  Three golden tests were added to `tests/core/test_trend.py`; none was changed.

## 8. Not yet decided
- Which regions and variables go into the demo cases (`docs/product-sense.md`).
- Whether to add a multiple-testing correction and a seasonal test (§6).
- Whether annual means are shown alongside the monthly trend as a plain-language check.
- Band level term: `s² / n_eff` with `s² = SSR / (n − 2)` (§4.2a). The slope part is the existing
  CI, so only the level term is new. A different convention (for example `SSR / (n_eff − 2)` as
  the slope uses) would give a wider band near the middle of the record. Team to confirm.
