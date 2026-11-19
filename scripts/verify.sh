#!/usr/bin/env bash
# Release gate. Run from anywhere in the repo. Nothing ships unless this exits 0.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/backend/venv/bin/python"
FAILED=0

row() { printf '  %-26s %s\n' "$1" "$2"; }

check() {
  local name="$1"; shift
  if "$@" >/tmp/verify_step.log 2>&1; then
    row "$name" "PASS"
  else
    row "$name" "FAIL  (see /tmp/verify_step.log)"
    tail -12 /tmp/verify_step.log | sed 's/^/      /'
    FAILED=1
  fi
}

echo "verify: $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo 'no-git')"
echo

check "python import"     bash -c "cd '$ROOT/backend' && '$PY' -c 'import app.main'"
check "settings load"     bash -c "cd '$ROOT/backend' && '$PY' -c 'from app.core.config import settings as s; s.REMINDERS_ENABLED; s.RENT_RUN_ENABLED'"
check "alembic single head" bash -c "cd '$ROOT/backend' && test \"\$(./venv/bin/alembic heads 2>/dev/null | grep -c 'head')\" = 1"
check "backend tests"     bash -c "cd '$ROOT/backend' && timeout 600 ./venv/bin/pytest -q"
check "tenant isolation"  bash -c "cd '$ROOT/backend' && timeout 300 ./venv/bin/pytest tests/test_property_isolation.py -q"
check "tsc --noEmit"      bash -c "cd '$ROOT/frontend' && npx tsc --noEmit"
check "vite build"        bash -c "cd '$ROOT/frontend' && npm run build"
check "sw syntax"         bash -c "cd '$ROOT/frontend' && node --check dist/sw.js"

echo
if [ "$FAILED" -eq 0 ]; then
  echo "GATE: PASS"
else
  echo "GATE: FAIL"
fi
exit "$FAILED"
