#!/usr/bin/env bash
# Run C2 cycle on Raspberry Pi (Level 3 hardware optional).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export EFFECTOR_BASE_URL="${EFFECTOR_BASE_URL:-${CLEARBOT_BASE_URL:-http://127.0.0.1:8000}}"
export CLEARBOT_BASE_URL="${CLEARBOT_BASE_URL:-$EFFECTOR_BASE_URL}"
uv sync --quiet
uv run python -m app.main "$@"
