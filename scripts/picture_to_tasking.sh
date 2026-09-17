#!/usr/bin/env bash
# One-shot Picture→Tasking demo: start local Core, run handshake, exit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export C2_HOST="${C2_HOST:-127.0.0.1}"
export C2_PORT="${C2_PORT:-8080}"
export C2_BASE_URL="${C2_BASE_URL:-http://${C2_HOST}:${C2_PORT}}"
export SCENARIO="${SCENARIO:-S2}"
export UNIT_ID="${UNIT_ID:-CUE-NODE-01}"

# If C2_BASE_URL points elsewhere (e.g. Cloudflare), skip local server.
START_LOCAL=1
if [[ -n "${C2_BASE_URL}" && "${C2_BASE_URL}" != "http://${C2_HOST}:${C2_PORT}" && "${C2_BASE_URL}" != "http://127.0.0.1:${C2_PORT}" ]]; then
  START_LOCAL=0
fi

uv sync

SERVER_PID=""
cleanup() {
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${START_LOCAL}" -eq 1 ]]; then
  uv run sdth-c2-server &
  SERVER_PID=$!
  for _ in $(seq 1 50); do
    if curl -sf "${C2_BASE_URL}/api/ontology/state" >/dev/null; then
      break
    fi
    sleep 0.1
  done
  if ! curl -sf "${C2_BASE_URL}/api/ontology/state" >/dev/null; then
    echo "FAIL: local sdth-c2-server did not become ready at ${C2_BASE_URL}" >&2
    exit 2
  fi
fi

EXTRA_ARGS=()
if [[ "${START_LOCAL}" -eq 1 ]]; then
  EXTRA_ARGS+=(--require-roundtrip)
fi

uv run python scripts/picture_to_tasking.py "${EXTRA_ARGS[@]}" "$@"
echo "Picture→Tasking demo complete (base=${C2_BASE_URL} scenario=${SCENARIO})."
