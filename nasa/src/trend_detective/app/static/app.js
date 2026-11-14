// Draws what the server computes. Nothing here is a statistic: every number comes from /api/trend.

const HOW_TO_READ = [
  "The dots are each month's difference from a normal year for that month.",
  "The bars are yearly averages of those differences.",
  "The line is the best straight-line fit through the monthly values.",
  "The shaded band is the range where the true line probably lies (95% confidence). A wide band means the trend is uncertain.",
  "A trend is called significant only if the chance of seeing it by luck is under 5%.",
];
const LIMITS = [
  "MERRA-2 is a computer model that uses observations. It is not a direct measurement.",
  "Each region is averaged over several grid cells of about 50 km, so small areas are blurred.",
  "Trend tests on a few regions and variables can look significant by chance. Read the results as a starting point.",
];

const state = {
  meta: null,
  variable: null,
  regionA: null,
  regionB: null,
  from: null,
  to: null,
  request: 0, // lets a slow reply be ignored when a newer one has started
};

const $ = (id) => document.getElementById(id);

function esc(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function fmt(x, digits = 2) {
  return typeof x === "number" && Number.isFinite(x) ? x.toFixed(digits) : "n/a";
}

function fmtSigned(x, digits = 2) {
  return typeof x === "number" && Number.isFinite(x) ? `${x >= 0 ? "+" : ""}${x.toFixed(digits)}` : "n/a";
}

function fmtP(p) {
  if (typeof p !== "number" || !Number.isFinite(p)) return "n/a";
  return p < 0.001 ? "< 0.001" : p.toFixed(3);
}

function finite(x) {
  return typeof x === "number" && Number.isFinite(x);
}

async function api(path) {
  const response = await fetch(path);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.description || body.error || `Request failed (${response.status})`);
  return body;
}

function showError(message) {
  const box = $("error");
  box.textContent = message;
  box.hidden = !message;
}

function chartSVG(data) {
  const W = 720, H = 300, M = { left: 56, right: 16, top: 16, bottom: 36 };
  const series = data.series;
  const n = series.length;
  if (n < 2) return `<p class="muted">Not enough months to draw a chart.</p>`;
  const firstYear = Number(series[0].period.slice(0, 4));
  const lastYear = Number(series[n - 1].period.slice(0, 4));
  const plotW = W - M.left - M.right;
  const plotH = H - M.top - M.bottom;
  const x = (i) => M.left + (i / (n - 1)) * plotW;

  const trend = { intercept: data.statistics.ols_intercept, slope: data.statistics.ols_slope_per_month };
  const hasLine = finite(trend.intercept) && finite(trend.slope);
  // 95% band from the server, one row per year. Drawn as given; nothing is computed here.
  const band = (data.band || []).filter((b) => finite(b.low) && finite(b.high));
  const candidates = [0];
  series.forEach((s) => finite(s.anomaly) && candidates.push(s.anomaly));
  data.annual.forEach((a) => finite(a.mean_anomaly) && candidates.push(a.mean_anomaly));
  if (hasLine) candidates.push(trend.intercept, trend.intercept + trend.slope * (n - 1));
  band.forEach((b) => candidates.push(b.low, b.high));
  let lo = Math.min(...candidates), hi = Math.max(...candidates);
  const pad = (hi - lo) * 0.08 || 1;
  lo -= pad;
  hi += pad;
  const y = (v) => M.top + (1 - (v - lo) / (hi - lo)) * plotH;

  let out = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(data.label)} anomalies, ${firstYear} to ${lastYear}">`;
  for (let k = 0; k < 5; k++) {
    const v = lo + ((hi - lo) * k) / 4;
    out += `<line class="grid" x1="${M.left}" x2="${W - M.right}" y1="${y(v)}" y2="${y(v)}"/>`;
    out += `<text class="tick" x="${M.left - 8}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(2)}</text>`;
  }
  out += `<line class="zero" x1="${M.left}" x2="${W - M.right}" y1="${y(0)}" y2="${y(0)}"/>`;

  const yearWidth = plotW / Math.max(1, n / 12);
  const barW = Math.max(2, yearWidth * 0.6);
  for (const a of data.annual) {
    if (!finite(a.mean_anomaly)) continue;
    const cx = x((a.year - firstYear) * 12 + 6);
    const top = Math.min(y(0), y(a.mean_anomaly));
    const height = Math.abs(y(a.mean_anomaly) - y(0));
    const cls = a.mean_anomaly >= 0 ? "bar warm" : "bar cool";
    out += `<rect class="${cls}" x="${cx - barW / 2}" y="${top}" width="${barW}" height="${height}"><title>${a.year}: ${a.mean_anomaly.toFixed(2)} ${esc(data.unit)}</title></rect>`;
  }
  if (band.length > 1) {
    // Same x as the yearly bars (month 6 of each year). Upper edge left to right, lower edge back.
    const at = (b) => x((b.year - firstYear) * 12 + 6);
    const upper = band.map((b) => `${at(b)},${y(b.high)}`);
    const lower = band.slice().reverse().map((b) => `${at(b)},${y(b.low)}`);
    out += `<path class="band" d="M${upper.join(" L")} L${lower.join(" L")} Z"><title>95% confidence band for the trend line</title></path>`;
  }
  series.forEach((s, i) => {
    if (finite(s.anomaly)) out += `<circle class="dot" cx="${x(i)}" cy="${y(s.anomaly)}" r="1.6"/>`;
  });
  if (hasLine) {
    out += `<path class="trend" d="M${x(0)},${y(trend.intercept)} L${x(n - 1)},${y(trend.intercept + trend.slope * (n - 1))}"/>`;
  }
  for (let yr = Math.ceil(firstYear / 5) * 5; yr <= lastYear; yr += 5) {
    out += `<text class="tick" x="${x((yr - firstYear) * 12)}" y="${H - 12}" text-anchor="middle">${yr}</text>`;
  }
  out += `<text class="axis-title" x="${W - M.right}" y="${M.top - 4}" text-anchor="end">${esc(data.unit)}</text></svg>`;
  return out;
}

function panelHTML(data) {
  const s = data.statistics;
  const ci = Array.isArray(s.ols_ci_per_decade) ? s.ols_ci_per_decade : [null, null];
  const hasTrend = finite(s.ols_per_decade);
  let html = `<section class="panel"><h3>${esc(data.region_name)}</h3>`;
  html += `<p class="headline">${esc(data.sentence)}</p>`;
  html += chartSVG(data);
  if (hasTrend) {
    html += `<div class="cards" style="margin-top:12px">
      <div class="card"><span class="card-label">Trend</span>
        <span class="card-value">${fmtSigned(s.ols_per_decade)} ${esc(data.unit)} per decade</span>
        <span class="card-sub">95% CI ${fmtSigned(ci[0])} to ${fmtSigned(ci[1])}</span></div>
      <div class="card"><span class="card-label">Record</span>
        <span class="card-value">${fmt(s.n_years, 1)} years</span>
        <span class="card-sub">${s.n_months} months with data</span></div>
      <div class="card"><span class="card-label">Test agreement</span>
        <span class="card-value">${s.tests_agree ? "Both tests agree" : "Tests disagree"}</span>
        <span class="card-sub">Mann-Kendall (Sen slope) ${fmtSigned(s.sen_per_decade)} ${esc(data.unit)} per decade</span></div>
    </div>
    <table class="stats-table"><tbody>
      <tr><th scope="row">OLS p-value (adjusted for autocorrelation)</th><td>${fmtP(s.ols_p)}</td></tr>
      <tr><th scope="row">Mann-Kendall p-value (not adjusted)</th><td>${fmtP(s.mk_p)}</td></tr>
    </tbody></table>`;
  }
  if (data.warnings.length) {
    html += `<ul class="warnings" role="note">${data.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`;
  }
  return html + `</section>`;
}

function comparisonNote(a, b) {
  const sa = a.statistics, sb = b.statistics;
  const bothSig = sa.ols_significant && sb.ols_significant;
  const sameSign = Math.sign(sa.ols_per_decade) === Math.sign(sb.ols_per_decade);
  if (bothSig && !sameSign) {
    return `${a.region_name} and ${b.region_name} show opposite trends, and both are statistically significant at 95%.`;
  }
  if (bothSig) {
    return `${a.region_name} and ${b.region_name} change in the same direction, and both trends are statistically significant at 95%.`;
  }
  return "At least one of these regions shows no significant trend (yet), so the difference between them is not established.";
}

function renderChips(container, items, selected, onPick) {
  container.innerHTML = "";
  for (const item of items) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = item.text;
    b.setAttribute("aria-pressed", String(item.key === selected));
    b.addEventListener("click", () => onPick(item.key));
    container.appendChild(b);
  }
}

function renderControls() {
  const m = state.meta;
  renderChips(
    $("questions"),
    m.variables.map((v) => ({ key: v.key, text: v.question })),
    state.variable,
    (key) => { state.variable = key; state.regionB = null; renderControls(); refresh(); },
  );
  const current = m.variables.find((v) => v.key === state.variable);
  $("variable-note").textContent = current ? current.description : "";

  const regions = m.regions;
  renderChips(
    $("regions"),
    regions.map((r) => ({ key: r.key, text: r.name })),
    state.regionA,
    (key) => { state.regionA = key; if (state.regionB === key) state.regionB = null; renderControls(); refresh(); },
  );

  const others = regions.filter((r) => r.key !== state.regionA);
  const compare = $("compare");
  compare.innerHTML = `<option value="">None</option>` +
    others.map((r) => `<option value="${esc(r.key)}">${esc(r.name)}</option>`).join("");
  compare.value = state.regionB || "";
}

function refresh() {
  const id = ++state.request;
  const range = { from: $("from").value, to: $("to").value };
  const query = (region) =>
    `api/trend?${new URLSearchParams({ variable: state.variable, region, ...range })}`;
  return (async () => {
    showError("");
    try {
      const a = await api(query(state.regionA));
      const b = state.regionB ? await api(query(state.regionB)) : null;
      if (id !== state.request) return; // a newer request has started
      $("result").innerHTML = b
        ? `<div class="compare-grid">${panelHTML(a)}${panelHTML(b)}</div>` +
          `<p class="comparison">${esc(comparisonNote(a, b))}</p>`
        : `<div class="result">${panelHTML(a)}</div>`;
    } catch (err) {
      if (id === state.request) showError(err.message);
    }
  })();
}

function renderNotes() {
  $("notes").innerHTML =
    `<h2>How to read the chart</h2><ul>${HOW_TO_READ.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` +
    `<h2>Limits</h2><ul>${LIMITS.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
}

async function init() {
  try {
    state.meta = await api("api/meta");
  } catch (err) {
    $("loading").textContent = "";
    showError(err.message);
    return;
  }
  const { first, last } = state.meta.years;
  state.variable = state.meta.variables[0]?.key ?? null;
  state.regionA = state.meta.regions[0]?.key ?? null;
  state.from = first;
  state.to = last;

  $("app-body").innerHTML = `
    <section class="step"><h2>1. Ask a question</h2>
      <div class="chips" id="questions"></div>
      <p class="muted" id="variable-note"></p></section>
    <section class="step"><h2>2. Pick a region</h2>
      <div class="chips" id="regions"></div>
      <div class="controls">
        <label class="control">Compare with another region:
          <select id="compare"></select></label>
        <label class="control">From year
          <input id="from" type="number" min="${first}" max="${last}" value="${first}" /></label>
        <label class="control">To year
          <input id="to" type="number" min="${first}" max="${last}" value="${last}" /></label>
      </div></section>
    <section class="step" aria-live="polite" id="result"></section>
    <section class="notes" id="notes"></section>`;

  $("compare").addEventListener("change", (ev) => { state.regionB = ev.target.value || null; refresh(); });
  $("from").addEventListener("change", refresh);
  $("to").addEventListener("change", refresh);
  renderControls();
  renderNotes();
  refresh();
}

init();
