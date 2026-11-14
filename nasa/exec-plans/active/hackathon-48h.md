# Hackathon 48h build

- Owner: team
- Started: 2026-11-14
- Status: active

## Goal
A submitted entry that meets full scope (visualisation + significance analysis) with ≥2
demo case studies that pass `./scripts/check.sh`, plus the project page and demo video,
submitted before the official deadline (TODO: confirm time, SGT).

## Context
`docs/product-sense.md`, `docs/science-rules.md`, `ARCHITECTURE.md`, claude.ai project doc
`claude/project-context.md`.

## Steps
- [x] 0. Harness + validated stats core (`core/trend.py`, golden tests)
- [ ] 1. Combine the 3 reviews → pick the concept → update product-sense.md "Status"
- [ ] 2. ADR 0003: UI framework
- [ ] 3. Pick 2–3 demo cases (variable + region + why it's interesting) → `docs/demo-cases.md`
- [ ] 4. Ingest for the demo variables → cache to `data/demo/`
- [ ] 5. App: question flow → plot → trend + verdict sentence
- [ ] 6. Regional comparison (opposite trends) view
- [ ] 7. Verifier subagent pass on every demo case
- [ ] 8. Freeze features at T-8h: write-up, video, submission

## Progress log
- 2026-11-14 10:20 SGT — harness and stats core in place; waiting on reviews.

## Decisions & surprises
