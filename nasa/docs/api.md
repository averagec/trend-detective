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

- **Trend units.** A trend is *per decade*, in the variable's own unit (`unit`): the per-month
  slope × 120. Example: `0.13` with `unit: "K"` means +0.13 K per decade. Never a bare number.
- **Anomalies.** `anomaly`, `mean_anomaly`, `band` and `ols_intercept` are *anomalies*: the value
  minus the mean of the same calendar month over the record. They are in `unit`.
- **Missing numbers are `null`.** `NaN` and infinity are never sent. A statistic is `null` when
  there is not enough data (fewer than 24 months with a value).
- **Months.** `"YYYY-MM"`. Every series starts in January of its first year, because
  deseasonalising assumes it (months before the data start are `null`).
- **Wording.** `sentence` is the plain-language result: "statistically significant at 95%" or
  "no significant trend detected (yet)". Do not paraphrase it into "proves" or "caused by".

## Errors

Every error on an `/api/*` route has this body and `Content-Type: application/json`:

```json
{"error": "from must be on or before to", "status": 400}
```

| Status | When |
|---|---|
| 400 | Bad or missing input: years not integers or outside 1-9999, `from` after `to`, a window with no months, a malformed `POST` body (see `/api/analyse`) |
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
| `from` | no | First year (default: first year of the record). January of this year starts the series |
| `to` | no | Last year, included (default: last year of the record) |

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
| `sentence` | string | The plain-language result |
| `warnings` | array of string | Record under 10 years; more than 10% of months missing; the two tests disagree |

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
| `mk_p_ar1` | number | Mann-Kendall p-value with the variance widened for lag-1 autocorrelation (same `n_eff` idea as the OLS test; docs/decisions/0005). Never below `mk_p` |
| `mk_ar1_significant` | boolean | `mk_p_ar1 < 0.05` |
| `tests_agree` | boolean | OLS and the **unadjusted** Mann-Kendall agree on the sign and on significance |
| `ols_intercept` | number | Intercept of the OLS line, anomaly units, month 0 = first month of `series` |
| `ols_slope_per_month` | number | The OLS slope per month (`ols_per_decade / 120`). **The OLS line** is `ols_intercept + ols_slope_per_month * i` at month index `i` of `series` |
| `n_eff` | number | Effective sample size behind `ols_p` and the CI: `n_months * (1 - r1) / (1 + r1)`, at least 3 |
| `r1` | number | Lag-1 autocorrelation of the OLS residuals, floored at 0. The larger it is, the smaller `n_eff` and the wider the CI |

With fewer than 24 months with a value, every statistic is `null` (`n_months`, `n_years` are still
given, `ols_significant`, `mk_significant`, `mk_ar1_significant`, `tests_agree` are `false`) and `sentence` says there
is not enough data.

## `POST /api/analyse`

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
curl -s -X POST localhost:5000/api/analyse -H 'Content-Type: application/json' \
  -d '{"label":"Demo","unit":"K","start":"2000-01","values":[...]}'
```

## `GET /api/scan`

Every region × variable in the data over one year window, with a correction for testing many
series at once. Testing 24 series at 5% flags about one by chance alone; the correction controls
the share of false alarms among the series flagged.

| Parameter | Required | Meaning |
|---|---|---|
| `from`, `to` | no | As for `/api/trend` (default: the whole record) |

Example: `/api/scan?from=1990&to=2019`

### Response

| Key | Type | Meaning |
|---|---|---|
| `from`, `to` | integer | The window |
| `method` | string | `"benjamini-hochberg"` (false discovery rate) |
| `alpha` | number | 0.05: a result is significant when `ols_q < alpha` |
| `n_tests` | integer | How many series were tested together (those with at least 24 months) |
| `n_significant_p` | integer | How many have `ols_p < 0.05` on their own (no correction) |
| `n_significant_q` | integer | How many have `ols_q < 0.05` (after the correction) |
| `note` | string | One sentence for the page explaining the q-value |
| `results` | array | One row per series, sorted by `region` then `variable` |

Row of `results` (the trend numbers are the same as in `statistics` of `/api/trend`):

| Key | Type | Meaning |
|---|---|---|
| `region`, `region_name`, `variable`, `label`, `unit` | string | As in `/api/trend` |
| `first_month`, `last_month` | string | `"YYYY-MM"` |
| `n_months`, `n_years`, `n_eff` | number | Months with a value, years, effective sample size |
| `ols_per_decade`, `ols_ci_per_decade` | number, [number, number] | OLS trend and its 95% CI, `unit` per decade |
| `ols_p` | number | OLS p-value (adjusted for autocorrelation), **before** the multiple-testing correction |
| `ols_q` | number | `ols_p` adjusted for all `n_tests` tests together (Benjamini-Hochberg). Never below `ols_p` |
| `significant_q` | boolean | `ols_q < 0.05`. **Use this one to say "significant" when results are shown together** |
| `ols_significant` | boolean | `ols_p < 0.05` alone. Shown so the page can say that a result lost significance after the correction |
| `sen_per_decade`, `mk_p`, `mk_p_ar1` | number | Sen's slope, the unadjusted Mann-Kendall p-value and the autocorrelation-adjusted one |
| `tests_agree` | boolean | OLS and Mann-Kendall agree |
| `warnings` | array of string | As in `/api/trend` |

A series with under 24 months has `null` for its numbers, `ols_q: null` and
`significant_q: false`, and does not count in `n_tests`.

Limit: Benjamini-Hochberg assumes the tests are independent or positively dependent. Variables in
one region are related (air temperature and land surface temperature move together), which this
accepts; see `docs/statistics.md`.

A window with no months in any series is a `400`.
