# 0008 - The website is served by Flask and gets every number from the API

- Status: proposed (2026-11-15). Needs the team's review of the choices marked **Review**.
- Extends: 0004 (Flask app) and 0007 (new API routes). Settles decision 1 of
  `exec-plans/active/web-integration.md` for the TREND.EXE part.

## Context
The TD-OS website (`web/`, Vite + three.js) computed its own statistics in the browser on synthetic
data (`web/src/stats/trend-analysis.js`). `ARCHITECTURE.md` says every user-facing number comes from
`core/`. The analysis engine (`core/` behind `/api/trend`, `/api/analyse`, `/api/scan`) now exists.

## Decision
- **One server, two halves.** Flask serves the built site (`web/dist`) at `/` and the JSON API under
  `/api/`. The plain internal page stays at `/classic`. `python src/trend_detective/app/web.py`
  serves both; `--web-dir` picks another build, `--web-dir ""` serves only the plain page.
  Same origin, so no CORS and no new dependency, and it runs offline on the demo laptop.
- **Development:** `npm run dev` (Vite) proxies `/api` to Flask on port 5000.
- **The seam is `docs/api.md`.** `web/src/data/api.js` is the only code that calls the backend.
  `web/src/data/to-chart.js` only reshapes a response into the chart spec; it computes nothing.
  The backend does not know about the site's code.
- **TREND.EXE** (`web/src/os/trend-app.js`) is a desktop app: pick a question, a place and the
  years; it shows the monthly series, the OLS line, the 95% band and the analysis the server returns
  (trend and CI, adjusted p, effective months, both Mann-Kendall p-values, the verdict and both q-values
  from the `significance` block of `/api/trend`, the server's sentence and warnings, verbatim).
- **Contract tests both ways.** `web/tests/fixtures/*.json` are real responses. `npm test` runs the
  mapper on them; `tests/app/test_web.py` fails if the live API's shape drifts from them.
  `scripts/check.sh` builds the site and runs both when `web/node_modules` exists.

## Consequences
- The browser still computes statistics elsewhere (MAP.EXE synthetic layers, CASES lineup). They are
  not touched here; the integration plan retires them step by step.
- Resolved by 0009: the page shows only the `significance` block's sentence, which allows for the other
  regions of the variable, so it no longer contradicts the q-value (East China air temperature 1990-2019:
  p = 0.041, q = 0.061, adjusted Mann-Kendall q = 0.007: verdict `unclear`).
- The first answer for a query is cached in the page, so a window already opened keeps working if the
  server stops; a new query shows "Cannot reach the analysis server".
- The family is the regions of one variable, so only the 3 MERRA-2 boxes can be
  drawn, not the 11 countries of the map, until country masks exist (plan step 8).
