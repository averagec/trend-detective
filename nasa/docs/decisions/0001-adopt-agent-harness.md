# 0001 — Adopt an agent harness

- Status: accepted
- Date: 2026-11-14

## Context
Most code will be written with AI coding agents under hackathon time pressure.
Agents lose context between sessions and drift without guardrails.

## Decision
Use a repo-local harness: `AGENTS.md` as a short always-loaded map, deeper docs
loaded on demand, exec plans for multi-step work, and `scripts/check.sh` as the
single verification gate.

## Consequences
Small upfront cost; every agent mistake should become a harness update.

---
_New ADRs: copy this file, bump the number, keep it under a page._
