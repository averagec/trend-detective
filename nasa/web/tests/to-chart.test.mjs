// Contract tests for data/to-chart.js, run on real API responses (tests/fixtures, made by the
// Flask app on a small synthetic record). Run: npm test
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { trendSpec } from "../src/data/to-chart.js";

const load = (n) => JSON.parse(readFileSync(new URL(`./fixtures/${n}.json`, import.meta.url), "utf8"));
const trend = load("trend"), custom = load("analyse"), short = load("trend_short");
const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);

test("points are placed at year + (month - 1) / 12 and missing months are left out", () => {
  const spec = trendSpec(custom);
  const mar = custom.series.find((r) => r.period === "2000-03");
  assert.deepEqual(spec.series[0], [2000 + 2 / 12, mar.anomaly]); // Jan and Feb are padding
  assert.equal(spec.series.length, custom.series.filter((r) => r.anomaly !== null).length);
  assert.ok(spec.series.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y)));
});

test("the trend line comes from the server's intercept and slope, at the first and last month", () => {
  const spec = trendSpec(trend), s = trend.statistics, n = trend.series.length;
  assert.equal(spec.fit.length, 2);
  close(spec.fit[0][0], 2000);
  close(spec.fit[0][1], s.ols_intercept);
  close(spec.fit[1][0], 2000 + (n - 1) / 12);
  close(spec.fit[1][1], s.ols_intercept + s.ols_slope_per_month * (n - 1));
});

test("the 95% band is drawn at July of each year", () => {
  const spec = trendSpec(trend);
  assert.equal(spec.band.length, trend.band.length);
  trend.band.forEach((b, i) => assert.deepEqual(spec.band[i], [b.year + 0.5, b.low, b.high]));
});

test("raw view plots the values and has no trend line or band (they are anomaly-scale)", () => {
  const spec = trendSpec(trend, { view: "raw" });
  assert.deepEqual(spec.series[0], [2000, trend.series[0].value]);
  assert.deepEqual([spec.fit, spec.band, spec.zero], [[], [], false]);
});

test("the sentence and warnings are the server's significance block, verbatim", () => {
  for (const data of [custom, trend]) {
    const spec = trendSpec(data);
    assert.equal(spec.notes[0], data.significance.sentence);
    for (const w of data.significance.warnings) assert.ok(spec.notes.includes(w.text));
  }
});

test("the page never shows the older per-series sentence, which ignores the family", () => {
  // significant on its own is not significant after correction: the two sentences can differ
  const doctored = structuredClone(trend);
  doctored.sentence = "Doctored rose by 9 K per decade, statistically significant at 95%.";
  assert.ok(!JSON.stringify(trendSpec(doctored).notes).includes("Doctored"));
});

test("stats show the autocorrelation adjustment and both Mann-Kendall p-values", () => {
  const stats = Object.fromEntries(trendSpec(trend).stats);
  const s = trend.statistics;
  assert.match(stats["EFFECTIVE MONTHS"], new RegExp(`${Math.round(s.n_eff)} of ${s.n_months}`));
  assert.match(stats["EFFECTIVE MONTHS"], new RegExp(`r1 = ${s.r1.toFixed(2)}`));
  assert.match(stats["MANN-KENDALL P"], /unadjusted/);
  assert.match(stats["MANN-KENDALL P"], /adjusted$/);
  assert.match(stats["TREND"], /K \/ decade$/);
});

test("q-values, the family and the verdict come from the response's significance block", () => {
  const sig = trend.significance;
  assert.equal(sig.family.name, "layer");
  const stats = Object.fromEntries(trendSpec(trend).stats);
  const key = `Q, CORRECTED FOR ${sig.family.n_tests} REGIONS`;
  assert.ok(stats[key], Object.keys(stats).join(" | "));
  assert.match(stats[key], new RegExp(`OLS ${sig.ols_q < 0.001 ? "< 0.001" : sig.ols_q.toFixed(3)}`));
  assert.match(stats[key], /MANN-KENDALL/);
  assert.equal(stats["VERDICT"], { rise: "RISING: both tests significant", fall: "FALLING: both tests significant", unclear: "UNCLEAR: the two tests do not agree", none: "NO SIGNIFICANT TREND (YET)" }[sig.verdict]);
});

test("every verdict has a label, and unknown ones are still shown rather than dropped", () => {
  for (const verdict of ["rise", "fall", "unclear", "none", "no_data"]) {
    const d = structuredClone(trend);
    d.significance.verdict = verdict;
    const label = Object.fromEntries(trendSpec(d).stats)["VERDICT"];
    assert.ok(label && !/undefined|null/i.test(label), `${verdict}: ${label}`);
  }
  const odd = structuredClone(trend);
  odd.significance.verdict = "surprise";
  assert.equal(Object.fromEntries(trendSpec(odd).stats)["VERDICT"], "SURPRISE");
});

test("your own data is judged alone: no correction is claimed", () => {
  const stats = Object.fromEntries(trendSpec(custom).stats);
  assert.equal(custom.significance.family.name, "none");
  assert.ok(stats["P-VALUES (NO CORRECTION)"]);
  assert.ok(!Object.keys(stats).some((k) => k.startsWith("Q, CORRECTED")));
  assert.match(trendSpec(custom).title, /STATION/);
});

test("a window too short for statistics gives a chart spec without trend numbers", () => {
  const spec = trendSpec(short);
  assert.equal(short.statistics.ols_per_decade, null);
  assert.deepEqual(spec.fit, []);
  assert.deepEqual(spec.stats.map(([k]) => k), ["RECORD", "VERDICT"]);
  assert.equal(Object.fromEntries(spec.stats)["VERDICT"], "NOT ENOUGH DATA");
  assert.equal(spec.notes[0], short.significance.sentence);
});

test("nothing renders as NaN or undefined", () => {
  for (const spec of [trendSpec(trend), trendSpec(custom), trendSpec(short)]) {
    const text = JSON.stringify([spec.title, spec.sub, spec.unit, spec.stats, spec.notes, spec.fitLabel]);
    assert.ok(!/NaN|undefined|null/.test(text), text);
  }
});
