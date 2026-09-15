#!/usr/bin/env bash
# Start Clearbot mock + run one auto-approved C2 cycle.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export CLEARBOT_BASE_URL="${CLEARBOT_BASE_URL:-http://127.0.0.1:8000}"
export GATE_TIMEOUT_SEC="${GATE_TIMEOUT_SEC:-5}"

uv sync

uv run uvicorn app.mock_server:app --host 127.0.0.1 --port 8000 &
MOCK_PID=$!
cleanup() { kill "$MOCK_PID" 2>/dev/null || true; wait "$MOCK_PID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -sf "$CLEARBOT_BASE_URL/api/v1/telemetry" >/dev/null; then
    break
  fi
  sleep 0.1
done

uv run python -m app.main --yes --timeout "${GATE_TIMEOUT_SEC}"
echo "Demo complete."
