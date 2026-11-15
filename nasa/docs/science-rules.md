# Science & statistics rules

Read before touching `src/trend_detective/core/` or writing any result text shown to users.
Judges include NASA scientists: a wrong "significant" costs more than a missing feature.

## Analysis rules
1. **Deseasonalise first.** Monthly data: subtract each calendar month's mean
   (`deseasonalize`). Trends computed on raw seasonal data are invalid.
2. **Record length.** Aim for ≥10 years of monthly data; show a warning under 10 years.
   A non-significant trend may just need a longer record: say so in the UI, don't hide it.
3. **Two tests, both shown.** OLS slope with an autocorrelation-adjusted 95% CI
   (`ols_trend`) plus Mann-Kendall with Sen's slope (`mann_kendall`). If they disagree,
   show both and explain why (outliers, non-linearity).
4. **Autocorrelation.** Monthly anomalies are usually autocorrelated, which makes naive
   p-values too optimistic. OLS uses n_eff; the Mann-Kendall p-value is unadjusted, so label it that way.
5. **Regional means are area-weighted** by cos(latitude) (`area_weighted_mean`).
6. **Units always.** Report the trend per decade in native units (slope × 120 for monthly
   data), e.g. "+0.21 K/decade". Never a bare number.
7. **Significance language.** p < 0.05 → "statistically significant at 95%".
   Otherwise → "no significant trend detected (yet)". Never "proves", "caused by", or
   "climate change did X" unless a cited source says it.
8. **Opposite regional trends are a feature**, not a bug (a core point of the challenge).
   Compare regions side by side rather than averaging them together.
9. **Linear only** in scope; flag visibly non-linear series instead of fitting them.

## Golden tests
`tests/core/test_trend.py` checks the stats against synthetic data with known answers.
Never loosen a tolerance to make a change pass; fix the code or open an ADR.
