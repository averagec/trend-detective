import { SFX } from "../audio/sfx.js";
import { say } from "../ui/dialogue.js";
import { analysis } from "../stats/trend-analysis.js";
import { pixelWeather } from "./pixel-weather.js";
import { desktop } from "./desktop.js";
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
    k: "t2m",
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
const WINS = [["FULL", 0], ["20 Y", 20], ["10 Y", 10]];
const PAL = { t: ["#1f4fa0", "#7fa8e8", "#c9c2b2", "#e9a93a", "#d94a36"], w: ["#8a5a2b", "#c9a46a", "#c9c2b2", "#7fc4a0", "#2f8f7a"] };
const GREY = "#56628a", VB = { world: [-4, -14, 368, 206], sea: [268, 58, 58, 52] };
const st = { v: 0, w: 0, yr: null, f: 0, fx: true, c: -1, view: "world", map: null, data: null, rows: null, seen: {}, legend: -1 };
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
  const li = st.v, L = LAYERS[li], [lo, hi0] = span(li);
  let y0 = lo, hi = hi0;
  if (st.yr) {
    y0 = Math.max(lo, Math.min(st.yr[0], hi0 - 9));
    hi = Math.min(hi0, Math.max(st.yr[1], y0 + 9));
  } else if (WINS[st.w][1]) y0 = Math.max(lo, hi0 - WINS[st.w][1] + 1);
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
    p.setAttribute("fill", r.na ? "url(#rmNA)" : r.col);
    p.classList.toggle("na", !!r.na);
  });
  fades();
  hud();
  clearTimeout(paint.t);
  paint.t = setTimeout(placeFx, sweep ? 650 : 0);
  const fmt = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(L.sd < 1 ? 2 : 1);
  $("#rm-leg").innerHTML = `<div><div>TREND, ${L.ud}</div><div class="rm-bins">${PAL[L.pal].map((c, i) => `<span data-b="${i}" style="background:${c}" title="${["strong fall", "fall", "flat", "rise", "strong rise"][i]}"></span>`).join("")}</div>
    <div class="rm-tk"><span>${fmt(-st.mxAbs)}</span><span>0</span><span>${fmt(st.mxAbs)}</span></div></div>
    <div><span class="rm-sw" style="background:${GREY}"></span>no clear trend<br><span class="rm-sw" style="background:repeating-linear-gradient(45deg,#c9c2b2 0 3px,#8b93ad 3px 5px)"></span>no data<br><span class="rm-sw" style="background:repeating-linear-gradient(45deg,#16204a 0 3px,#24326a 3px 5px)"></span>locked region</div>`;
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
  side();
  preview();
}
const FXTXT = { rain: () => "Heavier rain", storm: () => "Stronger storms", drought: (L) => L.k === "t2m" ? "Heat, drought" : "Drought" };
function fxOf(r) {
  if (!r || r.na || !(r.det || r.sus)) return null;
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
  if (!st.fx || st.view !== "sea" || !st.rows || zoom.busy) {
    cv.style.display = "none";
    return;
  }
  const svg = $("#rm-svg"), box = $("#rm-mapc").getBoundingClientRect(), ctm = svg.getScreenCTM();
  if (!ctm || !box.width) return;
  const cell = Math.max(3, Math.min(6, Math.round(ctm.a * 0.3))), GW = Math.ceil(box.width / cell), GH = Math.ceil(box.height / cell);
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
  W.querySelectorAll(".rm-c").forEach((p) => {
    const r = st.rows[+p.dataset.c];
    const hideF = st.f === 1 ? !(r.det || r.sus) : st.f === 2 ? !!r.na || r.det || r.sus : false;
    p.classList.toggle("fade", hideF || st.legend >= 0 && (!!r.na || !r.det || r.bin !== st.legend));
  });
}
function hud() {
  const rows = st.rows, L = LAYERS[st.v], det = rows.filter((r) => r.det).length, sus = rows.filter((r) => r.sus).length, nn = rows.filter((r) => !r.na).length;
  $("#rm-hud").innerHTML = `${st.view === "world" ? "EARTH" : "SE ASIA"} · ${L.name.toUpperCase()}<br><b>${det}</b> OF ${nn} WITH A CLEAR TREND${sus ? ` · <span style="color:var(--red)">${sus} USE CAUTION</span>` : ""} · ${st.span[0]}-${st.span[1]}`;
}
function side() {
  const [lo, hi] = span(st.v), yrs = (a, b) => {
    let o = "";
    for (let y = a; y <= b; y++) {
      const cur = st.span[st.pick], bad = st.pick === 0 ? y > st.span[1] - 9 : y < st.span[0] + 9;
      o += `<button data-yy="${y}" class="${y === cur ? "on" : ""}"${bad ? " disabled" : ""}>${y}</button>`;
    }
    return o;
  };
  $("#rm-side").innerHTML = `<h4>LAYER</h4>` + LAYERS.map((L, i) => `<div class="rm-l${i === st.v ? " on" : ""}${L.lock ? " lock" : ""}" data-l="${i}">
      <i style="background:${L.lock ? "repeating-linear-gradient(45deg,#16204a 0 3px,#24326a 3px 5px)" : PAL[L.pal][4]}"></i>
      <span>${L.name}${L.lock ? " <small>LOCKED</small>" : `<br><small>${L.src}</small>`}</span></div>`).join("") + `<h4>YEARS</h4><div class="rm-w">${WINS.map((w, i) => `<button data-w="${i}" class="${!st.yr && i === st.w ? "on" : ""}">${w[0]}</button>`).join("")}</div>
    <div class="rm-yr"><button class="rm-yb${st.pick === 0 ? " open" : ""}" data-y="0" aria-label="From year">${st.span[0]}<span>▾</span></button><span>to</span><button class="rm-yb${st.pick === 1 ? " open" : ""}" data-y="1" aria-label="To year">${st.span[1]}<span>▾</span></button></div>
    ${st.pick != null ? `<div class="rm-grid">${yrs(lo, hi)}</div>` : ""}
    <h4>SHOW</h4><div class="rm-w rm-f">${["ALL", "TREND", "NONE"].map((t, i) => `<button data-f="${i}" class="${i === st.f ? "on" : ""}">${t}</button>`).join("")}</div>
    <h4>WEATHER</h4><div class="rm-w"><button data-fx="1" class="${st.fx ? "on" : ""}">ON</button><button data-fx="0" class="${st.fx ? "" : "on"}">OFF</button></div>`;
  const grid = W.querySelector(".rm-grid");
  if (grid) {
    const row = W.querySelector(".rm-yr");
    grid.style.top = Math.max(4, row.offsetTop - grid.offsetHeight - 6) + "px";
    const on = grid.querySelector(".on");
    if (on) on.scrollIntoView({ block: "nearest" });
  }
  W.querySelectorAll(".rm-yb").forEach((b) => b.onclick = () => {
    st.pick = st.pick === +b.dataset.y ? null : +b.dataset.y;
    sfx("select");
    side();
  });
  W.querySelectorAll(".rm-grid button").forEach((b) => b.onclick = () => {
    const y = +b.dataset.yy;
    st.yr = st.pick === 0 ? [y, st.span[1]] : [st.span[0], y];
    st.pick = null;
    sfx("select");
    paint(true);
  });
  W.querySelectorAll("[data-f]").forEach((b) => b.onclick = () => {
    st.f = +b.dataset.f;
    sfx("select");
    W.querySelectorAll("[data-f]").forEach((x) => x.classList.toggle("on", x === b));
    fades();
    placeFx();
  });
  W.querySelectorAll("[data-fx]").forEach((b) => b.onclick = () => {
    st.fx = b.dataset.fx === "1";
    sfx("select");
    W.querySelectorAll("[data-fx]").forEach((x) => x.classList.toggle("on", x === b));
    placeFx();
  });
  W.querySelectorAll(".rm-l").forEach((d) => d.onclick = () => {
    const L = LAYERS[+d.dataset.l];
    if (L.lock) {
      sfx("err");
      return;
    }
    st.v = +d.dataset.l;
    st.yr = null;
    st.pick = null;
    sfx("select");
    paint(true);
  });
  W.querySelectorAll("[data-w]").forEach((b) => b.onclick = () => {
    st.w = +b.dataset.w;
    st.yr = null;
    st.pick = null;
    sfx("select");
    paint(true);
  });
}
function preview() {
  const box = $("#rm-pv"), L = LAYERS[st.v];
  W.querySelector("#rm-selg").innerHTML = "";
  if (st.c < 0) {
    box.innerHTML = `<h3>SELECT A COUNTRY</h3>
      <ul class="rm-empty" style="padding-left:18px;margin:10px 0 0"><li>Colour shows the trend per decade.</li><li>Grey means no clear trend.</li><li>Hover the legend to highlight one range.</li></ul>`;
    return;
  }
  const r = st.rows[st.c];
  const selg = W.querySelector("#rm-selg");
  el("path", { d: st.map.sea[r.n], class: "rm-sel", "vector-effect": "non-scaling-stroke" }, selg);
  const [px, py] = P(...LAB[r.n]);
  el("circle", { cx: px, cy: py, r: 1.4, class: "rm-pulse", "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, selg);
  if (r.na) {
    box.innerHTML = `<h3>${r.n.toUpperCase()}</h3><div class="dim">${L.name}</div><div style="margin-top:14px;font-size:22px">${r.na}</div>`;
    return;
  }
  const Wd = 268, Hd = 112, lo = Math.min(...r.ys), hi = Math.max(...r.ys), pad = (hi - lo) * 0.15 || 1;
  const X = (x) => 8 + (x - r.y0) / Math.max(1, r.y1 - r.y0) * (Wd - 16), Y = (y) => Hd - 8 - (y - lo + pad) / (hi - lo + 2 * pad) * (Hd - 16);
  let line = "";
  r.xs.forEach((x, i) => {
    line += (i && x - r.xs[i - 1] > 1 ? "M" : i ? "L" : "M") + X(x).toFixed(1) + " " + Y(r.ys[i]).toFixed(1);
  });
  const gap = L.gap && r.y0 <= L.gap[0] ? `<rect x="${X(L.gap[0] - 0.5)}" y="2" width="${X(L.gap[1] + 0.5) - X(L.gap[0] - 0.5)}" height="${Hd - 4}" fill="#d94a36" fill-opacity=".28"/>` : "";
  const dp = L.sd < 1 ? 2 : 1, f = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(dp);
  const need = Math.ceil(r.nstar), det = r.det, sus = r.sus;
  box.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center"><h3>${r.n.toUpperCase()}</h3>
      <span class="rm-badge" style="background:${r.real ? "var(--grn)" : "var(--mus)"}">${r.real ? "NASA DATA" : "SAMPLE DATA"}</span></div>
    <div class="dim" style="font-size:17px">${L.name} · ${r.y0}-${r.y1} · annual means</div>
    <svg class="rm-spark" viewBox="0 0 ${Wd} ${Hd}" preserveAspectRatio="none">
      ${[0.25, 0.5, 0.75].map((k) => `<path d="M6 ${(Hd * k).toFixed(0)}H${Wd - 6}" stroke="#1a2f6e" stroke-dasharray="2 2"/>`).join("")}${gap}
      <path class="ln" d="${line}"/>
      <path class="tr" d="M${X(r.xs[0])} ${Y(r.a + r.b * r.xs[0])}L${X(r.xs[r.N - 1])} ${Y(r.a + r.b * r.xs[r.N - 1])}"/>
      <text x="6" y="13" font-size="13" fill="#7fa8e8" font-family="VT323">${(hi + pad).toFixed(dp)} ${L.unit}</text>
      <text x="6" y="${Hd - 4}" font-size="13" fill="#7fa8e8" font-family="VT323">${(lo - pad).toFixed(dp)}</text></svg>
    <table class="rm-tab">
      <tr><td>Trend</td><td><span id="rm-count">${f(0)}</span> ${L.ud}</td></tr>
      <tr><td>95% range</td><td>${f(r.b10 - 1.96 * r.se10)} .. ${f(r.b10 + 1.96 * r.se10)}</td></tr>
      <tr><td>Autocorr.</td><td>${r.r1.toFixed(2)}</td></tr>
      <tr><td>n_eff / n</td><td>${r.neff.toFixed(1)} / ${r.N}</td></tr>
      <tr><td>p-value</td><td>${r.p < 1e-3 ? "<.001" : r.p.toFixed(3)} / ${r.padj < 1e-3 ? "<.001" : r.padj.toFixed(3)}</td></tr>
      ${FXTXT[fxOf(r)] ? `<tr><td>Linked risk</td><td>${FXTXT[fxOf(r)](L)}</td></tr>` : ""}
      <tr><td>Years needed</td><td>${need > r.N ? "≈" : ""}${need} (have ${r.N})</td></tr></table>
    <div class="rm-verd" style="background:${det ? "var(--grn)" : sus ? "var(--red)" : "var(--mus)"};color:${sus ? "#fff" : "var(--ink)"}">${det ? "TREND DETECTED" : sus ? "USE CAUTION" : "NO CLEAR TREND"}</div>
    <div class="dim" style="font-size:16px;margin-top:6px;line-height:1.12">${sus ? "Trend found, but the 2017-2018 satellite gap is inside this period. Treat with caution." : (L.gap && r.y0 <= L.gap[0] ? "Shaded band: no satellite data (2017-2018). " : "") + (det ? "Clear trend over this period." : need > r.N ? `No clear trend yet. About ${need - r.N} more years of data needed.` : "No clear trend once all 11 countries are compared.")}</div>
    <button class="obtn" id="rm-open">OPEN AS CASE ▸</button>`;
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
  t.innerHTML = r.na ? `${r.n.toUpperCase()} <span class="dim">· no data</span>` : `${r.n.toUpperCase()} <b style="font-weight:400;color:${r.det ? "var(--ink)" : r.sus ? "var(--red)" : "#5b6b8f"}">${(r.b10 >= 0 ? "+" : "−") + Math.abs(r.b10).toFixed(L.sd < 1 ? 2 : 1)} ${L.ud}</b>${r.det ? "" : r.sus ? ' <span class="hi">· use caution</span>' : ' <span class="dim">· no clear trend</span>'}`;
  t.style.display = "block";
  t.style.left = Math.min(e.clientX - box.left + 14, box.width - t.offsetWidth - 6) + "px";
  t.style.top = e.clientY - box.top + 16 + "px";
}
function pick(ci) {
  const r = st.rows[ci];
  if (st.view === "world") zoom("sea");
  st.c = ci;
  sfx(r.na ? "err" : "select");
  preview();
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
  const ls = Math.min(1, vb[2] / VB.sea[2]);
  W.querySelectorAll("#rm-labs text").forEach((t) => {
    t.setAttribute("font-size", (+t.dataset.fs * ls).toFixed(3));
    t.setAttribute("stroke-width", (0.28 * ls).toFixed(3));
  });
  if (!anim) {
    W.querySelector("#rm-fxc").style.display = "none";
    clearTimeout(setVB.t);
    setVB.t = setTimeout(placeFx, 140);
  }
}
function clampVB(vb) {
  const w = Math.max(12, Math.min(72, vb[2])), h = w * VB.sea[3] / VB.sea[2];
  let x = vb[0] + (vb[2] - w) / 2, y = vb[1] + (vb[3] - h) / 2;
  x = Math.max(SEA_BOX[0], Math.min(SEA_BOX[2] - w, x));
  y = Math.max(SEA_BOX[1], Math.min(SEA_BOX[3] - h, y));
  return [x, y, w, h];
}
function zoomAt(f, cx, cy) {
  if (zoom.busy) return;
  if (st.view !== "sea") {
    if (f < 1) zoom("sea");
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
      if (st.view === "sea") setVB(VB.sea.slice());
      else zoom("sea");
    } else zoomAt(z === "in" ? 1 / 1.5 : 1.5);
  });
  mc.addEventListener("wheel", (e) => {
    e.preventDefault();
    const u = toUnits(e);
    zoomAt(e.deltaY < 0 ? 1 / 1.2 : 1.2, u.x, u.y);
  }, { passive: false });
  let drag = null;
  mc.addEventListener("pointerdown", (e) => {
    if (st.view !== "sea" || e.button !== 0 || e.target.closest("button,.rm-tip")) return;
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
  if (st.view === to && !zoom.busy) return;
  const from = $("#rm-svg").getAttribute("viewBox").split(" ").map(Number), dst = VB[to].slice(), t0 = performance.now(), dur = 850;
  st.view = to;
  sfx("whoosh");
  zoom.busy = true;
  clearInterval(placeFx.iv);
  W.querySelector("#rm-fxc").style.display = "none";
  W.querySelectorAll(".rm-tog button").forEach((b) => b.classList.toggle("on", b.dataset.v === to));
  const labs = W.querySelector("#rm-labs");
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
    const vb = from.map((a, i) => a + (dst[i] - a) * e);
    setVB(vb, true);
    labs.setAttribute("opacity", to === "sea" ? e : 1 - e);
    if (k < 1) requestAnimationFrame(step);
    else {
      zoom.busy = false;
      if (st.rows) {
        hud();
        placeFx();
      }
    }
  };
  requestAnimationFrame(step);
}
async function load() {
  if (!st.map) st.map = await (await fetch("data/sea_map.json")).json();
  if (st.data === null) {
    try {
      const r = await fetch("data/sea_data.json");
      st.data = r.ok ? await r.json() : false;
    } catch (e) {
      st.data = false;
    }
  }
  if (st.data === false) st.data = null, st.noData = true;
}
async function open(win, helpers) {
  H = helpers;
  W = win(
    "w-rmap",
    "MAP.EXE · SOUTHEAST ASIA",
    `<div class="rm"><div class="rm-side" id="rm-side"></div>
    <div class="rm-map" id="rm-mapc"><svg id="rm-svg" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Trend map of Southeast Asia"></svg>
      <canvas class="rm-fxc" id="rm-fxc" aria-hidden="true"></canvas><svg id="rm-top" preserveAspectRatio="xMidYMid meet" aria-hidden="true" style="pointer-events:none"></svg><div class="rm-hud" id="rm-hud">ACQUIRING SCENE...</div>
      <div class="rm-tog"><button data-v="world">WORLD</button><button data-v="sea">SE ASIA</button></div>
      <div class="rm-zoom"><button data-z="in" title="Zoom in" aria-label="Zoom in">+</button><button data-z="out" title="Zoom out" aria-label="Zoom out">−</button><button data-z="home" title="Reset view" aria-label="Reset view">⌂</button></div>
      <div class="rm-tip" id="rm-tip"></div>
      <div class="rm-deny" id="rm-deny"><div class="tb"><span class="t">AREA LOCKED</span></div><div style="padding:8px 12px">Only Southeast Asia is available.</div></div>
      <div class="rm-scan"></div></div>
    <div class="rm-leg" id="rm-leg"></div><div class="rm-pv" id="rm-pv"></div></div>`,
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
  if (!open.ro) {
    open.ro = new ResizeObserver(() => placeFx());
  }
  open.ro.observe($("#rm-mapc"));
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
  setTimeout(() => zoom("sea"), 1700);
  H.log && H.log(st.data ? "MAP: NASA DATA LOADED." : "MAP: SAMPLE DATA.");
}
const regionMap = { open };
export {
  regionMap
};
