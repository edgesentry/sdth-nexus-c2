#!/usr/bin/env bash
# One-shot live LLM interpret smoke: Python LiteLLM + C2 + S2 /api/interpret.
# CI does **not** run this (stays LLM-free). Needs a backend key (GEMINI_API_KEY for default model).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LITELLM_DIR="${ROOT}/deploy/litellm"
LITELLM_HOST="${LITELLM_HOST:-127.0.0.1}"
LITELLM_PORT="${LITELLM_PORT:-4000}"
LITELLM_URL="http://${LITELLM_HOST}:${LITELLM_PORT}"

export C2_HOST="${C2_HOST:-127.0.0.1}"
export C2_PORT="${C2_PORT:-8080}"
export C2_BASE_URL="${C2_BASE_URL:-http://${C2_HOST}:${C2_PORT}}"
export SCENARIO="${SCENARIO:-S2}"
export LLM_BASE_URL="${LLM_BASE_URL:-${LITELLM_URL}/v1}"
export LLM_API_KEY="${LLM_API_KEY:-${LITELLM_MASTER_KEY:-sk-litellm-local}}"
export LLM_MODEL="${LLM_MODEL:-gemini-3.8-flash}"
export LLM_TIMEOUT_S="${LLM_TIMEOUT_S:-30}"

if [[ ! -f "${LITELLM_DIR}/.env" && -f "${LITELLM_DIR}/.env.example" ]]; then
  cp "${LITELLM_DIR}/.env.example" "${LITELLM_DIR}/.env"
  echo "NOTE: copied deploy/litellm/.env.example → .env (set GEMINI_API_KEY for live smoke)"
fi

wait_http() {
  local url="$1"
  local tries="${2:-60}"
  local delay="${3:-0.25}"
  for _ in $(seq 1 "${tries}"); do
    if curl -sf "${url}" >/dev/null; then
      return 0
    fi
    sleep "${delay}"
  done
  return 1
}

load_litellm_env() {
  set -a
  # shellcheck disable=SC1091
  source "${LITELLM_DIR}/.env"
  set +a
  export LLM_API_KEY="${LLM_API_KEY:-${LITELLM_MASTER_KEY:-sk-litellm-local}}"
}

LITELLM_PID=""
STARTED_LITELLM=0
SERVER_PID=""
cleanup() {
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  if [[ -n "${LITELLM_PID}" ]]; then
    kill "${LITELLM_PID}" 2>/dev/null || true
    wait "${LITELLM_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if ! curl -sf "${LITELLM_URL}/health/liveliness" >/dev/null; then
  echo "Starting LiteLLM via Python (uv --group litellm)…"
  uv sync --group litellm --group dev
  load_litellm_env
  uv run --group litellm litellm --config "${LITELLM_DIR}/config.yaml" --port "${LITELLM_PORT}" &
  LITELLM_PID=$!
  STARTED_LITELLM=1
  if ! wait_http "${LITELLM_URL}/health/liveliness" 80 0.5; then
    echo "FAIL: LiteLLM did not become ready at ${LITELLM_URL}" >&2
    echo "Start: uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000" >&2
    exit 2
  fi
fi
echo "LiteLLM ready at ${LITELLM_URL}"

START_LOCAL=1
if [[ -n "${C2_BASE_URL}" && "${C2_BASE_URL}" != "http://${C2_HOST}:${C2_PORT}" && "${C2_BASE_URL}" != "http://127.0.0.1:${C2_PORT}" ]]; then
  START_LOCAL=0
fi

uv sync --group dev

if [[ "${START_LOCAL}" -eq 1 ]]; then
  if curl -sf "${C2_BASE_URL}/api/ontology/state" >/dev/null; then
    echo "NOTE: reusing already-running Core at ${C2_BASE_URL}"
    echo "      (it must have been started with LLM_BASE_URL=${LLM_BASE_URL})"
    START_LOCAL=0
  fi
fi

if [[ "${START_LOCAL}" -eq 1 ]]; then
  load_litellm_env
  uv run sdth-c2-server &
  SERVER_PID=$!
  if ! wait_http "${C2_BASE_URL}/api/ontology/state" 50 0.1; then
    echo "FAIL: local sdth-c2-server did not become ready at ${C2_BASE_URL}" >&2
    exit 2
  fi
fi

uv run python scripts/litellm_interpret_smoke.py "$@"
echo "LiteLLM interpret smoke complete (base=${C2_BASE_URL} litellm=${LITELLM_URL} started_litellm=${STARTED_LITELLM})."
