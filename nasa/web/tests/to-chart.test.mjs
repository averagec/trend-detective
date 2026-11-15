// Contract tests for data/to-chart.js, run on real API responses (tests/fixtures, made by the
// Flask app on a small synthetic record). Run: npm test
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { trendSpec } from "../src/data/to-chart.js";

const load = (n) => JSON.parse(readFileSync(new URL(`./fixtures/${n}.json`, import.meta.url), "utf8"));
const trend = load("trend"), scan = load("scan"), custom = load("analyse"), short = load("trend_short");
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

test("the server's sentence and warnings are shown verbatim", () => {
  const spec = trendSpec(custom);
  assert.equal(spec.notes[0], custom.sentence);
  for (const w of custom.warnings) assert.ok(spec.notes.includes(w));
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

test("the q-value and the verdict after correction come from /api/scan", () => {
  const row = scan.results.find((r) => r.region === "east_asia_land" && r.variable === "t2m");
  const spec = trendSpec(trend, { scan });
  const stats = Object.fromEntries(spec.stats);
  assert.ok(stats[`Q (${scan.n_tests} TRENDS TESTED)`]);
  assert.equal(stats["AFTER THE CORRECTION"], row.significant_q ? "statistically significant at 95%" : "no significant trend detected (yet)");
  assert.ok(spec.notes.includes(scan.note));
  assert.ok(!trendSpec(trend).stats.some(([k]) => k.startsWith("Q (")), "no q-value without a scan");
});

test("your own data has no q-value (it is not one of the scanned series)", () => {
  assert.ok(!trendSpec(custom, { scan }).stats.some(([k]) => k.startsWith("Q (")));
  assert.match(trendSpec(custom).title, /STATION/);
});

test("a window too short for statistics gives a chart spec without trend numbers", () => {
  const spec = trendSpec(short);
  assert.equal(short.statistics.ols_per_decade, null);
  assert.deepEqual(spec.fit, []);
  assert.deepEqual(spec.stats.map(([k]) => k), ["RECORD"]);
  assert.equal(spec.notes[0], short.sentence);
});

test("nothing renders as NaN or undefined", () => {
  for (const spec of [trendSpec(trend, { scan }), trendSpec(custom), trendSpec(short)]) {
    const text = JSON.stringify([spec.title, spec.sub, spec.unit, spec.stats, spec.notes, spec.fitLabel]);
    assert.ok(!/NaN|undefined|null/.test(text), text);
  }
});
