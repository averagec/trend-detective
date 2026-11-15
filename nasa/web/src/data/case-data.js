// The records the CASES flow lets you choose from (public/data/cases_data.json, made by
// scripts/export_indonesia.py). DATA ONLY: this file picks and reshapes months for the page. It
// computes no statistic; the trend, the tests, the lineup and the verdict come from the server
// (POST /api/analyse-series and POST /api/lineup through data/api.js).
const DATASETS = {};

async function load(url = "data/cases_data.json") {
  if (load.done) return true;
  const r = await fetch(url);
  if (!r.ok) throw new Error("cases_data.json missing");
  const d = await r.json();
  for (const [k, ds] of Object.entries(d.datasets)) {
    // "yearly" datasets (event counts) have `yearly` instead of `monthly`: the engine path for them is not built, so SETUP does not offer them
    DATASETS[k] = { label: ds.label, unit: ds.unit, source: ds.source, start: ds.start, end: ds.end, freq: ds.freq || "monthly", regions: {} };
    for (const [rk, reg] of Object.entries(ds.regions)) DATASETS[k].regions[rk] = { name: reg.name, long: reg.long, y0: reg.y0, monthly: reg.monthly };
  }
  load.done = true;
  return true;
}

// A known change of instrument inside a record. `years` goes to the server, which flags a
// significant trend that spans it; `draw` is only where the page shades the plot.
const INSTRUMENT_GAPS = { tws: { years: [2017, 2018], draw: [2017.5, 2018.42], what: "GRACE to GRACE-FO" } };
const instrumentGap = (variable) => INSTRUMENT_GAPS[variable] || null;

// The months of calendar years y0..y1 of one record, as the server wants them: a "YYYY-01" start and
// one value (or null) per month. `t` and `v` are the months that have a value, for drawing.
function caseWindow(variable, region, y0, y1) {
  const reg = DATASETS[variable].regions[region];
  const values = [], t = [], v = [];
  for (let y = y0; y <= y1; y++) {
    for (let m = 0; m < 12; m++) {
      const x = reg.monthly[(y - reg.y0) * 12 + m];
      const val = Number.isFinite(x) ? x : null;
      values.push(val);
      if (val !== null) {
        t.push(y + (m + 0.5) / 12);
        v.push(val);
      }
    }
  }
  return { start: `${String(y0).padStart(4, "0")}-01`, values, t, v };
}

// The records SETUP can offer: monthly ones only.
const monthlyKeys = () => Object.keys(DATASETS).filter((k) => DATASETS[k].freq === "monthly");

export const caseData = { DATASETS, load, caseWindow, instrumentGap, monthlyKeys };
