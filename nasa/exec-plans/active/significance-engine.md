# Significance engine: evaluate the trend engine's series

- Owner: team (drafted by Claude, 2026-11-15)
- Started: 2026-11-15
- Status: **Phases 0 to 5 done** on branch `feature/significance-engine`, local only (not pushed). Open items below.

## Goal
The trend engine (cells, circles, regions, user series) hands every series to one significance
engine in `core/`. It returns the trend, both tests, a multiple-testing correction and one verdict,
the same way for every route. Done when: `scripts/check.sh` passes (lint, pytest, web build, web
tests); a city, a circle cell, a region and a pasted series all return the same `significance`
block; TREND.EXE shows a sentence that never contradicts the verdict; and a simulation of null
circles and null region sets stays inside the pre-written acceptance ranges below.

## Decisions already made (2026-11-15, by the user)
1. **Verdict ladder = both tests after correction.** `rise` or `fall` only when the OLS test and the
   Mann-Kendall test are both significant after correction and have the same sign. Only one
   significant: `unclear`. Neither: `none`.
2. **Correction family = regions within a layer** (one variable across regions). Used by TREND.EXE
   and the map. A circle's family is its cells. A single city or a pasted series has no family
   (plain p-values, one test).
3. **No cross-check of the trend engine's claimed slope.** The hand-off carries only the series.

Assumption to confirm: "the Mann-Kendall test" in the ladder is the **autocorrelation-adjusted** one
(`mk_p_ar1`, ADR 0007). The unadjusted p-value gives 29% false positives on AR(1) noise (phi 0.6), so
it should not decide a verdict. The map today corrects the unadjusted `mk_p`; that value stays in the
response as `mk_p_adj`, and the ladder uses the new `mk_p_ar1_adj`.

## Context
- Trend engine, on `main` (a7185e0): `process/selection.py` (city, circle), `process/regional_map.py`
  (`/api/map`), `process/cell_cube.py`, `core/detect.py`, `core/events.py`, ADR 0005-spatial-selection,
  ADR 0006-flood-drought-flow, `docs/stats_trend.md` (proposal).
- Our branch `feature/trend-exe-api-integration` (uncommitted): `mann_kendall_ar1`, `/api/scan`,
  `/api/analyse` for user series (to be renamed), JSON errors, `docs/api.md`, TREND.EXE, web tests.
- Dry-run merge result (scratch copy): 5 textual conflicts, route collision, positional-argument
  hazard, ADR number collisions. After fixes: 269 pass, 5 skip (no cell cube), 1 xfail.
- Rules: `docs/science-rules.md` (wording: only "statistically significant at 95%" or "no significant
  trend detected (yet)"). Core stays pure. Never loosen `tests/core/test_trend.py`.

## Design

### The hand-off (`SeriesBundle`, no `claimed` field)
`id`, `kind` (city | cell | circle_average | region | user), `label`, `unit`, `freq` (monthly |
yearly), `start`, `values` (null for gaps, never filled), `leading_pad`, `family` (name and the
members it is corrected with).

### Engine (`core/significance.py`, pure functions)
- `evaluate_series(...)`: wraps `summarise` (no second copy of any maths) and returns slope per
  decade, CI, `ols_p`, `mk_p`, `mk_p_ar1`, `n_eff`, `r1`, warnings.
- `correct_family(evals)`: Benjamini-Hochberg (`core.trend.benjamini_hochberg`) on `ols_p` and on
  `mk_p_ar1`, separately. Returns `ols_q`, `mk_q`, `n_tests` (series with a p-value),
  `expected_by_chance`.
- `verdict(ols_q, mk_q, ols_slope, sen_slope)`: the ladder above. For no family, q = p.
- `sentence(...)`: built from the verdict, rule-7 wording. `unclear` and `none` both say "no
  significant trend detected (yet)"; `unclear` adds a warning code `one_test_significant`.

### The block every route returns (additive, nothing renamed)
```
"significance": {
  "family":  {"name": "layer" | "circle" | "none", "n_tests": int|null, "method": "benjamini-hochberg"|null, "alpha": 0.05},
  "ols_p", "ols_q", "mk_p_ar1", "mk_q",        // q equals p when there is no family
  "verdict": "rise" | "fall" | "unclear" | "none" | "no_data",
  "significant": bool,                          // verdict is rise or fall
  "expected_by_chance": number|null,
  "sentence": str, "warnings": [{"code": str, "text": str}]
}
```
The existing top-level `sentence` of `/api/trend` stays (frozen) and is documented as the per-series,
uncorrected sentence. The page shows `significance.sentence`.

## Steps (each ends with `scripts/check.sh` green; commits only on the user's OK)

### Phase 0: merge (needs approval)
- [x] 0.1 [GATE] Commit our branch (leave the three stray `package-lock.json` files out).
- [x] 0.2 New branch `feature/significance-engine`; merge `main`. Resolutions: keep both sides in
      `ARCHITECTURE.md`, `app/web.py`, `core/summary.py`, `core/trend.py`; `vite.config.js` take main's.
- [x] 0.3 Rename our `POST /api/analyse` to `/api/analyse-series` (code, tests, docs, fixtures, classic
      page, `web/src/data/api.js`). Theirs keeps `/api/analyse`.
- [x] 0.4 Make `leading_pad` keyword-only in `summarise` (merged signature has `steps_per_year` before it).
- [x] 0.5 Their `SelectionError` handler returns our `{error, status}` shape.
- [x] 0.6 Renumber our ADRs 0005 to 0007 and 0006 to 0008; fix every reference; resolve the duplicate
      section 4.5 in `docs/statistics.md`.
- [x] 0.7 Result: 269 passed, 5 skipped (no cell cube), 1 xfailed; ruff, site build and web tests green. Every route
      family answers over HTTP. **Not done:** a browser run after the merge (the pane refused localhost:5060);
      `desktop.js` was checked statically instead (main + our four lines).

### Phase 1: freeze today's behaviour
- [x] 1.1 Snapshot tests on seeded synthetic data for `analyse_city`, `analyse_circle` and `build_map`
      (numbers only). Reuse the synthetic grid helpers in `tests/process/test_selection.py`.
- [x] 1.2 (nothing to add: their tests already cover it; they stay skipped until the cube exists) Keep the teammate's Jakarta checks (T2M +0.1645 K/decade, rain +0.3276 mm/day/decade); they
      run once the cell cube exists (skipped today).

### Phase 2: the engine, doc first
- [x] 2.1 ADR 0009: hand-off, three families, the ladder, which Mann-Kendall p enters it, the
      acceptance ranges below. Written before the code.
- [x] 2.2 `core/significance.py` with golden tests: a table of all ladder cases (both significant same
      sign, opposite signs, one significant, none, NaN), BH reuse on a hand example, single-series
      equals plain p-values, `n_tests` ignores series without a p-value.
- [x] 2.3 (criterion (d) was amended after the first run: ADR 0009 explains) Simulation tests (seeded, ranges fixed now, never loosened):
      (a) 50 independent null series in a family: share of runs with any `rise` or `fall` at most 8%
          over 300 runs (BH holds the global-null rate near 5%).
      (b) null circles of 50 cells: mixed-signal rate at most 8% (the teammate saw about 50% before
          correction).
      (c) the same with a shared noise component between cells (positive dependence): at most 8%.
      (d) a family with 3 real trends and 47 nulls: all 3 detected in at least 95% of runs.

### Phase 3: route the trend engine through it
- [x] 3.1 `analyse_city`: single series, no family.
- [x] 3.2 `analyse_circle`: cells use `correct_family`; rising and falling counts come from the verdict;
      the area average is evaluated as a single reference series. Existing keys stay.
- [x] 3.3 `build_map`: layer family. Keep `ols_p_adj` and `mk_p_adj`; add `mk_p_ar1_adj`, `ols_q`,
      `mk_q`; `direction` now follows the ladder.
- [x] 3.4 [GATE; done in auto mode as the user asked; the teammate must be told] These change the teammate's numbers (cells counted as rising or falling need both
      tests; the map's `direction`). Tell them, update their tests with the reason in the commit.
- [x] 3.5 `/api/trend` gains the `significance` block (layer family: all regions for that variable in
      that window). `/api/scan` becomes `scan?variable=` returning every region's block (the all
      region x variable family is dropped). `/api/analyse-series` returns a no-family block.
- [x] 3.6 One serializer (`process/significance_json.py`) used by trend, scan, city, circle, map.
      Frozen key tests: add the new keys, remove none.

### Phase 4: website
- [x] 4.1 `web/src/data/to-chart.js` reads `significance`: verdict, both q-values, family text
      ("tested across 3 regions for this variable"), sentence. TREND.EXE no longer calls `/api/scan`.
- [x] 4.2 Regenerate `web/tests/fixtures/*.json`, extend the node tests, keep the shape test in step.
- [x] 4.3 Their `region-map.js` and the circle tool read `direction` and the counts: no key moved (checked by their
      tests passing); not re-checked in a browser. The classic page was also switched to the block.

### Phase 5: docs and sign-off
- [x] 5.1 `docs/api.md`, `docs/statistics.md` (reporting section, families, verdict),
      `docs/science-rules.md` rule 3 and 7 (significant means both tests, after correction when several
      are shown), a note in `docs/stats_trend.md` that the headline question is settled here.
- [x] 5.2 Browser check on real data (done on port 5058): East China temperature 1990 to 2019 (p 0.041 alone) shows
      `unclear`, q OLS 0.061 / MK 0.007 and a matching sentence; the full record shows `rising` with the
      corrected sentence. Not tried in the browser: a null layer and a window with under 24 months (API tests cover them).
- [x] 5.3 Full gate; progress log; nothing pushed until the user says so.

## Acceptance
- No screen shows "statistically significant at 95%" next to "no significant trend detected (yet)".
- A verdict of `rise` or `fall` always has both q-values below 0.05 and the same sign.
- All Phase 2 simulation ranges hold. Golden tests untouched; `tests/core/test_trend.py` unchanged.

## Out of scope (listed so they are not forgotten)
- ~~Sen's slope with missing months~~ fixed on main by PR #4 (2026-11-15); the xfail is now a normal test.
- `years_needed` simulates the OLS test only. Under the two-test rule more years are needed; the
  adjusted Mann-Kendall is too slow inside that simulation. Label it "OLS only" for now.
- `core/events.py` tests its own trend with OLS at p < 0.05; it does not follow the ladder yet.
- City, circle and event on real data need the cell cubes (`data/processed/cells/*.npz`, not in the
  repo); until then those paths are tested on synthetic data only.
- JS statistics still in `web/src/stats/` and the MAP synthetic layers.

## Progress log
<!-- Append one line per session: date — what changed — what's next. -->
- 2026-11-15 — plan drafted after the audit of main (a7185e0). Decisions 1 to 3 recorded. Nothing executed. Next: user OK on Phase 0.
- 2026-11-15 — Phase 0 done: our work committed (e758415) on feature/trend-exe-api-integration, branch feature/significance-engine merges main (a7185e0). Route renamed to /api/analyse-series, leading_pad keyword-only, their errors now carry `status`, our ADRs are 0007 and 0008, their events section is statistics.md 3.6. Not pushed. Next: Phase 1 (freeze today's numbers).
- 2026-11-15 — Phase 1 done (snapshots of today's numbers and decisions). Phase 2 done: ADR 0009, `core/significance.py` (ladder, per-test BH, verdict sentence), 24 golden tests, 4 seeded simulations. Finding: the pre-registered criterion (d) was the wrong statistic (BH controls FDR, not the chance of any false flag); amended in the ADR with the reasoning, measured FDR 5.5% vs the 4.7% bound. Limitation: autocorrelated nulls (phi 0.6, 10 years) give 15% of families with a false flag. Next: Phase 3.
- 2026-11-15 — Phase 3 done: city, circle, map, /api/trend, /api/scan (now `?variable=`, layer family) and /api/analyse-series return the `significance` block (shared `process/significance_json.py`); circle cells and map `direction` follow the ladder; legacy keys kept, `mk_p_ar1`, `mk_p_ar1_adj` added. Trend/CI/p numbers unchanged (snapshot). Proven behaviour change: an AR(1) region with unadjusted MK p 0.0006 but adjusted 0.087 was a `rise`, is now `unclear`. Fixtures regenerate with `scripts/make_web_fixtures.py`. Next: Phase 4 (website).
- 2026-11-15 — Phase 4 done: TREND.EXE and the classic page read the `significance` block (verdict, both q-values, family label, server sentence); TREND.EXE no longer calls /api/scan; web tests 12. Next: Phase 5 (docs, science rules, real-data check).
- 2026-11-15 — Phase 5 done: docs/api.md, statistics.md 4.8, science-rules 3 and 7, ADR 0007/0008/0009 cross-references, ARCHITECTURE (stale duplicate app row removed). Real data: East China temperature 1990-2019 `unclear` (OLS q 0.061, MK q 0.007); full record 18 rises unchanged. Everything is local; nothing pushed.
- 2026-11-15 — Merged origin/main (762ba82: Sen fix PR #4, project window 1980-2018, GDIS counts, MAP layers) into the branch (5b7027d). User chose option A: the project window now limits /api/trend, /api/scan and /api/meta too. xfail removed (Sen fixed on main). Regional export regenerated (it was stale: made before main's own window change). Found: main's window change pads series that begin later (GRACE 2002, GLDAS 2000, ENSO 1993) from 1980 and reported the padding as '65% of months are missing'; fixed with leading_pad in regional_map (their test that the timeline starts in 1980 still holds). Not pushed since e11fe41.

## Decisions & surprises
- A silent merge hazard: `summarise(values, unit, label, leading_pad)` was called positionally, and after
  the merge that slot is `steps_per_year`. Keyword-only fixes it (Phase 0.4).
- The teammate's `/api/map` corrects the unadjusted Mann-Kendall p-value; the ladder here uses the
  adjusted one. Their `direction` values can change as a result (Phase 3.4).
