// TREND.EXE: pick a question, a place and the years; the analysis engine (Flask + Python core)
// returns the monthly series and every statistic, and this window only draws them.
// All numbers come from /api/trend and /api/scan through data/api.js; nothing is computed here.
import { getMeta, getTrend, getScan, newest, STALE } from "../data/api.js";
import { trendSpec } from "../data/to-chart.js";
import { renderChart, openChart } from "../ui/chart-view.js";
import { SFX } from "../audio/sfx.js";

const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const sel = { variable: null, region: null, from: null, to: null, view: "anomaly" }; // kept between openings
const latest = newest();

function frame(w, html) {
  w.querySelector(".bd").innerHTML = html;
}

async function open(win, ctx, preset) {
  const w = win("w-trend", "TREND.EXE", '<div class="dim">CONNECTING TO THE ANALYSIS ENGINE...</div>', { left: "120px", top: "10px", width: "800px", maxHeight: "97%" });
  let meta;
  try {
    meta = await getMeta();
  } catch (err) {
    SFX.err();
    frame(w, `<div class="tr-err" role="alert">${esc(err.message)}</div><button class="obtn" id="tr-retry">TRY AGAIN</button>`);
    w.querySelector("#tr-retry").onclick = () => open(win, ctx, preset);
    ctx.log(`TREND.EXE: ${err.message}`, "hi");
    return;
  }
  const { first, last } = meta.years;
  Object.assign(sel, preset || {});
  if (!meta.variables.some((v) => v.key === sel.variable)) sel.variable = meta.variables[0]?.key ?? null;
  if (!meta.regions.some((r) => r.key === sel.region)) sel.region = meta.regions[0]?.key ?? null;
  sel.from = Math.min(Math.max(sel.from ?? first, first), last);
  sel.to = Math.min(Math.max(sel.to ?? last, first), last);

  const opts = (items, cur) => items.map((i) => `<option value="${esc(i.key)}"${i.key === cur ? " selected" : ""}>${esc(i.text)}</option>`).join("");
  frame(w, `
    <div class="tr-bar">
      <label>QUESTION<select id="tr-v">${opts(meta.variables.map((v) => ({ key: v.key, text: v.question })), sel.variable)}</select></label>
      <label>PLACE<select id="tr-r">${opts(meta.regions.map((r) => ({ key: r.key, text: r.name })), sel.region)}</select></label>
      <label>FROM<input id="tr-f" type="number" min="${first}" max="${last}" value="${sel.from}"></label>
      <label>TO<input id="tr-t" type="number" min="${first}" max="${last}" value="${sel.to}"></label>
    </div>
    <div class="tr-bar">
      <button class="chip" id="tr-view" aria-pressed="${sel.view === "anomaly"}"></button>
      <button class="obtn" id="tr-full" disabled>FULL-SIZE CHART ▸</button>
    </div>
    <div class="dim" id="tr-note"></div>
    <div class="tr-err" id="tr-err" role="alert" hidden></div>
    <div class="cv-inline" id="tr-out"></div>`);

  const $ = (q) => w.querySelector(q), out = $("#tr-out");
  let last_ = null; // {data, scan}: the toggle redraws without asking the server again
  const draw = () => {
    if (!last_) return;
    const spec = trendSpec(last_.data, { scan: last_.scan, view: sel.view });
    renderChart(out, spec);
    $("#tr-full").disabled = false;
    $("#tr-full").onclick = () => (SFX.select(), openChart(spec));
    viewLabel();
  };
  const viewLabel = () => {
    const on = sel.view === "anomaly";
    $("#tr-view").setAttribute("aria-pressed", String(on));
    $("#tr-view").textContent = on ? "SEASONAL CYCLE: REMOVED" : "SEASONAL CYCLE: SHOWN";
  };
  const update = async () => {
    const v = meta.variables.find((x) => x.key === sel.variable);
    $("#tr-note").textContent = v ? v.description : "";
    $("#tr-err").hidden = true;
    out.classList.add("tr-busy");
    try {
      const params = { variable: sel.variable, region: sel.region, from: sel.from, to: sel.to };
      const result = await latest(Promise.all([getTrend(params), getScan({ from: sel.from, to: sel.to }).catch(() => null)]));
      if (result === STALE) return;
      last_ = { data: result[0], scan: result[1] };
      draw();
      ctx.log(`TREND.EXE: ${result[0].label} / ${result[0].region_name} ${sel.from}-${sel.to}`);
    } catch (err) {
      SFX.err();
      last_ = null;
      out.innerHTML = "";
      $("#tr-full").disabled = true;
      $("#tr-err").textContent = err.message;
      $("#tr-err").hidden = false;
    } finally {
      out.classList.remove("tr-busy");
    }
  };

  $("#tr-v").onchange = (e) => { sel.variable = e.target.value; SFX.select(); update(); };
  $("#tr-r").onchange = (e) => { sel.region = e.target.value; SFX.select(); update(); };
  const years = () => {
    sel.from = Number($("#tr-f").value);
    sel.to = Number($("#tr-t").value);
    update();
  };
  $("#tr-f").onchange = years;
  $("#tr-t").onchange = years;
  viewLabel();
  $("#tr-view").onclick = () => { sel.view = sel.view === "anomaly" ? "raw" : "anomaly"; SFX.select(); draw(); };
  update();
}

const trendApp = { open };
export { trendApp };
