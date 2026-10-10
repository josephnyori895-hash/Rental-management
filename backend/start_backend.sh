#!/usr/bin/env bash
# Launcher for Rental OS backend (port 8011). Run detached so it survives shell exits.
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BACKEND_DIR"
pkill -f "uvicorn.*rental" 2>/dev/null
sleep 1
nohup ./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 \
  > "$BACKEND_DIR/backend.log" 2>&1 < /dev/null &
disown
echo "backend started pid $!"
