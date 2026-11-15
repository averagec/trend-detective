# AGENTS.md: Trend Detective (NASA Space Apps 2026)

This file is a **map, not a manual**. Keep it under 80 lines (enforced). Detail lives in the
files below; read them only when the task touches that area.

## What this is
A 48h hackathon entry (Nov 14–15 2026) for "Be An Earth System Trend Detective!": pick an
Earth-science variable + region, plot it over time, and say what's changing, where, how much,
and whether it's significant. Audience: students and the public. Target: a Global Award.

## Where to look
| Need | Read |
|---|---|
| Challenge, users, awards, scope | `docs/product-sense.md` |
| **Stats/science rules (read before any analysis or result text)** | `docs/science-rules.md` |
| Modules, boundaries, invariants | `ARCHITECTURE.md` |
| NASA data sources + quirks | `docs/data-sources.md` |
| Style rules | `docs/conventions.md` |
| Why something was decided | `docs/decisions/` |
| What we're doing now | `PLANS.md` → `exec-plans/active/hackathon-48h.md` |
| Shortcuts to pay back | `exec-plans/tech-debt-tracker.md` |

## Commands
- Setup: `pip install -e ".[dev]"`
- Verify everything: `./scripts/check.sh` (silent on pass; prints only failures)
- A task is not done until `check.sh` passes.

## Working rules
1. **Resume from the plan.** Start each session by reading the active exec plan's
   Progress log; append a line before you stop.
2. **Plan first for anything >3 steps.** Use `exec-plans/TEMPLATE.md`.
3. **Stats come only from `core/trend.py`.** Never compute a trend or p-value ad hoc.
   Never loosen a golden test in `tests/core/` to make a change pass.
4. **Protect the context window.** Use the `data-scout` subagent for exploring datasets
   and APIs; never paste raw NetCDF/CSV contents. Use `verifier` before a demo case is marked done.
5. **Demo safety.** Every demo case runs offline from `data/demo/`.
6. **Record decisions** as ADRs. **Never** commit `.env` or raw data (`data/raw/` is ignored).
7. **Time-box.** Hackathon: prefer the simplest thing that's scientifically right.

## Updating this harness
When an agent gets something wrong, fix the harness as well as the code: a wrong command
→ Commands; repeated drift → `docs/conventions.md` or a check in `scripts/check.sh`.
Add rules only from observed failures.
