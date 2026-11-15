# 0004 - Dynamic app in Flask (replaces the React front end)

- Status: accepted (2026-11-14, on the team's request)
- Supersedes: the front-end part of 0003
- Amended by 0007: adds `POST /api/analyse-series` and `GET /api/scan`; routes and fields are in `docs/api.md`

## Context
The static React app read JSON copied from the pipeline. Changing the years or the region
meant re-running the pipeline and re-copying files. The team asked for something dynamic, and
the project already has Python code for the analysis, so the front end should use it.

## Decision
- `src/trend_detective/app/web.py` is a Flask app. It serves one page and two JSON routes:
  `/api/meta` (variables, regions, available years) and `/api/trend` (region, variable and
  year window in; the full result out).
- Each request calls `process.analyse_trends.build()`, which calls `core/summary.py`. So the
  trend is worked out for the window the user chose, using the same tested statistics.
- The page (`app/templates/index.html`, `app/static/app.js`, `app/static/app.css`) has no build
  step and no framework. It only draws what the server returns.
- The processed CSV is read once and reloaded when its file changes.
- Variable text lives in `catalog/variables.py`, so the question wording is not in the page.

## Consequences
- Flask is a project dependency (added to pyproject.toml).
- Each request reads the processed CSV in memory and runs the statistics. For the current size
  (about 550 months per series) this takes milliseconds.
- The app needs a server running. For an offline demo, run it locally on the demo laptop.
- The static JSON export (`process/analyse_trends.py`) is kept for reproducibility, and can be
  used to snapshot results.
- Tests: `tests/app/test_web.py` (routes, year window, error responses).
