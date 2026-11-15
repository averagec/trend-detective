# One case window for monthly and yearly trends

- Owner: agent (with Jacob)
- Started: 2026-11-15
- Status: phase 1 done on the branch, awaiting review (not committed)

## Goal
A case shows the monthly and the yearly view of the same record in one result window, both computed by the
engine, so nobody has to go to a second tool to see a yearly trend. Done when `POST /api/lineup` returns a
`yearly` block, the LINEUP window has a MONTHLY | YEARLY switch and a chart for each, existing screens
(TREND.EXE, the map, the other cases) work unchanged, `bash scripts/check.sh` passes with ruff and pytest
on PATH, and a browser run reaches both views.

## Context
- Decision and numbers: `docs/decisions/0011-one-case-window-monthly-and-yearly.md`.
- Builds on `core/lineup.py` (ADR 0010), `process/analyse_trends.py` `build_lineup`, `web/src/os/desktop.js`
  `openTest`, `web/src/data/to-chart.js`.
- Branch: feature/case-monthly-yearly, from feature/case-flow-on-engine (PR #12, not merged when this
  started). Rebase onto main when #12 lands.

## Steps
- [x] 1. `core/lineup.py`: `frequency` ("monthly" or "yearly"), `annual_means`, steps per decade, checks in
      steps of a year. Monthly results must not change (existing 14 tests stay green).
- [x] 2. `build_lineup`: add the `yearly` block and the `comparison` sentence. `docs/api.md`, API tests, fixture.
- [x] 3. Web: `yearlySpec`/`caseSpec` for the yearly block, MONTHLY | YEARLY switch in the LINEUP window.
- [x] 4. Browser check (monthly and yearly on a case), full gate, risk review for the user.
- [ ] 5. Phase 2 (not now): yearly event counts. Phase 3 (not now): decide TREND.EXE's future.

## Follow-up: wording fixes found by the Padang and Ambon dry run
Found by running the engine over all 23 sea-level places (Padang detected, Ambon not detected).
- [x] F1. **Comparison sentence** claimed the yearly view "has less power". For Ambon the yearly view is the
      one that finds a rise (p 0.043) and monthly does not (p 0.100): monthly values are very alike
      (r1 = 0.94), so 312 months count as only about 9 independent values against about 10 for 26 years.
      Compare the **effective number of independent values** (`n_eff`) in both views and say which has more
      power, or that they are about equal and the result sits near the 5% limit.
- [x] F2. **"Small" in the not-detected headline** is wrong when the slope is large but the record is noisy
      (Ambon +49 mm per decade, bigger than detected Padang +45). Say the data are too noisy to confirm it.
- [x] F3. **Borderline headline.** When no test passes but the result is close (a test p below 0.15, or the
      lineup alone below 5%), say "no significant trend detected (yet), but it is borderline" with what came
      close, instead of "could be chance" while the lineup disagrees. The 0.15 limit is our choice.
- [x] F4. Tests for each, docs (`docs/api.md`, ADR 0011 correction), fixture, browser check on Ambon.

## Progress log
<!-- Append one line per session: date — what changed — what's next. -->
- 2026-11-15 — ADR 0011 and this plan written; branch created.
- 2026-11-15 — phase 1 done. `core/lineup.py` takes `frequency` ("yearly" = yearly means of the monthly anomalies, checks in years; the 14 monthly tests unchanged, 11 new yearly tests). `build_lineup` adds the `yearly` block and the `comparison` sentence (`docs/api.md`, 5 new API tests, fixture). The LINEUP window has a MONTHLY | YEARLY switch, a histogram and a full chart for each (`yearlySpec`, 4 new web tests). Gate green (ruff, pytest, web build and tests). Browser-checked: CASE_001 sea level (both DETECTED, slopes +38.07 and +38.13 mm/decade), CASE_004 rainfall (monthly DETECTED, yearly NOT YET DETECTABLE, comparison sentence shown), TREND.EXE and the map to case path unchanged, no console errors. Latency 0.25 s typical and 0.5 s at 2000 months per `/api/lineup` (two lineups now), response 61 to 219 KiB. Next: review; phases 2 and 3.

- 2026-11-15 — one-sentence headline (user request: clearer trend detection): `core/lineup.headline` builds "Rising trend detected: ..." / "Rising trend found, but treat it with caution: ... (failed check in plain words)" / "No significant trend detected (yet): ..." (record too short, tests disagree, small against natural variation, or lineup says chance). In `lineup.headline` for both views (`docs/api.md`), shown at the top of the LINEUP result under the MONTHLY | YEARLY switch and as the first note in both full charts. 7 core tests, 1 API test, 1 web test. Gate green; browser-checked on Jakarta 2003-2017 (SUSPECT headline names the later-start reason). Known issue left alone: the later-start check wrongly flags about 40% of genuine trends at 15 years (see the calibration run); fixing it is a separate decision.

- 2026-11-15 — F1 to F4 done: comparison sentence compares effective independent values and no longer contradicts the outcome (checked on Ambon, Kupang, rainfall, temperature); "small" replaced by "too noisy to confirm"; new borderline headline; 8 comparison tests, 2 headline tests, API test updated; docs and ADR 0011 correction.

## Risk review (asked for by the user: too drastic?)
Not too drastic, because it is additive: the monthly block of `/api/lineup`, `/api/trend`, `/api/scan`,
TREND.EXE, the map and the cases are untouched in shape and behaviour (14 monthly lineup tests and 13 old API
tests pass unchanged; TREND.EXE and the map smoke-tested in the browser). What can still bite:
- **Stacked on PR #12** (feature/case-flow-on-engine). Merge #12 first, then rebase this branch.
- **Yearly view has less power**: expect "no significant trend" yearly where monthly says "rise" (5 of 24
  records measured). The UI says so with the `comparison` sentence; users may still ask "which is right?".
- **Yearly rule**: a calendar year needs 10 of its 12 months; a series starting in April loses its first year.
- **The guess is judged on the monthly view** only (stated next to the guess).
- **Cost**: each `/api/lineup` runs two lineups: 0.25 s typical, 0.5 s at 2000 months. Fine; revisit if a
  serverless time limit bites (Vercel deploy).
- **Not done on purpose**: yearly event counts (phase 2) and retiring TREND.EXE (phase 3, ADR 0011 decision 5):
  TREND.EXE is still a second place to look, and the only place with verdicts corrected across the 3 regions.
  The raw-versus-anomaly toggle of TREND.EXE is not in the case window yet.

## Decisions & surprises
- TREND.EXE is deliberately left alone (see ADR 0011, decision 5).
- The `count_trend` quirk (Jakarta floods: Sen 0.00, Mann-Kendall p 0.004, direction "none") belongs to phase 2.
