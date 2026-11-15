const DATASETS = {};
const SERIES = {};
async function load(url = "data/cases_data.json") {
  if (load.done) return true;
  const r = await fetch(url);
  if (!r.ok) throw new Error("cases_data.json missing");
  const d = await r.json();
  for (const [k, ds] of Object.entries(d.datasets)) {
    DATASETS[k] = { label: ds.label, unit: ds.unit, source: ds.source, start: ds.start, end: ds.end, regions: {} };
    for (const [rk, reg] of Object.entries(ds.regions)) {
      DATASETS[k].regions[rk] = { name: reg.name, long: reg.long, core: reg.core };
      const t = [], v = [];
      reg.monthly.forEach((x, i) => {
        if (x == null) return;
        t.push(reg.y0 + Math.floor(i / 12) + (i % 12 + 0.5) / 12);
        v.push(x);
      });
      SERIES[k + "|" + rk] = { t, v };
    }
  }
  load.done = true;
  return true;
}
function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = s * 1664525 + 1013904223 >>> 0;
    return s / 4294967296;
  };
}
function gauss(r) {
  let u = 0, v = 0;
  while (u === 0) u = r();
  v = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
function hash(str) {
  let h = 2166136261;
  for (const c of str) {
    h ^= c.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function makeSeries(vk, rk) {
  const ext = SERIES[vk + "|" + rk];
  if (ext) return { t: ext.t.slice(), v: ext.v.slice() };
  throw new Error(`no data for ${vk}/${rk}`);
}
function slice(s, y0, y1) {
  const t = [], v = [];
  s.t.forEach((x, i) => {
    if (x >= y0 && x < y1 + 1) {
      t.push(x);
      v.push(s.v[i]);
    }
  });
  return { t, v };
}
function deseason(s) {
  const sum = Array(12).fill(0), n = Array(12).fill(0);
  s.t.forEach((x, i) => {
    const m = Math.floor(x % 1 * 12);
    sum[m] += s.v[i];
    n[m]++;
  });
  return { t: s.t, v: s.v.map((x, i) => x - sum[Math.floor(s.t[i] % 1 * 12)] / n[Math.floor(s.t[i] % 1 * 12)]) };
}
const mean = (a) => a.reduce((p, c) => p + c, 0) / a.length;
function ols(t, v) {
  const mt = mean(t), mv = mean(v);
  let sxy = 0, sxx = 0;
  for (let i = 0; i < t.length; i++) {
    sxy += (t[i] - mt) * (v[i] - mv);
    sxx += (t[i] - mt) ** 2;
  }
  const b = sxy / sxx;
  const res = v.map((x, i) => x - (mv + b * (t[i] - mt)));
  const s2 = res.reduce((p, c) => p + c * c, 0) / (t.length - 2);
  return { b, a: mv - b * mt, se: Math.sqrt(s2 / sxx), res };
}
function sen(t, v) {
  const s = [];
  for (let i = 0; i < t.length; i++) for (let j = i + 1; j < t.length; j++) s.push((v[j] - v[i]) / (t[j] - t[i]));
  s.sort((a, b) => a - b);
  const k = s.length >> 1;
  return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2;
}
function lag1(r) {
  const m = mean(r);
  let num = 0, den = 0;
  for (let i = 0; i < r.length; i++) {
    den += (r[i] - m) ** 2;
    if (i) num += (r[i] - m) * (r[i - 1] - m);
  }
  return Math.max(-0.95, Math.min(0.95, num / den));
}
function ncdf(z) {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp(-z * z / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
}
function mk(v, r1) {
  const n = v.length;
  let S = 0;
  for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) S += Math.sign(v[j] - v[i]);
  let varS = n * (n - 1) * (2 * n + 5) / 18;
  const ess = Math.max(3, n * (1 - r1) / (1 + r1));
  varS *= n / ess;
  const Z = S > 0 ? (S - 1) / Math.sqrt(varS) : S < 0 ? (S + 1) / Math.sqrt(varS) : 0;
  return { S, Z, p: 2 * (1 - ncdf(Math.abs(Z))) };
}
function analyse(setup, onProgress) {
  const D = DATASETS[setup.v], full = makeSeries(setup.v, setup.r);
  const raw = slice(full, setup.y0, setup.y1), an = deseason(raw);
  const years = setup.y1 - setup.y0 + 1;
  const short = years < 10;
  const fit = ols(an.t, an.v), r1 = lag1(fit.res);
  const slope = sen(an.t, an.v);
  const m = mk(an.v, r1);
  const seEff = fit.se * Math.sqrt((1 + r1) / (1 - r1));
  const ci = [slope - 1.96 * seEff, slope + 1.96 * seEff];
  const sdRes = Math.sqrt(mean(fit.res.map((x) => x * x))), r = rng(hash("sur" + setup.v + setup.r + setup.y0 + setup.y1));
  const sims = [];
  let beat = 0;
  for (let k = 0; k < 1e3; k++) {
    let e = 0;
    const sv = an.t.map(() => e = r1 * e + gauss(r) * sdRes * Math.sqrt(1 - r1 * r1));
    const b = ols(an.t, sv).b;
    sims.push(b);
    if (Math.abs(b) >= Math.abs(fit.b)) beat++;
  }
  const shifts = [3, 5, 8].filter((s) => years - s >= 10).map((s) => {
    const sub = deseason(slice(raw, setup.y0 + s, setup.y1));
    const ss = sen(sub.t, sub.v);
    return { s, ss, p: mk(sub.v, r1).p };
  });
  const startOK = shifts.every((x) => Math.sign(x.ss) === Math.sign(slope) && x.p < 0.1);
  let worst = { y: null, change: 0 };
  for (let y = setup.y0; y <= setup.y1; y++) {
    const keep = an.t.map((x) => Math.floor(x) !== y);
    const tt = an.t.filter((_, i) => keep[i]), vv = an.v.filter((_, i) => keep[i]);
    const b = ols(tt, vv).b;
    const ch = Math.abs(b - fit.b) / Math.abs(fit.b || 1e-9);
    if (ch > worst.change) worst = { y, change: ch, flips: Math.sign(b) !== Math.sign(fit.b) };
  }
  const yearOK = !worst.flips && worst.change < 0.35;
  const gapIn = !!(D.gap && setup.y0 < D.gap[0] && setup.y1 + 1 > D.gap[1]);
  const sig = m.p < 0.05 && beat / 1e3 < 0.05;
  const checks = [
    { k: "At least 10 years of record (" + years + " chosen)", ok: !short },
    { k: "Seasonal cycle removed", ok: true },
    { k: "Two tests agree (Mann-Kendall + noise lineup)", ok: m.p < 0.05 === beat / 1e3 < 0.05 },
    { k: "Autocorrelation accounted for (lag-1 r = " + r1.toFixed(2) + ")", ok: true },
    { k: "Same answer with later start years", ok: startOK || !sig },
    { k: worst.y ? "No single year drives it (worst: " + worst.y + ")" : "No single year drives it", ok: yearOK || !sig },
    { k: gapIn ? "Instrument change inside period (GRACE to GRACE-FO gap)" : "No known instrument change in period", ok: !gapIn }
  ];
  let verdict, needed = null;
  if (sig && checks.every((c) => c.ok)) verdict = "DETECTED";
  else if (sig || gapIn && m.p < 0.05) verdict = "SUSPECT";
  else {
    verdict = "NOT YET DETECTABLE";
    needed = Math.min(150, Math.ceil(years * Math.pow(Math.max(1, 1.96 * seEff / Math.max(Math.abs(slope), 1e-9)), 2 / 3)));
  }
  // A span under 10 years cannot support a trend claim (docs/science-rules.md, rule 2).
  if (short) {
    verdict = "NOT YET DETECTABLE";
    needed = 10;
  }
  return { D, raw, an, fit, slope, ci, mk: m, r1, sims, beat, obs: fit.b, checks, verdict, needed, years, shifts, worst };
}
const analysis = { DATASETS, SERIES, load, makeSeries, slice, deseason, analyse, stats: { ols, sen, lag1, mk, rng, gauss } };
export {
  analysis
};
