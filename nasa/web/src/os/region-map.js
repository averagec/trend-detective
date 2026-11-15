import { SFX } from "../audio/sfx.js";
import { say } from "../ui/dialogue.js";
import { caseData } from "../data/case-data.js";
import { pixelWeather } from "./pixel-weather.js";
import { desktop } from "./desktop.js";
import { uiScale } from "../ui/scale.js";
import { openChart } from "../ui/chart-view.js";
import { glossaryFor } from "../data/glossary.js";
import { isSignificant, shortVerdict } from "../data/verdict-wording.js";
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
    real: true,
    noun: "sea level",
    upV: "rising",
    downV: "falling"
  },
  { k: "t2m", short: "TEMP", name: "Air temperature (2 m)", src: "MERRA-2 · NASA GES DISC", box: "merra2:t2m", unit: "°C", ud: "°C/dec", pal: "t", dp: 2, fxUp: "heat", fxDown: null, up: "Warmer", down: "Cooler", noun: "temperature", upV: "warming", downV: "cooling" },
  { k: "tsurf", short: "LAND T", name: "Land surface temperature", src: "MERRA-2 · NASA GES DISC", box: "merra2:tsurf", unit: "°C", ud: "°C/dec", pal: "t", dp: 2, fxUp: "heat", fxDown: null, up: "Warmer ground", down: "Cooler ground", noun: "land surface temperature", upV: "warming", downV: "cooling" },
  { k: "precip", short: "RAIN", name: "Rainfall", src: "MERRA-2 · NASA GES DISC", box: "merra2:precip", unit: "mm/day", ud: "mm/day per dec", pal: "w", dp: 2, fxUp: "rain", fxDown: "drought", up: "Wetter", down: "Drier", noun: "rainfall", upV: "getting wetter", downV: "getting drier" },
  { k: "qv2m", short: "HUMID", name: "Air humidity (2 m specific humidity)", src: "MERRA-2 · NASA GES DISC", box: "merra2:qv2m", unit: "g/kg", ud: "g/kg per dec", pal: "w", dp: 2, fxUp: null, fxDown: null, up: "More humid", down: "Less humid", noun: "humidity", upV: "getting more humid", downV: "getting less humid" },
  { k: "vpd", short: "VPD", name: "Dryness of the air (vapour pressure deficit)", src: "MERRA-2 · NASA GES DISC", box: "merra2:vpd", unit: "kPa", ud: "kPa per dec", pal: "t", dp: 3, fxUp: "drought", fxDown: null, up: "Drier air", down: "Moister air", noun: "vapour pressure deficit", upV: "getting drier", downV: "getting moister" },
  { k: "evap", short: "EVAP", name: "Surface evaporation", src: "MERRA-2 · NASA GES DISC", box: "merra2:evap", unit: "mm/day", ud: "mm/day per dec", pal: "w", dp: 2, fxUp: null, fxDown: null, up: "More evaporation", down: "Less evaporation", noun: "evaporation", upV: "evaporating more", downV: "evaporating less" }
];
const SSL_BINS = [30, 36, 42, 48];
const BOX_KEY = "se_asia_maritime", BOX = [95, -10, 141, 10];
const PAL = { s: ["#d8e6ee", "#9fd0e8", "#5aa6dd", "#2f6fc0", "#1c3d8c"], t: ["#1f4fa0", "#7fa8e8", "#c9c2b2", "#e9a93a", "#d94a36"], w: ["#8a5a2b", "#c9a46a", "#c9c2b2", "#7fc4a0", "#2f8f7a"] };
const GREY = "#56628a", VB = { world: [-4, -14, 368, 206], sea: [268, 58, 58, 52], idn: [273, 78, 50, 28] };
const st = { v: 0, city: -1, q: "", sat: false, dd: false, yr: null, more: false, f: 0, fx: true, c: -1, view: "world", map: null, data: null, rows: null, seen: {}, legend: -1, tool: false, drawing: null, circ: null, cells: null, cityRes: {} };
let W = null, H = null;
const $ = (s) => W.querySelector(s);
const ns = "http://www.w3.org/2000/svg";
const sfx = (k) => SFX[k] && SFX[k]();
const talk = (lines, key) => {
  if (key && st.seen[key]) return;
  if (key) st.seen[key] = 1;
  say(lines);
};
// The rows the map draws, one per country. They carry no statistics: every number on the map comes
// from the server (the sea level cells, the region boxes, the circle). Only the span is set here.
function compute() {
  const L = LAYERS[st.v], b = L.box && boxStat();
  st.rows = NAMES.map((n, ci) => ({ n, ci, na: "", neutral: true }));
  st.mxAbs = 1;
  st.span = L.real ? (st.ssl ? st.ssl.period.slice() : [1992, 2017]) : b ? [+b.first_period.slice(0, 4), +b.last_period.slice(0, 4)] : [0, 0];
  return st.rows;
}
const P = (lon, lat) => [lon + 180, 90 - lat];
function el(tag, attrs, parent) {
  const e = document.createElementNS(ns, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function dotScale() {
  const vb = st.vb || VB.sea, mc = W.querySelector("#rm-mapc"), px = mc ? mc.clientWidth || 1000 : 1000;
  return vb[2] / px;
}
function placeDots() {
  if (!st.ssl) return;
  const u = dotScale();
  W.querySelectorAll(".rm-city").forEach((d) => {
    const i = +d.dataset.i, r = (i === st.city ? 7 : d.classList.contains("cap") ? 5.5 : 4.5) * u;
    d.setAttribute("r", r.toFixed(4));
  });
  W.querySelectorAll(".rm-hit").forEach((d) => d.setAttribute("r", (12 * u).toFixed(4)));
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
  const pat3 = el("pattern", { id: "rmLand", width: 0.12, height: 0.12, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("rect", { width: 0.12, height: 0.12, fill: "#3d4c7c" }, pat3);
  el("rect", { width: 0.04, height: 0.12, fill: "#56628a" }, pat3);
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
  el("g", { id: "rm-boxg" }, svg);
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
      const d = el("circle", { cx: x, cy: y, r: 0.3, class: "rm-city", "data-i": i, "stroke-width": 1.5, "vector-effect": "non-scaling-stroke", role: "button", "aria-label": c.name }, cg);
      const hit = el("circle", { cx: x, cy: y, r: 0.6, class: "rm-hit", "data-i": i, fill: "transparent" }, cg);
      hit.onclick = (e) => {
        e.stopPropagation();
        if (!st.dragged && !st.tool) pickCity(i, true);
      };
      hit.onmousemove = (e) => cityTip(e, i);
      hit.onmouseleave = () => tip(null);
      d.onclick = (e) => {
        e.stopPropagation();
        if (!st.dragged) pickCity(i, true);
      };
      d.onmousemove = (e) => cityTip(e, i);
      d.onmouseleave = () => tip(null);
      const t = el("text", { x: x + 0.5, y: y - 0.35, class: "rm-clab", "data-i": i, "font-size": 0.85 }, cl);
      t.style.display = "none"; // hidden until cityLabels() sizes and places it
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
  drawBox();
  const fmt = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(L.sd < 1 ? 2 : 1);
  if (L.box) $("#rm-leg").innerHTML = `<i class="rm-sw" style="background:${PAL[L.pal][4]}"></i>clear rise<i class="rm-sw" style="background:${PAL[L.pal][0]}"></i>clear fall<i class="rm-sw" style="background:${GREY}"></i>no clear trend · one value for the box 95-141°E, 10°S-10°N`;
  else if (L.real) $("#rm-leg").innerHTML = `<span>&lt;${SSL_BINS[0]}</span><span class="rm-bins">${PAL.s.map((c, i) => `<span data-b="${i}" style="background:${c}" title="${sslRange(i)} mm per decade"></span>`).join("")}</span><span>&gt;${SSL_BINS[3]} mm/dec</span><i class="rm-sw" style="background:${GREY}"></i>no clear trend<i class="rm-sw rm-sw-in"></i>inland`;
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
  placeDots();
}
const KM_DEG = 111.32;
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
      const u = dotScale();
      t.setAttribute("x", (c.lon + 180 + 8 * u).toFixed(3));
      t.setAttribute("y", (90 - c.lat - 6 * u).toFixed(3));
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
  const c = st.ssl.cities[i], L = LAYERS[st.v];
  if (st.circ) {
    st.circ = null;
    circleDraw();
    placeFx();
  }
  // The layer the user chose stays. Sea level has its own city card; every other layer reads the grid cells around the city.
  st.city = i;
  st.c = -1;
  st.bx = false;
  if (L.real) {
    const k = cityState(c);
    sfx(k === "inland" ? "err" : "select");
    if (k === "sig") talk([`${c.name}. Up ${c.trend_mm_per_year.toFixed(1)} mm a year since ${st.ssl.period[0]}. That adds up.`, "Want a bigger picture? Press CIRCLE and drag over the sea around it."], "sig");
    else if (k === "ns") talk([`${c.name}. The sea climbs fast here too.`, "But it swings so much from year to year that I can’t prove it yet. That’s a different answer from no."], "ns");
    else talk(["Inland. The ocean data can’t speak for this one.", "I’m not inventing a number to fill the gap."], "inland");
  } else {
    sfx("select");
    talk([`${c.name}. Its number comes from the grid cells around it.`, "Each cell is about 55 km wide, so this is an area, not one spot."], "city-" + L.k);
  }
  if (fly) flyTo(cityBox(c));
  paint(false);
}
function cityBox(c) {
  const w = 7, h = w * VB.idn[3] / VB.idn[2], x = c.lon + 180, y = 90 - c.lat;
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
    ${st.more ? glossaryFor(["TREND", "95% RANGE", "OLS P", "MANN-KENDALL Q"]) : ""}
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
const coreText = (t, L) => t.replace(/^[a-z_0-9]+,/, L.name + ",").replace(/mm day-1/g, "mm/day").replace(/ K per decade/g, " °C per decade");
function boxStat() {
  const L = LAYERS[st.v];
  if (!L.box || !st.reg || !st.reg.layers[L.box]) return null;
  return st.reg.layers[L.box].regions.find((x) => x.key === BOX_KEY) || null;
}
// The box's verdict is the engine's: both tests below 0.05 after correction, slopes agreeing (ADR 0009).
const boxSig = (b) => !!b && b.status === "ok" && isSignificant(b.significance);
// The badge: the verdict in words, with the direction only when a trend is detected.
const badgeOf = (S, L) => (isSignificant(S) ? `TREND DETECTED · ${(S.verdict === "rise" ? L.up : L.down).toUpperCase()}` : shortVerdict(S));
const fmtBox = (v, L) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(L.dp);
function drawBox() {
  const g = W.querySelector("#rm-boxg");
  if (!g) return;
  g.innerHTML = "";
  const L = LAYERS[st.v], b = boxStat();
  if (!L.box || !b || st.f === 2 && boxSig(b) || st.f === 1 && !boxSig(b)) return;
  const col = boxSig(b) ? PAL[L.pal][b.slope_per_decade > 0 ? 4 : 0] : GREY;
  const [x0, y0] = P(BOX[0], BOX[3]), [x1, y1] = P(BOX[2], BOX[1]);
  const r = el("rect", { x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: col, "fill-opacity": st.bx ? 0.32 : 0.2, stroke: col, "stroke-width": 3, "stroke-dasharray": "8 5", "vector-effect": "non-scaling-stroke", class: "rm-box" }, g);
  r.onclick = (e) => {
    e.stopPropagation();
    if (st.dragged || st.tool) return;
    sfx("select");
    st.bx = true;
    st.city = -1;
    card();
    drawBox();
  };
  r.onmousemove = (e) => {
    const t = $("#rm-tip"), bb = $("#rm-mapc").getBoundingClientRect(), z = uiScale;
    t.innerHTML = `MARITIME SE ASIA BOX <b style="font-weight:400">${fmtBox(b.slope_per_decade, L)} ${L.ud}</b> <span class="dim">· click for the full result</span>`;
    t.style.display = "block";
    t.style.left = Math.min((e.clientX - bb.left) / z + 14, bb.width / z - t.offsetWidth - 6) + "px";
    t.style.top = (e.clientY - bb.top) / z + 16 + "px";
  };
  r.onmouseleave = () => tip(null);
  const lab = el("text", { x: x0 + 0.5, y: y0 + 1.6, class: "rm-boxlab", "font-size": 1.3 }, g);
  lab.textContent = `${L.short} ${fmtBox(b.slope_per_decade, L)} ${L.ud.toUpperCase()}${boxSig(b) ? "" : " · NO CLEAR TREND"}`;
}
// Monthly box series from the Python core, as decimal years (mid-month) for the same yearly-average code the cases use.
function boxSeries(b) {
  if (!b || !b.series) return null;
  const pts = b.series.filter((p) => p.value != null);
  return { t: pts.map((p) => +p.period.slice(0, 4) + (+p.period.slice(5, 7) - 1) / 12 + 1 / 24), v: pts.map((p) => p.value) };
}
function boxCard(box) {
  const L = LAYERS[st.v], b = boxStat(), ds = caseData.DATASETS[L.k], f = (v) => fmtBox(v, L), p = (v) => v < 1e-4 ? "< 0.0001" : v.toFixed(4);
  if (!b || !b.significance) {
    box.innerHTML = `<div class="hd"><h3>NO DATA</h3><button class="x" id="rm-close" aria-label="Close">×</button></div>`;
    box.querySelector("#rm-close").onclick = closeCard;
    return;
  }
  // The chart uses the same monthly series as the statistics above (regional_data.json, 1980 to 2018).
  const S = b.significance, sig = boxSig(b), ser = boxSeries(b), yrs = [];
  const qNote = S.family.name === "layer" ? ` The q-values are p-values corrected across the ${S.family.n_tests} regions tested together (Benjamini-Hochberg).` : "";
  if (ser) {
    const clim = Array(12).fill(0), n = Array(12).fill(0), mo = (t) => Math.min(11, Math.floor(t % 1 * 12)), by = {};
    ser.t.forEach((t, i) => {
      clim[mo(t)] += ser.v[i];
      n[mo(t)]++;
    });
    ser.t.forEach((t, i) => (by[Math.floor(t)] = by[Math.floor(t)] || []).push(ser.v[i] - clim[mo(t)] / n[mo(t)]));
    Object.keys(by).forEach((y) => by[y].length >= 6 && yrs.push([+y + 0.5, by[y].reduce((a, c) => a + c, 0) / by[y].length]));
  }
  const ym = yrs.length ? yrs.reduce((a, c) => a + c[0], 0) / yrs.length : 0, vm = yrs.length ? yrs.reduce((a, c) => a + c[1], 0) / yrs.length : 0;
  const line = (x, k) => vm + k / 10 * (x - ym);
  let spark = "";
  if (yrs.length > 2) {
    const Wd = 250, Hd = 70, lo = Math.min(...yrs.map((q) => q[1])), hi = Math.max(...yrs.map((q) => q[1])), pad = (hi - lo) * 0.15 || 1;
    const X = (x) => 8 + (x - yrs[0][0]) / (yrs[yrs.length - 1][0] - yrs[0][0]) * (Wd - 16), Y = (y) => Hd - 8 - (y - lo + pad) / (hi - lo + 2 * pad) * (Hd - 16);
    const d = yrs.map((q, i) => `${i && q[0] - yrs[i - 1][0] > 1.5 ? "M" : i ? "L" : "M"}${X(q[0]).toFixed(1)} ${Y(q[1]).toFixed(1)}`).join("");
    const a0 = yrs[0][0], a1 = yrs[yrs.length - 1][0];
    spark = `<svg class="rm-spark zoomable" id="rm-zoom" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none" role="button" tabindex="0" aria-label="Open the full chart"><path class="ln" d="${d}"/><path class="tr" d="M${X(a0)} ${Y(line(a0, b.slope_per_decade))}L${X(a1)} ${Y(line(a1, b.slope_per_decade))}"/></svg>
      <div class="zoom-hint">${Math.floor(a0)} · CLICK CHART TO ENLARGE · ${Math.floor(a1)}</div>`;
  }
  const warn = (S.warnings || []).map((w) => w.text).join(" ");
  box.innerHTML = `<div class="hd"><h3>MARITIME SE ASIA</h3><button class="x" id="rm-close" aria-label="Close">×</button></div>
    <div class="sub">${L.name.toUpperCase()} · ${b.first_period} TO ${b.last_period} · MONTHLY</div>
    <div class="big"><b>${f(b.slope_per_decade)}</b><span>${L.ud.replace("/dec", " / decade").replace(" per dec", " per decade")}</span></div>
    <span class="rm-verd" style="background:${sig ? "var(--grn)" : "var(--mus)"}">${badgeOf(S, L)}</span>
    ${spark}
    <table class="rm-tab">
      <tr><td>95% range</td><td>${f(b.ci_low)} to ${f(b.ci_high)}</td></tr>
      <tr><td>OLS q (corrected)</td><td>${p(S.ols_q)}</td></tr>
      <tr><td>Mann-Kendall q (corrected)</td><td>${p(S.mk_q)}</td></tr>
    </table>
    <button class="rm-more" id="rm-more" aria-expanded="${st.more}">${st.more ? "▾ Fewer stats" : "▸ More stats"}</button>
    ${st.more ? `<table class="rm-tab">
      <tr><td>Sen's slope</td><td>${f(b.sen_per_decade)}</td></tr>
      <tr><td>Mann-Kendall p (autocorrelation-adjusted, before correction)</td><td>${p(S.mk_p_ar1)}</td></tr>
      <tr><td>Regions corrected together</td><td>${S.family.n_tests ?? "none"}</td></tr>
      <tr><td>Month-to-month memory</td><td>r1 = ${b.noise_lag1.toFixed(2)}</td></tr>
      <tr><td>Years to see it</td><td>${b.years_needed_90 ? `about ${Math.round(b.years_needed_90)} (have ${Math.floor(b.n_years)})` : "n/a"}</td></tr>
      <tr><td>Grid cells</td><td>${b.cells_in_box}</td></tr></table>` : ""}
    <div class="rm-note">${coreText(S.sentence, L)} ${warn}</div>
    <div class="rm-note">${S.explanation}</div>
    <div class="rm-note">One average over the box 95-141°E, 10°S-10°N (land and sea). It does not say which island changed most.${qNote}</div>
    <div class="rm-note">NASA DATA · ${L.src}</div>
    ${ds ? `<button class="obtn" id="rm-open">INVESTIGATE AS A CASE ▸</button>` : ""}`;
  box.querySelector("#rm-close").onclick = closeCard;
  box.querySelector("#rm-more").onclick = () => {
    st.more = !st.more;
    sfx("select");
    card();
  };
  const ob = box.querySelector("#rm-open");
  if (ob) ob.onclick = () => {
    sfx("chime");
    desktop.startCase({ v: L.k, r: "idn", y0: ds.start, y1: ds.end });
  };
  const zs = box.querySelector("#rm-zoom");
  if (zs) zs.onclick = () => {
    sfx("select");
    openChart({
      title: `MARITIME SE ASIA · ${L.name.toUpperCase()}`,
      sub: `${b.first_period} TO ${b.last_period} · DIFFERENCE FROM THE AVERAGE FOR THAT MONTH, YEARLY · ${badgeOf(S, L)}`,
      unit: `${L.unit} vs normal`,
      zero: true,
      series: yrs,
      seriesLabel: "Yearly average, seasons removed (years with 6+ months)",
      fit: [[yrs[0][0], line(yrs[0][0], b.slope_per_decade)], [yrs[yrs.length - 1][0], line(yrs[yrs.length - 1][0], b.slope_per_decade)]],
      fitLabel: `Trend ${f(b.slope_per_decade)} ${L.ud} (Python core, OLS on monthly values)`,
      band: [yrs[0][0], ym, yrs[yrs.length - 1][0]].map((x) => [x, Math.min(line(x, b.ci_low), line(x, b.ci_high)), Math.max(line(x, b.ci_low), line(x, b.ci_high))]),
      bandLabel: "Lines inside the 95% range",
      dp: L.dp,
      stats: [["TREND", `${f(b.slope_per_decade)} ${L.ud}`], ["95% RANGE", `${f(b.ci_low)} to ${f(b.ci_high)}`], ["OLS Q", p(S.ols_q)], ["MANN-KENDALL Q", p(S.mk_q)], ["MONTHS", `${b.n_points}`], ["VERDICT", shortVerdict(S)]],
      notes: [coreText(S.sentence, L), S.explanation, "The trend line is the core's slope drawn through the middle of the yearly averages, for reading only.", warn].filter(Boolean),
      source: L.src
    });
  };
}
const FXTXT = { rain: () => "Heavier rain", storm: () => "Stronger storms", drought: (L) => L.k === "t2m" ? "Heat, drought" : "Drought" };
function fxOf(r) {
  if (!r || r.na || r.neutral || !(r.det || r.sus)) return null;
  const k = LAYERS[st.v].k, b = r.bin;
  if (k === "t2m") return b === 4 ? "drought" : null;
  if (k === "precip") return b === 4 ? "storm" : b === 3 ? "rain" : b <= 1 ? "drought" : null;
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
  const BL = LAYERS[st.v], bs = BL.box && boxStat();
  st.boxDry = null;
  if (bs && boxSig(bs) && st.f !== 2) {
    const kind = bs.slope_per_decade > 0 ? BL.fxUp : BL.fxDown;
    if (kind === "drought") st.boxDry = pixelWeather.drought(["Indonesia", "Malaysia", "Philippines"].map((n) => mask(st.map.sea[n])), GW, GH);
    else if (kind) [[101.5, 0.5], [114, 1], [120.8, -2.6], [110.6, -7.4], [138.5, -4.6], [124.8, 7.4], [104, -4.2], [117, -8.4]].forEach((ll) => {
      const [ax, ay] = toCell(ll);
      if (ax < 0 || ay < 0 || ax >= GW || ay >= GH || sp.length >= 8 || sp.some((q) => Math.abs(q.ax - ax) < 18 && Math.abs(q.ay - ay) < 18)) return;
      sp.push({ t: kind, ax, ay });
    });
  }
  const sel = st.city >= 0 && st.ssl ? st.ssl.cities[st.city] : null;
  const inRing = (c) => sel && Math.hypot((c.lon - sel.lon) * Math.cos(sel.lat * Math.PI / 180), c.lat - sel.lat) * KM_DEG < 60;
  if (LAYERS[st.v].real && st.ssl && !st.tool && !st.circ) {
    st.ssl.cities.map((c, i) => [c, i]).filter(([c, i]) => i !== st.city && !inRing(c) && cityState(c) === "sig" && !W.querySelector(`.rm-city[data-i="${i}"]`).classList.contains("fade")).sort((a, b) => b[0].population - a[0].population).forEach(([c]) => {
      const [ax, ay] = toCell([c.lon, c.lat]);
      if (ax < 0 || ay < 0 || ax >= GW || ay >= GH) return;
      if (sp.length >= 8 || sp.some((q) => Math.abs(q.ax - ax) < 17 && Math.abs(q.ay - ay) < 20)) return;
      sp.push({ t: "flood", ax: ax + 9, ay: ay + 1 });
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
    if (st.boxDry) pixelWeather.paintDrought(img, st.boxDry, f);
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
  if (LAYERS[st.v].box) {
    const L = LAYERS[st.v], b = boxStat();
    $("#rm-hud").innerHTML = b ? `${L.name.toUpperCase()} · MARITIME SE ASIA BOX · <b>${fmtBox(b.slope_per_decade, L)} ${L.ud}</b> · ${boxSig(b) ? (b.slope_per_decade > 0 ? L.up.toUpperCase() : L.down.toUpperCase()) : "NO CLEAR TREND"} · ${st.span[0]}-${st.span[1]}` : `${L.name.toUpperCase()} · DATA MISSING`;
    return;
  }
  const rows = st.rows, L = LAYERS[st.v], det = rows.filter((r) => r.det).length, sus = rows.filter((r) => r.sus).length, nn = rows.filter((r) => !r.na).length;
  $("#rm-hud").innerHTML = `${L.name.toUpperCase()} · <b>${det} of ${nn}</b> clear${sus ? ` · <span class="c">${sus} caution</span>` : ""}`;
}
function toolbar() {
  const locked = LAYERS.filter((L) => L.lock);
  $("#rm-bar").innerHTML = `<div class="rm-seg" role="group" aria-label="Layer">${LAYERS.map((L, i) => L.lock ? "" : `<button data-l="${i}" class="${i === st.v ? "on" : ""}" title="${L.name} · ${L.src}"><i style="background:${PAL[L.pal][4]}"></i>${L.short}</button>`).join("")}${locked.length ? `<button class="lk" data-lock title="${locked.map((L) => `${L.name}: locked until ${L.lock}`).join("\n")}">+${locked.length} LOCKED</button>` : ""}</div>
    <span class="rm-fixed" title="Trends are computed once over the full record by the Python core">FULL RECORD</span>
    <span class="rm-yrs" id="rm-yrs">${st.span[0]}-${st.span[1]}</span>
    <div class="rm-dd" id="rm-dd"><button class="rm-ddb${st.city >= 0 ? " on" : ""}" id="rm-ddb" aria-haspopup="listbox" aria-expanded="false"><i class="pin"></i><span>${st.city >= 0 && st.ssl ? st.ssl.cities[st.city].name.toUpperCase() : "CITIES"}</span><b>▾</b></button>
      <div class="rm-ddp" id="rm-ddp" hidden><input id="rm-q" type="search" placeholder="Type a city or province" autocomplete="off" aria-label="Search a city or province" value="${st.q.replace(/"/g, "&quot;")}"><div class="rm-res" id="rm-res" role="listbox"></div></div></div>
    <div class="rm-seg" role="group" aria-label="Show">${["ALL", "TREND", "NONE"].map((t, i) => `<button data-f="${i}" class="${i === st.f ? "ink" : ""}">${t}</button>`).join("")}</div>
    <button class="rm-chip${st.fx ? " on" : ""}" data-fx title="Weather effects">FX ${st.fx ? "ON" : "OFF"}</button>
    <button class="rm-chip rm-circb${st.tool ? " on" : ""}" data-circ title="Draw a circle: press on the map and drag" aria-pressed="${st.tool}"><i class="ci"></i>CIRCLE</button>
    <button class="rm-chip${st.sat ? " on" : ""}" data-sat title="NASA GIBS Blue Marble imagery">SAT ${st.sat ? "ON" : "OFF"}</button>`;
  W.querySelectorAll("[data-l]").forEach((b) => b.onclick = () => {
    st.v = +b.dataset.l;
    if (LAYERS[st.v].box && !st.circ) talk(["This one is a single box over the whole region. Indonesia, Malaysia, the Philippines.", "One honest number for the box. Not city by city. The grid is too coarse for that."], "box");
    st.yr = null;
    st.bx = false;
    st.c = -1;
    sfx("select");
    paint(true);
    if (st.circ && st.circ.r) circleResult();
  });
  const lk = W.querySelector("[data-lock]");
  if (lk) lk.onclick = () => sfx("err");
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
  W.querySelector("[data-circ]").onclick = () => circleTool(!st.tool);
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
function card() {
  const box = $("#rm-pv"), L = LAYERS[st.v];
  W.querySelector("#rm-selg").innerHTML = "";
  if (st.circ && st.circ.res && st.circ.res.layer === L.k && cellLayer()) {
    circleCard(box);
    return;
  }
  if (L.real) {
    box.hidden = st.city < 0;
    if (st.city >= 0) cityCard(box);
    return;
  }
  if (st.city >= 0 && st.ssl) {
    cityLayerCard(box);
    return;
  }
  if (L.box) {
    box.hidden = !st.bx;
    if (st.bx) boxCard(box);
    return;
  }
  box.hidden = true;
}
function closeCard() {
  st.c = -1;
  st.bx = false;
  if (st.circ) {
    st.circ = null;
    circleDraw();
    placeFx();
  }
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
  placeDots();
  circleDraw();
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
    let drag = null;
  mc.addEventListener("pointerdown", (e) => {
    if (st.tool) return circleDown(e);
    if (st.view === "world" || e.button !== 0 || e.target.closest("button,.rm-tip,.rm-float")) return;
    drag = { x: e.clientX, y: e.clientY, vb: (st.vb || VB.sea).slice(), k: $("#rm-svg").getScreenCTM().a, moved: false };
    st.dragged = false;
  });
  mc.addEventListener("pointermove", (e) => {
    if (st.drawing) return circleMove(e);
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
  mc.addEventListener("pointerup", (e) => {
    if (st.drawing) return circleUp(e);
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
async function loadReg() {
  if (st.reg) return;
  try {
    const r = await fetch("data/regional_data.json");
    if (r.ok) st.reg = await r.json();
  } catch (e) {
    st.reg = null;
  }
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
  await Promise.all([loadReg(), loadCells()]);
  if (!st.reg) LAYERS.forEach((L) => L.box && !L.lock && (L.lock = "regional_data.json (run scripts/export_regional.py)"));
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
  if (st.ssl) setTimeout(() => talk([`${st.ssl.cities.length} cities. ${st.ssl.tests} of them on the coast.`, "Click a city dot. Or press CIRCLE and drag on the map to draw your own area."], "map"), 2900);
  H.log && H.log(st.ssl ? `MAP: ECCO SEA LEVEL FOR ${st.ssl.tests} COASTAL CITIES LOADED.` : "MAP: SAMPLE DATA.");
}
// CIRCLE tool (like Earthdata Search): press the CIRCLE button, then press on the map and drag
// to draw. Every number shown comes from scripts/export_cells.py (core statistics per ECCO cell,
// Benjamini-Hochberg across all cells). The page only counts, lists and averages for the chart.
async function loadCells() {
  if (st.cells) return;
  try {
    const r = await fetch("data/indonesia_cells.json");
    if (r.ok) st.cells = await r.json();
  } catch (e) {
    st.cells = null;
  }
}
function cellLayer() {
  const D = st.cells && st.cells.layers && st.cells.layers[LAYERS[st.v].k];
  if (!D) return null;
  if (!D.list) {
    D.list = [];
    let k = 0;
    D.lat.forEach((la) => D.lon.forEach((lo) => {
      if (D.slope_per_decade[k] != null) D.list.push({ k, lat: la, lon: lo });
      k++;
    }));
  }
  return D;
}
function kmBetween(la1, lo1, la2, lo2) {
  const r = Math.PI / 180, a = Math.sin((la2 - la1) * r / 2) ** 2 + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin((lo2 - lo1) * r / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(a)));
}
function toast(msg, bad) {
  const mc = $("#rm-mapc");
  let t = $("#rm-toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "rm-toast";
    t.setAttribute("role", "alert");
    mc.appendChild(t);
  }
  t.className = "rm-toast" + (bad ? " bad" : "") + " on";
  t.innerHTML = msg;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => t.classList.remove("on"), bad ? 6000 : 4000);
}
function circleTool(on) {
  st.tool = on;
  st.drawing = null;
  sfx("select");
  placeFx();
  $("#rm-mapc").classList.toggle("drawing", on);
  if (on) {
    if (st.view === "world") zoom("idn");
    toast("<b>DRAW A CIRCLE</b> Press on the map and drag outwards. 75 to 250 km. Esc to cancel.");
  } else {
    const t = $("#rm-toast");
    if (t) t.classList.remove("on");
  }
  const b = W.querySelector("[data-circ]");
  if (b) {
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on);
  }
}
function circleDown(e) {
  if (e.button !== 0 || e.target.closest("button,.rm-float,.rm-card,.rm-zoom")) return;
  e.preventDefault();
  const p = toUnits(e);
  st.drawing = { lon: p.x - 180, lat: 90 - p.y };
  st.circ = { lon: st.drawing.lon, lat: st.drawing.lat, r: 0 };
  $("#rm-mapc").setPointerCapture(e.pointerId);
  tip(null);
  circleDraw();
}
function circleMove(e) {
  const p = toUnits(e), d = st.drawing;
  st.circ = { lon: d.lon, lat: d.lat, r: kmBetween(d.lat, d.lon, 90 - p.y, p.x - 180) };
  circleDraw();
}
function circleUp() {
  st.drawing = null;
  st.dragged = true;
  setTimeout(() => st.dragged = false, 0);
  if (!st.circ || st.circ.r < 8) {
    st.circ = null;
    circleDraw();
    toast("Press and <b>drag</b> to set the size of the circle.", true);
    return;
  }
  circleTool(false);
  circleResult();
}
function circleLimits() {
  return st.cells && st.cells.radius_km ? st.cells.radius_km : [75, 250];
}
function circleDraw() {
  const g = W && W.querySelector("#rm-circg");
  if (!g) return;
  g.innerHTML = "";
  W.querySelectorAll(".rm-city.in").forEach((d) => d.classList.remove("in"));
  const c = st.circ;
  if (!c) return;
  const [lo, hi] = circleLimits(), bad = c.r < lo || c.r > hi, ry = c.r / KM_DEG, rx = ry / Math.cos(c.lat * Math.PI / 180), [cx, cy] = P(c.lon, c.lat), u = dotScale();
  el("ellipse", { cx, cy, rx, ry, class: "rm-circ" + (bad ? " bad" : ""), "vector-effect": "non-scaling-stroke" }, g);
  el("circle", { cx, cy, r: 3 * u, class: "rm-circc" }, g);
  if (c.r > 0) {
    el("line", { x1: cx, y1: cy, x2: cx + rx, y2: cy, class: "rm-circr", "vector-effect": "non-scaling-stroke" }, g);
    const t = el("text", { x: cx + rx / 2, y: cy - 5 * u, class: "rm-circt" + (bad ? " bad" : ""), "font-size": (15 * u).toFixed(4), "stroke-width": (3 * u).toFixed(4) }, g);
    t.textContent = `${Math.round(c.r)} KM`;
  }
  if (st.ssl) st.ssl.cities.forEach((ct, i) => {
    if (kmBetween(c.lat, c.lon, ct.lat, ct.lon) <= c.r) {
      const d = W.querySelector(`.rm-city[data-i="${i}"]`);
      if (d) d.classList.add("in");
    }
  });
}
async function circleResult() {
  const c = st.circ, L = LAYERS[st.v], D = cellLayer(), [lo, hi] = circleLimits(), R = Math.round(c.r), need = st.cells ? st.cells.min_cells : 4;
  c.res = null;
  if (!st.cells) {
    toast("<b>NO CELL FILE</b> indonesia_cells.json is missing, so the circle cannot be read.", true);
    circleDraw();
    card();
    return;
  }
  if (c.r < lo) {
    sfx("err");
    toast(`<b>CIRCLE TOO SMALL</b> ${R} km. Draw at least ${lo} km from the centre. NASA's grid cells are about 55 km wide, so a smaller circle holds too few of them to say anything.`, true);
    circleDraw();
    card();
    return;
  }
  if (c.r > hi) {
    sfx("err");
    toast(`<b>CIRCLE TOO BIG</b> ${R} km. Keep it under ${hi} km. A bigger circle mixes very different places into one answer.`, true);
    circleDraw();
    card();
    return;
  }
  if (!D) {
    sfx("err");
    // Name the layers that do have grid cells, so the message says what to switch to.
    const withGrid = LAYERS.filter((x) => !x.lock && st.cells && st.cells.layers && st.cells.layers[x.k]).map((x) => x.short);
    toast(`<b>NO GRID CELLS FOR ${L.short} YET</b> A circle needs grid cells for ${L.noun}, and this build does not have them for ${L.short.toLowerCase()}. Layers with grid cells: ${withGrid.join(", ") || "none"}. Or click the box.`, true);
    circleDraw();
    card();
    return;
  }
  // The server takes the cells of THIS layer whose centre is inside the circle and judges them
  // together: one family, both tests, corrected for the cells in this circle only (POST
  // /api/cell-circle, ADR 0009). The page decides nothing statistical; it draws what comes back.
  let J;
  try {
    const r = await fetch("api/cell-circle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layer: L.k, lat: c.lat, lon: c.lon, radius_km: c.r }),
    });
    J = await r.json().catch(() => null);
    if (!r.ok) J = { failed: true, error: (J && J.error) || `Request failed (${r.status})` };
  } catch (e) {
    J = { failed: true, error: "Cannot reach the analysis server. Is it running?" };
  }
  if (st.circ !== c) return; // a newer circle was drawn while this one was being judged
  if (J.failed) {
    sfx("err");
    const inBox = c.lon >= D.lon[0] - 1 && c.lon <= D.lon[D.lon.length - 1] + 1 && c.lat >= D.lat[0] - 1 && c.lat <= D.lat[D.lat.length - 1] + 1;
    const why = L.real ? "Sea level only exists at sea: draw the circle over the coast or the water." : "Draw the circle over Indonesia.";
    toast(/at least/.test(J.error)
      ? (inBox ? `<b>NOT ENOUGH DATA</b> ${J.error}. ${why}` : "<b>OUTSIDE OUR DATA AREA</b> Draw the circle over Indonesia.")
      : `<b>CIRCLE NOT READ</b> ${J.error}`, true);
    circleDraw();
    card();
    return;
  }
  const cities = st.ssl ? st.ssl.cities.map((ct, i) => [ct, i]).filter(([ct]) => kmBetween(c.lat, c.lon, ct.lat, ct.lon) <= c.r) : [];
  const tt = $("#rm-toast");
  if (tt) tt.classList.remove("on");
  c.res = areaResult(J, D, cities, L.k);
  sfx("chime");
  st.city = -1;
  st.bx = false;
  circleDraw();
  card();
  placeFx();
  if (!st.seen["circle" + L.k]) {
    st.seen["circle" + L.k] = 1;
    const word = up >= down ? L.upV : L.downV;
    say(["Switch the layer and the same circle tells a different story."]);
  }
}
// The server's verdicts for one area, turned into the numbers the cards show. Nothing is judged here.
function areaResult(J, D, cities, layer) {
  const cells = J.cells, up = J.counts.rise, down = J.counts.fall, unclear = J.counts.unclear;
  const sl = cells.map((q) => q.slope_per_decade).filter((v) => v != null).sort((a, b) => a - b), med = sl[Math.floor(sl.length / 2)];
  const years = D.yearly_anomaly[cells[0].k].length, yrs = [];
  for (let y = 0; y < years; y++) {
    let sw = 0, sv = 0;
    cells.forEach((q) => {
      const v = D.yearly_anomaly[q.k][y], w = Math.cos(q.lat * Math.PI / 180);
      if (v != null) {
        sv += v * w;
        sw += w;
      }
    });
    if (sw) yrs.push([D.period[0] + y + 0.5, sv / sw]);
  }
  return { layer, n: J.cells_inside, up, down, unclear, flat: J.cells_inside - up - down, min: sl[0], max: sl[sl.length - 1], med, yrs, cities, note: J.note };
}
// A city on a layer other than sea level: the trend of the grid cells around it, judged the way a CIRCLE is.
const CITY_RADII = [75, 150, 250];
// The key of a city in cases_data.json (scripts/export_indonesia.py, export_city_cases.py).
const citySlug = (name) => name.toLowerCase().replace(/[^a-z0-9]/g, "");
function cityLayerCard(box) {
  const c = st.ssl.cities[st.city], L = LAYERS[st.v], D = cellLayer(), key = `${st.city}|${L.k}`;
  const selg = W.querySelector("#rm-selg"), [px, py] = P(c.lon, c.lat);
  const head = (sub) => `<div class="hd"><h3>${c.name.toUpperCase()}</h3><button class="x" id="rm-close" aria-label="Close">×</button></div><div class="sub">${sub}</div>`;
  box.hidden = false;
  el("circle", { cx: px, cy: py, r: (0.9 * Math.min(1, (st.vb || VB.sea)[2] / VB.sea[2])).toFixed(3), class: "rm-pulse", "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, selg);
  if (!D) {
    box.innerHTML = head(L.name.toUpperCase()) + `<div class="rm-note">This build has no grid cells for ${L.noun} yet, so ${c.name} has no number on this layer. Pick another layer.</div>`;
    box.querySelector("#rm-close").onclick = closeCard;
    return;
  }
  if (!st.cityRes[key]) loadCityArea(st.city, c, L, D);
  const g = st.cityRes[key];
  if (g.pending) box.innerHTML = head(L.name.toUpperCase() + " · READING THE GRID CELLS") + `<div class="rm-note">Reading the grid cells around ${c.name}…</div>`;
  else if (g.failed) box.innerHTML = head(L.name.toUpperCase()) + `<div class="rm-note" style="color:var(--red)">${g.error}</div>`;
  else {
    areaCard(box, { kind: "city", name: c.name, lat: c.lat, lon: c.lon, r: g.R, res: g.res, caseKey: c.case || citySlug(c.name) });
    return;
  }
  box.querySelector("#rm-close").onclick = closeCard;
}
// Asks the same server endpoint as a CIRCLE, centred on the city. 75 km first; wider only when too few cells have data.
async function loadCityArea(i, c, L, D) {
  const key = `${i}|${L.k}`;
  st.cityRes[key] = { pending: true };
  let out = null;
  for (const R of CITY_RADII) {
    let J = null;
    try {
      const r = await fetch("api/cell-circle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ layer: L.k, lat: c.lat, lon: c.lon, radius_km: R }),
      });
      J = await r.json().catch(() => null);
      if (r.ok) {
        out = { R, res: areaResult(J, D, [], L.k) };
        break;
      }
      out = { failed: true, error: (J && J.error) || `Request failed (${r.status})` };
    } catch (e) {
      out = { failed: true, error: "Cannot reach the analysis server. Is it running?" };
      break;
    }
    if (!/at least/.test(out.error)) break;
  }
  if (out.failed && /at least/.test(out.error)) out.error = `Too few grid cells with data within ${CITY_RADII[CITY_RADII.length - 1]} km of ${c.name} for ${L.noun}.`;
  st.cityRes[key] = out;
  if (st.city === i && LAYERS[st.v].k === L.k) card();
}
function circleCard(box) {
  areaCard(box, st.circ);
}
// One card for an area read from the grid cells: a drawn CIRCLE, or a city's surroundings (kind "city", with a name).
function areaCard(box, c) {
  const r = c.res, L = LAYERS[st.v], D = cellLayer(), dp = L.real ? 0 : L.dp, ud = L.real ? "mm/dec" : L.ud, city = c.kind === "city";
  // A city on a layer that has case data for it can be investigated as a case (SETUP > LINEUP).
  const caseSet = city && caseData.DATASETS[L.k], caseReg = caseSet && caseSet.regions[c.caseKey];
  const f = (v) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(dp), ll = (v, a, b) => `${Math.abs(v).toFixed(2)}°${v >= 0 ? a : b}`;
  const upW = L.upV, downW = L.downV;
  const Wd = 250, Hd = 70, vals = r.yrs, lo = Math.min(...vals.map((q) => q[1])), hi = Math.max(...vals.map((q) => q[1])), pad = (hi - lo) * 0.15 || 1;
  const X = (x) => 8 + (x - vals[0][0]) / (vals[vals.length - 1][0] - vals[0][0]) * (Wd - 16), Y = (y) => Hd - 8 - (y - lo + pad) / (hi - lo + 2 * pad) * (Hd - 16);
  const line = vals.map((q, i) => `${i && q[0] - vals[i - 1][0] > 1.5 ? "M" : i ? "L" : "M"}${X(q[0]).toFixed(1)} ${Y(q[1]).toFixed(1)}`).join("");
  const main = r.down > r.up ? r.down : r.up, mainW = r.down > r.up ? downW : upW;
  const verdict = main > r.n / 2 ? `MOSTLY ${mainW.toUpperCase()} CLEARLY` : main ? `PARTLY ${mainW.toUpperCase()} CLEARLY` : "NO CLEAR TREND";
  const cityRows = r.cities.length ? r.cities.map(([ct, i]) => {
    const k = cityState(ct), v = !L.real ? "open city" : k === "inland" ? "inland" : `${ct.trend_mm_per_decade >= 0 ? "+" : "−"}${Math.abs(ct.trend_mm_per_decade).toFixed(0)} mm/dec${k === "sig" ? "" : " · not clear yet"}`;
    return `<button class="rm-cc" data-ci="${i}"><span>${ct.name}</span><small>${v}</small></button>`;
  }).join("") : '<div class="rm-note" style="margin:2px 0">No study city inside this circle.</div>';
  box.hidden = false;
  box.innerHTML = `<div class="hd"><h3>${city ? `${c.name.toUpperCase()} · ` : "CIRCLE · "}${Math.round(c.r)} KM</h3><button class="x" id="rm-close" aria-label="Close">×</button></div>
    <div class="sub">${L.name.toUpperCase()} · ${D.period[0]}-${D.period[1]} · ${city ? "AROUND THE CITY" : `CENTRE ${ll(c.lat, "N", "S")} ${ll(c.lon, "E", "W")}`}</div>
    ${city ? `<div class="big"><b>${f(r.med)}</b><span>${ud} · middle grid cell</span></div>` : `<div class="big"><b>${main}</b><span>of ${r.n} grid cells ${mainW} clearly</span></div>`}
    <span class="rm-verd" style="background:${main > r.n / 2 ? "var(--grn)" : "var(--mus)"}">${verdict}</span>
    <svg class="rm-spark zoomable" id="rm-zoom" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none" role="button" tabindex="0" aria-label="Open the full chart"><path class="ln" d="${line}"/></svg>
    <div class="zoom-hint">${D.period[0]} · AVERAGE OF THE CELLS · CLICK TO ENLARGE · ${D.period[1]}</div>
    <table class="rm-tab">
      <tr><td>Cell trends</td><td>${f(r.min)} to ${f(r.max)} ${ud}</td></tr>
      <tr><td>Middle cell</td><td>${f(r.med)} ${ud}</td></tr>
      <tr><td>Clearly up / down / not clear</td><td>${r.up} / ${r.down} / ${r.flat}</td></tr>
      ${r.unclear ? `<tr><td>Unclear (one test only)</td><td>${r.unclear}</td></tr>` : ""}
    </table>
    ${r.up && r.down ? '<div class="rm-note" style="color:var(--red)">Cells disagree: some go up and some go down clearly. Look at them separately before trusting one number.</div>' : ""}
    ${city ? `<div class="rm-note">${c.name} has no grid cell of its own. This is the set of ${r.n} cells whose centre lies within ${Math.round(c.r)} km of it.${c.r > CITY_RADII[0] ? " The area is wider than 75 km because fewer cells had data closer in." : ""}</div>` : `<div class="rm-sec">CITIES INSIDE (${r.cities.length})</div>
    <div class="rm-ccs">${cityRows}</div>`}
    <div class="rm-note">${r.note}</div>
    <div class="rm-note">NASA DATA · ${D.dataset}</div>
    ${caseReg ? `<div class="rm-note">CASE DATA · ${caseReg.long}</div><button class="obtn" id="rm-case">INVESTIGATE AS A CASE ▸</button>` : `<button class="obtn" id="rm-redraw">${city ? "DRAW A CIRCLE HERE" : "DRAW ANOTHER CIRCLE"} ▸</button>`}`;
  box.querySelector("#rm-close").onclick = closeCard;
  const rc = box.querySelector("#rm-case"), rd = box.querySelector("#rm-redraw");
  if (rc) rc.onclick = () => {
    sfx("chime");
    desktop.startCase({ v: L.k, r: c.caseKey, y0: caseSet.start, y1: caseSet.end });
  };
  if (rd) rd.onclick = () => circleTool(true);
  box.querySelectorAll(".rm-cc").forEach((b) => b.onclick = () => {
    st.circ = null;
    circleDraw();
    pickCity(+b.dataset.ci, true);
  });
  const zs = box.querySelector("#rm-zoom"), open1 = () => {
    sfx("select");
    openChart({
      title: `${city ? c.name.toUpperCase() : "CIRCLE"} · ${Math.round(c.r)} KM · ${L.name.toUpperCase()}`,
      sub: `${city ? "AROUND THE CITY" : `CENTRE ${ll(c.lat, "N", "S")} ${ll(c.lon, "E", "W")}`} · AVERAGE OF ${r.n} GRID CELLS · YEARLY, SEASONS REMOVED`,
      unit: `${D.unit} vs normal`,
      series: vals,
      seriesLabel: `Average of the ${r.n} grid cells inside the circle`,
      zero: true,
      dp: L.real ? 1 : 2,
      stats: [["GRID CELLS INSIDE", `${r.n}`], [`${upW.toUpperCase()} CLEARLY`, `${r.up}`], [`${downW.toUpperCase()} CLEARLY`, `${r.down}`], ["NO CLEAR TREND", `${r.flat - r.unclear}`], ["UNCLEAR (ONE TEST ONLY)", `${r.unclear}`], ["CELL TRENDS", `${f(r.min)} to ${f(r.max)} ${ud}`], ["MIDDLE CELL", `${f(r.med)} ${ud}`]],
      notes: ["The line is the cells' yearly average, drawn for reading. The trend numbers come from each cell's own test in the Python core, not from this line.", r.note],
      source: D.dataset
    });
  };
  zs.onclick = open1;
  zs.onkeydown = (e) => e.key === "Enter" && open1();
}
addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !W || !W.isConnected || !st.tool) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  if (st.drawing) {
    st.drawing = null;
    st.circ = null;
    circleDraw();
  }
  circleTool(false);
}, true);
const regionMap = { open };
export {
  regionMap
};
