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
                            -> JSON to the page. Also: POST /api/analyse-series (a series the user
                            sends) and GET /api/scan (all series, corrected for many tests).
                            Response fields: docs/api.md
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

### 3.6 Flood and drought events and co-movement (`core/events.py`, `core/comovement.py`)
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
- `r1` (floored at 0, so a negative value never shrinks the uncertainty) and `n_eff` are returned
  with the result and sent to the page, which shows them as "effective sample size".

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

### 4.3a Mann-Kendall adjusted for autocorrelation (`mann_kendall_ar1`)
Added because the plain p-value of §4.3 is too optimistic on autocorrelated anomalies: on
trend-free AR(1) noise with φ = 0.6 it calls 29% of series significant at 5%, not 5%. Method
and the measured error rates are in `docs/decisions/0007-scan-family-and-autocorrelation-aware-mann-kendall.md`;
in short, with the same S as §4.3:
- `r1` = lag-1 autocorrelation of the series with Sen's trend removed, floored at 0;
- `n_eff = n (1 − r1) / (1 + r1)`, at least 3, as in §4.2;
- `Var*(S) = Var(S) · n / n_eff`; `z` and `p` as in §4.3 with `Var*`.

The result equals §4.3 when `r1 ≤ 0` and is never smaller otherwise. Both p-values are reported
(`mk_p` unadjusted, `mk_p_ar1` adjusted); `mk_p` and `tests_agree` are unchanged. The price is
power: with φ = 0.5 and a modest trend, 60% of series are detected instead of 85%.
It corrects lag-1 memory only.

### 4.4 Reporting (`core/summary.py`)
- Trends are reported **per decade**: the per-month slope × 120, in the data's unit
  (science rule 6). Example: "+0.21 K per decade".
- Significance uses p < 0.05 at 95% (science rule 7). The sentence is one of:
  - "*{region}: {variable} rose/fell by X per decade (95% CI a to b), statistically
    significant at 95%.*"
  - "*{region}: {variable}: no significant trend detected (yet). The estimated change is X per
    decade.*"
- **Record length:** under 10 years gives a warning; under 2 years gives no trend at all.
- **Gaps:** more than 10% of the months missing gives a warning. NaN months that only pad the
  front of a series to January (data that starts mid-year, see §4.7) are not gaps and are left out
  of that share (`summarise(..., leading_pad=)`).
- **Agreement:** if the OLS and Mann-Kendall tests disagree on sign or significance, the summary
  says so and asks the reader to check for outliers or non-linearity (science rule 3).
- **The sentence above is for one series on its own.** What a page shows is the significance engine's
  verdict and sentence (§4.8), which allow for the other series tested at the same time.

### 4.5 Many places at once: Benjamini-Hochberg (`benjamini_hochberg`)
The Indonesia map tests one trend per coastal city (62 tests). At p < 0.05 about 3 of them would
look significant by chance alone. `core.trend.benjamini_hochberg` turns the OLS p-values into
adjusted p-values that control the false discovery rate: among the cities shown as a clear trend,
the expected share of false alarms is at most 5%. A city is shown as a clear trend only when its
OLS test is significant **and** its adjusted p < 0.05.

The correction is applied by the significance engine (§4.8) to three named families: the cells of one
circle, the regions of one variable (`GET /api/scan`, `GET /api/map`, `GET /api/trend`), and nothing for
a single series. On the MERRA-2 record as of 2026-11-15 (1980-2026, 24 series) the correction removes none
of the 18 trends significant at 5%; for 1990-2019 it turns one (East China air temperature) into
`unclear`.

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
- Map CIRCLE tool: `scripts/export_cells.py` runs `core.summary.summarise` on every grid cell of
  each layer in the Indonesia box (94-142°E, 12°S-7°N) and saves each cell's own, uncorrected results.
  Sea level (2,478 ECCO cells) is built; TEMP and RAIN use the MERRA-2 cube from `process/cell_cube.py`
  when present. The correction is **not** done there: it depends on the circle a user draws.
  `POST /api/cell-circle` takes the cells of the selected layer whose centre is inside that circle (a
  centre outside is left out) and corrects only them, together (§4.8, ADR 0009). So "rising clearly"
  means both tests significant after correcting for the cells in this circle; a different circle is a
  different family. An earlier version corrected once across all of a layer's cells (and on the OLS
  test alone); that made the count independent of the circle but not of the sea around it.
- The CASES workflow uses the same monthly city series (`web/public/data/cases_data.json`) plus
  the MERRA-2 Maritime Southeast Asia temperature and rain series. Its lineup runs in the
  browser (Sen's slope, autocorrelation-adjusted Mann-Kendall, 1,000 AR(1) fakes) and always
  shows the core's full-record OLS result beside it, labelled PYTHON CORE.
- Limitation: ocean-model sea level next to the coast. It does not include land subsidence,
  which dominates relative sea-level rise in Jakarta and Semarang.

### 4.7 A series the user supplies (`POST /api/analyse-series`)
The same `summarise` runs on a monthly series sent in the request body. Deseasonalising works by
position (every 12th value), so the series is padded with NaN at the front until its first value
sits on its calendar month; this makes the yearly bars and the band fall on calendar years and
adds no information. The request is checked before any statistics run: 24 to 2000 values, at
least 24 of them numbers, finite and at most 1e12 in size, a valid start month. Nothing is stored.

### 4.8 The significance engine (`core/significance.py`, ADR 0009)
The trend engine (`process/`) chooses cells, regions and averages and hands over series; this module
decides what counts as significant. It never computes a trend itself: every slope, CI and p-value is from
`summarise` (§4.2, §4.3, §4.3a).

- **Families.** One variable across its regions (`layer`), the cells whose centre is inside one drawn
  circle (`circle`: the MERRA-2 and GPCP cells, and the ECCO ocean cells of the sea-level map), or a single
  series with no correction (`none`: a city, a pasted series). The OLS p-values and, separately, the
  autocorrelation-adjusted Mann-Kendall p-values are corrected with Benjamini-Hochberg (§4.5) across the
  family. Series without a p-value are not counted as tests.
- **Verdict ladder (both tests, after correction).** `rise` or `fall`: both q-values below 0.05 and the OLS
  and Sen slopes have the same sign. `unclear`: exactly one is significant, or both with opposite signs.
  `none`: neither. `no_data`: too little data.
- **Wording (rule 7).** Only "statistically significant at 95%" (with "after correcting for N tests at
  once" for a family) or "no significant trend detected (yet)". `unclear` uses the second phrase and adds
  a warning asking the reader to check for outliers or non-linearity.
- **Measured behaviour** (seeded simulations of 50-series families, 10 years of monthly data, 100 runs;
  `tests/core/test_significance_simulation.py`): independent trend-free series: any flagged 6%, a rise and
  a fall together 0% (57% without correction); shared noise between cells: 5%; **autocorrelated noise
  (phi 0.6): 15%, three times the nominal rate**; three strong trends among 47 nulls: all three found in
  every run, false discovery proportion 5.5% (Benjamini-Hochberg promises at most 4.7%). Read a flagged
  series in a short, strongly autocorrelated record as a lead and check `r1` and `n_eff`.
- **Not covered:** `years_needed` (`core/detect.py`) simulates the OLS test only, so under the two-test
  rule more years are needed than it says. `core/events.py` still tests its own trend at p < 0.05.

### 4.9 The noise lineup and the case verdict (`core/lineup.py`, ADR 0010)

Question: could random noise with the same wobble have made this trend? The lineup builds 1,000 records
with **no trend**: AR(1) noise with the real record's lag-1 autocorrelation (floored at 0, capped at 0.95)
and the standard deviation of the real OLS residuals, with the real record's missing months left missing.
Each fake gets the same OLS slope as the real record (`ols_trend`). The share of fakes whose slope is at
least as strong as the real one (either direction) is `beat / 1000`. Under 5% counts as evidence. The
random generator is seeded from the data, so the same record always gets the same fakes.

The case verdict combines three things: the engine's ladder for the series alone (`assess_single`, both
tests, same sign), the lineup, and the checks. `detected` needs all three; `suspect` is significant
evidence with a failed check, or a significant test across a known change of instrument; `not_detected`
is everything else, always under 10 years. Checks: record length; the two tests and the lineup agree;
later start years (cut 3, 5, 8 years, each only if 10 remain: same Sen sign and adjusted Mann-Kendall
p below 0.1); leave one year out (the OLS slope may not flip or move by 35% or more); known instrument
change (GRACE to GRACE-FO, 2017 to 2018, inside the window). The 0.1 and 35% thresholds are our choices,
not from a reference. The later-start and one-year checks run only when there is a trend to protect.

Limits: the fakes are linear-trend-free AR(1), not a model of El Nino or of any physical cycle. A
significant trend that fails the lineup is not proof of noise; a trend that passes is not proof of cause.

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
   5% some will look significant by chance. Corrected with Benjamini-Hochberg for the Indonesia
   city map, and by the significance engine (§4.8) across the regions of one variable and the cells of one
   circle. Limits: q-values depend on the family (the window and the regions in the data), the method
   assumes independent or positively dependent tests, and with strong autocorrelation on short records
   the chance that a family of null series contains a flagged one is about 15%, not 5%.
5. **Seasonal structure.** Deseasonalising removes the mean seasonal cycle but not a change in
   the cycle itself (for example, a longer summer). A seasonal Mann-Kendall test would be
   needed for that. Not done yet.
6. **Record length.** MERRA-2 starts in 1980, so the longest trends run about 46 years.
7. **Autocorrelation is corrected at lag 1 only** (OLS and `mann_kendall_ar1`). Longer memory, for
   example ENSO, is not, and `r1` is noisy on short records (at 120 months, 6 to 7% of trend-free
   series are still called significant, not 5%).
8. **Fixed 2026-11-15 (PR #4): Sen's slope with missing months.** `mann_kendall` used to drop the missing
   months before computing Sen's slope, so with gaps it was per valid value, not per month (+25% in a test
   with 14% missing). It now keeps each month's position; `test_sen_slope_survives_gaps` guards it.
9. **Project window 1980 to 2018** (`catalog/scope.py`). Every analysis route is limited to it. The
   choice matters: for the same data, 7 of 8 variables change verdict pattern between 1980-2018 and
   1980-2026 (East China air temperature: +0.215 against +0.302 K per decade). The end year was set by
   the disaster records (GDIS ends in 2018), not by the climate results.

## 7. Tests that protect this
- `tests/core/test_trend.py` (golden tests, never loosen): known trends are recovered, the
  seasonal cycle is removed, white noise is rarely significant, autocorrelation widens the CI,
  Mann-Kendall agrees with Kendall's tau, Sen's slope resists an outlier, opposite trends are
  both detected, and polar cells are down-weighted. Benjamini-Hochberg matches scipy's
  `false_discovery_control` on a textbook example and keeps false alarms near 5% on pure noise.
- `tests/core/test_trend_additions.py` (added beside the golden file, which is unchanged): `r1` and
  `n_eff` on hand-worked series (r1 = 1/6, n_eff = 30/7); the 15 p-values of the 1995
  Benjamini-Hochberg paper with hand-derived adjusted values; `mann_kendall_ar1` follows its
  formula with an independently computed `r1`, equals `mann_kendall` when `r1 ≤ 0`, matches a
  hand-computed value on a perfect line, is never below the plain p-value, finds white noise
  significant rarely, is far less often "significant" than the plain test on trend-free AR(1)
  noise, and still finds a real trend; `leading_pad` is not counted as missing months.
- `tests/app/test_web.py`: the `/api/trend` key sets are frozen; JSON errors for every failure;
  `/api/analyse-series` validation (malformed bodies, too short or long, NaN and overflow tokens,
  oversize body), a known slope per decade recovered, gaps; `/api/scan` q-values equal
  scipy's `false_discovery_control`, and a borderline series is significant by p but not by q.
- `tests/core/test_significance.py` (ladder table, hand-worked family, the original contradiction,
  wording, invariants) and `tests/core/test_significance_simulation.py` (ADR 0009 ranges);
  `tests/process/test_engine_snapshots.py` freezes the trend engine's numbers while its decisions are
  reviewed; `tests/process/test_engine_significance.py` shows the map following the ladder (an
  autocorrelated region whose unadjusted Mann-Kendall p 0.0006 would have made a `rise` is `unclear`).
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
- Whether to add a seasonal test (§6, item 5). The multiple-testing correction is done (§4.5).
- `tests_agree` and the `*_significant` flags in `statistics` are per-series and uncorrected. The verdict
  (§4.8) supersedes them for anything shown to users; whether to retire them is open.
- Whether `years_needed` should simulate both tests, and whether `core/events.py` should follow the
  verdict ladder (§4.8).
- Pre-whitened Mann-Kendall (`docs/stats_trend.md`) is not built; it could join as a third test.
- Whether annual means are shown alongside the monthly trend as a plain-language check.
- Band level term: `s² / n_eff` with `s² = SSR / (n − 2)` (§4.2a). The slope part is the existing
  CI, so only the level term is new. A different convention (for example `SSR / (n_eff − 2)` as
  the slope uses) would give a wider band near the middle of the record. Team to confirm.
