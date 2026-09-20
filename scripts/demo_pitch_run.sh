#!/usr/bin/env bash
# Pitch-day all-in-one runner (issue #75): S2 → S3 → Slide 11 scorecard.
# Default: in-process Core (no sdth-c2-server required). Pass --step for pauses.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv sync --quiet
exec uv run python scripts/demo_pitch_run.py "$@"
