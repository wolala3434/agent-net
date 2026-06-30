#!/usr/bin/env bash
# ============================================================
# start_all.sh — one-command demo startup
#
# Usage: bash platform/scripts/start_all.sh [backend_port] [dashboard_port] [agent_ports...]
# ============================================================
set -euo pipefail

# Configuration from environment or defaults
PLATFORM_URL="${PLATFORM_URL:-http://localhost:8000}"
AGENT_BASE_PORT="${AGENT_BASE_PORT:-9121}"

BACKEND_PORT="${1:-8000}"
DASHBOARD_PORT="${2:-8501}"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:${DASHBOARD_PORT}}"
AGENT_PORT_1="${3:-9121}"
AGENT_PORT_2="${4:-9122}"
AGENT_PORT_3="${5:-9123}"

REGISTRY_URL="${PLATFORM_URL}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "${PROJECT_ROOT}/data"

cleanup() {
    echo ""
    echo "[demo] Shutting down..."
    kill %1 %2 %3 %4 %5 2>/dev/null || true
    wait 2>/dev/null || true
    echo "[demo] All services stopped."
}
trap cleanup EXIT INT TERM

echo "============================================"
echo " Agent Internet — Demo"
echo "============================================"
echo " Backend    → ${REGISTRY_URL}"
echo " Dashboard  → ${DASHBOARD_URL}"
echo " Agents     → :${AGENT_PORT_1} :${AGENT_PORT_2} :${AGENT_PORT_3}"
echo "============================================"
echo ""

# --- 1. Start Backend ---
echo "[demo] Starting Backend on :${BACKEND_PORT}..."
cd "${PROJECT_ROOT}/platform/backend"
python -m uvicorn src.platform.main:app \
    --host 0.0.0.0 --port "${BACKEND_PORT}" &
BACKEND_PID=$!

# Wait for healthy
echo "[demo] Waiting for Backend health check..."
for i in $(seq 1 30); do
    if curl -s "${REGISTRY_URL}/health" > /dev/null 2>&1; then
        echo "[demo] Backend is healthy."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[demo] ERROR: Backend failed to start within 30s."
        exit 1
    fi
    sleep 1
done

# --- 2. Seed demo agents ---
echo "[demo] Seeding demo agents..."
python "${PROJECT_ROOT}/platform/scripts/seed_demo_agents.py" \
    --registry "${REGISTRY_URL}" || echo "[demo] (seed skipped)"

# --- 3. Start Demo Agents ---
echo "[demo] Starting Credit Risk Analyst on :${AGENT_PORT_1}..."
cd "${PROJECT_ROOT}/agent-side/agents/credit-risk-analyst"
python run.py --port "${AGENT_PORT_1}" --registry "${REGISTRY_URL}" &
AGENT1_PID=$!

echo "[demo] Starting Supply Chain Expert on :${AGENT_PORT_2}..."
cd "${PROJECT_ROOT}/agent-side/agents/supply-chain-expert"
python run.py --port "${AGENT_PORT_2}" --registry "${REGISTRY_URL}" &
AGENT2_PID=$!

echo "[demo] Starting Echo Agent on :${AGENT_PORT_3}..."
cd "${PROJECT_ROOT}/agent-side/agents/echo"
python run.py --port "${AGENT_PORT_3}" --registry "${REGISTRY_URL}" &
AGENT3_PID=$!

# --- 4. Start Dashboard ---
echo "[demo] Starting Dashboard on :${DASHBOARD_PORT}..."
cd "${PROJECT_ROOT}/dashboard"
npm install
npm run dev -- --host 0.0.0.0 --port "${DASHBOARD_PORT}" &
DASHBOARD_PID=$!

echo ""
echo "============================================"
echo " All services running!"
echo "   Dashboard → ${DASHBOARD_URL}"
echo "   Press Ctrl+C to stop all services."
echo "============================================"

wait
