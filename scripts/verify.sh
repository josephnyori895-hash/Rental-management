#!/usr/bin/env bash
# Release gate. Run from anywhere in the repo. Nothing ships unless this exits 0.
#
# Three rules this script exists to enforce:
#   1. A gate that silently skips is not a gate. A missing or unreachable test
#      database fails the run instead of producing a green tick over nothing.
#   2. The tenant-isolation tests must actually execute. Zero collected, or any
#      skipped, fails the run.
#   3. Counts come from the JUnit XML report, not from scraping terminal output:
#      pytest's text summary changes between versions and a missing line must
#      never be read as success.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/backend/venv/bin/python"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILED=0

row() { printf '  %-24s %s\n' "$1" "$2"; }

SUMMARISE='
import sys, xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    print("no xml report")
    raise SystemExit(1)
suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
t = f = e = s = 0
for su in suites:
    t += int(su.get("tests") or 0)
    f += int(su.get("failures") or 0)
    e += int(su.get("errors") or 0)
    s += int(su.get("skipped") or 0)
passed = t - f - e - s
print(f"{t} tests, {passed} passed, {f} failed, {e} errors, {s} skipped")
raise SystemExit(0 if (f + e) == 0 and t > 0 else 1)
'

step() {
  local name="$1" log="$2"
  shift 2
  if "$@" >"$log" 2>&1; then
    row "$name" "PASS"
  else
    row "$name" "FAIL"
    tail -15 "$log" | sed 's/^/      /'
    FAILED=1
  fi
}

echo "verify: $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo 'no-git')"
echo

# ── Test database must exist, not be skipped, and be provably scratch ──
if DB_REPORT="$(cd "$ROOT/backend" && "$PY" -c "
import sys
import tests.conftest as c
print(c.TEST_DATABASE_IDENTITY)
sys.exit(0 if c.DB_AVAILABLE else 1)
" 2>"$WORK/db.log")"; then
  row "test database" "reachable — $DB_REPORT"
else
  row "test database" "REFUSED/UNREACHABLE — gate fails"
  sed 's/^/      /' "$WORK/db.log" | tail -8
  FAILED=1
fi

step "python import"  "$WORK/import.log"  \
  bash -c "cd '$ROOT/backend' && '$PY' -c 'import app.main'"
step "settings load"  "$WORK/settings.log" \
  bash -c "cd '$ROOT/backend' && '$PY' -c 'from app.core.config import settings as s; s.REMINDERS_ENABLED; s.RENT_RUN_ENABLED'"
step "alembic single head" "$WORK/alembic.log" \
  bash -c "cd '$ROOT/backend' && test \"\$(./venv/bin/alembic heads 2>/dev/null | grep -c 'head')\" = 1"

# ── Backend suite ────────────────────────────────────────────────────
FULL_XML="$WORK/full.xml"
if (cd "$ROOT/backend" && timeout 900 ./venv/bin/pytest -q --junitxml="$FULL_XML") >"$WORK/full.log" 2>&1; then
  FULL_EXIT=0
else
  FULL_EXIT=$?
fi
FULL_SUMMARY="$("$PY" -c "$SUMMARISE" "$FULL_XML" 2>/dev/null || echo "no xml report")"
FULL_SKIPPED="$(printf '%s' "$FULL_SUMMARY" | grep -Eo '[0-9]+ skipped' | grep -Eo '[0-9]+' || echo 0)"
if [ "$FULL_EXIT" -ne 0 ]; then
  row "backend tests" "FAIL  [$FULL_SUMMARY]"
  tail -15 "$WORK/full.log" | sed 's/^/      /'
  FAILED=1
elif [ "${FULL_SKIPPED:-0}" -ne 0 ]; then
  row "backend tests" "FAIL  [$FULL_SUMMARY — skips are not passes]"
  FAILED=1
else
  row "backend tests" "PASS  [$FULL_SUMMARY]"
fi

# ── Isolation tests: must run, must not skip ─────────────────────────
ISO_XML="$WORK/iso.xml"
if (cd "$ROOT/backend" && timeout 300 ./venv/bin/pytest tests/test_property_isolation.py -q --junitxml="$ISO_XML") >"$WORK/iso.log" 2>&1; then
  ISO_EXIT=0
else
  ISO_EXIT=$?
fi
ISO_SUMMARY="$("$PY" -c "$SUMMARISE" "$ISO_XML" 2>/dev/null || echo "no xml report")"
ISO_TESTS="$(printf '%s' "$ISO_SUMMARY" | grep -Eo '^[0-9]+ tests' | grep -Eo '^[0-9]+' || echo 0)"
ISO_SKIPPED="$(printf '%s' "$ISO_SUMMARY" | grep -Eo '[0-9]+ skipped' | grep -Eo '[0-9]+' || echo 0)"

if [ "$ISO_EXIT" -ne 0 ]; then
  row "tenant isolation" "FAIL  [$ISO_SUMMARY]"
  tail -15 "$WORK/iso.log" | sed 's/^/      /'
  FAILED=1
elif [ "${ISO_TESTS:-0}" -eq 0 ]; then
  row "tenant isolation" "FAIL  [0 tests collected]"
  FAILED=1
elif [ "${ISO_SKIPPED:-0}" -ne 0 ]; then
  row "tenant isolation" "FAIL  [$ISO_SUMMARY — skipped]"
  FAILED=1
else
  row "tenant isolation" "PASS  [$ISO_SUMMARY]"
fi

step "tsc --noEmit"   "$WORK/tsc.log"     \
  bash -c "cd '$ROOT/frontend' && npx tsc --noEmit"
step "vite build"     "$WORK/build.log"   \
  bash -c "cd '$ROOT/frontend' && npm run build"
step "sw syntax"      "$WORK/sw.log"      \
  bash -c "cd '$ROOT/frontend' && node --check dist/sw.js"

echo
if [ "$FAILED" -eq 0 ]; then
  echo "GATE: PASS"
else
  echo "GATE: FAIL"
fi
exit "$FAILED"
