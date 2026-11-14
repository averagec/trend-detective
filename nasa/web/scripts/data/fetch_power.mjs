import fs from "fs";
const [, , A = "1981", B = String((new Date()).getFullYear() - 1)] = process.argv;
const START = +A, END = +B;
const PTS = JSON.parse(fs.readFileSync(new URL("./sample_points.json", import.meta.url)));
const OUT = new URL("../../public/data/sea_data.json", import.meta.url);
const DAYS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function point(lon, lat, tries = 4) {
  const url = `https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M,PRECTOTCORR&community=AG&longitude=${lon}&latitude=${lat}&start=${START}&end=${END}&format=JSON`;
  for (let k = 0; k < tries; k++) {
    try {
      const r = await fetch(url);
      if (r.status === 429 || r.status >= 500) throw new Error("HTTP " + r.status);
      if (!r.ok) throw new Error("HTTP " + r.status + " " + (await r.text()).slice(0, 200));
      return (await r.json()).properties.parameter;
    } catch (e) {
      console.warn(`  retry ${k + 1} (${lon},${lat}): ${e.message}`);
      await sleep(2e3 * (k + 1));
    }
  }
  throw new Error(`gave up on ${lon},${lat}`);
}
const out = { meta: {
  source: "NASA POWER monthly (MERRA-2 based)",
  fetched: (new Date()).toISOString(),
  start: START,
  end: END,
  note: "Country mean of grid points. precip converted from mm/day to mm/month."
}, t2m: {}, precip: {} };
for (const [name, { power }] of Object.entries(PTS)) {
  process.stdout.write(`${name.padEnd(12)} ${power.length} pts `);
  const n = (END - START + 1) * 12, sum = { t2m: Array(n).fill(0), precip: Array(n).fill(0) }, cnt = { t2m: Array(n).fill(0), precip: Array(n).fill(0) };
  for (const [lon, lat] of power) {
    const p = await point(lon, lat);
    for (let y = START; y <= END; y++) for (let m = 1; m <= 12; m++) {
      const key = `${y}${String(m).padStart(2, "0")}`, i = (y - START) * 12 + m - 1;
      const t = p.T2M[key], pr = p.PRECTOTCORR[key];
      if (t != null && t > -900) {
        sum.t2m[i] += t;
        cnt.t2m[i]++;
      }
      if (pr != null && pr > -900) {
        sum.precip[i] += pr * DAYS[m - 1];
        cnt.precip[i]++;
      }
    }
    process.stdout.write(".");
    await sleep(350);
  }
  for (const v of ["t2m", "precip"]) out[v][name] = { y0: START, m: sum[v].map((s, i) => cnt[v][i] ? +(s / cnt[v][i]).toFixed(3) : null) };
  console.log(" ok");
}
fs.writeFileSync(OUT, JSON.stringify(out));
console.log("wrote public/data/sea_data.json");
