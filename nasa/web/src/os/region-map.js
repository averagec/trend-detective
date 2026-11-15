import { SFX } from "../audio/sfx.js";
import { say } from "../ui/dialogue.js";
import { analysis } from "../stats/trend-analysis.js";
import { pixelWeather } from "./pixel-weather.js";
import { desktop } from "./desktop.js";
import { uiScale } from "../ui/scale.js";
import { startWater } from "./pixel-water.js";
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
    s: [0.2, 0.22, 0.17, 0.24, 0.21, 0.23, 0.19, 0.245, 0.25, 0.14, 0.22]
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
    s: [6, -4, 3, -2, 8, -6, 12, 5, -3, -9, 4]
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
    na: { Singapore: "No data. Too small for GRACE satellites.", Brunei: "No data. Too small for GRACE satellites.", "Timor-Leste": "No data. Too small for GRACE satellites." }
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
    na: { Laos: "No data. Laos has no coastline." }
  },
  { k: "ndvi", name: "Vegetation (NDVI)", src: "MODIS Terra", y0: 2001, y1: 2024, lock: "CASE 002" },
  { k: "aod", name: "Aerosols (AOD)", src: "MERRA-2", y0: 1981, y1: 2024, lock: "CASE 003" }
];
const SSL_BINS = [30, 36, 42, 48];
const PAL = { s: ["#d8e6ee", "#9fd0e8", "#5aa6dd", "#2f6fc0", "#1c3d8c"], t: ["#1f4fa0", "#7fa8e8", "#c9c2b2", "#e9a93a", "#d94a36"], w: ["#8a5a2b", "#c9a46a", "#c9c2b2", "#7fc4a0", "#2f8f7a"] };
const GREY = "#56628a", VB = { world: [-4, -14, 368, 206], sea: [268, 58, 58, 52], idn: [273, 78, 50, 28] };
const st = { v: 0, city: -1, q: "", yr: null, more: false, f: 0, fx: true, c: -1, view: "world", map: null, data: null, rows: null, seen: {}, legend: -1 };
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
  el("path", { d: g, stroke: "#dff2fb", "stroke-opacity": 0.18, "stroke-width": 1, "vector-effect": "non-scaling-stroke", fill: "none" }, svg);
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
  sfx(cityState(c) === "inland" ? "err" : "select");
  if (fly) flyTo(cityBox(c));
  paint(false);
}
function cityBox(c) {
  const w = 9, h = w * VB.idn[3] / VB.idn[2], x = c.lon + 180, y = 90 - c.lat;
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
  el("circle", { cx: px, cy: py, r: (0.9 * Math.min(1, (st.vb || VB.sea)[2] / VB.sea[2])).toFixed(3), class: "rm-pulse", "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, selg);
  const head = `<div class="hd"><h3>${c.name.toUpperCase()}</h3><button class="x" id="rm-close" aria-label="Close">×</button></div>
    <div class="sub">${c.province.toUpperCase()} · SEA LEVEL · ${m.period[0]}-${m.period[1]}</div>`;
  if (k === "inland") {
    box.innerHTML = head + `<div style="margin-top:10px;font-size:20px;line-height:1.15">${c.note}</div><div class="rm-note">Pick a coastal city to see its sea level.</div>`;
    box.querySelector("#rm-close").onclick = closeCard;
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
    <svg class="rm-spark" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none">
      <path d="${band}" fill="#e9a93a" fill-opacity=".18"/><path class="ln" d="${line}"/><path class="tr" d="${fit}"/></svg>
    <table class="rm-tab">
      <tr><td>Per decade</td><td>${f(c.trend_mm_per_decade)} mm</td></tr>
      <tr><td>95% range</td><td>${f(c.ci_mm_per_decade[0], 0)} .. ${f(c.ci_mm_per_decade[1], 0)} mm</td></tr>
      ${sig ? "<tr><td>Risk</td><td>Coastal flooding</td></tr>" : ""}
    </table>
    <button class="rm-more" id="rm-more" aria-expanded="${st.more}">${st.more ? "▾ Fewer stats" : "▸ More stats"}</button>
    ${st.more ? `<table class="rm-tab">
      <tr><td>p (OLS)</td><td>${c.p < 1e-3 ? "<.001" : c.p.toFixed(3)}</td></tr>
      <tr><td>p adjusted</td><td>${c.p_adjusted < 1e-3 ? "<.001" : c.p_adjusted.toFixed(3)}</td></tr>
      <tr><td>Sen's slope</td><td>${f(c.sen_mm_per_decade)} mm/dec</td></tr>
      <tr><td>MK p (unadj.)</td><td>${c.mk_p_unadjusted < 1e-3 ? "<.001" : c.mk_p_unadjusted.toFixed(3)}</td></tr>
      <tr><td>Ocean cells</td><td>${c.cells} · ${Math.round(c.nearest_cell_km)} km</td></tr></table>
      <div class="rm-note">${c.sentence} Adjusted p accounts for testing ${m.tests} coastal cities at once.${c.warnings.length ? " " + c.warnings.join(" ") : ""}</div>` : ""}
    <div class="rm-note">${m.caveat}</div>
    <div class="rm-note">NASA DATA · ${m.dataset}</div>`;
  box.querySelector("#rm-close").onclick = closeCard;
  box.querySelector("#rm-more").onclick = () => {
    st.more = !st.more;
    sfx("select");
    card();
  };
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
  if (LAYERS[st.v].real && st.ssl) {
    st.ssl.cities.map((c, i) => [c, i]).filter(([c, i]) => cityState(c) === "sig" && !W.querySelector(`.rm-city[data-i="${i}"]`).classList.contains("fade")).sort((a, b) => (b[1] === st.city) - (a[1] === st.city) || b[0].population - a[0].population).forEach(([c]) => {
      const [ax, ay] = toCell([c.lon, c.lat]);
      if (ax < 0 || ay < 0 || ax >= GW || ay >= GH) return;
      if (sp.length >= 10 || sp.some((q) => Math.hypot(q.ax - ax, q.ay - ay) < 16)) return;
      sp.push({ t: "flood", ax, ay: ay - 2 });
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
    <div class="rm-search"><input id="rm-q" type="search" placeholder="Search city…" autocomplete="off" aria-label="Search a city or province" value="${st.q.replace(/"/g, "&quot;")}"><div class="rm-res" id="rm-res" role="listbox" hidden></div></div>
    <div class="rm-seg" role="group" aria-label="Show">${["ALL", "TREND", "NONE"].map((t, i) => `<button data-f="${i}" class="${i === st.f ? "ink" : ""}">${t}</button>`).join("")}</div>
    <button class="rm-chip${st.fx ? " on" : ""}" data-fx title="Weather effects">FX ${st.fx ? "ON" : "OFF"}</button>`;
  W.querySelectorAll("[data-l]").forEach((b) => b.onclick = () => {
    st.v = +b.dataset.l;
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
  if (!LAYERS[st.v].real) bindRange(lo, hi);
  bindSearch();
}
function bindSearch() {
  const q = $("#rm-q"), res = $("#rm-res");
  let items = [], hi = 0;
  const norm = (x) => x.toLowerCase().normalize("NFD").replace(/[^a-z0-9 ]/g, "");
  const render = () => {
    const v = norm(q.value.trim());
    st.q = q.value;
    if (!v || !st.ssl) {
      res.hidden = true;
      return;
    }
    const cs = st.ssl.cities.map((c, i) => ({ t: "c", i, name: c.name, sub: c.province, n: norm(c.name), pop: c.population }));
    const ps = st.prov ? Object.keys(st.prov.provinces).map((name) => ({ t: "p", name, sub: "Province", n: norm(name), pop: 0 })) : [];
    const score = (x) => x.n.startsWith(v) ? 0 : x.n.split(" ").some((w) => w.startsWith(v)) ? 1 : x.n.includes(v) ? 2 : 9;
    items = cs.concat(ps).map((x) => [score(x), x]).filter((a) => a[0] < 9).sort((a, b) => a[0] - b[0] || b[1].pop - a[1].pop).slice(0, 8).map((a) => a[1]);
    hi = 0;
    res.innerHTML = items.length ? items.map((x, k) => `<button role="option" data-k="${k}" class="${k === hi ? "hi" : ""}"><span>${x.name}</span><small>${x.sub}</small></button>`).join("") : '<div class="none">No city found</div>';
    res.hidden = false;
    res.querySelectorAll("[data-k]").forEach((b) => b.onmousedown = (e) => {
      e.preventDefault();
      go(items[+b.dataset.k]);
    });
  };
  const go = (x) => {
    if (!x) return;
    res.hidden = true;
    q.blur();
    if (x.t === "c") pickCity(x.i, true);
    else {
      sfx("select");
      st.city = -1;
      flyTo(boxOf(st.prov.provinces[x.name]));
      paint(false);
    }
  };
  q.oninput = render;
  q.onfocus = render;
  q.onblur = () => setTimeout(() => res.hidden = true, 120);
  q.onkeydown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      hi = Math.max(0, Math.min(items.length - 1, hi + (e.key === "ArrowDown" ? 1 : -1)));
      res.querySelectorAll("[data-k]").forEach((b) => b.classList.toggle("hi", +b.dataset.k === hi));
    } else if (e.key === "Enter") go(items[hi]);
    else if (e.key === "Escape") {
      q.value = "";
      render();
    }
  };
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
    <svg class="rm-spark" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none">
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
    <button class="obtn" id="rm-open">OPEN AS CASE ▸</button>`;
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
  box.querySelector("#rm-open").onclick = () => openCase(r);
}
function closeCard() {
  st.c = -1;
  st.city = -1;
  cities();
  sfx("close");
  card();
}
function openCase(r) {
  const L = LAYERS[st.v], D = analysis.DATASETS;
  if (!D[L.k]) D[L.k] = { label: L.name, unit: L.unit, source: L.src, start: span(st.v)[0], end: span(st.v)[1], regions: {} };
  const rk = Object.keys(D[L.k].regions).find((k) => D[L.k].regions[k].name === r.n) || "m_" + r.n.replace(/\W/g, "").toLowerCase();
  if (r.real) D[L.k].source = L.src;
  if (L.k === "tws" && !D.tws.gap) D.tws.gap = [2017.5, 2018.42];
  D[L.k].regions[rk] = Object.assign(D[L.k].regions[rk] || {}, { name: r.n });
  const t = [], v = [];
  r.mo.m.forEach((x, i) => {
    if (x != null) {
      t.push(r.mo.y0 + (i + 0.5) / 12);
      v.push(x);
    }
  });
  analysis.SERIES[L.k + "|" + rk] = { t, v };
  D[L.k].start = Math.min(D[L.k].start, Math.floor(t[0]));
  D[L.k].end = Math.max(D[L.k].end, Math.floor(t[t.length - 1]));
  sfx("chime");
  desktop.startCase({ v: L.k, r: rk, y0: r.y0, y1: r.y1 });
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
    setVB.t = setTimeout(placeFx, 140);
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
    <div class="rm-map" id="rm-mapc"><canvas class="rm-water" id="rm-water" aria-hidden="true"></canvas><svg id="rm-svg" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Trend map of Southeast Asia"></svg>
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
  if (!open.ro) {
    open.ro = new ResizeObserver(() => placeFx());
  }
  open.ro.observe($("#rm-mapc"));
  if (open.stopWater) open.stopWater();
  open.stopWater = startWater($("#rm-water"), () => ({ cell: 3, ox: 0, oy: 0 }));
  buildSvg();
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
  H.log && H.log(st.ssl ? `MAP: ECCO SEA LEVEL FOR ${st.ssl.tests} COASTAL CITIES LOADED.` : "MAP: SAMPLE DATA.");
}
const regionMap = { open };
export {
  regionMap
};
