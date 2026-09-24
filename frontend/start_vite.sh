#!/usr/bin/env bash
# Launcher for Rental OS frontend dev server (port 5173). Detached, survives shell exits.
cd "$(dirname "$0")"
pkill -f "vite.*rental" 2>/dev/null
sleep 1
nohup npx vite --host 127.0.0.1 --port 5173 \
  > /home/nyorii/Projects/rental-os/frontend/vite.log 2>&1 < /dev/null &
disown
echo "vite started pid $!"
