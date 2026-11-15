# HTTP API

The Flask app (`src/trend_detective/app/web.py`) serves JSON under `/api/`. All statistics come
from `core/` (see `docs/statistics.md`); the page draws what it receives and computes nothing.

**Compatibility rule.** The page and the static export depend on these field names. Add fields
freely; never rename or remove one. `tests/app/test_web.py` freezes the key sets and fails on any
change, so a new field also means updating that test and this file.

## Who uses it

- The website's TREND.EXE (`web/src/data/api.js` and `to-chart.js`). `web/tests/fixtures/*.json`
  are real responses; `tests/app/test_web.py` fails if the live shape drifts from them. After an
  intended API change, regenerate the fixtures and run `npm test` in `web/`.
- The plain internal page at `/classic` (`app/static/app.js`).

## Conventions

- **Project window.** Every route that takes years (`from`, `to`) is limited to **1980 to 2018**
  (`catalog/scope.py`, the same limit as the city, circle and map routes), so every screen analyses the
  same years. No years given means the whole window; years outside it are cut to it; a range that does not
  overlap the window is a `400` ("the project covers 1980 to 2018 only"). `/api/meta` `years` reports the
  window. The one exception is `POST /api/analyse-series`: it is the user's own data, analysed as sent.
  Why 2018: the GDIS disaster records end there (docs/datasets.md).

- **Trend units.** A trend is *per decade*, in the variable's own unit (`unit`): the per-month
  slope × 120. Example: `0.13` with `unit: "K"` means +0.13 K per decade. Never a bare number.
- **Anomalies.** `anomaly`, `mean_anomaly`, `band` and `ols_intercept` are *anomalies*: the value
  minus the mean of the same calendar month over the record. They are in `unit`.
- **Missing numbers are `null`.** `NaN` and infinity are never sent. A statistic is `null` when
  there is not enough data (fewer than 24 months with a value).
- **Months.** `"YYYY-MM"`. Every series starts in January of its first year, because
  deseasonalising assumes it (months before the data start are `null`).
- **Verdict and wording.** The `significance` block (below) is the verdict. Its `sentence` is the
  plain-language result: "statistically significant at 95%" or "no significant trend detected (yet)".
  Do not paraphrase it into "proves" or "caused by". The older top-level `sentence` and the
  `*_significant` flags in `statistics` describe the series **alone**, with no correction for the other
  regions tested; they are kept so nothing breaks, but a page must not show them next to a verdict.

## Errors

Every error on an `/api/*` route has this body and `Content-Type: application/json`:

```json
{"error": "from must be on or before to", "status": 400}
```

| Status | When |
|---|---|
| 400 | Bad or missing input: years not integers or outside 1-9999, `from` after `to`, a window with no months, a malformed `POST` body (see `/api/analyse-series`) |
| 404 | No data for that region and variable; unknown `/api/...` route |
| 405 | Wrong HTTP method (the `Allow` header lists the right ones) |
| 413 | `POST` body larger than 128 KiB |
| 500 | Unexpected server error. The message is always `"internal error"`; details are only in the server log |
| 503 | The processed data file is missing. The message says which script to run |

Non-API pages (`/`, `/ocean`) keep Flask's normal HTML errors.

## `GET /api/meta`

What the page can ask for. No parameters.

```json
{
  "variables": [{"key": "t2m", "label": "...", "question": "...", "description": "...", "unit": "K"}],
  "regions":   [{"key": "east_asia_land", "name": "...", "why": "..."}],
  "years":     {"first": 1980, "last": 2026}
}
```

`variables` and `regions` list only what is in the data. `unit` is the unit used by every other
route for that variable (for example `K`, `Pa`, `kPa`, `g kg-1`, `mm day-1`).

## `GET /api/trend`

The trend for one region and variable over a window of whole calendar years.

| Parameter | Required | Meaning |
|---|---|---|
| `variable` | yes | A `variables[].key` from `/api/meta` |
| `region` | yes | A `regions[].key` from `/api/meta` |
| `from` | no | First year (default: 1980, the start of the project window). January of this year starts the series |
| `to` | no | Last year, included (default: 2018, the end of the project window) |

Example: `/api/trend?variable=t2m&region=east_asia_land&from=1990&to=2019`

### Response

| Key | Type | Meaning |
|---|---|---|
| `region`, `region_name` | string | Region key and its plain-language name |
| `variable`, `label` | string | Variable key and its label |
| `unit` | string | Unit of `value`, `anomaly` and the trends (per decade) |
| `first_month`, `last_month` | string | `"YYYY-MM"`; the first is always January |
| `series` | array | One row per month, in order: `{period, value, anomaly}`. `value` is the data, `anomaly` the deseasonalised value; both `null` for a missing month. **This is the plotted series** |
| `annual` | array | `{year, mean_anomaly, months}`: mean anomaly of each year and how many months it has (a display aggregate, not a statistic) |
| `band` | array | The 95% band around the OLS line, one row per year: `{year, fit, low, high}`, in anomaly units, evaluated at July. Empty when there is no trend |
| `statistics` | object | See below |
| `sentence` | string | This series on its own, with no correction (kept for compatibility). **Show `significance.sentence`** |
| `warnings` | array of string | Record under 10 years; more than 10% of months missing; the two tests disagree (uncorrected). `significance.warnings` is the corrected list with codes |
| `significance` | object | The verdict, both q-values and the sentence. See below |

### `statistics`

| Key | Type | Meaning |
|---|---|---|
| `n_months` | integer | Months with a value |
| `n_years` | number | `n_months / 12` |
| `ols_per_decade` | number | OLS trend of the anomalies, `unit` per decade |
| `ols_ci_per_decade` | [number, number] | 95% confidence interval of `ols_per_decade`, adjusted for autocorrelation |
| `ols_p` | number | Two-sided p-value of the OLS slope, adjusted for autocorrelation |
| `ols_significant` | boolean | `ols_p < 0.05` |
| `sen_per_decade` | number | Sen's slope (Mann-Kendall's slope), `unit` per decade |
| `mk_p` | number | Mann-Kendall p-value, **not** adjusted for autocorrelation |
| `mk_significant` | boolean | `mk_p < 0.05` |
| `mk_p_ar1` | number | Mann-Kendall p-value with the variance widened for lag-1 autocorrelation (same `n_eff` idea as the OLS test; docs/decisions/0007). Never below `mk_p` |
| `mk_ar1_significant` | boolean | `mk_p_ar1 < 0.05` |
| `tests_agree` | boolean | OLS and the **unadjusted** Mann-Kendall agree on the sign and on significance |
| `ols_intercept` | number | Intercept of the OLS line, anomaly units, month 0 = first month of `series` |
| `ols_slope_per_month` | number | The OLS slope per month (`ols_per_decade / 120`). **The OLS line** is `ols_intercept + ols_slope_per_month * i` at month index `i` of `series` |
| `n_eff` | number | Effective sample size behind `ols_p` and the CI: `n_months * (1 - r1) / (1 + r1)`, at least 3 |
| `r1` | number | Lag-1 autocorrelation of the OLS residuals, floored at 0. The larger it is, the smaller `n_eff` and the wider the CI |

### `significance`

The significance engine's verdict (`core/significance.py`, `docs/decisions/0009-*`). The same block
is returned by `/api/trend`, `/api/analyse-series`, `/api/scan` and, for each city, circle cell and
region, by the selection and map routes.

| Key | Type | Meaning |
|---|---|---|
| `family` | object | `{name, n_tests, method, alpha}`. `name` is `"layer"` (this variable across its regions), `"circle"` (the cells of one circle) or `"none"` (a single series: no correction, `n_tests` and `method` are `null`) |
| `ols_p`, `mk_p_ar1` | number | The two tests' p-values: OLS (adjusted for autocorrelation) and Mann-Kendall (adjusted for autocorrelation, ADR 0007) |
| `ols_q`, `mk_q` | number | Each p-value after Benjamini-Hochberg across the family. Equal to the p-values when `family.name` is `"none"`. Never below the p-value |
| `verdict` | string | `"rise"` or `"fall"`: **both** q-values below 0.05 and the two slopes have the same sign. `"unclear"`: exactly one is, or both but with opposite signs. `"none"`: neither. `"no_data"`: too little data (under 24 months monthly, 3 values yearly) |
| `significant` | boolean | The verdict is `"rise"` or `"fall"` |
| `expected_by_chance` | number or null | How many series of the family would look significant in one direction by luck alone if each were tested at 5% (2.5% per direction); `null` for a single series |
| `sentence` | string | Built from the verdict: only "statistically significant at 95%" (with "after correcting for N tests at once" when the family has more than one) or "no significant trend detected (yet)" |
| `explanation` | string | Why the verdict, built from the verdict, the q-values (p-values with no family, written `p`) and the two slopes: which tests are below 0.05, and whether their slopes agree in sign. Example: "Both tests are below 0.05 after correcting for 3 tests at once, and their slopes have the same sign: OLS +0.04 and Sen +0.04 mm day-1 per decade." Use it next to `sentence`, not instead of it |
| `warnings` | array | `{code, text}`: `short_record`, `missing_months`, `not_enough_data`, `one_test_significant`, `tests_disagree`, `note` |

Why a region can be significant on its own and still not be `rise`: with 4 regions tested, a p-value
of 0.029 at rank 2 becomes q = 0.029 x 4 / 2 = 0.059. A limit worth knowing: on 10 years of monthly data
with strong autocorrelation (phi 0.6), about 15% of families of 50 trend-free series contain a flagged
one (`docs/statistics.md` section 4.8).

With fewer than 24 months with a value, every statistic is `null` (`n_months`, `n_years` are still
given, `ols_significant`, `mk_significant`, `mk_ar1_significant`, `tests_agree` are `false`) and `sentence` says there
is not enough data.

## `POST /api/analyse-series`

Analyse a monthly series you send. The server only computes: nothing is stored, no file is
written, no network call is made, and the route works even when the processed data file is missing.

Send `Content-Type: application/json`:

```json
{"label": "Station temperature", "unit": "K", "start": "1995-03", "values": [281.2, 283.9, null, 288.4]}
```

| Field | Rule |
|---|---|
| `label` | text, 1 to 80 characters, no control characters. Shown in the sentence |
| `unit` | text, 1 to 20 characters. The trend is reported in this unit per decade |
| `start` | `"YYYY-MM"`: the calendar month of the first value (year 1 to 9999) |
| `values` | 24 to 2000 entries, consecutive months. Each is a number or `null` (a missing month). Not strings, not booleans, not `NaN`/`Infinity`, and not larger than 1e12 in size. At least 24 entries must be numbers |

The body may be at most 128 KiB. Any rule broken gives a `400` with a message naming the field
(for example `values[7] must be a number (finite, at most 1e+12 in size) or null`); an oversize body gives `413`.

### Response

The same shape as `/api/trend`, so one renderer draws both. Differences:

- `region` and `variable` are `"custom"`, `region_name` is `"Your data"`, `label` and `unit` are
  the ones you sent. `sentence` starts with your `label`.
- The series is aligned to the calendar: the front is padded so your first value sits on its real
  month. `series` therefore starts in January of the start year (`first_month`), and the padded
  months before `start` have `value: null` and `anomaly: null`. They are padding, not gaps, so
  they do not count towards the "months are missing" warning.
- Missing months (`null`) are skipped by the statistics; `n_months` counts only real values.
  More than 10% missing adds a warning.
- As for `/api/trend`, under 10 years of data adds a warning, and the sentence follows the
  significance wording rules.

```bash
curl -s -X POST localhost:5000/api/analyse-series -H 'Content-Type: application/json' \
  -d '{"label":"Demo","unit":"K","start":"2000-01","values":[...]}'
```

## `POST /api/lineup`

The CASES flow's LINEUP (ADR 0010): the analysis of a series you send, plus the noise lineup, the
robustness checks and the case verdict. Same body, limits and errors as `POST /api/analyse-series`, with
one optional field:

| Field | Rule |
|---|---|
| `gap_years` | optional `[first, last]`: the years of a known change of instrument inside the record (GRACE to GRACE-FO: `[2017, 2018]`). Two integers 1 to 9999, `first <= last`. Anything else is a `400` naming `gap_years` |

The series is analysed as sent (no cut to the 1980 to 2018 project window), like `/api/analyse-series`.
Nothing is stored.


### The `yearly` block (ADR 0011)

The response also has a `yearly` block: the same judgement on the **yearly averages of the seasonal
anomalies** of the same series, so one request answers both "monthly" and "yearly". Months are averaged
only for a year with at least 10 of its 12 months present (a thinner year is `null`); the yearly series
is analysed with steps of one year (OLS with the adjusted interval, Mann-Kendall, the ladder, the
lineup and the checks, all in years; later start years still cut 3, 5 and 8 years and leave-one-year-out
drops one yearly value). The monthly block (`series`, `statistics`, `significance`, `lineup`) is exactly as
before.

| `yearly` field | Meaning |
|---|---|
| `frequency` | `"yearly"` |
| `first_year`, `last_year` | The calendar years of the window; `series[0]` is `first_year` |
| `series` | `[{year, anomaly}]`: the yearly average of the monthly anomalies, `null` for a thin year. In `unit` ("vs normal for the month") |
| `statistics` | As the monthly `statistics`, per yearly step: `ols_per_decade`, `ols_ci_per_decade`, `ols_p`, `sen_per_decade`, `mk_p_ar1`, `n_months` (counts yearly values here), `ols_intercept` and `ols_slope_per_month` (per year, not per month) |
| `band` | `[{year, fit, low, high}]`: the 95% band around the OLS line, one row per year |
| `significance` | The ladder for the yearly series alone (family `none`) |
| `lineup` | As the monthly `lineup`; `sims_per_decade` are the yearly fakes' slopes |
| `warnings` | The yearly summary's warnings |
| `comparison` | One sentence on how the two views relate. When they reach the same verdict: "agree". When they differ it compares the **effective number of independent values** of each view (`n_eff`, which allows for each month being like the last: for Ambon sea level 312 months count as about 9, 26 yearly values as about 10) and says which view has more power, or that they carry about the same information and the result sits close to the 5% limit. It never claims more power for the view that did not find the trend |

The two views give the same slope but not always the same verdict. Usually monthly sees more (about 156 independent values against 28 for rainfall), but not always: sea-level months are so alike that Ambon's 312 months count as about 9, so the yearly view can be the one that finds a rise. With fewer than 3 yearly values `yearly.lineup.n_sims` is `null` and `comparison` says so.

### Response

The `/api/analyse-series` response, plus a `lineup` block. `significance` is the one the lineup judged,
so a page never shows two verdicts for one series.

| `lineup` field | Meaning |
|---|---|
| `verdict` | `"detected"`: the engine says rise or fall, fewer than 5% of the fakes are as strong, and every check passes. `"suspect"`: significant evidence but a check fails, or a known instrument change is inside the window and a test is significant. `"not_detected"`: not enough evidence yet, always so under 10 years |
| `headline` | One plain-language sentence for the top of the result: what was found and why. `"Rising trend detected: about 38 mm per decade. Both statistical tests agree, none of 1,000 random look-alike records were as strong, and it held up in every check."`; `"Rising trend found, but treat it with caution: ... yet it is not clearly there once the earliest years are left out."` (the failed check in plain words); `"No significant trend detected (yet), but it is borderline: a rise of about 49 mm per decade came close but did not pass the tests, and only 23 of 1,000 random look-alike records were as strong. More years of data could settle it."` (a test p-value below 0.15, or the lineup alone below 5%: our limit); or `"No significant trend detected (yet): ..."` with the reason (record too short, the two tests disagree, the tests find a slope that the lineup says chance could make, or the data are too noisy to confirm the change). Never states a cause. Built in `core/lineup.py` from the verdict and the checks; the page shows it as it is |
| `explanation` | Why, in plain words: the engine's explanation, how many fakes were as strong, and the failed checks |
| `n_sims`, `beat`, `share` | The number of fakes (1000), how many had a slope as strong as the real one (either direction), and `beat / n_sims`. `null` when there is too little data |
| `observed_per_decade` | The real OLS slope, in `unit` per decade |
| `sims_per_decade` | The fakes' slopes (trend-free AR(1) noise with the real lag-1 autocorrelation and residual spread, same missing months), in `unit` per decade, for drawing the histogram. Seeded from the data: the same request always gets the same fakes. `[]` when there is too little data |
| `checks` | `[{code, text, ok}]`: `record_length` (10 years), `tests_agree` (both tests and the lineup), `later_start` (still the same sign and Mann-Kendall p below 0.1 after cutting 3, 5 or 8 years), `one_year` (no single year moves the slope by 35% or flips it), `instrument_change`. The last two checks only count when there is a trend to protect |
| `years` | Years with data |
| `years_needed` | For `not_detected`: the record length (years) that would detect a trend of this size (`core/detect.py`); `10` under ten years; `null` when it cannot be estimated or the case is not `not_detected` |

## `GET /api/scan`

One variable in every region over one year window, judged together as one family (the "layer"
family, ADR 0009). Testing several regions at 5% flags some by chance alone; the correction controls
the share of false alarms among the regions flagged.

| Parameter | Required | Meaning |
|---|---|---|
| `variable` | yes | A `variables[].key` from `/api/meta`. Missing: `400`. Unknown: `404` |
| `from`, `to` | no | As for `/api/trend` (default: the project window, 1980 to 2018) |

Example: `/api/scan?variable=t2m&from=1990&to=2019`

### Response

| Key | Type | Meaning |
|---|---|---|
| `from`, `to` | integer | The window |
| `variable`, `family` | string | The variable, and `"layer"` |
| `method`, `alpha` | string, number | `"benjamini-hochberg"`, 0.05 |
| `n_tests` | integer | Regions tested together (those with enough data) |
| `n_significant_p` | integer | Regions with `ols_p < 0.05` on their own (no correction) |
| `n_significant_q` | integer | Regions that are `rise` or `fall` (both tests, after correction) |
| `note` | string | One sentence for the page explaining the correction |
| `results` | array | One row per region, in region order |

Row of `results`: the region and `statistics`-like numbers (`region`, `region_name`, `variable`, `label`,
`unit`, `first_month`, `last_month`, `n_months`, `n_years`, `n_eff`, `ols_per_decade`,
`ols_ci_per_decade`, `ols_p`, `sen_per_decade`, `mk_p`, `mk_p_ar1`, `tests_agree`, `warnings`), plus:

| Key | Type | Meaning |
|---|---|---|
| `ols_q` | number | `ols_p` after the correction (same as `significance.ols_q`) |
| `significant_q` | boolean | `significance.significant`: both tests, after correction |
| `ols_significant` | boolean | `ols_p < 0.05` alone, so a page can say a region lost significance after correction |
| `significance` | object | The block above. For one region it is identical to the block in `/api/trend` for the same window |

A region with under 24 months has `null` numbers and `verdict: "no_data"`, and is not counted in `n_tests`.
A window with no months in any region is a `400`.

Limit: Benjamini-Hochberg assumes independent or positively dependent tests. Regions of one variable
are positively related; ADR 0009 measures this.

## `POST /api/cell-circle`

A circle drawn on the map (MAP.EXE, CIRCLE), for the selected layer. The server takes the layer's grid
cells whose **centre** is inside the circle, corrects them together, and judges each by both tests (the
"circle" family, ADR 0009). A cell whose centre is outside is left out, even if it overlaps the circle.
The cells' own tests are made once by `scripts/export_cells.py` (`data/processed/cell_stats/<layer>.json`);
only the correction, which depends on the circle, happens per request.

Body (JSON): `{"layer": string, "lat": number, "lon": number, "radius_km": number}`.
- `layer`: `"ssl"` (sea level, the default), `"t2m"`, `"precip"` or `"tws"`: a short lower-case name, never
  a path (anything else is a `400`).
- The radius must be 75 to 250 km and at least 4 cells with data must be inside, otherwise `400` with the
  reason.
- A layer whose cell file is missing is a `503` that says what to run: `scripts/export_cells.py`, and for
  `t2m` and `precip` the MERRA-2 cell cube (`process/cell_cube.py`), for `tws` a GRACE cube (not built yet).

| Key | Type | Meaning |
|---|---|---|
| `layer`, `dataset`, `unit`, `period` | | The layer, its product, its unit (for example `"mm"`), first and last year |
| `centre`, `radius_km` | | The circle as received |
| `cells_inside` | integer | Cells with their centre inside |
| `counts` | object | Cells per verdict: `rise`, `fall`, `unclear`, `none`, `no_data` (they add up to `cells_inside`) |
| `expected_by_chance` | number | Cells that would look significant in one direction by luck if each were tested alone at 5% |
| `note` | string | One sentence explaining the correction, for the page |
| `cells` | array | One per cell: `k` (its position in that layer's grid in `indonesia_cells.json`), `lat`, `lon`, `slope_per_decade` (in the layer's unit), and the `significance` block |

## Selection and map routes (the trend engine)

`POST /api/analyse` (city and circle), `GET /api/map`, `GET /api/cities`, `GET /api/cell`,
`GET /api/variables` and `POST /api/event` belong to the trend engine (`docs/decisions/0005-spatial-selection.md`,
`0006-flood-drought-flow.md`). The significance engine adds only these fields; nothing was renamed:

| Route | Added |
|---|---|
| `POST /api/analyse`, city | `significance` on each result (family `"none"`: a city is one test) |
| `POST /api/analyse`, circle | `significance` on each cell (family `"circle"`, corrected across the cells) and on `average` (alone, a reference). A cell counts in `agreement.rising` or `falling` only when its verdict is `rise` or `fall`, so **both tests** must be significant after correction |
| `summary` objects | `n_eff`, `r1`, `mk_p_ar1`, `mk_ar1_significant` |
| `GET /api/map`, each region | `significance` (family `"layer"`), `mk_p_ar1`, `mk_p_ar1_adj`. `direction` is the verdict (`rise`, `fall`, `unclear`, `none`; `no_data` is reported as `none`). `ols_p_adj` is unchanged; `mk_p_adj` is kept as the corrected *unadjusted* Mann-Kendall p-value, for compatibility only |
