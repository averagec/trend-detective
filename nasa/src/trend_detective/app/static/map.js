(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const KM_PER_DEG = 111.2;
  const COLOUR = { rising: "#c2410c", falling: "#1d4ed8", flat: "#94a3b8" };
  const DATASET_COLOUR = { merra2: "#1d4ed8", gpcp: "#15803d" };

  const state = {
    mode: "city",
    cities: [],
    variables: [],
    selected: new Set(),
    centre: null,
    radiusKm: 100,
    cityRects: L.layerGroup(),
    cellRects: L.layerGroup(),
    circle: null,
    centreMarker: null,
  };

  const map = L.map("map").setView([-2.5, 118], 5);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  state.cityRects.addTo(map);
  state.cellRects.addTo(map);

  function showError(message) {
    const box = $("error");
    box.textContent = message;
    box.hidden = false;
  }

  function clearError() {
    $("error").hidden = true;
  }

  async function api(path, body) {
    const options = body
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : {};
    const response = await fetch(path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `The server returned ${response.status}.`);
    }
    return data;
  }

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function cellRectangle(lat, lon, heightKm, widthKm, options) {
    const halfLat = heightKm / KM_PER_DEG / 2;
    const halfLon = widthKm / (KM_PER_DEG * Math.cos((lat * Math.PI) / 180)) / 2;
    return L.rectangle(
      [
        [lat - halfLat, lon - halfLon],
        [lat + halfLat, lon + halfLon],
      ],
      options
    );
  }

  function drawCityCells(cells) {
    state.cityRects.clearLayers();
    for (const cell of cells) {
      cellRectangle(cell.lat, cell.lon, cell.height_km, cell.width_km, {
        color: DATASET_COLOUR[cell.dataset] || "#334155",
        weight: 2,
        dashArray: cell.dataset === "gpcp" ? "6 4" : null,
        fillOpacity: 0.08,
      })
        .bindTooltip(`${cell.dataset}: ${cell.width_km} × ${cell.height_km} km`)
        .addTo(state.cityRects);
    }
  }

  function drawCircleCells(cells) {
    state.cellRects.clearLayers();
    for (const cell of cells) {
      let colour = COLOUR.flat;
      if (cell.significant && cell.slope_per_decade > 0) colour = COLOUR.rising;
      if (cell.significant && cell.slope_per_decade < 0) colour = COLOUR.falling;
      cellRectangle(cell.lat, cell.lon, cell.height_km, cell.width_km, {
        color: colour,
        weight: 1,
        fillColor: colour,
        fillOpacity: 0.35,
      })
        .bindTooltip(
          `${cell.slope_per_decade === null ? "no trend" : cell.slope_per_decade.toFixed(3)} per decade`
        )
        .addTo(state.cellRects);
    }
  }

  function drawCircle() {
    if (state.circle) map.removeLayer(state.circle);
    if (state.centreMarker) map.removeLayer(state.centreMarker);
    if (!state.centre) return;
    state.circle = L.circle(state.centre, {
      radius: state.radiusKm * 1000,
      color: "#0b5cad",
      weight: 2,
      dashArray: "6 5",
      fill: false,
    }).addTo(map);
    state.centreMarker = L.circleMarker(state.centre, { radius: 4, color: "#0b5cad" }).addTo(map);
  }

  function renderVariables() {
    const holder = $("vars");
    holder.replaceChildren();
    for (const v of state.variables) {
      const pressed = state.selected.has(v.ref);
      const chip = el(
        "button",
        { type: "button", class: "chip", "aria-pressed": String(pressed) },
        `${v.label} (${v.dataset})`
      );
      chip.addEventListener("click", () => {
        if (state.selected.has(v.ref)) state.selected.delete(v.ref);
        else state.selected.add(v.ref);
        renderVariables();
      });
      holder.appendChild(chip);
    }
  }

  async function loadCityCells() {
    const cityId = $("city").value;
    if (!cityId) return;
    const data = await api(`/api/cell?city=${encodeURIComponent(cityId)}`);
    drawCityCells(data.cells);
    const city = state.cities.find((c) => c.id === cityId);
    if (city) map.setView([city.lat, city.lon], 9);
  }

  function setMode(mode) {
    state.mode = mode;
    $("city-row").hidden = mode !== "city";
    $("circle-row").hidden = mode !== "circle";
    state.cityRects.clearLayers();
    state.cellRects.clearLayers();
    if (mode === "city") {
      loadCityCells().catch((e) => showError(e.message));
    } else {
      drawCircle();
    }
  }

  function chart(periods, values, unit) {
    const width = 640;
    const height = 200;
    const pad = { l: 56, r: 12, t: 10, b: 26 };
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "chart");
    svg.setAttribute("role", "img");
    const finite = values.filter((v) => v !== null);
    if (!finite.length) return svg;
    const lo = Math.min(...finite);
    const hi = Math.max(...finite);
    const span = hi - lo || 1;
    const x = (i) => pad.l + (i / Math.max(values.length - 1, 1)) * (width - pad.l - pad.r);
    const y = (v) => pad.t + (1 - (v - lo) / span) * (height - pad.t - pad.b);
    const add = (tag, attrs, text) => {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      if (text !== undefined) node.textContent = text;
      svg.appendChild(node);
      return node;
    };
    add("line", { x1: pad.l, x2: pad.l, y1: pad.t, y2: height - pad.b, class: "axis" });
    add("line", { x1: pad.l, x2: width - pad.r, y1: height - pad.b, y2: height - pad.b, class: "axis" });
    add("text", { x: pad.l - 6, y: pad.t + 10, "text-anchor": "end" }, `${hi.toFixed(2)} ${unit}`);
    add("text", { x: pad.l - 6, y: height - pad.b, "text-anchor": "end" }, `${lo.toFixed(2)}`);
    add("text", { x: pad.l, y: height - 6 }, periods[0].slice(0, 4));
    add("text", { x: width - pad.r, y: height - 6, "text-anchor": "end" }, periods[periods.length - 1].slice(0, 4));

    let run = [];
    const flush = () => {
      if (run.length > 1) {
        add("polyline", { points: run.join(" "), class: "line", style: "stroke: var(--cool)" });
      }
      run = [];
    };
    values.forEach((v, i) => {
      if (v === null) flush();
      else run.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    });
    flush();
    return svg;
  }

  function summaryLine(summary) {
    return el("p", {}, summary.sentence);
  }

  function warningsList(warnings) {
    if (!warnings || !warnings.length) return null;
    const list = el("ul", { class: "muted" });
    for (const w of warnings) list.appendChild(el("li", {}, w));
    return list;
  }

  function renderCityResult(result) {
    const card = el("section", { class: "panel result" });
    card.appendChild(el("h3", {}, result.label));
    const cell = result.cell;
    card.appendChild(
      el(
        "p",
        { class: "muted" },
        `${result.dataset} cell: ${cell.width_km} × ${cell.height_km} km, centred at ${cell.lat.toFixed(3)}, ${cell.lon.toFixed(3)}`
      )
    );
    card.appendChild(summaryLine(result.summary));
    const warnings = warningsList(result.warnings);
    if (warnings) card.appendChild(warnings);
    card.appendChild(chart(result.periods, result.series, result.unit));
    return card;
  }

  function renderCircleResult(result) {
    const card = el("section", { class: "panel result" });
    card.appendChild(el("h3", {}, result.label));
    const a = result.agreement;
    card.appendChild(
      el(
        "p",
        { class: "agree" },
        `${a.rising} cell(s) rise significantly, ${a.falling} fall significantly, ` +
          `${a.not_significant} show no significant trend (of ${result.cells_used} cells).`
      )
    );
    if (a.slope_min !== null && a.slope_max !== null) {
      card.appendChild(
        el(
          "p",
          { class: "muted" },
          `Per-cell slope runs from ${a.slope_min.toFixed(3)} to ${a.slope_max.toFixed(3)} ${result.unit} per decade.`
        )
      );
    }
    const warnings = warningsList(result.warnings);
    if (warnings) card.appendChild(warnings);

    const reference = el("div", { class: "avg" });
    reference.appendChild(el("h3", {}, "Reference: combined average"));
    reference.appendChild(summaryLine(result.average.summary));
    reference.appendChild(chart(result.average.periods, result.average.series, result.unit));
    card.appendChild(reference);
    return card;
  }

  function renderResults(data) {
    const holder = $("results");
    holder.replaceChildren();
    data.results.forEach((result) => {
      holder.appendChild(data.mode === "city" ? renderCityResult(result) : renderCircleResult(result));
    });
    const first = data.results[0];
    if (data.mode === "circle" && first) {
      drawCircleCells(first.cells);
    }
  }

  let latestRun = 0;

  async function run() {
    clearError();
    if (!state.selected.size) {
      showError("Pick at least one variable.");
      return;
    }
    const body = { mode: state.mode, variables: [...state.selected] };
    if (state.mode === "city") {
      body.city_id = $("city").value;
    } else {
      if (!state.centre) {
        showError("Click the map to set the centre of the circle.");
        return;
      }
      body.lat = state.centre.lat;
      body.lon = state.centre.lng;
      body.radius_km = state.radiusKm;
    }
    const from = $("from").value;
    const to = $("to").value;
    if (from) body.from = Number(from);
    if (to) body.to = Number(to);
    const id = ++latestRun;
    try {
      const data = await api("/api/analyse", body);
      if (id === latestRun) renderResults(data);
    } catch (e) {
      if (id === latestRun) showError(e.message);
    }
  }

  async function init() {
    try {
      const [cities, variables] = await Promise.all([api("/api/cities"), api("/api/variables")]);
      state.cities = cities.cities;
      state.variables = variables.variables;
      const select = $("city");
      for (const c of state.cities) select.appendChild(el("option", { value: c.id }, c.name));
      const first = state.variables.find((v) => v.ref === "merra2:t2m") || state.variables[0];
      if (first) state.selected.add(first.ref);
      renderVariables();
      if (state.cities.length) loadCityCells().catch((e) => showError(e.message));
    } catch (e) {
      showError(e.message);
    }
  }

  $("mode").addEventListener("change", (event) => setMode(event.target.value));
  $("city").addEventListener("change", () => loadCityCells().catch((e) => showError(e.message)));
  $("radius").addEventListener("input", (event) => {
    state.radiusKm = Number(event.target.value);
    $("radius-out").textContent = `${state.radiusKm} km`;
    drawCircle();
  });
  map.on("click", (event) => {
    if (state.mode !== "circle") return;
    state.centre = event.latlng;
    drawCircle();
  });
  $("run").addEventListener("click", run);

  init();
})();
