# Architecture

Status: **provisional** (Python core decided, see ADR 0002; UI choice pending the build review).

## Overview
User picks a question (what and where) → we resolve it to a NASA variable + region →
`ingest` fetches and caches a time series → `core` deseasonalises it, then computes the trend
and significance → `app` shows the plot, the trend line and a plain-language verdict.

## Components
| Module | Path | Responsibility | May import |
|---|---|---|---|
| ingest | `src/trend_detective/ingest/` | Fetch + cache NASA data (only place with network calls) | — |
| core | `src/trend_detective/core/` | Pure stats: `trend.py` (deseasonalise, OLS, Mann-Kendall, Sen, area weighting) | numpy/scipy/pandas |
| catalog | `src/trend_detective/catalog/` | Variable/region definitions + plain-language descriptions | — |
| app | `src/trend_detective/app/` | UI the judges see (framework TBD) | core, catalog, ingest |
| demo data | `data/demo/` | Cached CSVs for demo cases (committed, small) | — |

## Invariants (enforced in `scripts/check.sh`)
- `core` never imports `app` or `ingest`, and does no network I/O.
- Only `ingest` uses the network (`requests`, `httpx`, `earthaccess`, `urllib`).
- Every number shown to users comes from `core` (no ad-hoc stats in `app`).
- Golden tests in `tests/core/` must pass (see `docs/science-rules.md`).
