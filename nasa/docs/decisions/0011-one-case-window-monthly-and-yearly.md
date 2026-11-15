# 0011 - One case window for monthly and yearly trends

- Status: proposed (2026-11-15), phase 1 implemented on branch feature/case-monthly-yearly.
- Extends: 0008 (website reads the API), 0009 (one significance engine), 0010 (case verdict on the engine).
- Plan: `exec-plans/active/case-monthly-yearly.md`.

## Context
Investigating a trend meant going to two places. TREND.EXE showed a monthly series, its trend and a
verdict for one of 3 region boxes, with the verdicts corrected across the layer's regions. MAP.EXE started
a case (SETUP, guess, PLOT, LINEUP) for any city or box, for monthly data only. Yearly data
(flood and drought counts) was in the data file but had no path through the engine.

Measured on 24 record and place pairs (`cases_data.json`, same engine): the monthly trend and the trend
of the yearly averages of the same record are the same number (largest difference 0.0003 per decade), but
the verdict differs in 5 of 24, always monthly "rise" against yearly "none" or "unclear". The yearly view
has 39 points instead of 468 months, so less power. Yearly event counts are a different problem: the
count engine (`core/counts.py`) uses Sen and Mann-Kendall without OLS, so the case ladder (OLS and
Mann-Kendall) does not apply to them. A trend-free Poisson count series gets flagged by the Gaussian
lineup in 4.5% of runs (nominal 5%), so the lineup recipe itself is sound for counts.

## Decision
1. **The case result shows both frequencies side by side.** `POST /api/lineup` keeps its monthly block
   exactly as it was and adds a `yearly` block: the yearly averages of the seasonal anomalies (months
   missing from a year are skipped when at least 10 of 12 are present), analysed by the same engine with
   `steps_per_year=1`: OLS and Mann-Kendall, the ladder, the lineup, the checks. Adding fields is
   compatible with `docs/api.md`.
2. **One verdict for the game, two views for the reader.** The guess, the log line and the detective's
   reply use the monthly verdict (it uses all the data). The page shows the yearly one next to it with a
   server-written `comparison` sentence that says when the two differ in significance and why (fewer
   points, less power), never as a contradiction, since the slopes agree.
3. **The page averages nothing.** Yearly means, the yearly lineup and the yearly chart numbers all come
   from the server.
4. **Not in this phase:** yearly event counts (floods, droughts). They need a count ladder (Sen and
   Mann-Kendall, as `core/counts.py`), a look at the case where Sen is 0 but Mann-Kendall is significant
   (Jakarta floods: Sen 0.00 per decade, p = 0.004, direction "none"), and the count-specific checks.
   SETUP keeps offering monthly datasets only until that is done.
5. **TREND.EXE is kept for now.** It is the only place that shows verdicts corrected across the three
   regions of one variable (ADR 0009 family "layer"), and it reads the server's own store. A case is a
   single place, so removing TREND.EXE would drop that view. Retiring it needs a decision from the team
   about where "compare places" lives.

## Correction (2026-11-15, found by a dry run over the 23 sea-level places)
The first version said the yearly view always "has less power" because it has fewer points. That is true on
average (rainfall: about 156 independent monthly values against 28 yearly) but not always. Sea-level months
are so alike (lag-1 autocorrelation 0.94 for Ambon) that 312 months count as only about 9 independent values,
while the 26 yearly values count as about 10, and the yearly view found a rise (p 0.043) that the monthly
view did not (p 0.100). The `comparison` sentence now compares the effective number of independent values
and never claims more power for the view that did not find the trend. The not-detected headline also stopped
calling a large slope "small" (Ambon's +49 mm per decade is bigger than detected Padang's +45; the record is
just noisier) and now says "borderline" when a test is within 0.15 of the limit or the lineup alone is under 5%.

## Consequences
- Nothing existing changes shape: the monthly block of `/api/lineup`, `/api/trend`, `/api/scan`, TREND.EXE,
  the map and the case flow keep working; the case result panel gains a MONTHLY | YEARLY switch.
- The yearly view usually has less power, so expect `none` where monthly says `rise`, but it can be the other way round (see the correction).
- The yearly checks use years as steps: later start years cut 3, 5, 8 years, leave-one-year-out drops one
  annual value, and the record must still have 10 years.
- Phase 2 (counts) and phase 3 (deciding TREND.EXE's future) are open.
