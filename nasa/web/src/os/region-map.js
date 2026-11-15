import { SFX } from "../audio/sfx.js";
import { say } from "../ui/dialogue.js";
import { analysis } from "../stats/trend-analysis.js";
import { pixelWeather } from "./pixel-weather.js";
import { desktop } from "./desktop.js";
import { uiScale } from "../ui/scale.js";
import { openChart } from "../ui/chart-view.js";
const NAMES = ["Brunei", "Cambodia", "Indonesia", "Laos", "Malaysia", "Myanmar", "Philippines", "Singapore", "Thailand", "Timor-Leste", "Vietnam"];
const LAB = {
  Brunei: [114.6, 5.9],
  Cambodia: [104.9, 12.6],
  Indonesia: [113.6, -1.4],
  Laos: [102.6, 19.6],
  Malaysia: [101.8, 4.6],
  Myanmar: [96.2, 21.4],
  Philippines: [122.4, 12.4],
  Singapore: [103.82, 1.35],
  Thailand: [101, 15.6],
  "Timor-Leste": [125.9, -8.8],
  Vietnam: [107, 14.6]
};
const LABPOS = { Brunei: [115.2, 6.4], Indonesia: [113.2, -0.4], Singapore: [104.5, 0.6], "Timor-Leste": [127.2, -9.4], Vietnam: [108.9, 15.2], Laos: [102.2, 19.9] };
const LAYERS = [
  {
    k: "ssl",
    short: "SEA LVL",
    name: "Sea level at the coast",
    src: "ECCO V4r4 · NASA PO.DAAC",
    unit: "mm",
    ud: "mm/dec",
    y0: 1992,
    y1: 2017,
    pal: "s",
    real: true
  },
  {
    k: "t2m",
    short: "TEMP",
    name: "Air temperature",
    src: "MERRA-2 · NASA POWER",
    unit: "°C",
    ud: "°C/dec",
    y0: 1981,
    y1: 2024,
    pal: "t",
    sd: 0.15,
    base: 27,
    amp: 1.2,
    s: [0.2, 0.22, 0.17, 0.24, 0.21, 0.23, 0.19, 0.245, 0.25, 0.14, 0.22],
    lock: "the regional panel (real 3-region values, not built yet)"
  },
  {
    k: "precip",
    short: "RAIN",
    name: "Rainfall",
    src: "MERRA-2 · NASA POWER",
    unit: "mm/mo",
    ud: "mm/mo/dec",
    y0: 1981,
    y1: 2024,
    pal: "w",
    sd: 22,
    base: 210,
    amp: 90,
    s: [6, -4, 3, -2, 8, -6, 12, 5, -3, -9, 4],
    lock: "the regional panel (real 3-region values, not built yet)"
  },
  {
    k: "tws",
    short: "WATER",
    name: "Water storage",
    src: "GRACE / GRACE-FO",
    unit: "cm",
    ud: "cm/dec",
    y0: 2003,
    y1: 2024,
    pal: "w",
    sd: 2.4,
    base: 0,
    amp: 8,
    gap: [2017, 2018],
    s: [-0.5, 1.8, -2.4, 0.6, -1.2, -1, 0.8, -0.3, 1.5, -0.4, 2.2],
    na: { Singapore: "No data. Too small for GRACE satellites.", Brunei: "No data. Too small for GRACE satellites.", "Timor-Leste": "No data. Too small for GRACE satellites." },
    lock: "the regional panel (real 3-region values, not built yet)"
  },
  {
    k: "sst",
    short: "SEA",
    name: "Sea surface temp.",
    src: "MUR SST · PO.DAAC",
    unit: "°C",
    ud: "°C/dec",
    y0: 2003,
    y1: 2024,
    pal: "t",
    sd: 0.12,
    base: 29,
    amp: 0.8,
    s: [0.18, 0.16, 0.2, 0.15, 0.21, 0.12, 0.23, 0.19, 0.17, 0.24, 0.2],
    na: { Laos: "No data. Laos has no coastline." },
    lock: "SST data (no real series in the Python pipeline yet)"
  },
  { k: "ndvi", name: "Vegetation (NDVI)", src: "MODIS Terra", y0: 2001, y1: 2024, lock: "CASE 002" },
  { k: "aod", name: "Aerosols (AOD)", src: "MERRA-2", y0: 1981, y1: 2024, lock: "CASE 003" }
];
const SSL_BINS = [30, 36, 42, 48];
const PAL = { s: ["#d8e6ee", "#9fd0e8", "#5aa6dd", "#2f6fc0", "#1c3d8c"], t: ["#1f4fa0", "#7fa8e8", "#c9c2b2", "#e9a93a", "#d94a36"], w: ["#8a5a2b", "#c9a46a", "#c9c2b2", "#7fc4a0", "#2f8f7a"] };
const GREY = "#56628a", VB = { world: [-4, -14, 368, 206], sea: [268, 58, 58, 52], idn: [273, 78, 50, 28] };
const st = { v: 0, city: -1, q: "", sat: false, dd: false, yr: null, more: false, f: 0, fx: true, c: -1, view: "world", map: null, data: null, rows: null, seen: {}, legend: -1, circ: { on: false, lat: null, lon: null, r: 150, v: "merra2:t2m", cells: null, out: null, msg: "" } };
let W = null, H = null;
const $ = (s) => W.querySelector(s);
const ns = "http://www.w3.org/2000/svg";
const sfx = (k) => SFX[k] && SFX[k]();
const talk = (lines, key) => {
  if (key && st.seen[key]) return;
  if (key) st.seen[key] = 1;
  say(lines);
};
function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = s * 1664525 + 1013904223 >>> 0;
    return s / 4294967296;
  };
}
function gauss(r) {
  let u = 0;
  while (!u) u = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}
function demoMonthly(li, ci) {
  const L = LAYERS[li], r = rng(1e3 * li + 37 * ci + 7), m = [];
  let a = 0;
  for (let y = L.y0; y <= L.y1; y++) {
    a = 0.45 * a + gauss(r) * L.sd * 0.89;
    for (let k = 0; k < 12; k++) {
      if (L.gap && (y > L.gap[0] || y === L.gap[0] && k >= 6) && (y < L.gap[1] || y === L.gap[1] && k < 5)) {
        m.push(null);
        continue;
      }
      m.push(L.base + L.amp * Math.sin((k - 3) / 12 * 2 * Math.PI) + L.s[ci] * (y + k / 12 - L.y0) / 10 + a + gauss(r) * L.sd * 0.8);
    }
  }
  return { y0: L.y0, m };
}
function monthly(li, ci) {
  const L = LAYERS[li], real = st.data && st.data[L.k] && st.data[L.k][NAMES[ci]];
  return real ? { ...real, real: true } : { ...demoMonthly(li, ci), real: false };
}
function annual(mo) {
  const out = { x: [], y: [] };
  for (let i = 0; i + 12 <= mo.m.length; i += 12) {
    const v = mo.m.slice(i, i + 12).filter((x) => x != null);
    if (v.length >= 10) {
      out.x.push(mo.y0 + i / 12);
      out.y.push(v.reduce((a, b) => a + b) / v.length);
    }
  }
  return out;
}
const ncdf = (z) => {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp(-z * z / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
};
function span(li) {
  if (LAYERS[li].real) return st.ssl ? st.ssl.period.slice() : [LAYERS[li].y0, LAYERS[li].y1];
  const L = LAYERS[li];
  let lo = L.y0, hi = L.y1;
  const d = st.data && st.data[L.k];
  if (d) {
    const any = Object.values(d)[0];
    if (any) {
      lo = any.y0;
      hi = any.y0 + Math.floor(any.m.length / 12) - 1;
    }
  }
  return [lo, hi];
}
function compute() {
  const li = st.v, L = LAYERS[li];
  if (L.real) {
    const rows = NAMES.map((n, ci) => ({ n, ci, na: "", neutral: true }));
    st.rows = rows;
    st.mxAbs = 1;
    st.span = st.ssl ? st.ssl.period.slice() : [L.y0, L.y1];
    return rows;
  }
  const [lo, hi0] = span(li);
  let y0 = lo, hi = hi0;
  if (st.yr) {
    y0 = Math.max(lo, Math.min(st.yr[0], hi0 - 9));
    hi = Math.min(hi0, Math.max(st.yr[1], y0 + 9));
  }
  const rows = NAMES.map((n, ci) => {
    if (L.na && L.na[n]) return { n, na: L.na[n] };
    const mo = monthly(li, ci), an = annual(mo), xs = [], ys = [];
    an.x.forEach((x, i) => {
      if (x >= y0 && x <= hi) {
        xs.push(x);
        ys.push(an.y[i]);
      }
    });
    const N = xs.length;
    if (N < 5) return { n, na: "Not enough years in this window." };
    const mx = xs.reduce((a2, b2) => a2 + b2) / N, my = ys.reduce((a2, b2) => a2 + b2) / N;
    let sxx = 0, sxy = 0;
    xs.forEach((x, i) => {
      sxx += (x - mx) ** 2;
      sxy += (x - mx) * (ys[i] - my);
    });
    const b = sxy / sxx, a = my - b * mx, res = ys.map((y, i) => y - a - b * xs[i]);
    let c0 = 0, c1 = 0;
    res.forEach((q, i) => {
      c0 += q * q;
      if (i) c1 += q * res[i - 1];
    });
    const r1 = Math.max(0, Math.min(0.95, c1 / c0)), neff = Math.max(3, N * (1 - r1) / (1 + r1));
    const sig = Math.sqrt(c0 / (N - 2)), se = sig / Math.sqrt(sxx) * Math.sqrt((N - 2) / Math.max(1, neff - 2));
    const p = 2 * (1 - ncdf(Math.abs(b / se)));
    const nstar = Math.pow(3.3 * sig / Math.max(1e-9, Math.abs(b)) * Math.sqrt((1 + r1) / (1 - r1)), 2 / 3);
    return { n, ci, xs, ys, N, b10: b * 10, se10: se * 10, a, b, r1, neff, p, nstar, real: mo.real, mo, y0, y1: hi };
  });
  const ok = rows.filter((r) => !r.na), ord = ok.slice().sort((p, q) => p.p - q.p);
  let run = 1;
  for (let q = ord.length - 1; q >= 0; q--) {
    run = Math.min(run, ord[q].p * ord.length / (q + 1));
    ord[q].padj = run;
  }
  const mxAbs = Math.max(...ok.map((r) => Math.abs(r.b10)), 1e-6);
  rows.forEach((r) => {
    if (r.na) return;
    r.det = r.padj < 0.05;
    r.sus = r.det && !!L.gap && r.y0 <= L.gap[0];
    if (r.sus) r.det = false;
    const z = r.b10 / mxAbs;
    r.bin = z < -0.5 ? 0 : z < -0.1 ? 1 : z <= 0.1 ? 2 : z <= 0.5 ? 3 : 4;
    r.col = r.det || r.sus ? PAL[L.pal][r.bin] : GREY;
  });
  st.rows = rows;
  st.mxAbs = mxAbs;
  st.span = [y0, hi];
  return rows;
}
const P = (lon, lat) => [lon + 180, 90 - lat];
function el(tag, attrs, parent) {
  const e = document.createElementNS(ns, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function buildSvg() {
  const svg = $("#rm-svg");
  svg.innerHTML = "";
  svg.setAttribute("viewBox", VB.world.join(" "));
  const defs = el("defs", {}, svg);
  const pat = el("pattern", { id: "rmHatch", width: 2.2, height: 2.2, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("rect", { width: 2.2, height: 2.2, fill: "#16204a" }, pat);
  el("rect", { width: 0.7, height: 2.2, fill: "#24326a" }, pat);
  const pat2 = el("pattern", { id: "rmNA", width: 1.2, height: 1.2, patternUnits: "userSpaceOnUse", patternTransform: "rotate(-45)" }, defs);
  el("rect", { width: 1.2, height: 1.2, fill: "#c9c2b2" }, pat2);
  el("rect", { width: 0.45, height: 1.2, fill: "#8b93ad" }, pat2);
  let g = "";
  for (let x = 0; x <= 360; x += 15) g += `M${x} -30V210`;
  for (let y = 0; y <= 180; y += 15) g += `M-20 ${y}H380`;
  el("path", { d: g, stroke: "#14255a", "stroke-width": 1, "vector-effect": "non-scaling-stroke", fill: "none" }, svg);
  const sg0 = el("g", { id: "rm-satg", style: "display:none" }, svg);
  el("image", { id: "rm-sat0", preserveAspectRatio: "none", class: "rm-satimg" }, sg0);
  el("image", { id: "rm-sat1", preserveAspectRatio: "none", class: "rm-satimg" }, sg0);
  const rest = el("path", { d: st.map.rest, class: "rm-rest", "stroke-width": 1, "vector-effect": "non-scaling-stroke" }, svg);
  rest.onclick = (e) => {
    if (!st.dragged) denied(e);
  };
  let tr = "";
  for (let lon = -180; lon <= 180; lon += 4) {
    const [x, y] = P(lon, 62 * Math.sin((lon - 104) / 180 * Math.PI));
    tr += (tr ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  }
  el("path", { d: tr, class: "rm-track", "stroke-width": 1.5, "vector-effect": "non-scaling-stroke" }, svg);
  const sat = el("g", { id: "rm-sat" }, svg);
  el("rect", { x: -1.5, y: -1.5, width: 3, height: 3, fill: "#7fd6e8", id: "rm-satdot" }, sat);
  el("text", { x: 3, y: -1.5, fill: "#7fd6e8", "font-family": "VT323,monospace", "font-size": 8, id: "rm-sattx" }, sat).textContent = "TERRA";
  el("animateMotion", { dur: "18s", repeatCount: "indefinite", path: tr }, sat);
  NAMES.forEach((n, ci) => {
    const p = el("path", { d: st.map.sea[n], class: "rm-c", fill: "#0b1534", stroke: "#06090f", "stroke-width": 1.2, "vector-effect": "non-scaling-stroke", "data-c": ci }, svg);
    p.onclick = () => {
      if (!st.dragged) pick(ci);
    };
    p.onmousemove = (e) => tip(e, ci);
    p.onmouseleave = () => tip(null);
  });
  if (st.prov) {
    const pg = el("g", { id: "rm-prov", "pointer-events": "none" }, svg);
    for (const [n, d] of Object.entries(st.prov.provinces)) el("path", { d, class: "rm-prv", "data-n": n, "vector-effect": "non-scaling-stroke" }, pg);
  }
  el("g", { id: "rm-gridg" }, svg);
  el("g", { id: "rm-circg", "pointer-events": "none" }, svg);
  const [sx, sy] = P(...LAB.Singapore);
  const sg = el("circle", { cx: sx, cy: sy, r: 0.5, class: "rm-c", "data-c": 7, stroke: "#ece6d6", "stroke-width": 2, "vector-effect": "non-scaling-stroke", fill: "#0b1534" }, svg);
  sg.onclick = () => {
    if (!st.dragged) pick(7);
  };
  sg.onmousemove = (e) => tip(e, 7);
  sg.onmouseleave = () => tip(null);
  const top = $("#rm-top");
  top.innerHTML = "";
  top.setAttribute("viewBox", VB.world.join(" "));
  el("g", { id: "rm-selg" }, top);
  const labs = el("g", { id: "rm-labs", opacity: 0 }, top);
  if (st.ssl) {
    const cg = el("g", { id: "rm-cities" }, svg);
    const cl = el("g", { id: "rm-clabs" }, top);
    st.ssl.cities.forEach((c, i) => {
      const [x, y] = P(c.lon, c.lat);
      const d = el("circle", { cx: x, cy: y, r: 0.3, class: "rm-city", "data-i": i, "stroke-width": 1.5, "vector-effect": "non-scaling-stroke" }, cg);
      d.onclick = (e) => {
        e.stopPropagation();
        if (!st.dragged) pickCity(i);
      };
      d.onmousemove = (e) => cityTip(e, i);
      d.onmouseleave = () => tip(null);
      const t = el("text", { x: x + 0.5, y: y - 0.35, class: "rm-clab", "data-i": i }, cl);
      t.textContent = c.name;
    });
  }
  NAMES.forEach((n) => {
    const [x, y] = P(...LABPOS[n] || LAB[n]);
    const t = el("text", { x, y, class: "rm-lab", "font-size": n === "Singapore" ? 0.95 : 1.25, "data-fs": n === "Singapore" ? 0.95 : 1.25, "stroke-width": 0.28 }, labs);
    t.textContent = n.toUpperCase();
  });
}
function paint(sweep) {
  const rows = compute(), L = LAYERS[st.v];
  W.querySelectorAll(".rm-c").forEach((p) => {
    const r = rows[+p.dataset.c];
    p.style.transitionDelay = sweep ? Math.round((LAB[r.n][0] - 92) * 14) + "ms" : "0ms";
    p.setAttribute("fill", r.neutral ? (r.n === "Indonesia" ? "#3d4c7c" : "#2b3762") : r.na ? "url(#rmNA)" : r.col);
    p.classList.toggle("na", !!r.na);
  });
  fades();
  hud();
  clearTimeout(paint.t);
  paint.t = setTimeout(placeFx, sweep ? 650 : 0);
  cities();
  const fmt = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(L.sd < 1 ? 2 : 1);
  if (L.real) $("#rm-leg").innerHTML = `<span>&lt;${SSL_BINS[0]}</span><span class="rm-bins">${PAL.s.map((c, i) => `<span data-b="${i}" style="background:${c}" title="${sslRange(i)} mm per decade"></span>`).join("")}</span><span>&gt;${SSL_BINS[3]} mm/dec</span><i class="rm-sw" style="background:${GREY}"></i>no clear trend<i class="rm-sw rm-sw-in"></i>inland`;
  else $("#rm-leg").innerHTML = `<span>${fmt(-st.mxAbs)}</span><span class="rm-bins">${PAL[L.pal].map((c, i) => `<span data-b="${i}" style="background:${c}" title="${["strong fall", "fall", "flat", "rise", "strong rise"][i]}"></span>`).join("")}</span><span>${fmt(st.mxAbs)} ${L.ud}</span><i class="rm-sw" style="background:${GREY}"></i>no trend<i class="rm-sw" style="background:repeating-linear-gradient(45deg,#c9c2b2 0 3px,#8b93ad 3px 5px)"></i>no data`;
  W.querySelectorAll(".rm-bins span").forEach((b) => {
    b.onmouseenter = () => {
      st.legend = +b.dataset.b;
      fades();
      placeFx();
    };
    b.onmouseleave = () => {
      st.legend = -1;
      fades();
      placeFx();
    };
  });
  toolbar();
  card();
}
function sslBin(v) {
  let b = 0;
  while (b < SSL_BINS.length && v >= SSL_BINS[b]) b++;
  return b;
}
function sslRange(i) {
  return i === 0 ? `under ${SSL_BINS[0]}` : i === SSL_BINS.length ? `${SSL_BINS[i - 1]} or more` : `${SSL_BINS[i - 1]} to ${SSL_BINS[i]}`;
}
function cityState(c) {
  if (!c.coastal || c.trend_mm_per_decade == null) return "inland";
  return c.significant ? "sig" : "ns";
}
function cities() {
  if (!st.ssl) return;
  const real = LAYERS[st.v].real;
  W.querySelector("#rm-cities").classList.toggle("off", !real && !zoomedIn());
  st.ssl.cities.forEach((c, i) => {
    const d = W.querySelector(`.rm-city[data-i="${i}"]`), k = cityState(c);
    let fill = "#ece6d6";
    if (real) fill = k === "sig" ? PAL.s[sslBin(c.trend_mm_per_decade)] : k === "ns" ? GREY : "#0b1534";
    d.setAttribute("fill", fill);
    d.setAttribute("stroke", real && k === "inland" ? "#8b93ad" : "#06090f");
    d.classList.toggle("cap", c.capital);
    d.classList.toggle("on", i === st.city);
  });
  cityFades();
  cityLabels();
  drawGrid();
}
const KM_DEG = 111.32;
function drawGrid() {
  const g = W.querySelector("#rm-gridg");
  if (!g) return;
  g.innerHTML = "";
  const c = st.ssl && st.city >= 0 ? st.ssl.cities[st.city] : null;
  if (!c || !c.grid || !LAYERS[st.v].real) return;
  const step = st.ssl.grid.cell_deg, R = st.ssl.grid.radius_km, h = step / 2;
  c.grid.forEach((q) => {
    const x = q.lon + 180 - h, y = 90 - q.lat - h;
    const fill = q.ocean && q.trend_mm_per_decade != null ? PAL.s[sslBin(q.trend_mm_per_decade)] : "none";
    const r = el("rect", { x, y, width: step, height: step, fill, "fill-opacity": q.used ? 0.92 : 0.45, "pointer-events": "all", class: "rm-cell" + (q.used ? " used" : "") + (q.ocean ? "" : " land"), "vector-effect": "non-scaling-stroke", "shape-rendering": "crispEdges" }, g);
    r.onmousemove = (e) => cellTip(e, c, q);
    r.onmouseleave = () => tip(null);
    if (q.ocean && q.trend_mm_per_decade != null) {
      const t = el("text", { x: x + h, y: y + h + step * 0.08, class: "rm-cellv" + (q.used ? " used" : ""), "font-size": (step * 0.24).toFixed(3) }, g);
      t.textContent = (q.trend_mm_per_decade >= 0 ? "+" : "−") + Math.abs(q.trend_mm_per_decade).toFixed(0);
    }
  });
  const [cx, cy] = P(c.lon, c.lat), ry = R / KM_DEG, rx = ry / Math.cos(c.lat * Math.PI / 180);
  el("ellipse", { cx, cy, rx, ry, class: "rm-radius", "vector-effect": "non-scaling-stroke" }, g);
  const used = c.grid.filter((q) => q.used).length;
  const cap = el("text", { x: cx, y: cy + ry + 0.22, class: "rm-gridcap", "font-size": 0.17 }, g);
  cap.textContent = `${used} OF ${c.grid.length} CELLS USED · CENTRES WITHIN ${R} KM`;
}
function cellTip(e, c, q) {
  const t = $("#rm-tip"), box = $("#rm-mapc").getBoundingClientRect(), ll = (v, p, n) => `${Math.abs(v).toFixed(2)}°${v >= 0 ? p : n}`;
  const val = q.ocean && q.trend_mm_per_decade != null ? `<b style="font-weight:400">${q.trend_mm_per_decade >= 0 ? "+" : "−"}${Math.abs(q.trend_mm_per_decade).toFixed(1)} mm/dec</b>` : '<span class="dim">land · no sea data</span>';
  t.innerHTML = `CELL ${ll(q.lat, "N", "S")} ${ll(q.lon, "E", "W")} ${val} <span class="dim">· ${Math.round(q.km)} km · ${q.used ? `used for ${c.name}` : "not used"}</span>`;
  t.style.display = "block";
  const z = uiScale;
  t.style.left = Math.min((e.clientX - box.left) / z + 14, box.width / z - t.offsetWidth - 6) + "px";
  t.style.top = (e.clientY - box.top) / z + 16 + "px";
}
const GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";
const SAT_LAYERS = ["BlueMarble_NextGeneration", "BlueMarble_ShadedRelief_Bathymetry"];
const SAT_BASE = [88, -16, 148, 32];
function satUrl(b, w, li) {
  const h = Math.max(16, Math.round(w * (b[3] - b[1]) / (b[2] - b[0])));
  return [`${GIBS}?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS=${SAT_LAYERS[li]}&STYLES=&SRS=EPSG:4326&BBOX=${b.map((v) => v.toFixed(3)).join(",")}&WIDTH=${w}&HEIGHT=${h}&FORMAT=image/jpeg`, h];
}
function satImage(img, b, w, li = 0) {
  const [url] = satUrl(b, w, li);
  if (img.dataset.u === url) return;
  img.dataset.u = url;
  Object.entries({ x: b[0] + 180, y: 90 - b[3], width: b[2] - b[0], height: b[3] - b[1] }).forEach(([k, v]) => img.setAttribute(k, v));
  img.style.opacity = 0;
  img.onload = () => {
    img.style.opacity = 1;
    satStatus(true);
  };
  img.onerror = () => {
    if (li + 1 < SAT_LAYERS.length) {
      img.dataset.u = "";
      satImage(img, b, w, li + 1);
    } else satStatus(false);
  };
  img.setAttribute("href", url);
}
function satStatus(ok) {
  const chip = W && W.querySelector("[data-sat]");
  if (!chip || !st.sat) return;
  chip.classList.toggle("bad", !ok);
  chip.title = ok ? "NASA GIBS Blue Marble imagery" : "Satellite imagery needs internet (NASA GIBS). Offline: map only.";
}
function satRefresh() {
  const g = W && W.querySelector("#rm-satg");
  if (!g) return;
  g.style.display = st.sat ? "" : "none";
  $("#rm-mapc").classList.toggle("sat", st.sat);
  if (!st.sat) return;
  satImage(W.querySelector("#rm-sat0"), SAT_BASE, 1024);
  const vb = st.vb, d = W.querySelector("#rm-sat1");
  if (!vb || st.view === "world" || vb[2] > 24) {
    d.style.display = "none";
    return;
  }
  d.style.display = "";
  const pad = vb[2] * 0.25, b = [vb[0] - 180 - pad, 90 - vb[1] - vb[3] - pad, vb[0] - 180 + vb[2] + pad, 90 - vb[1] + pad];
  const q = Math.pow(2, Math.ceil(Math.log2(vb[2] * 1.5)));
  const snap = (v) => Math.round(v / (q / 8)) * (q / 8);
  satImage(d, [snap(b[0]), snap(b[1]), snap(b[0]) + q, snap(b[1]) + q * (b[3] - b[1]) / (b[2] - b[0])], 512);
}
function zoomedIn() {
  return st.view !== "world" && st.vb && st.vb[2] <= 34;
}
function cityFades() {
  if (!st.ssl || !LAYERS[st.v].real) return;
  st.ssl.cities.forEach((c, i) => {
    const k = cityState(c), d = W.querySelector(`.rm-city[data-i="${i}"]`);
    const hideF = st.f === 1 ? k !== "sig" : st.f === 2 ? k === "sig" : false;
    const hideL = st.legend >= 0 && (k !== "sig" || sslBin(c.trend_mm_per_decade) !== st.legend);
    d.classList.toggle("fade", hideF || hideL);
  });
}
function cityLabels() {
  if (!st.ssl || !st.vb) return;
  const w = st.vb[2], ls = Math.min(1, w / VB.sea[2]);
  st.ssl.cities.forEach((c, i) => {
    const t = W.querySelector(`.rm-clab[data-i="${i}"]`);
    const show = st.view !== "world" && (i === st.city || (c.capital && w <= 30) || w <= 13);
    t.style.display = show ? "" : "none";
    if (show) {
      t.setAttribute("font-size", (0.85 * ls).toFixed(3));
      t.setAttribute("stroke-width", (0.24 * ls).toFixed(3));
      t.setAttribute("x", (c.lon + 180 + 0.55 * ls).toFixed(3));
      t.setAttribute("y", (90 - c.lat - 0.45 * ls).toFixed(3));
    }
  });
}
function cityTip(e, i) {
  const c = st.ssl.cities[i], k = cityState(c), t = $("#rm-tip"), box = $("#rm-mapc").getBoundingClientRect();
  const val = k === "inland" ? '<span class="dim">· inland</span>' : `<b style="font-weight:400;color:${k === "sig" ? "var(--ink)" : "#5b6b8f"}">${c.trend_mm_per_year >= 0 ? "+" : "−"}${Math.abs(c.trend_mm_per_year).toFixed(1)} mm/yr</b>${k === "sig" ? "" : ' <span class="dim">· no clear trend</span>'}`;
  t.innerHTML = `${c.name.toUpperCase()} <span class="dim">${c.province}</span> ${LAYERS[st.v].real ? val : ""}`;
  t.style.display = "block";
  const z = uiScale;
  t.style.left = Math.min((e.clientX - box.left) / z + 14, box.width / z - t.offsetWidth - 6) + "px";
  t.style.top = (e.clientY - box.top) / z + 16 + "px";
}
function pickCity(i, fly) {
  const c = st.ssl.cities[i];
  if (!LAYERS[st.v].real) {
    st.v = LAYERS.findIndex((L) => L.real);
    st.yr = null;
  }
  st.city = i;
  st.c = -1;
  const k = cityState(c);
  sfx(k === "inland" ? "err" : "select");
  if (k === "sig") talk([`${c.name}. Up ${c.trend_mm_per_year.toFixed(1)} mm a year since ${st.ssl.period[0]}. That adds up.`, "The yellow squares are the ocean cells I averaged. Nothing hidden."], "sig");
  else if (k === "ns") talk([`${c.name}. The sea climbs fast here too.`, "But it swings so much from year to year that I can’t prove it yet. That’s a different answer from no."], "ns");
  else talk(["Inland. The ocean data can’t speak for this one.", "I’m not inventing a number to fill the gap."], "inland");
  if (fly) flyTo(cityBox(c));
  paint(false);
}
function cityBox(c) {
  const w = c.grid ? 5.6 : 9, h = w * VB.idn[3] / VB.idn[2], x = c.lon + 180, y = 90 - c.lat;
  return [x - w * 0.42, y - h / 2, w, h];
}
function boxOf(d) {
  const n = d.match(/-?\d+(\.\d+)?/g).map(Number);
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (let i = 0; i + 1 < n.length; i += 2) {
    x0 = Math.min(x0, n[i]);
    x1 = Math.max(x1, n[i]);
    y0 = Math.min(y0, n[i + 1]);
    y1 = Math.max(y1, n[i + 1]);
  }
  const pad = Math.max(1, (x1 - x0) * 0.15);
  return [x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad];
}
function flyTo(box) {
  zoom(box);
}
function cityCard(box) {
  const c = st.ssl.cities[st.city], k = cityState(c), m = st.ssl;
  const selg = W.querySelector("#rm-selg");
  const [px, py] = P(c.lon, c.lat);
  if (!c.grid) el("circle", { cx: px, cy: py, r: (0.9 * Math.min(1, (st.vb || VB.sea)[2] / VB.sea[2])).toFixed(3), class: "rm-pulse", "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, selg);
  const head = `<div class="hd"><h3>${c.name.toUpperCase()}</h3><button class="x" id="rm-close" aria-label="Close">×</button></div>
    <div class="sub">${c.province.toUpperCase()} · SEA LEVEL · ${m.period[0]}-${m.period[1]}</div>`;
  if (k === "inland") {
    const nc = c.nearest_coastal, ni = nc && nc.km <= 200 ? m.cities.findIndex((x) => x.name === nc.name) : -1;
    box.innerHTML = head + `<div style="margin-top:10px;font-size:20px;line-height:1.15">${c.note}</div>
      <div class="rm-note">Sea level is measured in the ocean, so it only tells you about cities on the coast. Rivers can still carry high tides inland, but this data cannot show that.</div>
      ${ni >= 0 ? `<button class="obtn" id="rm-near" style="margin-top:8px">SEE ${nc.name.toUpperCase()} · ${nc.km} KM ▸</button>` : ""}`;
    box.querySelector("#rm-close").onclick = closeCard;
    if (ni >= 0) box.querySelector("#rm-near").onclick = () => pickCity(ni, true);
    return;
  }
  const f = (v, d = 1) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);
  const pts = c.annual_anomaly_mm.filter((q) => q[1] != null), ln = c.line_mm;
  const vals = pts.map((q) => q[1]).concat(ln.flatMap((q) => [q[2], q[3]]));
  const lo = Math.min(...vals), hi = Math.max(...vals), Wd = 250, Hd = 70;
  const X = (yr) => 6 + (yr - m.period[0]) / (m.period[1] - m.period[0]) * (Wd - 12), Y = (v) => Hd - 6 - (v - lo) / (hi - lo || 1) * (Hd - 12);
  const line = pts.map((q, i) => (i ? "L" : "M") + X(q[0]).toFixed(1) + " " + Y(q[1]).toFixed(1)).join("");
  const band = ln.length ? "M" + ln.map((q) => X(q[0]).toFixed(1) + " " + Y(q[3]).toFixed(1)).join("L") + "L" + ln.slice().reverse().map((q) => X(q[0]).toFixed(1) + " " + Y(q[2]).toFixed(1)).join("L") + "Z" : "";
  const fit = ln.length ? `M${X(ln[0][0])} ${Y(ln[0][1])}L${X(ln[ln.length - 1][0])} ${Y(ln[ln.length - 1][1])}` : "";
  const sig = k === "sig";
  box.innerHTML = head + `
    <div class="big"><b>${f(c.trend_mm_per_year)}</b><span>mm a year</span></div>
    <span class="rm-verd" style="background:${sig ? "var(--grn)" : "var(--mus)"}">${sig ? "TREND DETECTED" : "NO CLEAR TREND"}</span>
    <svg class="rm-spark zoomable" id="rm-zoom" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none" role="button" tabindex="0" aria-label="Open the full chart">
      <path d="${band}" fill="#e9a93a" fill-opacity=".18"/><path class="ln" d="${line}"/><path class="tr" d="${fit}"/></svg>
    <div class="zoom-hint">${m.period[0]} · CLICK CHART TO ENLARGE · ${m.period[1]}</div>
    <table class="rm-tab">
      <tr><td>Per decade</td><td>${f(c.trend_mm_per_decade)} mm</td></tr>
      <tr><td>95% range</td><td>${f(c.ci_mm_per_decade[0], 0)} .. ${f(c.ci_mm_per_decade[1], 0)} mm</td></tr>
      ${sig ? "<tr><td>Risk</td><td>Coastal flooding</td></tr>" : ""}
      <tr><td>Grid cells</td><td>${c.cells} used · ${Math.round(c.nearest_cell_km)} km</td></tr>
    </table>
    <button class="rm-more" id="rm-more" aria-expanded="${st.more}">${st.more ? "▾ Fewer stats" : "▸ More stats"}</button>
    ${st.more ? `<table class="rm-tab">
      <tr><td>p (OLS)</td><td>${c.p < 1e-3 ? "<.001" : c.p.toFixed(3)}</td></tr>
      <tr><td>p adjusted</td><td>${c.p_adjusted < 1e-3 ? "<.001" : c.p_adjusted.toFixed(3)}</td></tr>
      <tr><td>Sen's slope</td><td>${f(c.sen_mm_per_decade)} mm/dec</td></tr>
      <tr><td>MK p (unadj.)</td><td>${c.mk_p_unadjusted < 1e-3 ? "<.001" : c.mk_p_unadjusted.toFixed(3)}</td></tr>
      <tr><td>Ocean cells</td><td>${c.cells} · ${Math.round(c.nearest_cell_km)} km</td></tr></table>
      <div class="rm-note">${c.sentence} Adjusted p accounts for testing ${m.tests} coastal cities at once.${c.warnings.length ? " " + c.warnings.join(" ") : ""}</div>` : ""}
    <div class="rm-note">${m.caveat} ${m.grid ? m.grid.note : ""}</div>
    <div class="rm-note">NASA DATA · ${m.dataset}</div>
    <button class="obtn" id="rm-case">INVESTIGATE AS A CASE ▸</button>`;
  box.querySelector("#rm-close").onclick = closeCard;
  const zc = box.querySelector("#rm-zoom");
  zc.onclick = () => cityChart(c);
  zc.onkeydown = (e) => e.key === "Enter" && cityChart(c);
  box.querySelector("#rm-case").onclick = () => {
    sfx("chime");
    desktop.startCase({ v: "ssl", r: c.case, y0: m.period[0], y1: m.period[1] });
  };
  box.querySelector("#rm-more").onclick = () => {
    st.more = !st.more;
    sfx("select");
    card();
  };
}
function cityChart(c) {
  const m = st.ssl, f = (v, d = 1) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d), p = (v) => v < 1e-3 ? "< 0.001" : v.toFixed(3);
  sfx("select");
  openChart({
    title: `${c.name.toUpperCase()} · SEA LEVEL ${m.period[0]}-${m.period[1]}`,
    sub: `${c.province.toUpperCase()} · ${c.region.toUpperCase()} · YEARLY AVERAGE, SEASONS REMOVED`,
    unit: "mm vs average",
    series: c.annual_anomaly_mm,
    seriesLabel: "Yearly sea level vs the 1992-2017 average",
    fit: c.line_mm.map((q) => [q[0], q[1]]),
    fitLabel: `Trend ${f(c.trend_mm_per_decade)} mm per decade`,
    band: c.line_mm.map((q) => [q[0], q[2], q[3]]),
    bandLabel: "95% range of the trend line",
    zero: true,
    stats: [
      ["TREND", `${f(c.trend_mm_per_year)} mm / year`],
      ["95% RANGE", `${f(c.ci_mm_per_decade[0], 0)} to ${f(c.ci_mm_per_decade[1], 0)} mm / decade`],
      ["OVER THE RECORD", `${f(c.trend_mm_per_year * (m.period[1] - m.period[0] + 1), 0)} mm in ${m.period[1] - m.period[0] + 1} years`],
      ["SEN'S SLOPE", `${f(c.sen_mm_per_decade)} mm / decade`],
      ["P (ADJUSTED)", `${p(c.p_adjusted)} · ${m.tests} cities tested`],
      ["VERDICT", cityState(c) === "sig" ? "TREND DETECTED" : "NO CLEAR TREND YET"]
    ],
    notes: [c.sentence, `Built from ${c.cells} ECCO ocean cells (0.5°) within ${m.grid ? m.grid.radius_km : 120} km; the nearest is ${Math.round(c.nearest_cell_km)} km away.`, m.caveat],
    source: m.dataset,
    dp: 1
  });
}
const FXTXT = { rain: () => "Heavier rain", storm: () => "Stronger storms", drought: (L) => L.k === "t2m" ? "Heat, drought" : "Drought" };
function fxOf(r) {
  if (!r || r.na || r.neutral || !(r.det || r.sus)) return null;
  const k = LAYERS[st.v].k, b = r.bin;
  if (k === "t2m") return b === 4 ? "drought" : null;
  if (k === "precip") return b === 4 ? "storm" : b === 3 ? "rain" : b <= 1 ? "drought" : null;
  if (k === "tws") return b >= 3 ? "rain" : b <= 1 ? "drought" : null;
  if (k === "sst") return b === 4 ? "storm" : null;
  return null;
}
function placeFx() {
  clearInterval(placeFx.iv);
  const cv = W && W.querySelector("#rm-fxc");
  if (!cv) return;
  if (!st.fx || st.view === "world" || !st.rows || zoom.busy) {
    cv.style.display = "none";
    return;
  }
  const svg = $("#rm-svg"), z = uiScale, rb = $("#rm-mapc").getBoundingClientRect(), sc = svg.getScreenCTM();
  if (!sc || !rb.width) return;
  const box = { left: rb.left / z, top: rb.top / z, width: rb.width / z, height: rb.height / z }, ctm = { a: sc.a / z, e: sc.e / z, f: sc.f / z };
  const cell = 3, GW = Math.ceil(box.width / cell), GH = Math.ceil(box.height / cell);
  cv.width = GW;
  cv.height = GH;
  Object.assign(cv.style, { display: "block", width: GW * cell + "px", height: GH * cell + "px" });
  const k = ctm.a / cell, ox = (ctm.e - box.left) / cell, oy = (ctm.f - box.top) / cell;
  const off = document.createElement("canvas");
  off.width = GW;
  off.height = GH;
  const o = off.getContext("2d", { willReadFrequently: true });
  const mask = (d) => {
    o.setTransform(1, 0, 0, 1, 0, 0);
    o.clearRect(0, 0, GW, GH);
    o.setTransform(k, 0, 0, k, ox, oy);
    o.fill(new Path2D(d));
    const a = o.getImageData(0, 0, GW, GH).data, m = new Uint8Array(GW * GH);
    for (let i = 0; i < m.length; i++) m[i] = a[i * 4 + 3] > 60;
    return m;
  };
  const toCell = ([lon, lat]) => [Math.floor((lon + 180) * k + ox), Math.floor((90 - lat) * k + oy)];
  const shown = (r) => {
    const p = W.querySelector(`path.rm-c[data-c="${r.ci}"]`);
    return st.f !== 2 && !(p && p.classList.contains("fade"));
  };
  const items = st.rows.filter((r) => fxOf(r) && shown(r));
  const dry = items.filter((r) => fxOf(r) === "drought");
  const dst = dry.length ? pixelWeather.drought(dry.map((r) => mask(st.map.sea[r.n])), GW, GH) : null;
  const sp = [];
  items.filter((r) => fxOf(r) !== "drought").sort((a, b) => Math.abs(b.b10) - Math.abs(a.b10)).forEach((r) => {
    const [ax, ay] = toCell(st.map.anchor && st.map.anchor[r.n] || LAB[r.n]);
    if (sp.length >= 6 || sp.some((q) => Math.hypot(q.ax - ax, q.ay - ay) < 15)) return;
    sp.push({ t: fxOf(r), ax, ay });
  });
  const sel = st.city >= 0 && st.ssl ? st.ssl.cities[st.city] : null;
  const inRing = (c) => sel && sel.grid && Math.hypot((c.lon - sel.lon) * Math.cos(sel.lat * Math.PI / 180), c.lat - sel.lat) * KM_DEG < st.ssl.grid.radius_km * 1.6;
  if (LAYERS[st.v].real && st.ssl) {
    st.ssl.cities.map((c, i) => [c, i]).filter(([c, i]) => i !== st.city && !inRing(c) && cityState(c) === "sig" && !W.querySelector(`.rm-city[data-i="${i}"]`).classList.contains("fade")).sort((a, b) => b[0].population - a[0].population).forEach(([c]) => {
      const [ax, ay] = toCell([c.lon, c.lat]);
      if (ax < 0 || ay < 0 || ax >= GW || ay >= GH) return;
      if (sp.length >= 8 || sp.some((q) => Math.abs(q.ax - ax) < 17 && Math.abs(q.ay - ay) < 20)) return;
      sp.push({ t: "flood", ax, ay: ay - 3 });
    });
  }
  const g = cv.getContext("2d"), img = g.createImageData(GW, GH);
  let f = 0;
  const tick = () => {
    if (!cv.isConnected) {
      clearInterval(placeFx.iv);
      return;
    }
    img.data.fill(0);
    if (dst) pixelWeather.paintDrought(img, dst, f);
    sp.forEach((q) => pixelWeather.paintSprite(img, GW, GH, pixelWeather[q.t](f), q.ax, q.ay));
    g.putImageData(img, 0, 0);
    f++;
  };
  tick();
  placeFx.iv = setInterval(tick, 125);
}
function fades() {
  cityFades();
  W.querySelectorAll(".rm-c").forEach((p) => {
    const r = st.rows[+p.dataset.c];
    const hideF = st.f === 1 ? !(r.det || r.sus) : st.f === 2 ? !!r.na || r.det || r.sus : false;
    p.classList.toggle("fade", hideF || st.legend >= 0 && (!!r.na || !r.det || r.bin !== st.legend));
  });
}
function hud() {
  if (LAYERS[st.v].real && st.ssl) {
    const cs = st.ssl.cities, tested = cs.filter((c) => c.trend_mm_per_decade != null), sig = tested.filter((c) => c.significant).length;
    $("#rm-hud").innerHTML = `SEA LEVEL · <b>${sig} of ${tested.length}</b> coastal cities rising clearly · ${st.ssl.period[0]}-${st.ssl.period[1]}`;
    return;
  }
  const rows = st.rows, L = LAYERS[st.v], det = rows.filter((r) => r.det).length, sus = rows.filter((r) => r.sus).length, nn = rows.filter((r) => !r.na).length;
  $("#rm-hud").innerHTML = `${L.name.toUpperCase()} · <b>${det} of ${nn}</b> clear${sus ? ` · <span class="c">${sus} caution</span>` : ""}`;
}
function toolbar() {
  const [lo, hi] = span(st.v), locked = LAYERS.filter((L) => L.lock);
  $("#rm-bar").innerHTML = `<div class="rm-seg" role="group" aria-label="Layer">${LAYERS.map((L, i) => L.lock ? "" : `<button data-l="${i}" class="${i === st.v ? "on" : ""}" title="${L.name} · ${L.src}"><i style="background:${PAL[L.pal][4]}"></i>${L.short}</button>`).join("")}<button class="lk" data-lock title="${locked.map((L) => `${L.name}: locked until ${L.lock}`).join("\n")}">+${locked.length} LOCKED</button></div>
    ${LAYERS[st.v].real ? `<span class="rm-fixed" title="Trends are computed once over the full ECCO record by the Python core">FULL RECORD</span>` : `<div class="rm-range" id="rm-range" role="group" aria-label="Years"><div class="tr"></div><div class="fl"></div><button class="hd" data-h="0" aria-label="Start year"></button><button class="hd" data-h="1" aria-label="End year"></button></div>`}
    <span class="rm-yrs" id="rm-yrs">${LAYERS[st.v].real ? `${st.span[0]}-${st.span[1]}` : ""}</span>
    <div class="rm-dd" id="rm-dd"><button class="rm-ddb${st.city >= 0 ? " on" : ""}" id="rm-ddb" aria-haspopup="listbox" aria-expanded="false"><i class="pin"></i><span>${st.city >= 0 && st.ssl ? st.ssl.cities[st.city].name.toUpperCase() : "CITIES"}</span><b>▾</b></button>
      <div class="rm-ddp" id="rm-ddp" hidden><input id="rm-q" type="search" placeholder="Type a city or province" autocomplete="off" aria-label="Search a city or province" value="${st.q.replace(/"/g, "&quot;")}"><div class="rm-res" id="rm-res" role="listbox"></div></div></div>
    <div class="rm-seg" role="group" aria-label="Show">${["ALL", "TREND", "NONE"].map((t, i) => `<button data-f="${i}" class="${i === st.f ? "ink" : ""}">${t}</button>`).join("")}</div>
    <button class="rm-chip${st.fx ? " on" : ""}" data-fx title="Weather effects">FX ${st.fx ? "ON" : "OFF"}</button>
    <button class="rm-chip${st.circ.on ? " on" : ""}" data-circ title="Draw a circle of grid cells and test it">CIRCLE ${st.circ.on ? "ON" : "OFF"}</button>
    <button class="rm-chip${st.sat ? " on" : ""}" data-sat title="NASA GIBS Blue Marble imagery">SAT ${st.sat ? "ON" : "OFF"}</button>`;
  W.querySelectorAll("[data-l]").forEach((b) => b.onclick = () => {
    st.v = +b.dataset.l;
    if (!LAYERS[st.v].real) talk(["Careful. This layer is sample data. It shows how the map works, not what’s real.", "Real temperature and rain are in CASES."], "sample");
    st.yr = null;
    if (!LAYERS[st.v].real) st.city = -1;
    st.c = -1;
    sfx("select");
    paint(true);
  });
  W.querySelector("[data-lock]").onclick = () => sfx("err");
  W.querySelectorAll("[data-f]").forEach((b) => b.onclick = () => {
    st.f = +b.dataset.f;
    sfx("select");
    W.querySelectorAll("[data-f]").forEach((x) => x.classList.toggle("ink", x === b));
    fades();
    placeFx();
  });
  W.querySelector("[data-fx]").onclick = (e) => {
    st.fx = !st.fx;
    sfx("select");
    e.currentTarget.classList.toggle("on", st.fx);
    e.currentTarget.textContent = `FX ${st.fx ? "ON" : "OFF"}`;
    placeFx();
  };
  W.querySelector("[data-sat]").onclick = (e) => {
    st.sat = !st.sat;
    sfx("select");
    e.currentTarget.classList.toggle("on", st.sat);
    e.currentTarget.classList.remove("bad");
    e.currentTarget.textContent = `SAT ${st.sat ? "ON" : "OFF"}`;
    satRefresh();
  };
  W.querySelector("[data-circ]").onclick = () => circleToggle(!st.circ.on);
  if (!LAYERS[st.v].real) bindRange(lo, hi);
  bindSearch();
}
function bindSearch() {
  const q = $("#rm-q"), res = $("#rm-res"), btn = $("#rm-ddb"), pnl = $("#rm-ddp");
  let items = [], hi = 0;
  const norm = (x) => x.toLowerCase().normalize("NFD").replace(/[^a-z0-9 ]/g, "");
  const val = (c) => {
    const k = cityState(c);
    if (k === "inland") return ["inland", "#0b1534"];
    const v = `${c.trend_mm_per_year >= 0 ? "+" : "−"}${Math.abs(c.trend_mm_per_year).toFixed(1)} mm/yr`;
    return [k === "sig" ? v : v + " ·?", k === "sig" ? PAL.s[sslBin(c.trend_mm_per_decade)] : GREY];
  };
  const row = (x, k) => {
    if (x.t === "h") return `<div class="grp">${x.name.toUpperCase()} <small>${x.n}</small></div>`;
    if (x.t === "p") return `<button role="option" data-k="${k}"><span><i class="sw prov"></i>${x.name}</span><small>province</small></button>`;
    const c = st.ssl.cities[x.i], [v, col] = val(c);
    return `<button role="option" data-k="${k}" class="${x.i === st.city ? "cur" : ""}" title="${c.province}"><span><i class="sw" style="background:${col}"></i>${c.name}</span><small>${v}</small></button>`;
  };
  const render = () => {
    if (!st.ssl) return;
    const v = norm(q.value.trim());
    st.q = q.value;
    const all = st.ssl.cities.map((c, i) => ({ t: "c", i, n: norm(c.name), reg: c.region || c.province, pop: c.population }));
    let list;
    if (!v) {
      const by = {};
      all.forEach((x) => (by[x.reg] = by[x.reg] || []).push(x));
      list = Object.keys(by).flatMap((p) => [{ t: "h", name: p, n: by[p].length }, ...by[p]]);
    } else {
      const ps = st.prov ? Object.keys(st.prov.provinces).map((name) => ({ t: "p", name, n: norm(name), pop: 0 })) : [];
      const score = (x) => x.n.startsWith(v) ? 0 : x.n.split(" ").some((w) => w.startsWith(v)) ? 1 : x.n.includes(v) ? 2 : 9;
      list = all.concat(ps).map((x) => [score(x), x]).filter((a) => a[0] < 9).sort((a, b) => a[0] - b[0] || b[1].pop - a[1].pop).slice(0, 12).map((a) => a[1]);
    }
    items = list;
    const picks = list.map((x, k) => x.t === "h" ? -1 : k).filter((k) => k >= 0);
    hi = v ? picks[0] ?? -1 : -1;
    res.innerHTML = list.length ? list.map(row).join("") : '<div class="none">No city found</div>';
    mark();
    res.querySelectorAll("[data-k]").forEach((b) => b.onmousedown = (e) => {
      e.preventDefault();
      go(items[+b.dataset.k]);
    });
  };
  const mark = () => {
    res.querySelectorAll("[data-k]").forEach((b) => b.classList.toggle("hi", +b.dataset.k === hi));
    const h = res.querySelector(".hi");
    if (h) h.scrollIntoView({ block: "nearest" });
  };
  const show = (on) => {
    st.dd = on;
    pnl.hidden = !on;
    btn.setAttribute("aria-expanded", on);
    btn.classList.toggle("open", on);
    if (on) {
      render();
      q.focus();
      const cur = res.querySelector(".cur");
      if (cur && !q.value) cur.scrollIntoView({ block: "center" });
    }
  };
  const go = (x) => {
    if (!x || x.t === "h") return;
    q.value = st.q = "";
    show(false);
    if (x.t === "c") pickCity(x.i, true);
    else {
      sfx("select");
      st.city = -1;
      flyTo(boxOf(st.prov.provinces[x.name]));
      paint(false);
    }
  };
  btn.onclick = () => {
    sfx("select");
    show(pnl.hidden);
  };
  q.oninput = render;
  q.onkeydown = (e) => {
    const ks = items.map((x, k) => x.t === "h" ? -1 : k).filter((k) => k >= 0);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const at = ks.indexOf(hi);
      hi = ks[Math.max(0, Math.min(ks.length - 1, at < 0 ? 0 : at + (e.key === "ArrowDown" ? 1 : -1)))];
      mark();
    } else if (e.key === "Enter") go(items[hi]);
    else if (e.key === "Escape") {
      if (q.value) {
        q.value = "";
        render();
      } else show(false);
    }
  };
  if (!bindSearch.doc) {
    bindSearch.doc = true;
    document.addEventListener("pointerdown", (e) => {
      const dd = W && W.querySelector("#rm-dd");
      if (st.dd && dd && !dd.contains(e.target)) {
        st.dd = false;
        dd.querySelector("#rm-ddp").hidden = true;
        dd.querySelector("#rm-ddb").classList.remove("open");
      }
    });
  }
  if (st.dd) show(true);
}
function bindRange(lo, hi) {
  const box = $("#rm-range"), hs = box.querySelectorAll(".hd"), fl = box.querySelector(".fl"), lab = $("#rm-yrs");
  const val = st.span.slice(), MIN = 9;
  const pct = (y) => 7 + (hi > lo ? (y - lo) / (hi - lo) : 0) * (box.clientWidth - 14);
  const draw = () => {
    hs[0].style.left = pct(val[0]) + "px";
    hs[1].style.left = pct(val[1]) + "px";
    fl.style.left = pct(val[0]) + "px";
    fl.style.width = pct(val[1]) - pct(val[0]) + "px";
    lab.textContent = `${val[0]}-${val[1]}`;
    hs[0].setAttribute("aria-valuetext", val[0]);
    hs[1].setAttribute("aria-valuetext", val[1]);
  };
  const set = (h, y) => {
    y = Math.round(Math.max(lo, Math.min(hi, y)));
    if (h === 0) val[0] = Math.min(y, val[1] - MIN);
    else val[1] = Math.max(y, val[0] + MIN);
    val[0] = Math.max(lo, val[0]);
    val[1] = Math.min(hi, val[1]);
    draw();
  };
  const commit = () => {
    if (val[0] === st.span[0] && val[1] === st.span[1]) return;
    st.yr = val.slice();
    sfx("select");
    paint(true);
  };
  const yearAt = (e) => {
    const r = box.getBoundingClientRect();
    return lo + (e.clientX - r.left - 7 * uiScale) / Math.max(1, r.width - 14 * uiScale) * (hi - lo);
  };
  let drag = -1;
  box.onpointerdown = (e) => {
    const y = yearAt(e);
    drag = e.target.dataset.h != null ? +e.target.dataset.h : Math.abs(y - val[0]) < Math.abs(y - val[1]) ? 0 : 1;
    box.setPointerCapture(e.pointerId);
    set(drag, y);
  };
  box.onpointermove = (e) => {
    if (drag >= 0) set(drag, yearAt(e));
  };
  box.onpointerup = () => {
    if (drag < 0) return;
    drag = -1;
    commit();
  };
  hs.forEach((h, i) => h.onkeydown = (e) => {
    const d = e.key === "ArrowLeft" || e.key === "ArrowDown" ? -1 : e.key === "ArrowRight" || e.key === "ArrowUp" ? 1 : 0;
    if (!d) return;
    e.preventDefault();
    set(i, val[i] + d);
    commit();
    W.querySelectorAll(".rm-range .hd")[i].focus();
  });
  draw();
}
function card() {
  const box = $("#rm-pv"), L = LAYERS[st.v];
  W.querySelector("#rm-selg").innerHTML = "";
  if (L.real) {
    box.hidden = st.city < 0;
    if (st.city >= 0) cityCard(box);
    return;
  }
  box.hidden = st.c < 0;
  if (st.c < 0) return;
  const r = st.rows[st.c];
  const selg = W.querySelector("#rm-selg");
  el("path", { d: st.map.sea[r.n], class: "rm-sel", "vector-effect": "non-scaling-stroke" }, selg);
  const [px, py] = P(...LAB[r.n]);
  el("circle", { cx: px, cy: py, r: 1.4, class: "rm-pulse", "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, selg);
  if (r.na) {
    box.innerHTML = `<div class="hd"><h3>${r.n.toUpperCase()}</h3><button class="x" id="rm-close" aria-label="Close">×</button></div><div class="sub">${L.name.toUpperCase()}</div><div style="margin-top:12px;font-size:20px">${r.na}</div>`;
    box.querySelector("#rm-close").onclick = closeCard;
    return;
  }
  const Wd = 250, Hd = 70, lo = Math.min(...r.ys), hi = Math.max(...r.ys), pad = (hi - lo) * 0.15 || 1;
  const X = (x) => 8 + (x - r.y0) / Math.max(1, r.y1 - r.y0) * (Wd - 16), Y = (y) => Hd - 8 - (y - lo + pad) / (hi - lo + 2 * pad) * (Hd - 16);
  let line = "";
  r.xs.forEach((x, i) => {
    line += (i && x - r.xs[i - 1] > 1 ? "M" : i ? "L" : "M") + X(x).toFixed(1) + " " + Y(r.ys[i]).toFixed(1);
  });
  const gap = L.gap && r.y0 <= L.gap[0] ? `<rect x="${X(L.gap[0] - 0.5)}" y="2" width="${X(L.gap[1] + 0.5) - X(L.gap[0] - 0.5)}" height="${Hd - 4}" fill="#d94a36" fill-opacity=".28"/>` : "";
  const dp = L.sd < 1 ? 2 : 1, f = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(dp);
  const need = Math.ceil(r.nstar), det = r.det, sus = r.sus;
  const verdict = det ? "TREND DETECTED" : sus ? "USE CAUTION" : "NO CLEAR TREND";
  const note = sus ? "Trend found, but the 2017-2018 satellite gap is inside this period." : det ? "Clear trend over this period." : need > r.N ? `No clear trend yet. About ${need - r.N} more years of data needed.` : "No clear trend once all 11 countries are compared.";
  box.innerHTML = `<div class="hd"><h3>${r.n.toUpperCase()}</h3><button class="x" id="rm-close" aria-label="Close">×</button></div>
    <div class="sub">${L.name.toUpperCase()} · ${r.y0}-${r.y1}${r.real ? "" : " · SAMPLE DATA"}</div>
    <div class="big"><b id="rm-count">${f(0)}</b><span>${L.ud.replace("/dec", " / decade")}</span></div>
    <span class="rm-verd" style="background:${det ? "var(--grn)" : sus ? "var(--red)" : "var(--mus)"};color:${sus ? "#fff" : "var(--ink)"}">${verdict}</span>
    <svg class="rm-spark zoomable" id="rm-zoom" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none" role="button" tabindex="0" aria-label="Open the full chart">
      ${[0.33, 0.66].map((q) => `<path d="M4 ${(Hd * q).toFixed(0)}H${Wd - 4}" stroke="#1a2f6e" stroke-dasharray="2 2"/>`).join("")}${gap}
      <path class="ln" d="${line}"/>
      <path class="tr" d="M${X(r.xs[0])} ${Y(r.a + r.b * r.xs[0])}L${X(r.xs[r.N - 1])} ${Y(r.a + r.b * r.xs[r.N - 1])}"/></svg>
    <table class="rm-tab">
      <tr><td>95% range</td><td>${f(r.b10 - 1.96 * r.se10)} .. ${f(r.b10 + 1.96 * r.se10)}</td></tr>
      ${FXTXT[fxOf(r)] ? `<tr><td>Linked risk</td><td>${FXTXT[fxOf(r)](L)}</td></tr>` : ""}
    </table>
    <button class="rm-more" id="rm-more" aria-expanded="${st.more}">${st.more ? "▾ Fewer stats" : "▸ More stats"}</button>
    ${st.more ? `<table class="rm-tab">
      <tr><td>Autocorr. r1</td><td>${r.r1.toFixed(2)}</td></tr>
      <tr><td>n_eff / n</td><td>${r.neff.toFixed(1)} / ${r.N}</td></tr>
      <tr><td>p / adj. p</td><td>${r.p < 1e-3 ? "<.001" : r.p.toFixed(3)} / ${r.padj < 1e-3 ? "<.001" : r.padj.toFixed(3)}</td></tr>
      <tr><td>Years needed</td><td>${need > r.N ? "≈" : ""}${need} (have ${r.N})</td></tr></table>
      <div class="rm-note">${note}</div>` : ""}
    <div class="zoom-hint">${r.y0} · CLICK CHART TO ENLARGE · ${r.y1}</div>
    <div class="rm-note">SAMPLE DATA, made up to show how the map works. Real NASA records live in the Indonesia sea level layer and in CASES.</div>
    ${analysis.DATASETS[L.k] ? `<button class="obtn" id="rm-open">OPEN THE REAL ${L.k === "t2m" ? "TEMPERATURE" : "RAINFALL"} CASE ▸</button>` : ""}`;
  box.querySelector("#rm-close").onclick = closeCard;
  box.querySelector("#rm-more").onclick = () => {
    st.more = !st.more;
    sfx("select");
    card();
  };
  const ln = box.querySelector(".ln"), len = ln.getTotalLength();
  ln.style.strokeDasharray = `${len} ${len}`;
  ln.style.strokeDashoffset = len;
  const d0 = performance.now(), drawStep = (t) => {
    const k = Math.min(1, (t - d0) / 900);
    ln.style.strokeDashoffset = (len * (1 - Math.floor(k * 24) / 24)).toFixed(1);
    if (k < 1) requestAnimationFrame(drawStep);
  };
  requestAnimationFrame(drawStep);
  const t0 = performance.now(), el2 = box.querySelector("#rm-count");
  const tick = (t) => {
    const k = Math.min(1, (t - t0) / 500);
    el2.textContent = f(r.b10 * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  const ob = box.querySelector("#rm-open");
  if (ob) ob.onclick = () => {
    const ds = analysis.DATASETS[L.k];
    sfx("chime");
    desktop.startCase({ v: L.k, r: "idn", y0: ds.start, y1: ds.end });
  };
  const zs = box.querySelector("#rm-zoom");
  zs.onclick = () => {
    sfx("select");
    openChart({
      title: `${r.n.toUpperCase()} · ${L.name.toUpperCase()} · SAMPLE DATA`,
      sub: `${r.y0}-${r.y1} · YEARLY · NOT NASA DATA`,
      unit: L.unit,
      series: r.xs.map((x, i) => [x, r.ys[i]]),
      seriesLabel: "Yearly value (sample)",
      fit: [[r.xs[0], r.a + r.b * r.xs[0]], [r.xs[r.N - 1], r.a + r.b * r.xs[r.N - 1]]],
      fitLabel: `Trend ${f(r.b10)} ${L.ud}`,
      stats: [["TREND", `${f(r.b10)} ${L.ud}`], ["95% RANGE", `${f(r.b10 - 1.96 * r.se10)} .. ${f(r.b10 + 1.96 * r.se10)}`], ["VERDICT", verdict]],
      notes: ["Sample data, generated to demonstrate the map. Use the Indonesia sea level layer or CASES for real NASA records."],
      dp
    });
  };
}
function closeCard() {
  st.c = -1;
  st.city = -1;
  cities();
  sfx("close");
  card();
}
function tip(e, ci) {
  const t = $("#rm-tip");
  if (!e) {
    t.style.display = "none";
    return;
  }
  const r = st.rows[ci], L = LAYERS[st.v], box = $("#rm-mapc").getBoundingClientRect();
  t.innerHTML = r.neutral ? `${r.n.toUpperCase()} <span class="dim">· ${r.n === "Indonesia" ? "click a city dot" : "click to zoom in"}</span>` : r.na ? `${r.n.toUpperCase()} <span class="dim">· no data</span>` : `${r.n.toUpperCase()} <b style="font-weight:400;color:${r.det ? "var(--ink)" : r.sus ? "var(--red)" : "#5b6b8f"}">${(r.b10 >= 0 ? "+" : "−") + Math.abs(r.b10).toFixed(L.sd < 1 ? 2 : 1)} ${L.ud}</b>${r.det ? "" : r.sus ? ' <span class="hi">· use caution</span>' : ' <span class="dim">· no clear trend</span>'}`;
  t.style.display = "block";
  const z = uiScale;
  t.style.left = Math.min((e.clientX - box.left) / z + 14, box.width / z - t.offsetWidth - 6) + "px";
  t.style.top = (e.clientY - box.top) / z + 16 + "px";
}
function pick(ci) {
  const r = st.rows[ci];
  if (r.neutral) {
    sfx("select");
    st.city = -1;
    flyTo(boxOf(st.map.sea[r.n]));
    card();
    cities();
    return;
  }
  if (st.view === "world") zoom("sea");
  st.c = ci;
  sfx(r.na ? "err" : "select");
  card();
}
function denied(e) {
  sfx("err");
  const rest = W.querySelector(".rm-rest");
  rest.classList.remove("deny");
  void rest.getBoundingClientRect();
  rest.classList.add("deny");
  const d = $("#rm-deny");
  d.style.display = "block";
  d.style.animation = "none";
  void d.offsetWidth;
  d.style.animation = "";
  const crt = document.querySelector(".crt");
  if (crt) {
    crt.classList.remove("jolt");
    void crt.offsetWidth;
    crt.classList.add("jolt");
  }
  clearTimeout(denied.t);
  denied.t = setTimeout(() => d.style.display = "none", 2200);
}
const SEA_BOX = [262, 50, 336, 118];
function setVB(vb, anim) {
  st.vb = vb;
  const v = vb.join(" ");
  $("#rm-svg").setAttribute("viewBox", v);
  $("#rm-top").setAttribute("viewBox", v);
  const s = vb[2] / 368;
  W.querySelector("#rm-sattx").setAttribute("font-size", (8 * s).toFixed(2));
  W.querySelector("#rm-sattx").setAttribute("x", 3 * s);
  const d = W.querySelector("#rm-satdot");
  d.setAttribute("width", 3 * s);
  d.setAttribute("height", 3 * s);
  d.setAttribute("x", -1.5 * s);
  d.setAttribute("y", -1.5 * s);
  const zr = W.querySelector("#rm-zr");
  if (zr) zr.textContent = st.view !== "world" ? `${(VB.sea[2] / vb[2]).toFixed(1).replace(".0", "")}×` : "";
  const ls = Math.min(1, vb[2] / VB.sea[2]);
  W.querySelectorAll("#rm-labs text").forEach((t) => {
    t.setAttribute("font-size", (+t.dataset.fs * ls).toFixed(3));
    t.setAttribute("stroke-width", (0.28 * ls).toFixed(3));
  });
  const cr = Math.min(1, vb[2] / VB.sea[2]);
  W.querySelectorAll(".rm-city").forEach((d) => d.setAttribute("r", ((d.classList.contains("cap") ? 0.42 : 0.3) * cr).toFixed(3)));
  cityLabels();
  const cg = W.querySelector("#rm-cities");
  if (cg && !LAYERS[st.v].real) cg.classList.toggle("off", !zoomedIn());
  if (!anim) {
    W.querySelector("#rm-fxc").style.display = "none";
    clearTimeout(setVB.t);
    setVB.t = setTimeout(() => {
      placeFx();
      satRefresh();
    }, 140);
  }
}
function clampVB(vb) {
  const w = Math.max(5, Math.min(72, vb[2])), h = w * VB.sea[3] / VB.sea[2];
  let x = vb[0] + (vb[2] - w) / 2, y = vb[1] + (vb[3] - h) / 2;
  x = Math.max(SEA_BOX[0], Math.min(SEA_BOX[2] - w, x));
  y = Math.max(SEA_BOX[1], Math.min(SEA_BOX[3] - h, y));
  return [x, y, w, h];
}
function zoomAt(f, cx, cy) {
  if (zoom.busy) return;
  if (st.view === "world") {
    if (f < 1) zoom("idn");
    return;
  }
  const vb = st.vb || VB.sea.slice();
  if (cx == null) {
    cx = vb[0] + vb[2] / 2;
    cy = vb[1] + vb[3] / 2;
  }
  setVB(clampVB([cx - (cx - vb[0]) * f, cy - (cy - vb[1]) * f, vb[2] * f, vb[3] * f]));
}
function toUnits(e) {
  const svg = $("#rm-svg"), p = svg.createSVGPoint();
  p.x = e.clientX;
  p.y = e.clientY;
  return p.matrixTransform(svg.getScreenCTM().inverse());
}
function bindNav() {
  const mc = $("#rm-mapc");
  W.querySelectorAll(".rm-zoom button").forEach((b) => b.onclick = () => {
    sfx("select");
    const z = b.dataset.z;
    if (z === "home") {
      zoom("idn");
    } else zoomAt(z === "in" ? 1 / 1.5 : 1.5);
  });
  mc.addEventListener("wheel", (e) => {
    if (e.target.closest(".rm-card")) return;
    e.preventDefault();
    const u = toUnits(e);
    zoomAt(e.deltaY < 0 ? 1 / 1.2 : 1.2, u.x, u.y);
  }, { passive: false });
  // In circle mode a map click places the circle centre, and the country and city clicks are skipped.
  mc.addEventListener("click", (e) => {
    if (!st.circ.on || st.dragged || e.target.closest("#rm-circ,.rm-nav,.rm-float,.rm-zoom,.rm-seg,button")) return;
    e.stopPropagation();
    e.preventDefault();
    const p = toUnits(e);
    circleCentre(p.x - 180, 90 - p.y);
  }, true);
  let drag = null;
  mc.addEventListener("pointerdown", (e) => {
    if (st.view === "world" || e.button !== 0 || e.target.closest("button,.rm-tip,.rm-float")) return;
    drag = { x: e.clientX, y: e.clientY, vb: (st.vb || VB.sea).slice(), k: $("#rm-svg").getScreenCTM().a, moved: false };
    st.dragged = false;
  });
  mc.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    if (!drag.moved) mc.setPointerCapture(e.pointerId);
    drag.moved = true;
    st.dragged = true;
    mc.classList.add("grab");
    tip(null);
    setVB(clampVB([drag.vb[0] - dx / drag.k, drag.vb[1] - dy / drag.k, drag.vb[2], drag.vb[3]]));
  });
  mc.addEventListener("pointerup", () => {
    if (!drag) return;
    mc.classList.remove("grab");
    drag = null;
    setTimeout(() => st.dragged = false, 0);
  });
}
function zoom(to) {
  const box = Array.isArray(to);
  if (!box && st.view === to && !zoom.busy && to !== "idn") return;
  const from = $("#rm-svg").getAttribute("viewBox").split(" ").map(Number), dst = box ? clampVB(to) : VB[to].slice(), t0 = performance.now(), dur = 850;
  if (box) to = "box";
  const wasWorld = st.view === "world";
  st.view = to;
  sfx("whoosh");
  zoom.busy = true;
  clearInterval(placeFx.iv);
  W.querySelector("#rm-fxc").style.display = "none";
  W.querySelectorAll(".rm-tog button").forEach((b) => b.classList.toggle("on", b.dataset.v === to));
  if (to === "world") W.querySelector("#rm-zr").textContent = "";
  const labs = W.querySelector("#rm-labs");
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
    const vb = from.map((a, i) => a + (dst[i] - a) * e);
    setVB(vb, true);
    labs.setAttribute("opacity", to === "world" ? (wasWorld ? 0 : 1 - e) : wasWorld ? e : 1);
    if (k < 1) requestAnimationFrame(step);
    else {
      zoom.busy = false;
      if (st.rows) {
        hud();
        cities();
        placeFx();
      }
      satRefresh();
    }
  };
  requestAnimationFrame(step);
}
async function load() {
  if (!st.map) st.map = await (await fetch("data/sea_map.json")).json();
  const opt = async (u) => {
    try {
      const r = await fetch(u);
      return r.ok ? await r.json() : null;
    } catch (e) {
      return null;
    }
  };
  if (!st.prov) st.prov = await opt("data/indonesia_provinces.json");
  if (!st.ssl) st.ssl = await opt("data/indonesia_sea_level.json");
  if (!st.ssl && LAYERS[0].real) LAYERS.shift();
}
async function open(win, helpers) {
  H = helpers;
  W = win(
    "w-rmap",
    "MAP.EXE · INDONESIA",
    `<div class="rm"><div class="rm-bar" id="rm-bar"></div>
    <div class="rm-map" id="rm-mapc"><svg id="rm-svg" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Trend map of Southeast Asia"></svg>
      <canvas class="rm-fxc" id="rm-fxc" aria-hidden="true"></canvas><svg id="rm-top" preserveAspectRatio="xMidYMid meet" aria-hidden="true" style="pointer-events:none"></svg>
      <div class="rm-float rm-hud" id="rm-hud">LOADING MAP...</div>
      <div class="rm-float rm-leg" id="rm-leg"></div>
      <div class="rm-nav"><div class="rm-seg rm-tog"><button data-v="world">WORLD</button><button data-v="sea">SE ASIA</button><button data-v="idn">INDONESIA</button></div>
        <div class="rm-zoom"><span id="rm-zr" aria-live="polite"></span><button data-z="in" title="Zoom in" aria-label="Zoom in">+</button><button data-z="out" title="Zoom out" aria-label="Zoom out">−</button><button data-z="home" title="Reset view" aria-label="Reset view">⌂</button></div></div>
      <div class="rm-float rm-card" id="rm-pv" hidden></div>
      <div class="rm-tip" id="rm-tip"></div>
      <div class="rm-deny" id="rm-deny"><div class="tb"><span class="t">AREA LOCKED</span></div><div style="padding:8px 12px">Only Southeast Asia is available.</div></div>
      <div class="rm-scan"></div></div></div>`,
    { left: "122px", top: "6px", right: "8px", bottom: "8px" }
  );
  Object.assign(W.querySelector(".bd").style, { padding: "0", overflow: "hidden" });
  try {
    await load();
  } catch (e) {
    $("#rm-hud").textContent = "MAP FILE MISSING";
    return;
  }
  st.view = "world";
  st.c = -1;
  st.city = -1;
  st.dd = false;
  if (!open.ro) {
    open.ro = new ResizeObserver(() => placeFx());
  }
  open.ro.observe($("#rm-mapc"));
  buildSvg();
  satRefresh();
  bindNav();
  W.querySelectorAll(".rm-tog button").forEach((b) => {
    b.classList.toggle("on", b.dataset.v === "world");
    b.onclick = () => {
      sfx("select");
      zoom(b.dataset.v);
    };
  });
  setTimeout(() => paint(true), 350);
  setTimeout(() => zoom("idn"), 1700);
  if (st.ssl) setTimeout(() => talk([`${st.ssl.cities.length} cities. ${st.ssl.tests} of them on the coast.`, "Pick one from CITIES. I’ll show you exactly which ocean cells the number comes from."], "map"), 2900);
  H.log && H.log(st.ssl ? `MAP: ECCO SEA LEVEL FOR ${st.ssl.tests} COASTAL CITIES LOADED.` : "MAP: SAMPLE DATA.");
}
// CIRCLE mode: click the map for the centre, pick a radius (75 to 250 km) and a variable, RUN.
// The page draws cells and text only. Every number comes from POST api/analyse (Python core).
const CIRC_VARS = [
  ["merra2:t2m", "Air temperature (MERRA-2)"],
  ["merra2:precip", "Rainfall (MERRA-2)"],
  ["merra2:evap", "Evaporation (MERRA-2)"],
  ["merra2:vpd", "Vapour pressure deficit (MERRA-2)"],
  ["merra2:qv2m", "Humidity (MERRA-2)"],
  ["merra2:tsurf", "Land surface temperature (MERRA-2)"],
  ["gpcp:gpcp_precip", "Rainfall (GPCP)"],
];
const CIRC_COL = { rise: "#d94a36", fall: "#1f4fa0", none: "#c9c2b2" };
const signed = (v) => (v == null ? "n/a" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`);
function circleToggle(on) {
  const c = st.circ;
  c.on = on;
  c.msg = on ? "Click the map to place the circle." : "";
  if (!on) {
    c.lat = c.lon = null;
    c.cells = null;
    c.out = null;
  }
  sfx("select");
  circleDraw();
  circlePanel();
  toolbar();
}
function circleCentre(lon, lat) {
  const c = st.circ;
  c.lon = lon;
  c.lat = lat;
  c.cells = null;
  c.out = null;
  c.msg = "Centre set. Press RUN.";
  circleDraw();
  circlePanel();
}
function circleDraw() {
  const g = W.querySelector("#rm-circg");
  if (!g) return;
  g.innerHTML = "";
  const c = st.circ;
  if (!c.on || c.lat == null) return;
  (c.cells || []).forEach((q) => {
    const h = q.height_km / KM_DEG, w = q.width_km / (KM_DEG * Math.cos((q.lat * Math.PI) / 180));
    const kind = q.significant ? (q.slope_per_decade > 0 ? "rise" : "fall") : "none";
    el("rect", { x: q.lon + 180 - w / 2, y: 90 - q.lat - h / 2, width: w, height: h, fill: CIRC_COL[kind], "fill-opacity": 0.7, stroke: "#06090f", "stroke-width": 0.04, "vector-effect": "non-scaling-stroke" }, g);
  });
  const ry = c.r / KM_DEG, rx = ry / Math.cos((c.lat * Math.PI) / 180);
  el("ellipse", { cx: c.lon + 180, cy: 90 - c.lat, rx, ry, class: "rm-radius", "vector-effect": "non-scaling-stroke" }, g);
}
function circlePanel() {
  const c = st.circ;
  let p = $("#rm-circ");
  if (!c.on) {
    if (p) p.remove();
    return;
  }
  if (!p) {
    p = document.createElement("div");
    p.id = "rm-circ";
    p.className = "rm-float rm-card";
    p.style.cssText = "left:12px;bottom:12px;right:auto;top:auto;width:300px";
    p.innerHTML = `<div class="hd"><h3>CIRCLE</h3><button class="x" id="rm-cx" aria-label="Close circle">×</button></div>
      <div style="display:grid;gap:6px;margin-top:6px">
        <label>Variable <select id="rm-cv">${CIRC_VARS.map(([k, l]) => `<option value="${k}">${l}</option>`).join("")}</select></label>
        <label>Radius <b id="rm-cr-v">${c.r}</b> km <input id="rm-cr" type="range" min="75" max="250" step="5" value="${c.r}"></label>
        <div><button id="rm-crun" class="obtn">RUN</button></div>
      </div>
      <div id="rm-cchart" style="margin-top:6px"></div>
      <div id="rm-cmsg" class="sub"></div><div id="rm-cout" style="font-size:14px;line-height:1.4;margin-top:6px"></div>`;
    $("#rm-mapc").appendChild(p);
    $("#rm-cx").onclick = () => circleToggle(false);
    $("#rm-cv").value = c.v;
    $("#rm-cv").onchange = (e) => {
      c.v = e.target.value;
      c.cells = null;
      c.out = null;
      circleDraw();
      circlePanel();
    };
    $("#rm-cr").oninput = (e) => {
      c.r = +e.target.value;
      c.cells = null;
      c.out = null;
      $("#rm-cr-v").textContent = c.r;
      circleDraw();
    };
    $("#rm-crun").onclick = circleRun;
  }
  $("#rm-cmsg").textContent = c.msg;
  const box = $("#rm-cout");
  box.replaceChildren(...(c.out || []).map((t) => {
    const d = document.createElement("div");
    d.textContent = t;
    return d;
  }));
  circleChart();
}
// Monthly average of the cells inside the circle, as returned by /api/analyse. Only in-circle cells
// are averaged, and the line is drawn from that average. Raw monthly values (seasonal cycle included).
function circleChart() {
  const box = $("#rm-cchart"), c = st.circ;
  if (!box) return;
  box.replaceChildren();
  if (!c.cells || !c.avg) return;
  const { periods, series, valid, unit } = c.avg;
  const pts = series.map((v, i) => [i, v]).filter(([, v]) => v != null);
  if (pts.length < 2) return;
  const W = 280, H = 130, L = 34, R = 270, T = 8, B = 112;
  const lo = Math.min(...pts.map((p) => p[1])), hi = Math.max(...pts.map((p) => p[1]));
  const span = hi - lo || 1;
  const x = (i) => L + (i / (series.length - 1)) * (R - L);
  const y = (v) => B - ((v - lo) / span) * (B - T);
  const cap = document.createElement("div");
  cap.style.fontSize = "12px";
  cap.textContent = `Average of the ${c.cells.length} cells inside the circle, monthly (${unit}). Cells with data each month: ${Math.min(...valid)} to ${Math.max(...valid)}.`;
  box.appendChild(cap);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", role: "img", "aria-label": "Monthly average of the cells inside the circle" }, box);
  el("line", { x1: L, y1: B, x2: R, y2: B, stroke: "#56628a", "stroke-width": 1 }, svg);
  el("line", { x1: L, y1: T, x2: L, y2: B, stroke: "#56628a", "stroke-width": 1 }, svg);
  const d = pts.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  el("path", { d, fill: "none", stroke: "#1b2440", "stroke-width": 1.2 }, svg);
  const label = (txt, x0, y0) => {
    const t = el("text", { x: x0, y: y0, "font-size": 10, fill: "#1b2440" }, svg);
    t.textContent = txt;
  };
  label(hi.toFixed(2), 2, T + 6);
  label(lo.toFixed(2), 2, B);
  label(periods[0].slice(0, 4), L, H - 2);
  label(periods[periods.length - 1].slice(0, 4), R - 20, H - 2);
}
async function circleRun() {
  const c = st.circ;
  if (c.lat == null) {
    c.msg = "Click the map first to place the circle.";
    circlePanel();
    return;
  }
  c.msg = "Working...";
  c.out = null;
  circlePanel();
  let res;
  try {
    res = await fetch("api/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "circle", lat: c.lat, lon: c.lon, radius_km: c.r, variables: [c.v] }),
    });
  } catch {
    c.msg = "The analysis server is not running, so no numbers can be shown.";
    circlePanel();
    return;
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    c.msg = body.error || `The server said ${res.status}.`;
    c.cells = null;
    circleDraw();
    circlePanel();
    return;
  }
  const r = body.results[0], a = r.agreement;
  c.cells = r.cells;
  c.avg = { periods: r.average.periods, series: r.average.series, valid: r.average.valid_per_month, unit: r.unit };
  c.msg = "";
  c.out = [
    `${r.label}, circle of ${c.r} km`,
    `${r.cells_used} of ${r.cells_in_circle} cells used (centres inside the circle).`,
    `Significant rises: ${a.rising}. Significant falls: ${a.falling}. Not significant: ${a.not_significant}.`,
    `Cell slopes range from ${signed(a.slope_min)} to ${signed(a.slope_max)} per decade.`,
    r.average.summary.sentence,
    ...r.warnings.map((w) => `Note: ${w}`),
  ];
  circleDraw();
  circlePanel();
}
const regionMap = { open };
export {
  regionMap
};
