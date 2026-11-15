# 0007 - The scan's test family, and an autocorrelation-aware Mann-Kendall test

- Status: proposed (2026-11-15). Needs the team's review of the choices marked **Review**.
- Extends: 0004 (adds `POST /api/analyse-series`, `GET /api/scan` and the fields below)
- Note: this ADR was first numbered 0005 and the website ADR 0006; they became 0007 and 0008 when the
  teammate's 0005-spatial-selection and 0006-flood-drought-flow reached `main`.

## Context
Two statistical gaps remained in `docs/statistics.md` (§6 items 1 and 4, §4.3):

1. Showing many regions and variables means many tests. At 5%, about one in twenty looks
   significant by chance. The Indonesia city map already corrects for this (§4.5), the regions did not.
2. The Mann-Kendall p-value ignores autocorrelation, while the OLS p-value adjusts for it. On
   monthly anomalies the Mann-Kendall test then finds trends that are not there. Measured on
   trend-free AR(1) noise, 400 runs each, share called significant at 5%:

   | n (months) | lag-1 φ | Mann-Kendall (existing) | OLS (adjusted) |
   |---|---|---|---|
   | 240 | 0.0 | 3.2% | 2.5% |
   | 240 | 0.3 | 16.0% | 5.5% |
   | 240 | 0.6 | 29.0% | 4.8% |
   | 120 | 0.6 | 30.2% | 6.8% |

   The existing p-value is already labelled "not adjusted" in the UI (science rule 4); this
   gives readers a second number that is adjusted.

## Decision

### A. The scan corrects across one family of tests
- **Family:** every (region, variable) series with at least 24 months in the chosen year window.
  Series with less have no p-value and are not counted.
- **Which p-value:** the OLS p-value (the headline test, science rule 3). Mann-Kendall p-values are
  shown but not corrected.
- **Method:** Benjamini-Hochberg (`core.trend.benjamini_hochberg`, already tested). It controls the
  false discovery rate: among the series called significant, the expected share of false
  alarms is at most 5%.
- **Flag:** `significant_q` is `q < 0.05`. The raw `ols_significant` is kept next to it so the page
  can say when a result lost significance after the correction.
- **Review:** the family is "all series in the data for this window". It changes with the window
  and with the data loaded, so q-values from different scans are not comparable. The page does not
  correct for the places the user chose to look at.
- **Known limit:** Benjamini-Hochberg is exact for independent tests and also valid for positively
  dependent ones. Variables in one region are positively related (air temperature, land surface
  temperature), so this is plausible but not proven. Benjamini-Yekutieli is valid under any
  dependence but much less powerful; not adopted.

### B. Mann-Kendall with the variance widened for lag-1 autocorrelation (`mann_kendall_ar1`)
Same effective-sample-size idea as the OLS path (Santer et al., 2000), so one adjustment explains
both tests:

1. Sen's slope `b` of the series (as the existing test).
2. Residuals `e(t) = y(t) − b·t` (the trend removed), and their lag-1 autocorrelation `r1`,
   floored at 0 (a negative value is not used to shrink the variance), as in `ols_trend`.
3. `n_eff = n (1 − r1) / (1 + r1)`, at least 3.
4. `Var*(S) = Var(S) · n / n_eff`, where `Var(S)` is the tie-corrected variance of §4.3.
5. `z = (S ∓ 1) / √Var*(S)` and `p = 2·P(Z > |z|)` as before.

When `r1 ≤ 0` the result equals the existing test exactly. The adjusted p-value is never smaller
than the unadjusted one. The existing `mann_kendall()` is unchanged.

Why `r1` comes from the **trend-removed** series: the trend itself creates autocorrelation, and
using the raw series would shrink `n_eff` just because a trend exists. The measured difference is
small (power 0.60 against 0.56 at φ = 0.5, slope 0.004 per month, n = 240) but the reasoning
is the standard one.

Measured with this method (same simulations as above, share significant at 5%):

| n | φ | Mann-Kendall unadjusted | Mann-Kendall adjusted |
|---|---|---|---|
| 240 | 0.0 | 3.2% | 3.0% |
| 240 | 0.3 | 16.0% | 4.5% |
| 240 | 0.6 | 29.0% | 5.0% |
| 120 | 0.3 | 15.5% | 6.8% |
| 120 | 0.6 | 30.2% | 6.0% |

The price is power: with φ = 0.5 and a trend of 0.004 per month over 240 months, the share
detected falls from 85% (unadjusted, which was over-confident) to 60%. With a trend of 0.008 it is 98%.

Alternatives considered:
- *Hamed and Rao (1998) modified Mann-Kendall:* corrects with the rank autocorrelation at every
  significant lag. More general, but it needs a significance rule per lag, is unstable at about 240
  points, and is harder to explain next to the OLS adjustment.
- *Trend-free pre-whitening (Yue et al., 2002):* changes the data before testing; the slope and
  p-value then no longer describe the series shown.
- *Block bootstrap:* needs a block-length choice and randomness (the app must be repeatable).

## Consequences
- New fields `mk_p_ar1` and `mk_ar1_significant` (statistics of `/api/trend`, `/api/analyse`;
  `mk_p_ar1` in `/api/scan`), and `r1`, `n_eff` (already added in `/api/trend`). Nothing renamed.
- `mk_p`, `mk_significant` and `tests_agree` keep their meaning (unadjusted). **Review:** whether
  `tests_agree` should compare OLS with the adjusted Mann-Kendall. Not changed, because it would
  alter existing output.
- The UI shows both Mann-Kendall p-values and labels each one.
- Limits: lag-1 only (seasonal or longer memory is not corrected); `r1` is noisy on short records,
  so at 120 months the rate is 6 to 7% rather than 5%; with missing months `r1` is taken over the
  remaining values as consecutive, exactly as the OLS path does.
- Tests: `tests/core/test_trend_additions.py` (golden: the p-value follows the stated formula
  with an independently computed `r1`; equals the existing test when `r1 ≤ 0`; never below the
  unadjusted p; white noise rarely significant; AR(1) with no trend is less often significant
  than with the unadjusted test; a real trend is still found) and the Benjamini-Hochberg worked
  example of the 1995 paper; `tests/app/test_web.py` for the scan.
