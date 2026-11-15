// Contract tests for the CASES flow: data/case-data.js (which months go to the server) and
// caseSpec in data/to-chart.js (how a /api/lineup response becomes the full-size chart).
// Run: npm test
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { caseSpec, trendSpec, yearlySpec } from "../src/data/to-chart.js";
import { caseData } from "../src/data/case-data.js";
import { CASE_VERDICT } from "../src/data/verdict-wording.js";

const load = (n) => JSON.parse(readFileSync(new URL(`./fixtures/${n}.json`, import.meta.url), "utf8"));
const lineup = load("lineup");
const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);

test("the fixture is a real /api/lineup response: trend shape plus a lineup block", () => {
  const lu = lineup.lineup;
  assert.equal(lu.n_sims, 1000);
  assert.equal(lu.sims_per_decade.length, 1000);
  assert.ok(["detected", "suspect", "not_detected"].includes(lu.verdict));
  assert.ok(lu.checks.length > 0 && lu.checks.every((c) => typeof c.ok === "boolean" && c.text));
  assert.equal(lineup.significance.family.name, "none");
});

test("the case chart is the TREND.EXE chart plus the lineup rows and the case verdict", () => {
  const base = trendSpec(lineup), spec = caseSpec(lineup);
  assert.deepEqual(spec.series, base.series);
  assert.deepEqual(spec.fit, base.fit);
  const keys = spec.stats.map(([k]) => k);
  assert.ok(keys.includes("NOISE LINEUP"));
  assert.ok(!keys.includes("VERDICT"), "one verdict row only: the case verdict");
  const verdictRow = spec.stats.find(([k]) => k === "CASE VERDICT");
  assert.equal(verdictRow[1], CASE_VERDICT[lineup.lineup.verdict]);
  assert.equal(spec.stats.at(-1)[0], "CASE VERDICT");
});

test("the notes are the server's words: headline, sentence, why, warnings, then the page's own", () => {
  const spec = caseSpec(lineup, { notes: ["Region: x."] });
  assert.equal(spec.notes[0], lineup.lineup.headline);
  assert.equal(spec.notes[1], lineup.significance.sentence);
  assert.equal(spec.notes[2], lineup.lineup.explanation);
  assert.equal(spec.notes.at(-1), "Region: x.");
});

test("the headline is one plain sentence in both views and says detected or not detected (yet)", () => {
  for (const block of [lineup.lineup, lineup.yearly.lineup]) {
    assert.ok(typeof block.headline === "string" && block.headline.length > 20);
    assert.match(block.headline, /^(Rising|Falling) trend (detected|found)|^A possible trend|^No significant trend detected \(yet\)/);
    assert.ok(!/\n/.test(block.headline));
  }
  assert.equal(yearlySpec(lineup).notes[0], lineup.yearly.lineup.headline);
});

test("title and source can be set by the case, and nothing else changes", () => {
  const spec = caseSpec(lineup, { title: "CASE · X", source: "SRC" });
  assert.equal([spec.title, spec.source].join("|"), "CASE · X|SRC");
});

test("a response without a lineup block is drawn as a plain trend chart", () => {
  const plain = { ...lineup };
  delete plain.lineup;
  assert.deepEqual(caseSpec(plain), trendSpec(plain));
});

test("caseWindow cuts whole calendar years, starts in January, and marks missing months null", () => {
  caseData.DATASETS.demo = {
    regions: { r: { y0: 2000, monthly: Array.from({ length: 48 }, (_, i) => (i === 14 ? null : i)) } },
  };
  const w = caseData.caseWindow("demo", "r", 2001, 2002);
  assert.equal(w.start, "2001-01");
  assert.equal(w.values.length, 24);
  assert.equal(w.values[0], 12);
  assert.equal(w.values[2], null); // index 14 of the record is March 2001
  assert.equal(w.t.length, 23);
  assert.ok(Math.abs(w.t[0] - (2001 + 0.5 / 12)) < 1e-12);
});

test("the GRACE to GRACE-FO change is known for water storage only", () => {
  assert.deepEqual(caseData.instrumentGap("tws").years, [2017, 2018]);
  assert.equal(caseData.instrumentGap("t2m"), null);
});

test("the loader survives yearly datasets (event counts have `yearly`, not `monthly`) and SETUP skips them", async () => {
  // Regression: the old browser loader read reg.monthly.forEach on every region, threw on the flood
  // and drought datasets, and the CASES window never opened.
  const file = JSON.parse(readFileSync(new URL("../public/data/cases_data.json", import.meta.url), "utf8"));
  assert.ok(Object.values(file.datasets).some((d) => d.freq === "yearly"), "the data file has a yearly dataset");
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => file });
  try {
    await caseData.load();
  } finally {
    globalThis.fetch = realFetch;
  }
  const keys = caseData.monthlyKeys();
  assert.ok(keys.includes("ssl") && keys.includes("t2m"));
  for (const [k, d] of Object.entries(caseData.DATASETS)) {
    assert.equal(keys.includes(k), d.freq === "monthly", `${k} offered only if monthly`);
  }
});

test("every map layer with grid cells has a case record for every study city it can name", () => {
  const sets = ["t2m", "tsurf", "precip", "qv2m", "vpd", "evap"];
  const slug = (name) => name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const cities = JSON.parse(readFileSync(new URL("../public/data/indonesia_sea_level.json", import.meta.url), "utf8")).cities;
  for (const k of sets) {
    const ds = caseData.DATASETS[k];
    assert.ok(ds, `${k} has a dataset`);
    assert.ok(ds.regions.idn, `${k} has the region box`);
    for (const c of cities) {
      const reg = ds.regions[c.case || slug(c.name)];
      assert.ok(reg, `${k} has ${c.name}`);
      assert.equal(reg.monthly.length, (ds.end - ds.start + 1) * 12);
    }
  }
});

test("the data files are valid UTF-8 (a degree sign written in cp1252 shows as a broken character)", () => {
  for (const f of ["cases_data.json", "indonesia_cells.json", "regional_data.json"]) {
    const bytes = readFileSync(new URL(`../public/data/${f}`, import.meta.url));
    assert.doesNotThrow(() => new TextDecoder("utf-8", { fatal: true }).decode(bytes), f);
  }
});

test("the fixture has a yearly block: yearly values, band, its own lineup and a comparison sentence", () => {
  const y = lineup.yearly;
  assert.equal(y.frequency, "yearly");
  assert.equal(y.series.length, y.last_year - y.first_year + 1);
  assert.equal(y.band.length, y.series.length);
  assert.equal(y.lineup.n_sims, 1000);
  assert.ok(typeof y.comparison === "string" && y.comparison.length > 10);
});

test("the yearly chart puts each year at its middle and draws the server's line and band", () => {
  const y = lineup.yearly, spec = yearlySpec(lineup), s = y.statistics;
  assert.equal(spec.step, 1);
  assert.equal(spec.monthly, false);
  assert.deepEqual(spec.series[0], [y.first_year + 0.5, y.series[0].anomaly]);
  assert.equal(spec.fit.length, 2);
  const i0 = y.series.findIndex((r) => r.anomaly !== null);
  close(spec.fit[0][0], y.first_year + i0 + 0.5);
  close(spec.fit[0][1], s.ols_intercept + s.ols_slope_per_month * i0);
  assert.equal(spec.band.length, y.band.length);
  y.band.forEach((b, i) => assert.deepEqual(spec.band[i], [b.year + 0.5, b.low, b.high]));
});

test("the yearly chart says it is yearly and ends with its own case verdict and the comparison", () => {
  const spec = yearlySpec(lineup, { title: "CASE · X", notes: ["Region: x."] });
  assert.match(spec.sub, /YEARLY AVERAGES/);
  assert.equal(spec.title, "CASE · X");
  assert.equal(spec.stats.at(-1)[0], "CASE VERDICT");
  assert.equal(spec.stats.at(-1)[1], CASE_VERDICT[lineup.yearly.lineup.verdict]);
  assert.ok(spec.notes.includes(lineup.yearly.comparison));
  assert.equal(spec.notes.at(-1), "Region: x.");
  assert.ok(spec.stats[0][1].includes("yearly values"));
});

test("a yearly block with no trend still draws the points", () => {
  const empty = JSON.parse(JSON.stringify(lineup));
  empty.yearly.statistics.ols_per_decade = null;
  empty.yearly.lineup.n_sims = null;
  const spec = yearlySpec(empty);
  assert.deepEqual([spec.fit, spec.band], [[], []]);
  assert.ok(spec.series.length > 0);
  assert.ok(!spec.stats.some(([k]) => k === "NOISE LINEUP"));
});
