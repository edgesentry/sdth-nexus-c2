#!/usr/bin/env bash
# Level 3: optional RasPi GPIO on the Screen 2 / edge machine (issue #20).
# Core (local or Cloudflare) never drives GPIO — clients do after Ack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export EFFECTOR_BASE_URL="${EFFECTOR_BASE_URL:-${CLEARBOT_BASE_URL:-http://127.0.0.1:8000}}"
export CLEARBOT_BASE_URL="${CLEARBOT_BASE_URL:-$EFFECTOR_BASE_URL}"
export RASPI_ACK_BLINK="${RASPI_ACK_BLINK:-1}"

uv sync --quiet

case "${1:-}" in
  --blink)
    shift
    exec uv run python scripts/raspi_ack_blink.py "$@"
    ;;
  --c2-server)
    echo "NOTE: GPIO blink is client-side. Use --blink after Ack, or:" >&2
    echo "  RASPI_ACK_BLINK=1 ./scripts/picture_to_tasking.sh" >&2
    shift
    exec uv run sdth-c2-server "$@"
    ;;
  *)
    # Default: CLI cycle with RaspiHardwareAdapter on dispatch.
    exec uv run python -m app.main --raspi "$@"
    ;;
esac
