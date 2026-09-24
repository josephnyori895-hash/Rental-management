#!/usr/bin/env bash
# Launcher for Rental OS backend (port 8011). Run detached so it survives shell exits.
cd "$(dirname "$0")"
pkill -f "uvicorn.*rental" 2>/dev/null
sleep 1
nohup ./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 \
  > /home/nyorii/Projects/rental-os/backend/backend.log 2>&1 < /dev/null &
disown
echo "backend started pid $!"
