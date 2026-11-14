import fs from "fs";
import { feature } from "topojson-client";
const SEA = ["Brunei", "Cambodia", "Indonesia", "Laos", "Malaysia", "Myanmar", "Philippines", "Singapore", "Thailand", "Timor-Leste", "Vietnam"];
const load = (r) => {
  const t = JSON.parse(fs.readFileSync(`node_modules/world-atlas/countries-${r}.json`));
  return feature(t, t.objects.countries).features;
};
const f50 = load("50m"), f110 = load("110m");
const P = ([lon, lat]) => [lon + 180, 90 - lat];
function toD(geom, prec, minArea) {
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  let d = "";
  for (const poly of polys) for (const ring of poly) {
    const pts2 = ring.map(P);
    let a = 0;
    for (let i = 0; i < pts2.length - 1; i++) a += pts2[i][0] * pts2[i + 1][1] - pts2[i + 1][0] * pts2[i][1];
    if (Math.abs(a / 2) < minArea) continue;
    const xs = pts2.map((p) => p[0]);
    if (Math.max(...xs) - Math.min(...xs) > 200) continue;
    let last = "";
    d += "M" + pts2.map((p) => p.map((v) => v.toFixed(prec)).join(" ")).filter((s) => s !== last && (last = s)).join("L") + "Z";
  }
  return d;
}
function inside(geom, lon, lat) {
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  for (const poly of polys) {
    let c = false;
    const r = poly[0];
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const [xi, yi] = r[i], [xj, yj] = r[j];
      if (yi > lat !== yj > lat && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) c = !c;
    }
    if (c) return true;
  }
  return false;
}
function grid(geom, step, cap) {
  const all = geom.type === "Polygon" ? geom.coordinates[0] : geom.coordinates.flatMap((p) => p[0]);
  const lons = all.map((p) => p[0]), lats = all.map((p) => p[1]);
  const out = [];
  for (let lat = Math.ceil(Math.min(...lats) / step) * step; lat <= Math.max(...lats); lat += step)
    for (let lon = Math.ceil(Math.min(...lons) / step) * step; lon <= Math.max(...lons); lon += step)
      if (inside(geom, lon + step / 2, lat + step / 2)) out.push([+(lon + step / 2).toFixed(3), +(lat + step / 2).toFixed(3)]);
  if (out.length > cap) {
    const k = out.length / cap;
    return Array.from({ length: cap }, (_, i) => out[Math.floor(i * k)]);
  }
  return out;
}
const FALLBACK = { Singapore: [103.82, 1.35], Brunei: [114.73, 4.54], "Timor-Leste": [125.73, -8.87] };
function anchor(geom, keep = () => true) {
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  const area = (r) => Math.abs(r.reduce((a, p, i) => a + (i ? r[i - 1][0] * p[1] - p[0] * r[i - 1][1] : 0), 0) / 2);
  const big = polys.filter((p) => keep(p[0])).sort((a, b) => area(b[0]) - area(a[0]))[0], g = { type: "Polygon", coordinates: big }, ring = big[0];
  const lons = ring.map((p) => p[0]), lats = ring.map((p) => p[1]);
  let best = null, bd = -1;
  const segd = (x, y, a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy || 1)));
    return Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy);
  };
  for (let la = Math.min(...lats); la <= Math.max(...lats); la += 0.1) for (let lo = Math.min(...lons); lo <= Math.max(...lons); lo += 0.1) {
    if (!inside(g, lo, la)) continue;
    let d = 1e9;
    for (let i = 1; i < ring.length; i++) d = Math.min(d, segd(lo, la, ring[i - 1], ring[i]));
    if (d > bd) {
      bd = d;
      best = [+lo.toFixed(2), +la.toFixed(2)];
    }
  }
  return best;
}
const map = { sea: {}, rest: "", anchor: {} }, pts = {};
for (const n of SEA) {
  const f = f50.find((x) => x.properties.name === n);
  map.sea[n] = toD(f.geometry, 2, n === "Singapore" ? 0 : 0.01);
  map.anchor[n] = n === "Singapore" ? [103.82, 1.35] : n === "Malaysia" ? anchor(f.geometry, (r) => r[0][0] < 105) : anchor(f.geometry);
  let g = grid(f.geometry, 1, 16);
  if (!g.length) g = [FALLBACK[n]];
  let gr = grid(f.geometry, 0.5, 400);
  if (!gr.length) gr = [FALLBACK[n]];
  pts[n] = { power: g, grace: gr };
}
for (const f of f110) {
  if (SEA.includes(f.properties.name) || f.properties.name === "Antarctica" || !f.geometry) continue;
  map.rest += toD(f.geometry, 1, 1.5);
}
fs.writeFileSync("public/data/sea_map.json", JSON.stringify(map));
fs.writeFileSync("scripts/data/sample_points.json", JSON.stringify(pts, null, 1));
console.log(Object.entries(pts).map(([k, v]) => `${k}:${v.power.length}/${v.grace.length}`).join(" "));
