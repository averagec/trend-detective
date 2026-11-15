# Trend engine statistics (proposal)

Status: **proposal, not built.** Note (2026-11-15): the headline-test question is settled for now by
`docs/decisions/0009-significance-engine-*.md`: both OLS and Mann-Kendall are shown, and a trend is
rising or falling only when both are significant after correction. Pre-whitening below is not built.

Original status: **proposal, not built.** Once approved, this file defines the statistics for the trend
engine and replaces `docs/statistics.md` for that engine. `docs/science-rules.md` still applies:
the changes it needs are listed in §8 for a decision.

Scope: linear trends of one series (one cell, a city, or a circle's area average), on a
**monthly** or **yearly** basis chosen by the user. Each cell of a circle is tested on its own.

## 1. Inputs
- **Monthly:** the valid monthly values in the chosen years.
- **Yearly:** the annual mean for each calendar year that has at least 10 valid months (proposed).
- **Gaps:** never filled or interpolated. A missing value stays missing, and the count is shown.
- **Record length:** under 10 years gives a warning (rule 2). The numbers are still shown.

## 2. Preparation
- **Monthly:** subtract each calendar month's mean over the chosen years (deseasonalise, rule 1).
- **Yearly:** no subtraction. There is one value per year, so there is no seasonal cycle to remove.
- **Circles:** the cell set is fixed (cells with no value in any month are dropped). Each month or
  year is the cos-latitude weighted mean of the valid cells.

## 3. Tests (both shown)
**Headline test: Mann-Kendall after pre-whitening.**
- Remove the trend, remove lag-1 autocorrelation, add the trend back, then run Mann-Kendall.
- Pre-whitening only when the lag-1 autocorrelation is significant (proposed).
- Magnitude: Sen's slope, with a 95% confidence interval from the Kendall-based method.
- **Why:** rank-based, so no normal distribution is assumed and one extreme year does not
  dominate. Pre-whitening handles autocorrelation directly, instead of the approximation
  used by the current effective-sample-size adjustment.

**Secondary check: OLS slope with the effective-sample-size CI** (the current `ols_trend`).
- Kept so the result can be compared with the current check and so rule 3 is still met.
- If the sign or the significance differs from the headline, the result says so and asks
  the reader to check for outliers or non-linearity.

Significance: two-sided, 5%.

## 4. Several cells at once (circles)
- Each cell gets the headline test.
- **Benjamini-Hochberg (BH)** is applied to the cell p-values at a 5% false discovery rate.
  Only the cells that survive BH are counted as rising or falling.
- **Mixed signal:** shown only when BH-surviving cells rise **and** fall.
- A count of cells alone is not shown without the chance level. About 2.5% of cells
  would be "significantly rising" by chance alone, so 50 cells give about one.
- A single city is one test, so no correction is applied.

## 5. Units and wording
- Per decade: monthly slope × 120; yearly slope × 10 (rule 6).
- Wording as in rule 7: "statistically significant at 95%" or "no significant trend detected (yet)".
- The p-value label names the test: "Mann-Kendall p (after pre-whitening)".

## 6. Fields the engine returns for each series
- `freq` (monthly or yearly), `n_points`, `n_years`, `missing`.
- `slope_per_decade`, `ci_low`, `ci_high`, `method` (Sen's slope).
- `p_value`, `p_method` ("Mann-Kendall, pre-whitened").
- `ols_slope_per_decade`, `ols_p`, `ols_ci_low`, `ols_ci_high` (secondary check).
- `agree` (true when the two tests match in sign and significance).
- `warnings`: a list of `{code, text}`.
- Output format is to be confirmed against the main dashboard code (see the exec plan).

## 7. Tests to write
- A synthetic series with a known slope is recovered, for monthly and yearly data.
- Under no trend, the false-positive rate is near 5% over a seeded set of series. The
  accepted range is written into the test before it runs and is not loosened later.
- On autocorrelated noise, the pre-whitened test gives fewer false positives than the
  unadjusted test.
- BH matches a small worked example done by hand.
- The existing golden tests in `tests/core/` are not changed.

## 8. Changes needed to `docs/science-rules.md` (for your decision)
- **Rule 4:** the Mann-Kendall p-value is adjusted (pre-whitened), so the "unadjusted" label changes.
- **Rule 1:** deseasonalising applies to monthly series only.
- **Rule 6:** per decade for yearly series is × 10.
- **Rule 8 and circles:** BH is applied across cells before any count is shown.

## 9. Open points
- Yearly completeness: 10 of 12 months (proposed).
- Whether OLS stays as a secondary check or is dropped.
