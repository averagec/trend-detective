import fs from "fs";
import { feature } from "topojson-client";
const topo = JSON.parse(fs.readFileSync("node_modules/world-atlas/countries-50m.json"));
const land = feature(topo, topo.objects.countries);
const out = [];
for (const f of land.features) {
  const g = f.geometry;
  if (!g) continue;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  for (const p of polys) for (const ring of p) {
    if (ring.some(([x, y]) => x > 55 && x < 130 && y > -15 && y < 45)) out.push({ id: f.properties.name, ring });
  }
}
fs.writeFileSync("assets/source/asia.json", JSON.stringify(out));
console.log(out.length);
