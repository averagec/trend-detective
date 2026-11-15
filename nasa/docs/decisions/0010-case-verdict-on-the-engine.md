# 0010 - The case verdict runs on the engine

- Status: implemented on branch feature/case-flow-on-engine (2026-11-15), proposed for the team.
- Extends: 0008 (website reads the API), 0009 (one significance engine).
- Plan: `exec-plans/active/case-flow-on-engine.md`.

## Context
The website had two statistics paths. TREND.EXE and the map box read the engine (`core/`, ADR 0009).
The CASES flow (SETUP, PLOT, LINEUP) ran its own browser engine (`web/src/stats/trend-analysis.js`):
Sen's slope as the headline, its own Mann-Kendall, 1,000 surrogates, three robustness checks and the
verdict DETECTED / NOT YET DETECTABLE / SUSPECT. The same variable and years could get two different
answers on two screens, and the browser engine broke the rule that every number comes from `core/`.

## Decision
1. **`core/lineup.py` owns the case verdict.** It never computes a trend: slopes and p-values come
   from `core.summary.summarise`, the ladder from `core.significance.assess_single` (a single series,
   family `none`), "years needed" from `core.detect`.
2. **The lineup** builds 1,000 trend-free AR(1) records with the real lag-1 autocorrelation and residual
   spread and the real missing months, seeded from the data (the same record always gets the same
   fakes), and counts those whose slope is as strong as the real one. Under 5% is the third piece of
   evidence beside the two tests.
3. **Verdict.** `detected`: engine says rise or fall, lineup below 5%, every check passes.
   `suspect`: that evidence, but a check fails; or a known instrument change is inside the window and a
   test is significant. `not_detected`: everything else, always under 10 years.
4. **Checks:** record length, tests and lineup agree, later start years (3, 5, 8), leave one year out
   (35%), instrument change. Later-start and one-year checks run only when there is a trend to protect.
5. **`POST /api/lineup`** takes the series as sent, like `/api/analyse-series`, because the cases use
   records the Store does not hold (ECCO per city, GRACE, years outside 1980 to 2018). The page sends
   months and draws what comes back. `docs/api.md` has the contract.
6. **The page computes nothing.** `web/src/stats/` is deleted and `scripts/check.sh` fails if it returns.

## Consequences
- The headline estimator is now OLS with the autocorrelation-adjusted interval, with Sen shown second
  (science rule 3), not Sen as the old page had it. Case slopes can differ in the last digits.
- The Mann-Kendall p in the case panel is the autocorrelation-adjusted one, labelled as such.
- A water-storage window that spans GRACE to GRACE-FO is now flagged `suspect` (the old page never
  flagged it: its data carried no gap marker).
- The "PYTHON CORE" comparison line is gone: there is one result.
- The one-year check rarely fires in practice: a single odd year is mostly absorbed by the monthly means
  and by the autocorrelation-adjusted test. It is a safeguard, not a common outcome.
- The page compares the player's guess with the case verdict: a significant rise that is `suspect`
  counts as "didn't match" (pre-existing rule, kept).
