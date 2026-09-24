#!/usr/bin/env bash
# Rental OS — Launch everything
# Starts: backend (FastAPI) → frontend (Vite) → desktop app (GTK+WebKit)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "╔══════════════════════════════════════════╗"
echo "║        Rental OS — Launch v0.1.0         ║"
echo "╚══════════════════════════════════════════╝"

# ── Clean up old processes ──
echo "[1/4] Cleaning old processes..."
pkill -f "uvicorn.*rental" 2>/dev/null || true
pkill -f "vite.*rental" 2>/dev/null || true
pkill -f "rental_desktop.py" 2>/dev/null || true
sleep 1

# ── Start backend ──
echo "[2/4] Starting backend on :8011..."
cd "$BACKEND_DIR"
nohup "$BACKEND_DIR/venv/bin/uvicorn" app.main:create_app --factory \
    --host 0.0.0.0 --port 8011 --log-level warning \
    > /tmp/rental_backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend
for i in $(seq 1 15); do
    if curl -sf --noproxy '*' http://localhost:8011/health > /dev/null 2>&1; then
        echo "  ✓ Backend healthy"
        break
    fi
    sleep 1
done

# ── Start frontend dev server ──
echo "[3/4] Starting frontend on :5173..."
cd "$FRONTEND_DIR"
nohup npx vite --host 0.0.0.0 --port 5173 \
    > /tmp/rental_vite.log 2>&1 &
VITE_PID=$!
echo "  Vite PID: $VITE_PID"

# Wait for frontend
for i in $(seq 1 15); do
    if curl -sf --noproxy '*' http://localhost:5173/ > /dev/null 2>&1; then
        echo "  ✓ Frontend ready"
        break
    fi
    sleep 1
done

# ── Launch desktop app ──
echo "[4/4] Launching desktop app..."
cd "$SCRIPT_DIR"
PYTHONUNBUFFERED=1 nohup python3 -u rental_desktop.py \
    > /tmp/rental_desktop.log 2>&1 &
DESKTOP_PID=$!
echo "  Desktop PID: $DESKTOP_PID"

sleep 2
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        All systems operational           ║"
echo "╠══════════════════════════════════════════╣"
echo "║ Desktop  : Rental OS (1200x800)          ║"
echo "║ Web      : http://localhost:5173         ║"
echo "║ Network  : http://10.42.0.1:5173         ║"
echo "║ API      : http://localhost:8011/docs    ║"
echo "║ Hotspot  : Rental OS / rental1234        ║"
echo "╚══════════════════════════════════════════╝"
