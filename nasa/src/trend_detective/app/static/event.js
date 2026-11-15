(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];

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

  function fmt(value, digits, unit) {
    if (value === null || value === undefined) return "not available";
    const text = Number(value).toFixed(digits);
    return unit ? `${text} ${unit}` : text;
  }

  function signed(value, digits, unit) {
    if (value === null || value === undefined) return "not available";
    const v = Number(value);
    return `${v > 0 ? "+" : ""}${v.toFixed(digits)}${unit ? " " + unit : ""}`;
  }

  function section(title) {
    const card = el("section", { class: "panel result" });
    card.appendChild(el("h2", {}, title));
    return card;
  }

  function table(headers, rows, numericFrom) {
    const wrap = el("div", { class: "table-wrap" });
    const t = el("table");
    const thead = el("thead");
    const headRow = el("tr");
    headers.forEach((h, i) => headRow.appendChild(el("th", i >= numericFrom ? { class: "num" } : {}, h)));
    thead.appendChild(headRow);
    t.appendChild(thead);
    const tbody = el("tbody");
    for (const row of rows) {
      const tr = el("tr");
      row.forEach((cell, i) => tr.appendChild(el("td", i >= numericFrom ? { class: "num" } : {}, cell)));
      tbody.appendChild(tr);
    }
    t.appendChild(tbody);
    wrap.appendChild(t);
    return wrap;
  }

  function renderCall(data) {
    const card = section("1. Trend or one-time event?");
    card.appendChild(el("p", { class: "call" }, data.sentence));
    const trend = data.trend;
    const sig = trend.p_value !== null && trend.p_value < 0.05;
    const line = sig
      ? `The rainfall record shows a significant ${trend.direction} trend of ${signed(trend.slope_per_decade, 3, trend.unit + " per decade")} (95% test).`
      : `The rainfall record shows no significant trend (yet). The estimated change is ${signed(trend.slope_per_decade, 3, trend.unit + " per decade")}.`;
    card.appendChild(el("p", {}, line));
    return card;
  }

  function renderWhere(data) {
    const card = section("2. Where and when?");
    const cell = data.where_when.cell;
    const datasetName = cell.dataset === "gpcp" ? "GPCP" : "MERRA-2";
    card.appendChild(el("p", {},
      `Where: the ${datasetName} grid cell that contains ${data.city.name}, ` +
      `${cell.width_km} × ${cell.height_km} km, centred at ${cell.lat.toFixed(3)}, ${cell.lon.toFixed(3)}.`));
    const peak = data.where_when.peak;
    if (peak) {
      card.appendChild(el("p", {},
        `When: the strongest signal fell in ${peak.period} (${Math.round(peak.percentile)}th percentile for that month).`));
    }
    if (data.period.kind === "year") {
      const rows = data.where_when.months.map((m) => [
        m.period,
        fmt(m.total_mm, 0, "mm"),
        fmt(m.median_mm, 0, "mm"),
        signed(m.percent, 0, "%"),
        fmt(m.percentile, 0),
      ]);
      card.appendChild(table(["Month", "Total", "Median", "Change", "Percentile"], rows, 1));
    }
    return card;
  }

  function renderAmount(data) {
    const card = section("3. By how much did it change?");
    const a = data.amount;
    const word = data.incident === "flood" ? "wetter" : "drier";
    card.appendChild(table(
      ["Measure", "Value"],
      [
        ["Observed rainfall", fmt(a.observed_mm, 0, "mm")],
        ["Usual rainfall (median)", fmt(a.median_mm, 0, "mm")],
        ["Change in amount", signed(a.amount_mm, 0, "mm")],
        ["Change in percent", signed(a.percent, 0, "%")],
        ["Rank against the record", `${fmt(a.percentile, 0)} (0 is driest, 100 is wettest)`],
      ],
      1
    ));
    card.appendChild(el("p", { class: "note" },
      `Measured against the usual amount for the same ${data.period.kind}. A ${word} result is marked as an extreme when it reaches the 10th or 90th percentile.`));
    return card;
  }

  function renderFactors(data) {
    const card = section("4. Factors that moved together with the rain");
    card.appendChild(el("p", { class: "note" },
      "Co-movement only. These factors moved with rainfall in the record. None of them is shown as a cause."));
    if (!data.co_movement.length) {
      card.appendChild(el("p", {}, "No factors had enough overlapping months to compare."));
      return card;
    }
    const rows = data.co_movement.map((f) => [
      f.label,
      f.source,
      f.r === null ? "not available" : f.r.toFixed(2),
      f.p_value === null ? "not available" : (f.p_value < 0.001 ? "< 0.001" : f.p_value.toFixed(3)),
      String(f.n),
      f.period_anomaly === null ? "not available" : signed(f.period_anomaly, 2, f.unit),
      signed(f.implied_rain_change, 2, "mm/day"),
    ]);
    card.appendChild(table(
      ["Factor", "Source", "Correlation", "p-value", "Months shared", "Change in the period", "Rain change implied"],
      rows,
      2
    ));
    return card;
  }

  function renderWarnings(data) {
    if (!data.warnings || !data.warnings.length) return null;
    const card = section("Notes");
    const list = el("ul", { class: "note" });
    for (const w of data.warnings) list.appendChild(el("li", {}, w));
    card.appendChild(list);
    return card;
  }

  function renderResult(data) {
    const holder = $("results");
    holder.replaceChildren();
    const head = el("p", { class: "note" },
      `${data.incident === "flood" ? "Flood" : "Drought"} check for ${data.city.name}, ` +
      `${data.period.label}. Rainfall source: ${data.city.rainfall_label}. ` +
      (data.incident === "flood"
        ? "Flood here means unusually heavy rainfall in the record. It does not measure river or street flooding."
        : "Drought here means unusually little rainfall in the record. It does not measure soil or water supply."));
    holder.appendChild(head);
    holder.appendChild(renderCall(data));
    holder.appendChild(renderWhere(data));
    holder.appendChild(renderAmount(data));
    holder.appendChild(renderFactors(data));
    const notes = renderWarnings(data);
    if (notes) holder.appendChild(notes);
  }

  function periodKind() {
    return document.querySelector('input[name="ptype"]:checked').value;
  }

  function syncPeriodControls() {
    $("month-row").hidden = periodKind() !== "month";
  }

  async function run() {
    clearError();
    const body = {
      incident: document.querySelector('input[name="incident"]:checked').value,
      city_id: $("city").value,
      period: { type: periodKind(), year: Number($("year").value), month: Number($("month").value) },
    };
    try {
      renderResult(await api("/api/event", body));
    } catch (e) {
      showError(e.message);
    }
  }

  async function init() {
    for (let m = 1; m <= 12; m++) {
      $("month").appendChild(el("option", { value: m }, MONTHS[m - 1]));
    }
    $("month").value = "7";
    try {
      const data = await api("/api/cities");
      for (const c of data.cities) $("city").appendChild(el("option", { value: c.id }, c.name));
      if (!data.cities.length) showError("The city list is empty.");
    } catch (e) {
      showError(e.message);
    }
    syncPeriodControls();
  }

  document.querySelectorAll('input[name="ptype"]').forEach((input) =>
    input.addEventListener("change", syncPeriodControls));
  $("run").addEventListener("click", run);
  init();
})();
