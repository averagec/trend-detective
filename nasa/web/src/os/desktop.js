import { SFX } from "../audio/sfx.js";
import { say, closeSay } from "../ui/dialogue.js";
import { analysis } from "../stats/trend-analysis.js";
import { openChart } from "../ui/chart-view.js";
import { regionMap } from "./region-map.js";
import { leaveDesk } from "../scene/office.js";
import { toLocal } from "../ui/scale.js";
const $ = (s) => document.querySelector(s);
import { beginSkip, endSkip, skipWait as wait } from "../ui/skip.js";
const CASES = [
  { id: "001", name: "JAKARTA_TIDE", q: "Is the sea rising at Jakarta?", preset: { v: "ssl", r: "jakarta", y0: 1992, y1: 2017 }, open: true },
  { id: "002", name: "THE_EAST", q: "Ambon’s sea rose fastest. Can we prove it?", preset: { v: "ssl", r: "ambon", y0: 1992, y1: 2017 }, open: true },
  { id: "003", name: "HOTTER_ISLANDS", q: "Are the islands getting hotter?", preset: { v: "t2m", r: "idn", y0: 1980, y1: 2025 }, open: true },
  { id: "004", name: "MORE_RAIN", q: "Is more rain falling on the islands?", preset: { v: "precip", r: "idn", y0: 1980, y1: 2025 }, open: true },
  { id: "005", name: "WETTER_GROUND", q: "Is more water soaking into the islands?", preset: { v: "tws", r: "idn", y0: 2002, y1: 2025 }, open: true },
  { id: "006", name: "SINKING_CITY", q: "How fast is Jakarta’s ground sinking?", open: false, lock: "NEEDS LAND SUBSIDENCE DATA (INSAR, E.G. NASA-ISRO NISAR)" }
];
let current = 0, z = 10, noiseTimer = null, booting = false;
const LOG = [];
const S = { setup: null, guess: null, look: null, runs: 0, exploratory: false, lastKey: null, deseason: false };
const D = () => analysis.DATASETS;
const unlock = (id) => {
  const ic = document.querySelector(`.icon[data-id="${id}"]`);
  if (ic) ic.classList.remove("locked");
};
const isLocked = (id) => {
  const ic = document.querySelector(`.icon[data-id="${id}"]`);
  return ic && ic.classList.contains("locked");
};
const fmt = (x, d = 2) => (x > 0 ? "+" : "") + x.toFixed(d);
function runNoise(cv) {
  const c = cv.getContext("2d"), w = cv.width, h = cv.height, img = c.createImageData(w, h);
  return setInterval(() => {
    for (let i = 0; i < img.data.length; i += 4) {
      const v = Math.random() * 255;
      img.data[i] = v * 0.7;
      img.data[i + 1] = v * 0.8;
      img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
    c.putImageData(img, 0, 0);
  }, 50);
}
function focus(w) {
  document.querySelectorAll(".win").forEach((x) => x.classList.toggle("active", x === w));
  w.style.zIndex = ++z;
}
function drag(w) {
  const tb = w.querySelector(".tb");
  w.addEventListener("pointerdown", () => focus(w));
  tb.onpointerdown = (e) => {
    if (e.target.closest(".bx")) return;
    const r = w.getBoundingClientRect(), pr = $("#wins").getBoundingClientRect();
    const ox = e.clientX - r.left, oy = e.clientY - r.top;
    if (w.style.right && w.style.right !== "auto") w.style.width = toLocal(r.width) + "px";
    if (w.style.bottom && w.style.bottom !== "auto") w.style.height = toLocal(r.height) + "px";
    w.style.right = "auto";
    w.style.bottom = "auto";
    const mv = (ev) => {
      w.style.left = Math.max(0, toLocal(ev.clientX - pr.left - ox)) + "px";
      w.style.top = Math.max(0, toLocal(ev.clientY - pr.top - oy)) + "px";
    };
    const up = () => {
      removeEventListener("pointermove", mv);
      removeEventListener("pointerup", up);
    };
    addEventListener("pointermove", mv);
    addEventListener("pointerup", up);
  };
}
const closeId = (...ids) => ids.forEach((id) => {
  const w = document.getElementById(id);
  if (w) w.remove();
});
function closeWin(w) {
  SFX.close();
  w.classList.add("closing");
  setTimeout(() => w.remove(), 150);
}
function win(id, title, html, st) {
  let w = document.getElementById(id), fresh = false;
  if (!w) {
    fresh = true;
    w = document.createElement("div");
    w.className = "win";
    w.id = id;
    w.innerHTML = '<div class="tb"><span class="t"></span><button class="bx" aria-label="Close window">×</button></div><div class="bd"></div>';
    $("#wins").appendChild(w);
    drag(w);
    w.querySelector(".bx").onclick = () => closeWin(w);
    Object.assign(w.style, st || {});
  }
  w.querySelector(".t").textContent = title;
  w.querySelector(".bd").innerHTML = html;
  focus(w);
  if (fresh) SFX.open();
  return w;
}
function log(msg, cls) {
  LOG.push(`<div><span class="dim">23:${String(48 + Math.floor(LOG.length / 2)).padStart(2, "0")}</span>  <span class="${cls || ""}">${msg}</span></div>`);
  const el = document.querySelector("#w-log .bd");
  if (el) {
    el.innerHTML = LOG.join("");
    el.scrollTop = el.scrollHeight;
  }
}
function plotLine(cv, t, v, opts) {
  const c = cv.getContext("2d"), W = cv.width, H = cv.height;
  c.imageSmoothingEnabled = false;
  c.fillStyle = "#0e1a40";
  c.fillRect(0, 0, W, H);
  const lo = Math.min(...v), hi = Math.max(...v), t0 = t[0], t1 = t[t.length - 1];
  const X = (x) => Math.round(6 + (x - t0) / (t1 - t0) * (W - 12)), Y = (y) => Math.round(H - 8 - (y - lo) / (hi - lo || 1) * (H - 16));
  c.fillStyle = "#1a2f6e";
  for (let k = 1; k < 4; k++) for (let x = 0; x < W; x += 4) c.fillRect(x, Math.round(H * k / 4), 2, 1);
  const dot = (x, y, col) => {
    c.fillStyle = col;
    c.fillRect(x, y, 2, 2);
  };
  for (let i = 1; i < t.length; i++) {
    if (t[i] - t[i - 1] > 0.2) continue;
    const x0 = X(t[i - 1]), y0 = Y(v[i - 1]), x1 = X(t[i]), y1 = Y(v[i]), n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1);
    for (let k = 0; k <= n; k++) dot(Math.round(x0 + (x1 - x0) * k / n), Math.round(y0 + (y1 - y0) * k / n), "#7fd6e8");
  }
  if (opts && opts.trend) {
    const [a, b] = opts.trend;
    const n = W;
    for (let k = 0; k < n; k += 3) {
      const x = t0 + (t1 - t0) * k / n;
      dot(X(x), Y(a + b * x), "#e9a93a");
    }
  }
  if (opts && opts.gap) {
    c.fillStyle = "rgba(217,74,54,.35)";
    c.fillRect(X(opts.gap[0]), 0, Math.max(2, X(opts.gap[1]) - X(opts.gap[0])), H);
  }
  return { lo, hi };
}
function plotHist(cv, sims, obs) {
  const c = cv.getContext("2d"), W = cv.width, H = cv.height;
  c.fillStyle = "#0e1a40";
  c.fillRect(0, 0, W, H);
  const m = Math.max(Math.abs(obs) * 1.15, ...sims.map(Math.abs)), B = 40, bins = Array(B).fill(0);
  sims.forEach((s) => bins[Math.min(B - 1, Math.floor((s + m) / (2 * m) * B))]++);
  const top = Math.max(...bins), bw = Math.floor((W - 8) / B);
  bins.forEach((n, i) => {
    const h = Math.round(n / top * (H - 14));
    const x0 = 4 + i * bw, mid = -m + (i + 0.5) * 2 * m / B;
    c.fillStyle = Math.abs(mid) >= Math.abs(obs) ? "#e9a93a" : "#3b7ddd";
    c.fillRect(x0, H - 4 - h, bw - 1, h);
  });
  const xo = Math.round(4 + (obs + m) / (2 * m) * B * bw);
  c.fillStyle = "#d94a36";
  c.fillRect(xo - 1, 0, 3, H);
}
function openCases() {
  guideDone("cases");
  if (!analysis.load.done) {
    analysis.load().then(openCases, () => {
      SFX.err();
      log("CASE DATA MISSING: data/cases_data.json", "hi");
    });
    return;
  }
  const w = win("w-cases", "CASES", CASES.map((c, i) => `<div class="row${i === current ? " sel" : ""}" data-i="${i}" tabindex="0" role="button"><img src="images/icons/${c.open ? "folder" : "lock"}.png" alt=""><span>CASE_${c.id}<br><span style="font-size:18px">${c.name}</span></span><span class="tag2 ${c.open ? "open" : "lock"}">${c.open ? "OPEN" : "LOCKED"}</span></div>`).join("") + '<div class="dim" style="margin-top:8px">DOUBLE-CLICK A FILE TO OPEN IT</div>', { left: "150px", top: "30px", width: "440px" });
  w.querySelectorAll(".row").forEach((r) => {
    r.onclick = () => {
      current = +r.dataset.i;
      SFX.select();
      w.querySelectorAll(".row").forEach((x) => x.classList.toggle("sel", x === r));
    };
    r.ondblclick = () => openBrief();
    r.onkeydown = (e) => {
      if (e.key === "Enter") openBrief();
    };
  });
}
function openBrief() {
  const c = CASES[current];
  if (!c.open) {
    SFX.err();
    log(`CASE_${c.id}: LOCKED. ${c.lock}.`, "hi");
    say(["Not that one. Sea level from the ocean can’t see the ground sinking under the city.", "That needs satellite radar of the land. Not in my files yet."]);
    return;
  }
  const p = c.preset, ds = D()[p.v];
  const w = win(
    "w-brief",
    `CASE_${c.id}.TXT`,
    `
    <div style="font-size:32px;line-height:1;color:var(--blue)">${c.q}</div>
    <div style="margin-top:12px">SUGGESTED .... ${ds.label}</div><div>REGION ....... ${ds.regions[p.r].name}</div><div>RECORD ....... ${ds.source}, ${ds.start} to ${ds.end}</div>
    <div class="dim" style="margin-top:10px">You choose the variable, region and years. Then lock in your guess before anything is plotted.</div>
    <div style="margin-top:12px;text-align:right"><button class="obtn" id="go-setup">START INVESTIGATION ▸</button></div>`,
    { left: "610px", top: "40px", width: "540px" }
  );
  w.querySelector("#go-setup").onclick = () => {
    S.setup = Object.assign({}, p);
    closeId("w-brief", "w-cases");
    openSetup();
  };
  log(`CASE_${c.id} OPENED.`);
}
function yearPick(btn, from, to, sel, onPick) {
  const host = btn.closest(".bd"), old = host.querySelector(".ygrid");
  if (old) {
    old.remove();
    if (old.dataset.for === btn.id) return;
  }
  SFX.select();
  const g = document.createElement("div");
  g.className = "ygrid";
  g.dataset.for = btn.id;
  for (let y = from; y <= to; y++) g.innerHTML += `<button data-y="${y}" class="${y === sel ? "on" : ""}">${y}</button>`;
  host.appendChild(g);
  const R = (r) => ({ left: toLocal(r.left), top: toLocal(r.top), bottom: toLocal(r.bottom) });
  const hb = R(host.getBoundingClientRect()), bb = R(btn.getBoundingClientRect());
  const below = hb.bottom - bb.bottom, above = bb.top - hb.top, h = Math.min(g.offsetHeight, Math.max(below, above) - 10);
  g.style.maxHeight = h + "px";
  g.style.left = Math.max(4, Math.min(bb.left - hb.left + host.scrollLeft, host.clientWidth - g.offsetWidth - 4)) + "px";
  g.style.top = (below >= h + 10 ? bb.bottom - hb.top + 4 : bb.top - hb.top - h - 4) + host.scrollTop + "px";
  const on = g.querySelector(".on");
  if (on) on.scrollIntoView({ block: "nearest" });
  g.onclick = (e) => {
    const b = e.target.closest("[data-y]");
    if (!b) return;
    e.stopPropagation();
    g.remove();
    SFX.select();
    onPick(+b.dataset.y);
  };
}
function setupKey(s) {
  return [s.v, s.r, s.y0, s.y1].join("|");
}
function openSetup() {
  const s = S.setup || (S.setup = Object.assign({}, CASES[0].preset));
  const ds = D()[s.v];
  if (!ds.regions[s.r]) s.r = Object.keys(ds.regions)[0];
  s.y0 = Math.max(ds.start, Math.min(s.y0, ds.end - 9));
  s.y1 = Math.min(ds.end, Math.max(s.y1, s.y0 + 9));
  const w = win(
    "w-setup",
    "SETUP.EXE",
    `
    <div class="step"><h4>1. WHAT ARE YOU MEASURING?</h4><div class="chips">${Object.entries(D()).map(([k, d]) => `<button class="chip${k === s.v ? " on" : ""}" data-v="${k}">${d.label}<br><small>${d.source}</small></button>`).join("")}</div></div>
    <div class="step"><h4>2. WHERE?</h4><div class="chips">${Object.entries(ds.regions).map(([k, r]) => `<button class="chip${k === s.r ? " on" : ""}" data-r="${k}">${r.name}</button>`).join("")}</div></div>
    <div class="step"><h4>3. WHICH YEARS?</h4><label>FROM <button class="ypick" id="y0">${s.y0} ▾</button></label> <label>TO <button class="ypick" id="y1">${s.y1} ▾</button></label> <span class="dim">(${s.y1 - s.y0 + 1} years, min 10)</span></div>
    ${S.runs && setupKey(s) !== S.lastKey ? '<div><span class="flag">EXPLORATORY</span> <span class="dim">Changed after seeing results.</span></div>' : ""}
    <div style="text-align:right;margin-top:8px"><button class="obtn" id="go-next">${S.guess === null ? "NEXT: LOCK MY GUESS ▸" : "PLOT IT ▸"}</button></div>`,
    { left: "230px", top: "40px", width: "600px" }
  );
  w.querySelectorAll("[data-v]").forEach((b) => b.onclick = () => {
    s.v = b.dataset.v;
    SFX.select();
    openSetup();
  });
  w.querySelectorAll("[data-r]").forEach((b) => b.onclick = () => {
    s.r = b.dataset.r;
    SFX.select();
    openSetup();
  });
  w.querySelector("#y0").onclick = (e) => yearPick(e.currentTarget, ds.start, ds.end - 9, s.y0, (y) => {
    s.y0 = y;
    openSetup();
  });
  w.querySelector("#y1").onclick = (e) => yearPick(e.currentTarget, s.y0 + 9, ds.end, s.y1, (y) => {
    s.y1 = y;
    openSetup();
  });
  w.querySelector("#go-next").onclick = () => {
    if (S.runs && setupKey(s) !== S.lastKey) {
      S.exploratory = true;
      log("SETUP CHANGED AFTER RESULTS: CASE MARKED EXPLORATORY.", "hi");
    }
    log(`SETUP: ${D()[s.v].label} / ${D()[s.v].regions[s.r].name} / ${s.y0}-${s.y1}`);
    closeId("w-setup", "w-test");
    if (S.guess === null) openHyp();
    else openPlot();
  };
}
function openHyp() {
  const s = S.setup, ds = D()[s.v];
  const opts = ["INCREASE", "DECREASE", "NO SIGNIFICANT CHANGE", "UNCERTAIN"];
  const labels = ["I expect an increase", "I expect a decrease", "I expect no significant change", "I'm not sure"];
  const w = win(
    "w-hyp",
    "MY_GUESS.LCK",
    `
    <div>${ds.label} in ${ds.regions[s.r].name}, ${s.y0} to ${s.y1}. What do you expect?</div>
    ${labels.map((o, i) => `<button class="opt${S.guess === i ? " picked" : ""}" data-o="${i}">[${i + 1}] ${o}</button>`).join("")}
    <div>${S.guess !== null ? '<span class="stamp">LOCKED 23:49</span>' : '<span class="dim">One answer. It can’t be changed.</span>'}</div>`,
    { left: "380px", top: "160px", width: "520px" }
  );
  w.querySelectorAll(".opt").forEach((b) => b.onclick = () => {
    if (S.guess !== null) {
      SFX.err();
      log("GUESS ALREADY LOCKED.", "hi");
      return;
    }
    S.guess = +b.dataset.o;
    SFX.stamp();
    openHyp();
    log(`GUESS LOCKED: ${opts[S.guess]}`, "hi");
    unlock("evidence");
    setTimeout(() => say(["Written down. No changing my mind once I’ve seen the data.", "Now let’s look at the actual record."], () => {
      closeId("w-hyp");
      openPlot();
    }), 400);
  });
}
function openPlot() {
  if (!S.setup || S.guess === null) {
    SFX.err();
    say(["Not yet. Which city, which years? And I write my guess down first."]);
    return;
  }
  closeId("w-hyp");
  const s = S.setup, ds = D()[s.v];
  let ser = analysis.slice(analysis.makeSeries(s.v, s.r), s.y0, s.y1);
  if (S.deseason) ser = analysis.deseason(ser);
  const w = win(
    "w-plot",
    "PLOT.PCX",
    `
    <div style="display:flex;justify-content:space-between;align-items:center"><span>${ds.label}, ${ds.regions[s.r].name} (${ds.unit})</span><label style="cursor:pointer"><input type="checkbox" id="ds"${S.deseason ? " checked" : ""}> REMOVE SEASONAL CYCLE</label></div>
    <canvas class="cv zoomable" id="cv-plot" width="360" height="150" title="Click to enlarge"></canvas>
    <div class="axis"><span>${s.y0}</span><span class="dim">MONTHLY · ${ds.source} · CLICK TO ENLARGE</span><span>${s.y1}</span></div>
    <div style="margin-top:10px">Look at it yourself first. Does it look like a trend?</div>
    <div class="chips" style="margin-top:6px">${["GOING UP", "GOING DOWN", "CAN’T TELL"].map((t, i) => `<button class="chip${S.look === i ? " on" : ""}" data-l="${i}">${t}</button>`).join("")}</div>
    ${S.look !== null ? '<div style="text-align:right;margin-top:8px"><button class="obtn" id="go-lineup">RUN THE LINEUP ▸</button></div>' : ""}`,
    { left: "200px", top: "30px", width: "640px" }
  );
  plotLine(w.querySelector("#cv-plot"), ser.t, ser.v, { gap: ds.gap && s.y0 < ds.gap[0] && s.y1 + 1 > ds.gap[1] ? ds.gap : null });
  w.querySelector("#cv-plot").onclick = () => openChart({
    title: `${ds.regions[s.r].name.toUpperCase()} · ${ds.label.toUpperCase()}`,
    sub: `${s.y0}-${s.y1} · MONTHLY${S.deseason ? " · SEASONAL CYCLE REMOVED" : ""} · NO TREND LINE UNTIL THE LINEUP`,
    unit: ds.unit,
    series: ser.t.map((t, i) => [t, ser.v[i]]),
    seriesLabel: S.deseason ? "Monthly value minus that month’s average" : "Monthly value",
    step: 1 / 12,
    monthly: true,
    zero: S.deseason,
    dp: ds.unit === "mm" ? 0 : 2,
    notes: [ds.regions[s.r].long ? `Region: ${ds.regions[s.r].long}.` : "", "Judge it by eye first. The trend line and the tests come after you make your call."].filter(Boolean),
    source: ds.source
  });
  w.querySelector("#ds").onchange = (e) => {
    S.deseason = e.target.checked;
    SFX.select();
    openPlot();
    if (S.deseason) say(["There. With the seasons taken out, it’s easier to see what’s left."]);
  };
  w.querySelectorAll("[data-l]").forEach((b) => b.onclick = () => {
    S.look = +b.dataset.l;
    SFX.select();
    openPlot();
    unlock("lineup");
    log(`EYEBALL CALL: ${["UP", "DOWN", "CAN’T TELL"][S.look]}`);
    say(["That’s my gut talking. It’s been wrong before.", "Time to check it properly. LINEUP."]);
  });
  const gl = w.querySelector("#go-lineup");
  if (gl) gl.onclick = () => {
    SFX.click();
    openTest();
  };
}
function openTest() {
  if (!S.setup || S.look === null) {
    SFX.err();
    say(["Not yet. I haven’t even looked at the record."]);
    return;
  }
  const s = S.setup, ds = D()[s.v];
  closeId("w-plot");
  const w = win("w-test", "LINEUP.EXE", `
    <div>Is this trend real, or could random noise have made it?</div>
    <div class="dim">We build 1,000 fake records with the same wobble and no trend, and see how many look this strong.</div>
    <div style="margin:10px 0;text-align:right"><button class="obtn" id="go-run">RUN 1,000 SIMULATIONS ▸</button></div>
    <div id="test-out"></div>`, { left: "300px", top: "20px", width: "660px", maxHeight: "96%" });
  w.querySelector("#go-run").onclick = async () => {
    const out = w.querySelector("#test-out");
    SFX.click();
    out.innerHTML = '<canvas class="cv" id="cv-h" width="360" height="110"></canvas><div id="cnt">SIMULATING... 0 / 1000</div>';
    const R = analysis.analyse(s);
    for (let k = 100; k <= 1e3; k += 100) {
      plotHist(out.querySelector("#cv-h"), R.sims.slice(0, k), R.obs);
      out.querySelector("#cnt").textContent = `SIMULATING... ${k} / 1000`;
      SFX.key();
      await wait(110);
    }
    S.runs++;
    S.lastKey = setupKey(s);
    const perDec = 10, unit = ds.unit + " / decade", core = ds.regions[s.r].core, full = s.y0 === ds.start && s.y1 === ds.end;
    const V = { "DETECTED": ["#2c7a2a", "●"], "NOT YET DETECTABLE": ["#1f4fa0", "◌"], "SUSPECT": ["#d94a36", "▲"] }[R.verdict];
    const guessDir = ["UP", "DOWN", "NONE", null][S.guess], realDir = R.verdict === "DETECTED" ? R.slope > 0 ? "UP" : "DOWN" : "NONE";
    out.innerHTML = `
      <canvas class="cv" id="cv-h" width="360" height="110"></canvas>
      <div class="axis"><span>FAKE RECORDS (BLUE / GOLD) VS REAL (RED LINE)</span><span>${R.beat} / 1000 AS STRONG</span></div>
      <div class="verdict" style="color:${V[0]};border-color:${V[0]}">${V[1]} ${R.verdict}</div> ${S.exploratory ? '<span class="flag">EXPLORATORY</span>' : ""}
      <div class="res">
        <span>TREND</span><span>${fmt(R.slope * perDec)} ${unit}</span>
        <span>95% RANGE</span><span>${fmt(R.ci[0] * perDec)} to ${fmt(R.ci[1] * perDec)}</span>
        <span>MANN-KENDALL</span><span>p = ${R.mk.p < 1e-4 ? "< 0.0001" : R.mk.p.toFixed(4)} (autocorrelation-adjusted)</span>
        <span>NOISE LINEUP</span><span>${R.beat} of 1,000 fakes as strong (${(R.beat / 10).toFixed(1)}%)</span>
        ${core ? `<span>PYTHON CORE</span><span>${fmt(core.per_decade, 2)} ${unit} over the ${full ? "same" : "full"} record (OLS, ${core.significant ? "significant" : "not significant"})</span>` : ""}
        ${R.needed ? `<span>YEARS NEEDED</span><span>about ${R.needed} years of record for a change this size (you have ${R.years})</span>` : ""}
      </div>
      <div style="margin-top:8px">${R.checks.map((c) => `<div class="chk ${c.ok ? "ok" : "no"}"><b>${c.ok ? "✓" : "✗"}</b>${c.k}</div>`).join("")}</div>
      <div class="dim" style="margin-top:8px">${R.verdict === "NOT YET DETECTABLE" ? "Not detecting a trend does not mean nothing is changing. The record is too short or too noisy to tell yet." : R.verdict === "SUSPECT" ? "Something in the checks above makes this result unsafe to trust as it stands." : "The trend survives every check."}</div>
      <div style="margin-top:6px">YOUR GUESS: ${["AN INCREASE", "A DECREASE", "NO CHANGE", "NOT SURE"][S.guess]} · ${guessDir === null ? "NO CALL" : guessDir === realDir ? "MATCHED" : "DIDN’T MATCH"}</div>
      <div style="text-align:right;margin-top:8px"><button class="obtn" id="go-chart">VIEW FULL CHART ▸</button> <button class="obtn" id="go-again">CHANGE SETUP</button></div>`;
    plotHist(out.querySelector("#cv-h"), R.sims, R.obs);
    SFX.stamp();
    const crt = document.querySelector(".crt");
    crt.classList.remove("jolt");
    void crt.offsetWidth;
    crt.classList.add("jolt");
    log(`VERDICT: ${R.verdict}${S.exploratory ? " (EXPLORATORY)" : ""}`, "hi");
    const showChart = () => {
      const an = R.an, tm = an.t.reduce((p, c) => p + c, 0) / an.t.length, vm = an.v.reduce((p, c) => p + c, 0) / an.v.length;
      const yrs = [];
      for (let y = s.y0; y <= s.y1; y++) {
        const vs = an.v.filter((_, i) => Math.floor(an.t[i]) === y);
        if (vs.length) yrs.push([y + 0.5, vs.reduce((p, c) => p + c, 0) / vs.length]);
      }
      const at = (x, b) => vm + b * (x - tm);
      openChart({
        title: `CASE · ${ds.regions[s.r].name.toUpperCase()} · ${ds.label.toUpperCase()}`,
        sub: `${s.y0}-${s.y1} · YEARLY AVERAGE OF THE DESEASONALISED RECORD · VERDICT: ${R.verdict}`,
        unit: ds.unit,
        series: yrs,
        seriesLabel: "Yearly average, seasons removed",
        fit: [[s.y0 + 0.5, at(s.y0 + 0.5, R.slope)], [s.y1 + 0.5, at(s.y1 + 0.5, R.slope)]],
        fitLabel: `Sen’s slope ${fmt(R.slope * perDec)} ${unit}`,
        band: [s.y0 + 0.5, (s.y0 + s.y1 + 1) / 2, s.y1 + 0.5].map((x) => [x, Math.min(at(x, R.ci[0]), at(x, R.ci[1])), Math.max(at(x, R.ci[0]), at(x, R.ci[1]))]),
        bandLabel: "Range of slopes inside the 95% interval",
        zero: true,
        dp: ds.unit === "mm" ? 1 : 2,
        stats: [["TREND", `${fmt(R.slope * perDec)} ${unit}`], ["95% RANGE", `${fmt(R.ci[0] * perDec)} to ${fmt(R.ci[1] * perDec)}`], ["MANN-KENDALL P", R.mk.p < 1e-4 ? "< 0.0001" : R.mk.p.toFixed(4)], ["NOISE LINEUP", `${R.beat} / 1000 as strong`], ["AUTOCORRELATION", `r1 = ${R.r1.toFixed(2)}`], ["VERDICT", R.verdict]],
        notes: [core ? `Python core, full record: ${core.sentence}` : "", ds.regions[s.r].long ? `Region: ${ds.regions[s.r].long}.` : ""].filter(Boolean),
        source: ds.source
      });
    };
    out.querySelector("#go-chart").onclick = showChart;
    out.querySelector("#cv-h").classList.add("zoomable");
    out.querySelector("#cv-h").onclick = showChart;
    out.querySelector("#go-again").onclick = () => {
      closeId("w-test");
      openSetup();
    };
    const lines = { "DETECTED": [`It holds up. ${ds.regions[s.r].name}, ${fmt(R.slope * perDec, ds.unit === "mm" ? 0 : 2)} ${unit}.`, "Every way I push on it, the same answer. That goes in the report."], "NOT YET DETECTABLE": ["Can’t call it yet. Too few years, too much wobble.", s.v === "ssl" ? "El Niño years shove the sea up and down out east. That noise hides the climb." : "That doesn’t mean nothing’s happening. It means I can’t prove it yet."], "SUSPECT": ["Looks strong. Something about it still bothers me.", "One of the checks failed. I’m not signing off on this."] }[R.verdict];
    setTimeout(() => say(lines), 600);
  };
}
const ABOUT_HTML = `<div class="about">
<h3>TREND DETECTIVE: CASE FILES</h3>
<div class="dim">NASA SPACE APPS CHALLENGE 2026 · BE AN EARTH SYSTEM TREND DETECTIVE</div>
<h4>MISSION</h4>
<p>Help anyone in Indonesia, a student or a city planner, answer one honest question with NASA data: <b>is this really changing, where, by how much, and can we prove it?</b> No guessing from one scary graph. Every claim has to survive the tests.</p>
<h4>WHAT IT IS</h4>
<p>A detective game built on real satellite and model records. MAP.EXE shows sea level next to 31 Indonesian cities, from Banda Aceh to Jayapura, and the ocean grid cells each number comes from. CASES lets you lock in a guess, look at the record, and test it against 1,000 trend-free fakes before you get a verdict: Detected, Not Yet Detectable, or Suspect.</p>
<h4>HOW A CASE WORKS</h4>
<p>1. Pick a variable, a place and the years.<br>2. Lock in your guess before you see anything.<br>3. Look at the record yourself.<br>4. LINEUP: is it stronger than random noise?<br>5. Read the verdict and the checks behind it.</p>
<h4>WHAT THE DATA CAN’T SAY</h4>
<p>ECCO sea level is the ocean next to the coast. It does not include land sinking, which drives much of the flooding in Jakarta and Semarang. Inland cities have no sea level number. Map layers marked SAMPLE are demonstrations, not NASA data.</p>
<h4>DATA AND REFERENCES</h4>
<p>· ECCO Consortium, ECCO V4 Release 4 sea surface height, 0.5° monthly (ECCO_L4_SSH_05DEG_MONTHLY_V4R4), NASA PO.DAAC.<br>
· Gelaro et al. (2017), MERRA-2, J. Climate 30, 5419-5454. Monthly 2 m temperature and rainfall, NASA GES DISC.<br>
· NASA GIBS, Blue Marble imagery (SAT view).<br>
· Natural Earth 1:10m provinces, places and coastline (public domain).<br>
· Mann (1945), Kendall (1975): trend test. Sen (1968): slope.<br>
· Benjamini and Hochberg (1995): false discovery rate across cities.<br>
· Batam and Prabumulih positions and populations: Statistics Indonesia 2020 census, via Wikipedia.<br>
· Room model by nickheitzman, CC BY 4.0 (modified).</p>
<div class="team">CREATED BY TEAM: SANSONG</div>
</div>`;
const readme = () => win("w-readme", "ABOUT.TXT", ABOUT_HTML, { left: "190px", top: "24px", width: "640px", maxHeight: "92%" });
const earth = () => win("w-earth", "EARTH.PCX", '<img class="pcx" src="images/earth.png" alt="Pixel art Earth from orbit"><div class="dim" style="margin-top:6px;font-size:18px">Wallpaper only. Case data comes from NASA records.</div>', { left: "640px", top: "60px", width: "360px" });
const map = () => {
  guideDone("map");
  return regionMap.open(win, { log, closeId });
};
function startCase(setup) {
  Object.assign(S, { setup: Object.assign({}, setup), guess: null, look: null, runs: 0, exploratory: false, lastKey: null, deseason: false });
  ["evidence", "lineup"].forEach((id) => {
    const ic = document.querySelector(`.icon[data-id="${id}"]`);
    if (ic) ic.classList.add("locked");
  });
  closeId("w-hyp", "w-plot", "w-test", "w-brief", "w-cases");
  log(`NEW CASE FROM MAP: ${D()[setup.v].label} / ${D()[setup.v].regions[setup.r].name}`, "hi");
  openSetup();
}
const data = () => {
  if (!analysis.load.done) {
    analysis.load().then(data, () => SFX.err());
    return;
  }
  win("w-data", "DATA.LNK", Object.values(D()).map((d) => `<div style="margin-bottom:8px"><span style="color:var(--blue)">${d.label}</span><br>${d.source} · ${d.start} to ${d.end} · ${d.unit} · ${Object.keys(d.regions).length === 1 ? Object.values(d.regions)[0].long || Object.values(d.regions)[0].name : Object.keys(d.regions).length + " coastal cities"}</div>`).join("") + '<div class="dim">All case data is real NASA data, processed by the Python core (scripts/export_indonesia.py). It works offline.</div>', { left: "520px", top: "90px", width: "480px" });
};
const logw = () => {
  win("w-log", "LOG.TXT", LOG.join(""), { left: "260px", bottom: "20px", width: "600px", height: "220px" });
};
const idcard = () => win("w-id", "ID.CARD", `<div style="display:flex;gap:16px;align-items:center"><div style="width:96px;height:120px;border:3px solid var(--ink);background:#1f4fa0 url(images/portrait.png) center top/96px 144px no-repeat;image-rendering:pixelated"></div><div>DETECTIVE<br>EARTH SYSTEM DESK<br>CASES RUN: ${S.runs}<br><span class="dim">TOOL FALSE ALARMS: [x.x]%</span></div></div>`, { right: "30px", top: "30px", width: "380px" });
const trash = () => {
  SFX.err();
  log("TRASH IS EMPTY. NO DATA WAS HARMED.", "dim");
};
const ICONS = [
  ["cases", "folder", "CASES", openCases],
  ["readme", "doc", "ABOUT.TXT", readme],
  ["data", "dish", "DATA.LNK", data],
  ["earth", "picture", "EARTH.PCX", earth],
  ["map", "globe", "MAP.EXE", map],
  ["log", "disk", "LOG.TXT", logw],
  ["id", "id", "ID.CARD", idcard],
  ["evidence", "mag", "EVIDENCE", () => isLocked("evidence") ? (SFX.err(), say(["Guess first. Then the evidence."])) : openPlot(), true],
  ["lineup", "chart", "LINEUP", () => isLocked("lineup") ? (SFX.err(), say(["Not yet. I haven’t even looked at the record."])) : openTest(), true],
  ["trash", "trash", "TRASH", trash]
];
let guide = 0;
const GUIDE = [["map", "START HERE · DOUBLE-CLICK"], ["cases", "NEXT · DOUBLE-CLICK"]];
function glow() {
  document.querySelectorAll(".icon").forEach((b) => {
    const g = GUIDE[guide] && GUIDE[guide][0] === b.dataset.id;
    b.classList.toggle("glow", !!g);
    const old = b.querySelector(".hint");
    if (old) old.remove();
    if (g) b.insertAdjacentHTML("beforeend", `<em class="hint">${GUIDE[guide][1]}</em>`);
  });
}
function guideDone(id) {
  if (GUIDE[guide] && GUIDE[guide][0] === id) {
    guide++;
    glow();
  }
}
let built = false;
function buildDesk() {
  if (built) return;
  built = true;
  $("#icons").innerHTML = ICONS.map((ic) => `<button class="icon${ic[4] ? " locked" : ""}" data-id="${ic[0]}"><img src="images/icons/${ic[1]}.png" alt=""><span>${ic[2]}</span></button>`).join("");
  document.querySelectorAll(".icon").forEach((b) => {
    const ic = ICONS.find((x) => x[0] === b.dataset.id);
    b.onclick = () => {
      const was = b.classList.contains("sel");
      document.querySelectorAll(".icon").forEach((x) => x.classList.remove("sel"));
      b.classList.add("sel");
      SFX.select();
      if (was) ic[3]();
    };
    b.ondblclick = () => ic[3]();
    b.onkeydown = (e) => {
      if (e.key === "Enter") ic[3]();
    };
  });
  glow();
  document.querySelectorAll(".fk").forEach((b) => b.onclick = () => key(b.dataset.k));
}
function key(k) {
  SFX.click();
  if (k === "help") readme();
  else if (k === "cases") openCases();
  else if (k === "log") logw();
  else if (k === "leave") shutdown();
}
async function typeField(el, text, mask) {
  el.innerHTML = '<span class="car"></span>';
  for (let i = 1; i <= text.length; i++) {
    el.innerHTML = (mask ? "•".repeat(i) : text.slice(0, i)) + '<span class="car"></span>';
    SFX.key();
    await wait(32 + Math.random() * 28);
  }
}
async function open() {
  if (booting) return;
  booting = true;
  beginSkip();
  document.body.classList.add("in-os");
  ["#desk", "#login", "#bios"].forEach((s) => $(s).style.display = "none");
  clearInterval(noiseTimer);
  noiseTimer = runNoise($("#noise"));
  const pwr = $("#pwr");
  pwr.className = "pwr on";
  pwr.innerHTML = "<i></i>";
  SFX.thunk();
  await wait(520);
  pwr.className = "pwr";
  const st = $("#static");
  st.style.display = "block";
  const stt = runNoise(st);
  SFX.static(0.5);
  await wait(300);
  clearInterval(stt);
  st.style.display = "none";
  const bios = $("#bios");
  bios.style.display = "block";
  bios.innerHTML = "";
  for (const L of ["<b>TD-OS 1.0</b>  EARTH SYSTEM DESK", "MEMORY ........ 640K OK", "LINK ECCO ..... OK", "LINK MERRA-2 .. OK", "LINK GRACE-FO . OK"]) {
    bios.innerHTML += L + "\n";
    SFX.click();
    await wait(70);
  }
  await wait(120);
  bios.style.display = "none";
  const lg = $("#login");
  lg.style.display = "flex";
  $("#f-user").innerHTML = '<span class="car"></span>';
  $("#f-pass").innerHTML = "";
  $("#lmsg").textContent = "";
  $("#lmsg").className = "lmsg";
  const btn = $("#lbtn");
  btn.classList.remove("press");
  await wait(220);
  await typeField($("#f-user"), "detective");
  await wait(100);
  $("#f-user").querySelector(".car").remove();
  await typeField($("#f-pass"), "xxxxxxxx", true);
  $("#f-pass").querySelector(".car").remove();
  const cur = $("#cur"), cr = $(".crt").getBoundingClientRect(), crt = { left: toLocal(cr.left), top: toLocal(cr.top), width: toLocal(cr.width), height: toLocal(cr.height) };
  cur.style.transition = "none";
  cur.style.left = crt.width * 0.86 + "px";
  cur.style.top = crt.height * 0.86 + "px";
  cur.style.display = "block";
  await wait(60);
  const bR = btn.getBoundingClientRect(), br = { left: toLocal(bR.left), top: toLocal(bR.top), width: toLocal(bR.width), height: toLocal(bR.height) };
  cur.style.transition = "";
  cur.style.left = br.left - crt.left + br.width * 0.55 + "px";
  cur.style.top = br.top - crt.top + br.height * 0.35 + "px";
  await wait(650);
  btn.classList.add("press");
  SFX.mouse();
  await wait(160);
  btn.classList.remove("press");
  $("#lmsg").textContent = "ACCESS GRANTED. WELCOME BACK.";
  $("#lmsg").className = "lmsg ok";
  SFX.chime();
  await wait(450);
  cur.style.display = "none";
  lg.style.display = "none";
  $("#desk").style.display = "flex";
  buildDesk();
  if (!LOG.length) {
    log("LOGGED IN AS DETECTIVE.");
    log("CASE_001 FLAGGED: IS THE SEA RISING AT JAKARTA?", "hi");
  }
  booting = false;
  endSkip();
  setTimeout(() => say(["Okay. I’m in.", "Thirty-one cities across Indonesia. The tide keeps coming further in.", "Is the sea really rising, or does it just feel that way? MAP.EXE first, then the case files."]), 400);
}
async function shutdown() {
  closeSay();
  const pwr = $("#pwr");
  pwr.innerHTML = "<i></i>";
  pwr.className = "pwr on off";
  SFX.thunk();
  await wait(560);
  document.body.classList.remove("in-os");
  pwr.className = "pwr";
  clearInterval(noiseTimer);
  document.querySelectorAll(".win").forEach((w) => w.remove());
  leaveDesk();
}
const desktop = { open, shutdown, startCase };
addEventListener("keydown", (e) => {
  if (!document.body.classList.contains("in-os") || $("#desk").style.display !== "flex") return;
  const map2 = { F1: "help", F2: "cases", F3: "log", F10: "leave", Escape: "leave" };
  if (map2[e.key]) {
    e.preventDefault();
    key(map2[e.key]);
  }
});
export {
  desktop
};
