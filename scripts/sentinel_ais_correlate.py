#!/usr/bin/env python3
"""AIS ingest → Sentinel run_cv (correlate) → optional C2 dark-vessel ingress.

Requires a running Sentinel-Imagery-Analysis sibling on ``SAR_UPSTREAM_URL``
(default ``http://127.0.0.1:5050``) with a downloaded scan folder.

AIS sources (``--ais-source``):

  demo     Live community feed via Sentinel ``AISFriendsPlugin`` (pitch / venue)
  offline  Deterministic ``MockAISPlugin`` (CI / no network)

AIS history stays in SIA local SQLite via SIA's own ``ingest_ais`` plugins.

Typical flow:

  # Terminal A — sibling repo with COP_* in .env
  cd ~/work/Sentinel-Imagery-Analysis && python app.py

  # Terminal B — this repo
  uv run sdth-c2-server
  uv run python scripts/sentinel_ais_correlate.py \\
    --scan 20260916_224721_162544676155 \\
    --ais-source demo \\
    --ingest-c2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

DEFAULT_SAR = "http://127.0.0.1:5050"
DEFAULT_C2 = "http://127.0.0.1:8080"

# Profile → Sentinel scraper plugin.
AIS_SOURCE_PROFILES: dict[str, dict[str, Any]] = {
    "demo": {
        "plugin": "AISFriendsPlugin",
        "blurb": "live AISFriends community API (venue / pitch)",
    },
    "offline": {
        "plugin": "MockAISPlugin",
        "blurb": "deterministic mock trajectories (CI / airplane mode)",
    },
}
# Aliases for muscle memory / docs.
AIS_SOURCE_ALIASES = {
    "friends": "demo",
    "aisfriends": "demo",
    "mock": "offline",
}


def _c2_headers() -> dict[str, str]:
    token = os.environ.get("C2_API_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _get_json(client: httpx.Client, url: str) -> dict[str, Any]:
    resp = client.get(url)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"expected object from {url}")
    return data


def _post_json(client: httpx.Client, url: str, body: dict[str, Any]) -> dict[str, Any]:
    resp = client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"expected object from {url}")
    return data


def _bbox_from_scan(scan: dict[str, Any]) -> list[float]:
    """Convert GET /api/scan bounds → [min_lon, min_lat, max_lon, max_lat]."""
    bounds = scan.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise RuntimeError("scan response missing bounds[[min_lat,min_lon],[max_lat,max_lon]]")
    (min_lat, min_lon), (max_lat, max_lon) = bounds
    return [float(min_lon), float(min_lat), float(max_lon), float(max_lat)]


def _resolve_ais_source(raw: str) -> str:
    key = (raw or "demo").strip().lower()
    key = AIS_SOURCE_ALIASES.get(key, key)
    if key not in AIS_SOURCE_PROFILES:
        allowed = ", ".join(sorted(AIS_SOURCE_PROFILES))
        raise ValueError(f"unknown --ais-source {raw!r}; use {allowed} (or friends/mock)")
    return key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scan",
        default=os.environ.get("SAR_UPSTREAM_SCAN", ""),
        help="Sentinel scan folder name (or SAR_UPSTREAM_SCAN)",
    )
    parser.add_argument(
        "--sar-url",
        default=os.environ.get("SAR_UPSTREAM_URL", DEFAULT_SAR),
        help="Sentinel base URL (default SAR_UPSTREAM_URL or :5050)",
    )
    parser.add_argument(
        "--c2-url",
        default=os.environ.get("C2_BASE_URL", DEFAULT_C2),
        help="C2 Core base URL (default C2_BASE_URL or :8080)",
    )
    parser.add_argument(
        "--ais-source",
        default=os.environ.get("AIS_SOURCE", "demo"),
        help="AIS profile: demo|offline (aliases: friends|mock). Default demo / AIS_SOURCE",
    )
    parser.add_argument(
        "--plugin",
        default="",
        help="Override Sentinel scraper plugin name (ignores --ais-source plugin mapping)",
    )
    parser.add_argument(
        "--skip-ais-ingest",
        action="store_true",
        help="Skip AIS ingest (use AIS already in Sentinel DB)",
    )
    parser.add_argument(
        "--ais-correlation-distance",
        type=float,
        default=100.0,
        help="Meters for run_cv AIS match (default 100)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=40,
        help="CV brightness threshold 0-255 (default 40)",
    )
    parser.add_argument(
        "--dem-land-mask",
        action="store_true",
        help="Enable DEM land mask in run_cv (default off for faster demos)",
    )
    parser.add_argument(
        "--ingest-c2",
        action="store_true",
        help="POST uncorrelated detections to C2 as run_cv payload",
    )
    parser.add_argument(
        "--reset-c2",
        action="store_true",
        help="POST /api/admin/reset on C2 before ingest",
    )
    parser.add_argument(
        "--save-run-cv",
        default="",
        help="Optional path to write raw run_cv JSON",
    )
    args = parser.parse_args(argv)

    scan_id = (args.scan or "").strip()
    if not scan_id:
        print("FAIL: provide --scan or SAR_UPSTREAM_SCAN", file=sys.stderr)
        return 2

    try:
        ais_source = _resolve_ais_source(args.ais_source)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    profile = AIS_SOURCE_PROFILES[ais_source]
    plugin = (args.plugin or "").strip() or profile["plugin"]

    sar = args.sar_url.rstrip("/")
    timeout = httpx.Timeout(180.0, connect=10.0)

    with httpx.Client(timeout=timeout) as client:
        print(f"1) GET {sar}/api/scan/{scan_id}")
        try:
            scan = _get_json(client, f"{sar}/api/scan/{scan_id}")
        except httpx.HTTPError as exc:
            print(f"FAIL: cannot load scan ({exc})", file=sys.stderr)
            return 1
        bbox = _bbox_from_scan(scan)
        pass_time = str(scan.get("datetime") or "")
        print(f"   bbox={bbox} pass_time={pass_time or '-'}")
        print(f"   ais-source={ais_source} ({profile['blurb']})")

        if not args.skip_ais_ingest:
            print(f"2) POST {sar}/api/ingest_ais plugin={plugin}")
            ingest_body: dict[str, Any] = {"bbox": bbox, "plugin": plugin}
            # Live community feeds only return *current* positions. Binding a
            # historical SAR pass_time (±5 min) filters them all out → 0 rows.
            # Demo therefore scrapes "now"; offline Mock can use pass_time.
            use_pass = ais_source != "demo" and bool(pass_time)
            if use_pass:
                ingest_body["pass_time"] = pass_time
            elif ais_source == "demo" and pass_time:
                print(
                    "   NOTE: demo omits pass_time on ingest "
                    "(live AIS vs historical SAR; correlate uses spatial fallback)"
                )
            try:
                ingest = _post_json(client, f"{sar}/api/ingest_ais", ingest_body)
            except httpx.HTTPError as exc:
                print(f"FAIL: AIS ingest ({exc})", file=sys.stderr)
                return 1
            outcome = ingest.get("ingestion_outcome") or ingest.get("status")
            print(f"   OK outcome={outcome!r}")
            summary = _get_json(client, f"{sar}/api/ais/summary")
            print(
                f"   AIS summary vessels={summary.get('vessel_count')} "
                f"records={summary.get('record_count')} band={summary.get('freshness_band')}"
            )
        else:
            print("2) skip AIS ingest")

        print(f"3) POST {sar}/api/run_cv/{scan_id}")
        run_body = {
            "threshold": args.threshold,
            "dem_land_mask_enabled": bool(args.dem_land_mask),
            "ais_correlation_distance": args.ais_correlation_distance,
        }
        try:
            run_cv = _post_json(client, f"{sar}/api/run_cv/{scan_id}", run_body)
        except httpx.HTTPError as exc:
            print(f"FAIL: run_cv ({exc})", file=sys.stderr)
            return 1
        if run_cv.get("status") != "success":
            print(f"FAIL: run_cv status={run_cv.get('status')!r}", file=sys.stderr)
            return 1

        dets = run_cv.get("detections") or []
        uncorr = int(run_cv.get("uncorrelated_count") or 0)
        corr = int(run_cv.get("correlated_count") or 0)
        inside = int(run_cv.get("inside_box_count") or 0)
        outside = int(run_cv.get("outside_box_count") or 0)
        print(
            f"   OK detections={len(dets)} uncorrelated={uncorr} "
            f"correlated={corr} (inside={inside} outside={outside})"
        )
        for d in dets[:5]:
            if not isinstance(d, dict):
                continue
            print(
                f"     idx={d.get('index')} {d.get('correlation_status')} "
                f"lat={d.get('lat')} lng={d.get('lng')} conf={d.get('confidence')}"
            )
        if len(dets) > 5:
            print(f"     ... {len(dets) - 5} more")

        run_cv = {
            **run_cv,
            "scan_id": scan_id,
            "timestamp": pass_time or run_cv.get("timestamp"),
        }
        if args.save_run_cv:
            with open(args.save_run_cv, "w", encoding="utf-8") as fh:
                json.dump(run_cv, fh, indent=2)
            print(f"   wrote {args.save_run_cv}")

        if not args.ingest_c2:
            print("4) skip C2 ingest (pass --ingest-c2 to push dark vessels)")
            print("RESULT: AIS correlate smoke complete")
            return 0

        c2 = args.c2_url.rstrip("/")
        print(f"4) POST {c2}/api/ingress/candidate-event (run_cv)")
        if args.reset_c2:
            try:
                client.post(f"{c2}/api/admin/reset", headers=_c2_headers()).raise_for_status()
                print("   reset OK")
            except httpx.HTTPError as exc:
                print(f"FAIL: C2 reset ({exc})", file=sys.stderr)
                return 1
        try:
            resp = client.post(
                f"{c2}/api/ingress/candidate-event",
                json={"run_cv": run_cv},
                headers=_c2_headers(),
            )
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError as exc:
            print(f"FAIL: C2 ingress ({exc})", file=sys.stderr)
            return 1

        if body.get("status") != "INGESTED":
            print(f"FAIL: expected INGESTED, got {body!r}", file=sys.stderr)
            return 1
        print(
            f"   OK source={body.get('source')} count={body.get('count')} "
            f"(only uncorrelated → UNANNOUNCED_DARK_VESSEL)"
        )
        print("RESULT: AIS correlate → C2 ingress complete")
        return 0


if __name__ == "__main__":
    sys.exit(main())
