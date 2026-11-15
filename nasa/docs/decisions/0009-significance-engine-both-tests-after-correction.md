# 0009 - One significance engine: both tests, after correction, one verdict

- Status: implemented on branch feature/significance-engine (2026-11-15), proposed for the team. Decisions 1 to 3
  were made by the user; the rest needs team review.
- Extends: 0005-spatial-selection, 0007 (adjusted Mann-Kendall, scan family), 0008 (website).
- Plan: `exec-plans/active/significance-engine.md`.

## Context
Significance was decided in three places that did not agree. `summarise()` called a trend significant
at p < 0.05. The circle tool corrected the OLS p-values across its cells. The regional map corrected
the OLS and the *unadjusted* Mann-Kendall p-values across regions. My `/api/scan` corrected across every
region and variable. So one trend could read "statistically significant at 95%" (p = 0.041) next to
"no significant trend" (q = 0.076) on the same screen, and the same region could get different
q-values on different screens.

## Decision
1. **The trend engine hands over series; it does no significance testing.** A series is a monthly or
   yearly vector with `null` for gaps (never filled), its unit and label, the leading pad that only
   aligns it to January, and the family it belongs to. The engine does not receive or check a slope
   the trend engine computed itself (user decision 3).
2. **`core/significance.py` decides.** Per series it uses `summarise` (no second copy of the maths).
   Per family it applies Benjamini-Hochberg to the OLS p-values and, separately, to the
   autocorrelation-adjusted Mann-Kendall p-values (`mk_p_ar1`, ADR 0007). It returns both q-values.
3. **Verdict ladder (user decision 1): both tests, after correction.**
   - `rise` or `fall`: both q-values below 0.05 and the OLS and Sen slopes have the same sign.
   - `unclear`: exactly one q-value below 0.05, or both but with opposite signs.
   - `none`: neither. `no_data`: the series is too short for any statistic (under 24 months monthly,
     under 3 values yearly).
   A single series (a city, a pasted series) has no correction; the ladder runs on the plain p-values.
4. **Families (user decision 2): regions within a layer.** One variable across the regions, in the
   chosen window, for the map and TREND.EXE. A circle's family is the cells **inside the circle the user
   draws**: a cell belongs when its centre lies inside it, and a cell whose centre is outside is left out even if it
   overlaps (user decision, 2026-11-15; this also applies to the cells of every layer of the map's CIRCLE tool, via
   `POST /api/cell-circle`, so the correction is done per drawn circle, never once for a whole box). The earlier "every
   region x variable" family of `/api/scan` is dropped.
5. **Which Mann-Kendall p-value.** The ladder uses the adjusted one. The unadjusted p-value calls 29%
   of trend-free AR(1) series (phi 0.6) significant (ADR 0007), so it must not decide a verdict. The
   map keeps its old unadjusted `mk_p_adj` field for compatibility and gains `mk_p_ar1_adj`.
   *Assumption to confirm: the user said "both tests" without naming the Mann-Kendall variant.*
6. **Wording (science rule 7) stays exactly two phrases.** `rise` or `fall`: "... statistically
   significant at 95%" (with " after correcting for N tests at once" when there is a family).
   `unclear` and `none`: "... no significant trend detected (yet). The estimated change is ...".
   `unclear` adds the warning code `one_test_significant` (or `tests_disagree`) asking the reader to
   check for outliers or non-linearity (rule 3). The sentence is built from the verdict, never from
   the uncorrected p-value.

## Acceptance ranges (written before the simulations run, never loosened)
Seeded runs, 50-series families, 10 years of monthly data, 100 runs per scenario. Under a global null
Benjamini-Hochberg holds the chance of any flagged series at about 5%; with two tests required it is
lower. The upper limits are the 99th percentile of Binomial(100, 0.05), 11 of 100, rounded up.
- **(a) 50 independent null series:** runs with any `rise` or `fall` at most 12%; runs with both a rise
  and a fall (a "mixed signal") at most 12%. (The teammate measured about 50% for the mixed-signal
  warning before any correction.)
- **(b) 50 null series with a shared noise component** (positively dependent, like neighbouring cells):
  any flagged at most 12%.
- **(c) 50 null series with autocorrelated noise (phi 0.6):** any flagged at most 15%. Looser, because
  small-sample estimation of the autocorrelation leaves each p-value slightly too small (ADR 0007).
- **(d) 3 strong real trends among 47 nulls:** all three flagged in at least 95% of runs, and the mean
  false discovery proportion (flagged nulls divided by all flagged) at most 8%.
  *Amended after the first run.* The original wording was "no more than 12% of runs with any flagged
  null". That is the wrong statistic: Benjamini-Hochberg controls the expected false discovery
  proportion, not the chance of any false flag, and with real trends present the chance of any false
  flag is expected to be far above 5% (theory: FDR at most 0.05 x 47/50 = 4.7%, so with 3 flags in a
  run one extra false flag is 25% of that run's flags, about 19% of runs). The first run measured 20%
  of runs with a false flag but a mean false discovery proportion of 5.5% (sampling error about 1%),
  so the engine behaved as promised and the criterion was mistaken. The 8% limit is the theoretical
  4.7% plus 2.5 standard errors of the mean over 100 runs, rounded up.

## Measured (2026-11-15, seeds 101 to 104)
| Scenario | Any flagged | Mixed rise and fall | Limit |
|---|---|---|---|
| (a) independent nulls | 6% | 0% (57% without correction) | 12% |
| (b) shared noise between cells | 5% | 0% | 12% |
| (c) autocorrelated nulls, phi 0.6 | **15%** | 3% | 15% |
| (d) 3 real trends + 47 nulls | all three found in 100% of runs | | 95% |

(c) is at its limit and three times the nominal 5%: with 10 years of monthly data and strong memory,
each adjusted p-value is a little too small in the extreme tail, and a family of 50 gives that tail
many chances. The ladder makes the verdict more cautious than either test alone, but not safe against
this. Read a flagged series in a short, strongly autocorrelated record as a lead, and check the
`r1` and `n_eff` shown next to it.

## Consequences
- The teammate's numbers change in two places, on purpose: circle cells count as rising or falling only
  when both tests agree after correction, and the map's `direction` follows the ladder with the adjusted
  Mann-Kendall p-value. Trend, CI and p-value numbers do not change (snapshot test).
- **Project window (user decision A, 2026-11-15).** `/api/trend`, `/api/scan` and `/api/meta` use the same
  1980 to 2018 limit as the trend engine (`catalog/scope.py`), so the page and the map analyse the same years.
  Verdicts depend on it (7 of 8 variables change pattern with 1980-2026), so it is shown and documented.
- Every route returns one `significance` block (`docs/api.md`). The old top-level `sentence` of
  `/api/trend` stays for compatibility and is the per-series, uncorrected one.
- `years_needed` (core/detect.py) simulates the OLS test only. Requiring both tests needs more years;
  the adjusted Mann-Kendall is too slow inside that simulation. It is labelled "OLS only".
- Pre-whitened Mann-Kendall (`docs/stats_trend.md`) is not built. With both tests shown the headline
  question no longer blocks anything; it can join later as a third test without changing the hand-off.
- `core/events.py` still tests its own trend at p < 0.05 and does not follow the ladder.
- Benjamini-Hochberg assumes independent or positively dependent tests. Regions in a layer and cells
  in a circle are positively related; scenario (b) checks it.
