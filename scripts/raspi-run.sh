#!/usr/bin/env bash
# Level 3: C2 cycle with optional RasPi GPIO (issue #20).
# Without RPi.GPIO / hardware the adapter is a no-op.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export EFFECTOR_BASE_URL="${EFFECTOR_BASE_URL:-${CLEARBOT_BASE_URL:-http://127.0.0.1:8000}}"
export CLEARBOT_BASE_URL="${CLEARBOT_BASE_URL:-$EFFECTOR_BASE_URL}"
# Opt-in Ack blink when running sdth-c2-server on this host (Screen 2 proof).
export RASPI_ACK_BLINK="${RASPI_ACK_BLINK:-1}"

uv sync --quiet

if [[ "${1:-}" == "--c2-server" ]]; then
  shift
  exec uv run sdth-c2-server "$@"
fi

# Default: CLI cycle; pass --raspi to dispatch via RaspiHardwareAdapter.
exec uv run python -m app.main --raspi "$@"
