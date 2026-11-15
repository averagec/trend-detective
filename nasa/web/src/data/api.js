// The only place the website talks to the analysis backend (Flask). Contract: docs/api.md.
// Nothing here computes a statistic: it fetches, caches and reports errors.
// Paths are relative so the site works wherever Flask serves it, and through the Vite proxy.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 = the server could not be reached
  }
}

// Every /api error is {"error": "...", "status": N}: show that message as it is.
async function request(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError("Cannot reach the analysis server. Is it running?", 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError((body && (body.error || body.description)) || `Request failed (${response.status})`, response.status);
  }
  if (body === null) throw new ApiError("The analysis server sent something that is not JSON.", response.status);
  return body;
}

const cache = new Map(); // GET url -> promise; a failed request is not kept
function get(path) {
  if (!cache.has(path)) {
    const p = request(path);
    cache.set(path, p);
    p.catch(() => cache.delete(path));
  }
  return cache.get(path);
}

const query = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== "")).toString();

export const getMeta = () => get("api/meta"); // {variables, regions, years}
export const getTrend = ({ variable, region, from, to }) => get(`api/trend?${query({ variable, region, from, to })}`);
// One variable across all its regions, judged together (the "layer" family).
export const getScan = ({ variable, from, to }) => get(`api/scan?${query({ variable, from, to })}`);
// Your own monthly series: {label, unit, start: "YYYY-MM", values: [number|null, ...]}
export const analyseOwn = (body) =>
  request("api/analyse-series", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// For rapid changes (a year box, a picker): only the newest request may update the screen.
//   const latest = newest();  latest(getTrend(...)).then((data) => { if (data !== STALE) draw(data); });
export const STALE = Symbol("stale");
export function newest() {
  let n = 0;
  return (promise) => {
    const id = ++n;
    return promise.then((v) => (id === n ? v : STALE), (e) => { if (id === n) throw e; return STALE; });
  };
}
