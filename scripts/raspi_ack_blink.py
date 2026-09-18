#!/usr/bin/env python3
"""Screen 2 client: optional RasPi GPIO blink after recipient Ack (issue #20).

Core (local or Cloudflare) never touches GPIO. Run this on the laptop / Pi
that has the LED — typically right after a successful POST /api/recipient/ack.

  # After Screen 2 curl Ack against Cloudflare or local Core:
  RASPI_ACK_BLINK=1 uv run python scripts/raspi_ack_blink.py

Env:
  RASPI_ACK_BLINK / RASPI_GPIO  Opt-in (1|true|yes|on)
  RASPI_LED_PIN                BCM pin (default 17)

Exit 0 even when hardware is absent (no-op telemetry). Exit 2 if opt-in unset.
"""

from __future__ import annotations

import json
import sys

from app.adapters.raspi_hardware import blink_on_ack_sync, raspi_ack_blink_enabled


def main() -> int:
    if not raspi_ack_blink_enabled():
        print(
            "RASPI_ACK_BLINK / RASPI_GPIO not set — nothing to do.\n"
            "Example: RASPI_ACK_BLINK=1 uv run python scripts/raspi_ack_blink.py",
            file=sys.stderr,
        )
        return 2
    tel = blink_on_ack_sync(enabled=True)
    print(json.dumps(tel or {}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
