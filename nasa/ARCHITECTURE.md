# Architecture

Status: **provisional**. Python core decided (ADR 0002). Pipeline decided in ADR 0003. The
interactive app is a Flask app that computes on request (ADR 0004; it replaces the React plan).

## Overview
User picks a question (what), a region (where) and a year window (when) → the app asks `core`
for the trend and significance → the page shows the plot, the trend line and a plain-language
verdict. The data path behind it:

```
ingest/merra2_download.py  -> data/raw/merra2/subset/        (Harmony, network)
process/merra2_clean.py    -> data/processed/merra2/monthly_regional.csv
app/web.py (Flask)         -> per request: process.analyse_trends.build() -> core/summary.py -> browser
(optional) process/analyse_trends.py -> data/processed/json/  (static export for snapshots)
```

## Components
| Module | Path | Responsibility | May import |
|---|---|---|---|
| ingest | `src/trend_detective/ingest/` | Fetch + cache NASA data (only place with network calls) | — |
| process | `src/trend_detective/process/` | Clean raw files, unit conversion, VPD, regional means, series builder. No statistics. | core, catalog, numpy, h5py |
| core | `src/trend_detective/core/` | Pure stats: `trend.py` (deseasonalise, OLS, Mann-Kendall, Sen, area weighting), `summary.py` (tests + plain-language sentence) | numpy/scipy |
| catalog | `src/trend_detective/catalog/` | Variables (`variables.py`), regions (`regions.py`), study sites (`sites.py`): plain-language text | — |
| app | `src/trend_detective/app/` | `web.py`: the dynamic app for students and the public (Flask). `nasa_view.py`: internal checks of raw files. | core, catalog, process |
| demo data | `data/demo/` | Cached CSVs for demo cases (committed, small). Demo cases must run offline. | — |

## Invariants (enforced in `scripts/check.sh`)
- `core` never imports `app` or `ingest`, and does no network I/O.
- Only `ingest` uses the network (`requests`, `httpx`, `earthaccess`, `urllib`, Harmony).
- Every number shown to users comes from `core` (no ad-hoc stats in `app`, `process` or the browser).
- Golden tests in `tests/core/` must pass (see `docs/science-rules.md`).
- `process` reads local files only. The app computes statistics only through `core/`; the page
  computes none.
- Statistics are described in `docs/statistics.md`. Any change to `core/` updates that file.
