// Turns an /api/trend (or /api/analyse-series) response into the spec that ui/chart-view.js draws.
// No statistics here: it only reshapes numbers the server already computed. The verdict, the
// q-values and the sentence come from the response's `significance` block (docs/api.md).
// Time is `year + (month - 1) / 12`, as chart-view expects.
import { VERDICT, CASE_VERDICT } from "./verdict-wording.js";

const MINUS = "−";
const finite = (x) => typeof x === "number" && Number.isFinite(x);
const when = (period) => Number(period.slice(0, 4)) + (Number(period.slice(5, 7)) - 1) / 12;
const dp = (x) => (Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : Math.abs(x) >= 1 ? 2 : 3);
const sgn = (v) => (finite(v) ? `${v < 0 ? MINUS : "+"}${Math.abs(v).toFixed(dp(v))}` : "n/a");
const pv = (v) => (!finite(v) ? "n/a" : v < 0.001 ? "< 0.001" : v.toFixed(3));
const UNIT_OF_FAMILY = { layer: "REGIONS", circle: "CELLS" };

// data: the server response. opts.view: "anomaly" (seasons removed, default: the trend line and band apply) or "raw".
export function trendSpec(data, opts = {}) {
  const view = opts.view === "raw" ? "raw" : "anomaly";
  const s = data.statistics, unit = data.unit, field = view === "raw" ? "value" : "anomaly";
  const custom = data.region === "custom";
  const hasTrend = finite(s.ols_per_decade);
  const firstYear = Number(data.first_month.slice(0, 4));
  const series = data.series.filter((r) => finite(r[field])).map((r) => [when(r.period), r[field]]);

  // The OLS line and its 95% band are in anomaly units, so they only go with that view.
  let fit = [], band = [];
  if (view === "anomaly" && hasTrend && finite(s.ols_intercept) && finite(s.ols_slope_per_month)) {
    const idx = data.series.map((r, i) => (finite(r.anomaly) ? i : -1)).filter((i) => i >= 0);
    fit = [idx[0], idx[idx.length - 1]].map((i) => [firstYear + i / 12, s.ols_intercept + s.ols_slope_per_month * i]);
    band = (data.band || []).filter((b) => finite(b.low) && finite(b.high)).map((b) => [b.year + 0.5, b.low, b.high]);
  }

  const sig = data.significance;
  const per = `${unit} / decade`;
  const stats = [["RECORD", `${s.n_years.toFixed(1)} years · ${s.n_months} months with data`]];
  if (hasTrend) {
    const ci = s.ols_ci_per_decade;
    stats.push(
      ["TREND", `${sgn(s.ols_per_decade)} ${per}`],
      ["95% RANGE", `${sgn(ci[0])} to ${sgn(ci[1])} ${per}`],
      ["P (OLS, ADJUSTED)", pv(s.ols_p)],
      ["EFFECTIVE MONTHS", `${s.n_eff.toFixed(0)} of ${s.n_months} (autocorrelation r1 = ${s.r1.toFixed(2)})`],
      ["MANN-KENDALL P", `${pv(s.mk_p)} unadjusted · ${pv(s.mk_p_ar1)} adjusted`],
      ["SEN'S SLOPE", `${sgn(s.sen_per_decade)} ${per}`]
    );
    const fam = sig.family;
    const label = fam.name === "none"
      ? "P-VALUES (NO CORRECTION)"
      : `Q, CORRECTED FOR ${fam.n_tests} ${UNIT_OF_FAMILY[fam.name] || "TESTS"}`;
    stats.push([label, `OLS ${pv(sig.ols_q)} · MANN-KENDALL ${pv(sig.mk_q)}`]);
  }
  stats.push(["VERDICT", VERDICT[sig.verdict] || sig.verdict.toUpperCase()]);
  // The sentence and warnings are the server's, built from the verdict (never from one p-value).
  const notes = [sig.sentence, ...sig.warnings.map((w) => w.text)];

  return {
    title: `${(custom ? data.label : `${data.region_name} · ${data.label}`).toUpperCase()}`,
    sub: `${data.first_month} TO ${data.last_month} · MONTHLY · ${view === "raw" ? "RAW VALUES" : "SEASONAL CYCLE REMOVED"}`,
    unit: view === "raw" ? unit : `${unit} vs normal for the month`,
    series,
    seriesLabel: view === "raw" ? "Monthly value" : "Monthly value minus that month's average",
    fit,
    fitLabel: hasTrend ? `Trend ${sgn(s.ols_per_decade)} ${per}` : "Trend line",
    band,
    bandLabel: "95% range of the trend line",
    step: 1 / 12,
    monthly: true,
    zero: view === "anomaly",
    dp: 2,
    stats,
    notes,
    source: custom ? "YOUR DATA, ANALYSED BY THE PROJECT'S PYTHON CORE" : "NASA MERRA-2 (GES DISC) · ANALYSED BY THE PROJECT'S PYTHON CORE"
  };
}

// A /api/lineup response as a chart: the same chart as TREND.EXE plus the lineup and the case verdict.
// opts: {title, source, notes}. Still no statistics: every number is the server's.
export function caseSpec(data, opts = {}) {
  const spec = trendSpec(data, opts), lu = data.lineup;
  if (opts.title) spec.title = opts.title;
  if (opts.source) spec.source = opts.source;
  if (!lu) return spec;
  spec.stats = spec.stats.filter(([k]) => k !== "VERDICT");
  if (lu.n_sims) spec.stats.push(["NOISE LINEUP", `${lu.beat} of ${lu.n_sims} trend-free fakes as strong (${(lu.share * 100).toFixed(1)}%)`]);
  if (finite(lu.years_needed)) spec.stats.push(["YEARS NEEDED", `about ${lu.years_needed.toFixed(0)}`]);
  spec.stats.push(["CASE VERDICT", CASE_VERDICT[lu.verdict] || String(lu.verdict).toUpperCase()]);
  spec.notes = [lu.headline, data.significance.sentence, lu.explanation, ...data.significance.warnings.map((w) => w.text), ...(opts.notes || [])].filter(Boolean);
  return spec;
}

// The `yearly` block of a /api/lineup response as a chart (ADR 0011): yearly averages of the seasonal
// anomalies, with the trend line and 95% band the server computed per year. opts: {title, source, notes}.
export function yearlySpec(data, opts = {}) {
  const y = data.yearly, s = y.statistics, lu = y.lineup, sig = y.significance, unit = data.unit;
  const series = y.series.filter((r) => finite(r.anomaly)).map((r) => [r.year + 0.5, r.anomaly]);
  const hasTrend = finite(s.ols_per_decade) && finite(s.ols_intercept) && finite(s.ols_slope_per_month);
  let fit = [], band = [];
  if (hasTrend) {
    // ols_intercept and ols_slope_per_month are per yearly step here: the index is the year offset
    const idx = y.series.map((r, i) => (finite(r.anomaly) ? i : -1)).filter((i) => i >= 0);
    fit = [idx[0], idx[idx.length - 1]].map((i) => [y.first_year + i + 0.5, s.ols_intercept + s.ols_slope_per_month * i]);
    band = y.band.filter((b) => finite(b.low) && finite(b.high)).map((b) => [b.year + 0.5, b.low, b.high]);
  }
  const per = `${unit} / decade`;
  const stats = [["RECORD", `${s.n_months} yearly values (${y.first_year} to ${y.last_year})`]];
  if (hasTrend) {
    const ci = s.ols_ci_per_decade;
    stats.push(
      ["TREND", `${sgn(s.ols_per_decade)} ${per}`],
      ["95% RANGE", `${sgn(ci[0])} to ${sgn(ci[1])} ${per}`],
      ["P (OLS, ADJUSTED)", pv(s.ols_p)],
      ["MANN-KENDALL P", `${pv(s.mk_p_ar1)} adjusted`],
      ["SEN'S SLOPE", `${sgn(s.sen_per_decade)} ${per}`],
      ["P-VALUES (NO CORRECTION)", `OLS ${pv(sig.ols_q)} · MANN-KENDALL ${pv(sig.mk_q)}`]
    );
  }
  if (lu.n_sims) stats.push(["NOISE LINEUP", `${lu.beat} of ${lu.n_sims} trend-free fakes as strong (${(lu.share * 100).toFixed(1)}%)`]);
  if (finite(lu.years_needed)) stats.push(["YEARS NEEDED", `about ${lu.years_needed.toFixed(0)}`]);
  stats.push(["CASE VERDICT", CASE_VERDICT[lu.verdict] || String(lu.verdict).toUpperCase()]);
  return {
    title: opts.title || data.label.toUpperCase(),
    sub: `${y.first_year} TO ${y.last_year} · YEARLY AVERAGES · SEASONAL CYCLE REMOVED`,
    unit: `${unit} vs normal for the month`,
    series,
    seriesLabel: "Yearly average of the monthly anomalies",
    fit,
    fitLabel: hasTrend ? `Trend ${sgn(s.ols_per_decade)} ${per}` : "Trend line",
    band,
    bandLabel: "95% range of the trend line",
    step: 1,
    monthly: false,
    zero: true,
    dp: 2,
    stats,
    notes: [lu.headline, sig.sentence, lu.explanation, y.comparison, ...y.warnings, ...(opts.notes || [])].filter(Boolean),
    source: opts.source || "ANALYSED BY THE PROJECT'S PYTHON CORE"
  };
}
