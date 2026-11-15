#!/usr/bin/env bash
# Single verification gate for humans and agents.
# Silent on success (saves agent context); prints only what failed.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
log=$(mktemp)
run() { # run <label> <cmd...>
  local label=$1; shift
  if ! "$@" >"$log" 2>&1; then
    echo "✗ $label"; tail -n 40 "$log"; fail=1
  fi
}

# --- Harness checks (always on) ---
lines=$(wc -l < AGENTS.md)
[ "$lines" -le 80 ] || { echo "✗ AGENTS.md is $lines lines (max 80) — move detail into docs/"; fail=1; }
if git ls-files 2>/dev/null | grep -qE '(^|/)\.env$'; then echo "✗ .env is tracked by git"; fail=1; fi

# --- Architecture invariants (see ARCHITECTURE.md) ---
PKG=src/trend_detective
if [ -d $PKG/core ]; then
  if grep -rnE '(from|import) +(trend_detective\.|\.\.)(app|ingest)' $PKG/core; then
    echo "✗ core imports app/ingest — core must stay pure"; fail=1
  fi
fi
net='^\s*(import|from) +(requests|httpx|earthaccess|urllib)'
offenders=$(grep -rlE "$net" $PKG --include=*.py 2>/dev/null | grep -v "^$PKG/ingest/" || true)
if [ -n "$offenders" ]; then
  echo "✗ network imports outside ingest/:"; echo "$offenders"; fail=1
fi
# The engine (core, process, app) never imports ingest: downloads stay in ingest/ and scripts/.
if grep -rnE '(from|import) +trend_detective\.ingest' $PKG/core $PKG/process $PKG/app 2>/dev/null; then
  echo "✗ core, process or app imports ingest"; fail=1
fi
# Golden tests must exist (science sensors)
[ -f tests/core/test_trend.py ] || { echo "✗ tests/core/test_trend.py missing (golden tests)"; fail=1; }

# --- Stack checks (auto-enable when the stack exists) ---
if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  if python -m ruff --version >/dev/null 2>&1; then run "ruff" python -m ruff check --quiet .; fi
  if python -m pytest --version >/dev/null 2>&1 && [ -d tests ]; then run "pytest" python -m pytest -q; fi
fi
if [ -f package.json ]; then
  grep -q '"lint"' package.json && run "npm lint" npm run -s lint
  grep -q '"typecheck"' package.json && run "typecheck" npm run -s typecheck
  grep -q '"test"' package.json && run "npm test" npm test --silent
fi

rm -f "$log"
[ $fail -eq 0 ] && exit 0 || exit 1
