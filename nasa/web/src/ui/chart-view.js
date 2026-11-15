// Full-size chart preview. Every graph in the app opens here when clicked.
// spec: { title, sub, unit, series: [[x, y]], seriesLabel, fit: [[x, y]], fitLabel,
//         band: [[x, lo, hi]], bandLabel, stats: [[label, value]], notes: [text], source }
const NS = "http://www.w3.org/2000/svg";
const W = 860, H = 380, L = 64, R = 18, T = 16, B = 40;

function niceStep(span, target) {
  const raw = span / target, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
}
function ticks(lo, hi, target) {
  const st = niceStep(hi - lo || 1, target), out = [];
  for (let v = Math.ceil(lo / st) * st; v <= hi + st * 1e-9; v += st) out.push(+v.toFixed(10));
  return { out, st };
}
const fmtN = (v, st) => {
  const d = st >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(st)));
  return (v < 0 ? "−" : "") + Math.abs(v).toFixed(d);
};
function svgEl(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function close() {
  const o = document.getElementById("chartview");
  if (o) o.remove();
  document.removeEventListener("keydown", onKey, true);
}
function onKey(e) {
  if (e.key === "Escape") {
    e.stopPropagation();
    close();
  }
}
// Draws the chart, legend, stats and notes for `spec` into `el` (any element). Used inline by
// TREND.EXE and, through openChart, in the full-size overlay.
function renderChart(el, spec) {
  el.innerHTML = `<div class="cv-sub">${spec.sub || ""}</div>
      <div class="cv-plot"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"></svg><div class="cv-read" hidden></div></div>
      <div class="cv-leg"></div>
      ${spec.stats && spec.stats.length ? `<div class="cv-stats">${spec.stats.map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`).join("")}</div>` : ""}
      ${(spec.notes || []).map((n) => `<div class="cv-note">${n}</div>`).join("")}
      ${spec.source ? `<div class="cv-src">SOURCE · ${spec.source}</div>` : ""}`;
  const o = el;
  const svg = o.querySelector("svg"), ser = spec.series.filter((p) => p[1] != null);
  const xs = ser.map((p) => p[0]), ys = ser.map((p) => p[1]);
  (spec.band || []).forEach((b) => ys.push(b[1], b[2]));
  (spec.fit || []).forEach((f) => ys.push(f[1]));
  if (spec.zero) ys.push(0);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = (y1 - y0) * 0.08 || 1;
  y0 -= pad;
  y1 += pad;
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const X = (x) => L + (x - x0) / (x1 - x0 || 1) * (W - L - R), Y = (y) => H - B - (y - y0) / (y1 - y0) * (H - T - B);

  const g = svgEl("g", { class: "cv-grid" }, svg);
  const yt = ticks(y0, y1, 6);
  yt.out.forEach((v) => {
    svgEl("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: v === 0 ? "zero" : "" }, g);
    svgEl("text", { x: L - 8, y: Y(v) + 5, class: "ty" }, g).textContent = fmtN(v, yt.st);
  });
  const xt = ticks(x0, x1, 9);
  xt.out.forEach((v) => {
    svgEl("line", { x1: X(v), x2: X(v), y1: T, y2: H - B, class: "v" }, g);
    svgEl("text", { x: X(v), y: H - B + 20, class: "tx" }, g).textContent = Math.round(v);
  });
  svgEl("text", { x: 14, y: T + (H - T - B) / 2, class: "ta", transform: `rotate(-90 14 ${T + (H - T - B) / 2})` }, svg).textContent = spec.unit || "";
  svgEl("rect", { x: L, y: T, width: W - L - R, height: H - T - B, class: "cv-frame" }, svg);

  const leg = [];
  if (spec.band && spec.band.length) {
    const b = spec.band;
    svgEl("path", { d: "M" + b.map((q) => `${X(q[0])} ${Y(q[2])}`).join("L") + "L" + b.slice().reverse().map((q) => `${X(q[0])} ${Y(q[1])}`).join("L") + "Z", class: "cv-band" }, svg);
    leg.push(["band", spec.bandLabel || "95% range of the trend"]);
  }
  let d = "";
  ser.forEach((p, i) => {
    const gap = i && p[0] - ser[i - 1][0] > (spec.step || 1) * 1.5;
    d += (i && !gap ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1);
  });
  svgEl("path", { d, class: "cv-line" }, svg);
  if (ser.length <= 80) ser.forEach((p) => svgEl("rect", { x: X(p[0]) - 3, y: Y(p[1]) - 3, width: 6, height: 6, class: "cv-pt" }, svg));
  leg.push(["line", spec.seriesLabel || "Data"]);
  if (spec.fit && spec.fit.length) {
    svgEl("path", { d: "M" + spec.fit.map((q) => `${X(q[0])} ${Y(q[1])}`).join("L"), class: "cv-fit" }, svg);
    leg.push(["fit", spec.fitLabel || "Trend line"]);
  }
  o.querySelector(".cv-leg").innerHTML = leg.map(([k, t]) => `<span><i class="lg-${k}"></i>${t}</span>`).join("");

  const cross = svgEl("line", { y1: T, y2: H - B, class: "cv-cross", visibility: "hidden" }, svg);
  const dot = svgEl("rect", { width: 10, height: 10, class: "cv-hot", visibility: "hidden" }, svg);
  const read = o.querySelector(".cv-read"), unit = spec.unit || "";
  const fitAt = (x) => {
    const f = spec.fit;
    if (!f || f.length < 2) return null;
    for (let i = 1; i < f.length; i++) if (x <= f[i][0]) return f[i - 1][1] + (f[i][1] - f[i - 1][1]) * (x - f[i - 1][0]) / (f[i][0] - f[i - 1][0] || 1);
    return f[f.length - 1][1];
  };
  svg.addEventListener("pointermove", (e) => {
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const u = pt.matrixTransform(svg.getScreenCTM().inverse());
    if (u.x < L || u.x > W - R) return;
    const xv = x0 + (u.x - L) / (W - L - R) * (x1 - x0);
    let best = ser[0];
    for (const p of ser) if (Math.abs(p[0] - xv) < Math.abs(best[0] - xv)) best = p;
    const px = X(best[0]), py = Y(best[1]);
    cross.setAttribute("x1", px);
    cross.setAttribute("x2", px);
    cross.setAttribute("visibility", "visible");
    dot.setAttribute("x", px - 5);
    dot.setAttribute("y", py - 5);
    dot.setAttribute("visibility", "visible");
    const fv = fitAt(best[0]), when = spec.monthly ? `${Math.floor(best[0])}-${String(Math.floor(best[0] % 1 * 12 + 1e-6) + 1).padStart(2, "0")}` : Math.floor(best[0]);
    read.innerHTML = `<b>${when}</b> ${best[1] >= 0 ? "+" : "−"}${Math.abs(best[1]).toFixed(spec.dp ?? 1)} ${unit}${fv != null ? `<br><span>trend line ${fv >= 0 ? "+" : "−"}${Math.abs(fv).toFixed(spec.dp ?? 1)}</span>` : ""}`;
    read.hidden = false;
    const bw = svg.clientWidth, k = bw / W, oy = (svg.clientHeight - H * k) / 2;
    read.style.left = Math.min(px * k + 14, bw - 170) + "px";
    read.style.top = Math.max(4, oy + py * k - 46) + "px";
  });
  svg.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    read.hidden = true;
  });
  return el;
}
// Full-size chart preview. Every graph in the app opens here when clicked.
function openChart(spec) {
  close();
  const host = document.querySelector("#os .crt") || document.body;
  const o = document.createElement("div");
  o.id = "chartview";
  o.className = "cv-over";
  o.innerHTML = `<div class="cv-win" role="dialog" aria-label="${spec.title}">
    <div class="cv-tb"><span>${spec.title}</span><button class="cv-x" aria-label="Close chart">×</button></div>
    <div class="cv-body"></div></div>`;
  host.appendChild(o);
  o.addEventListener("pointerdown", (e) => {
    if (e.target === o) close();
  });
  o.querySelector(".cv-x").onclick = close;
  document.addEventListener("keydown", onKey, true);
  renderChart(o.querySelector(".cv-body"), spec);
  return o;
}
export { openChart, renderChart, close as closeChart };
