#!/usr/bin/env python3
"""Smoke: Sentinel-Imagery-Analysis → C2 candidate-event ingress (issue #47).

Fixture path (CI / Pattern A) always runs. Optional ``--pull`` tries Pattern B
against ``SAR_UPSTREAM_URL`` (default http://127.0.0.1:5050) and falls back to
the Singapore Strait fixture when the sibling upstream is down.

  uv run sdth-c2-server
  uv run python scripts/sentinel_ingress_smoke.py
  uv run python scripts/sentinel_ingress_smoke.py --pull
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import httpx

DEFAULT_BASE = "http://127.0.0.1:8080"


def _headers() -> dict[str, str]:
    token = os.environ.get("C2_API_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _post(base: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{base.rstrip('/')}/api/ingress/candidate-event"
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, json=body, headers=_headers())
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("C2_BASE_URL", DEFAULT_BASE),
        help="C2 Core base URL (default C2_BASE_URL or localhost:8080)",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Also exercise pull_upstream (falls back to fixture if upstream down)",
    )
    args = parser.parse_args(argv)

    print(f"fixture → {args.base_url}/api/ingress/candidate-event")
    fixture_body = _post(args.base_url, {"use_sentinel_fixture": True})
    if fixture_body.get("status") != "INGESTED":
        print(f"FAIL: expected INGESTED, got {fixture_body!r}", file=sys.stderr)
        return 1
    count = int(fixture_body.get("count") or 0)
    if count < 1:
        print(f"FAIL: expected dark vessels, count={count}", file=sys.stderr)
        return 1
    obs = fixture_body.get("observation") or {}
    attrs = obs.get("attributes") or {}
    if not attrs.get("ais_absent"):
        print("FAIL: ais_absent not set on first observation", file=sys.stderr)
        return 1
    print(
        f"  OK source={fixture_body.get('source')} count={count} "
        f"event_type={obs.get('entity_hint')} track={fixture_body.get('track_id')}"
    )

    if args.pull:
        print("pull_upstream → (upstream or fixture fail-safe)")
        pull_body = _post(args.base_url, {"pull_upstream": True})
        if pull_body.get("status") != "INGESTED":
            print(f"FAIL pull: {pull_body!r}", file=sys.stderr)
            return 1
        print(
            f"  OK source={pull_body.get('source')} count={pull_body.get('count')} "
            f"(fixture = fail-safe when Sentinel :5050 is down)"
        )

    print("RESULT: sentinel ingress smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
