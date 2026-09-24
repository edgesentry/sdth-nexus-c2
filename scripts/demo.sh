#!/usr/bin/env bash
# Start USV REST mock + run one auto-approved C2 cycle.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer EFFECTOR_BASE_URL; CLEARBOT_BASE_URL remains a compat fallback.
export EFFECTOR_BASE_URL="${EFFECTOR_BASE_URL:-${CLEARBOT_BASE_URL:-http://127.0.0.1:8000}}"
export CLEARBOT_BASE_URL="${CLEARBOT_BASE_URL:-$EFFECTOR_BASE_URL}"
export GATE_TIMEOUT_SEC="${GATE_TIMEOUT_SEC:-5}"
export SCENARIO="${SCENARIO:-S3}"

uv sync

uv run uvicorn mocks.usv:app --host 127.0.0.1 --port 8000 &
MOCK_PID=$!
cleanup() { kill "$MOCK_PID" 2>/dev/null || true; wait "$MOCK_PID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -sf "$EFFECTOR_BASE_URL/api/v1/telemetry" >/dev/null; then
    break
  fi
  sleep 0.1
done

uv run python -m app.main --scenario "${SCENARIO}" --yes --timeout "${GATE_TIMEOUT_SEC}"
echo "Demo complete (scenario=${SCENARIO})."
