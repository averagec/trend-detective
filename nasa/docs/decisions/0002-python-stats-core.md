# 0002 — Python stats core, UI undecided

- Status: accepted (core), pending (UI)
- Date: 2026-11-14

## Context
The trend math must be correct whichever idea wins the shortlist. NASA data tooling
(earthaccess, xarray, Giovanni downloads) is Python-first.

## Decision
Stats live in a pure Python module (`src/trend_detective/core/trend.py`) with golden tests.
The UI framework (e.g. Streamlit for speed vs a web front end for storytelling) is chosen
after the software-engineer review; record that as ADR 0003.

## Consequences
The UI can change late without touching the validated stats.
