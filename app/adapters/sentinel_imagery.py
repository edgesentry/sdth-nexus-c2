"""Sentinel-Imagery-Analysis → CandidateEvent bridge (issue #47).

Maps ``POST /api/run_cv/<scan>`` detection payloads into assumed CandidateEvent
v1.3.0 for NexusGate ingress. CI and venue demos stay fixture-first; optional
HTTP pull from a sibling upstream (default ``http://127.0.0.1:5050``) falls back
to the Singapore Strait recorded export when unreachable (GLINT fail-safe).

Upstream is a separate process — not a git submodule.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.adapters.sar_candidate_event import (
    CandidateEvent,
    CandidateEventBoundingBox,
    CandidateEventLocation,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SENTINEL_FIXTURE = ROOT / "tests" / "fixtures" / "sentinel_run_cv_sg_strait.json"
DEFAULT_CHIP_URI = "tests/fixtures/sentinel_chip.jpg"

DEFAULT_SAR_UPSTREAM_URL = "http://127.0.0.1:5050"
DEFAULT_SAR_UPSTREAM_SCAN = "sg_strait_s1_20260918"
DEFAULT_SAR_UPSTREAM_TIMEOUT_S = 3.0

DARK_VESSEL_EVENT_TYPE = "UNANNOUNCED_DARK_VESSEL"
SOURCE_ID = "SENTINEL_IMAGERY_ANALYSIS"


def resolve_sar_upstream_url(explicit: str | None = None) -> str:
    return (explicit or os.environ.get("SAR_UPSTREAM_URL") or DEFAULT_SAR_UPSTREAM_URL).rstrip("/")


def resolve_sar_upstream_scan(explicit: str | None = None) -> str:
    return explicit or os.environ.get("SAR_UPSTREAM_SCAN") or DEFAULT_SAR_UPSTREAM_SCAN


def resolve_sar_upstream_timeout_s(explicit: float | None = None) -> float:
    if explicit is not None:
        return explicit
    raw = os.environ.get("SAR_UPSTREAM_TIMEOUT_S")
    if raw is None or not raw.strip():
        return DEFAULT_SAR_UPSTREAM_TIMEOUT_S
    return float(raw)


def load_sentinel_run_cv_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_SENTINEL_FIXTURE
    with fixture_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _parse_timestamp(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        ts = raw
    elif isinstance(raw, str) and raw.strip():
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        ts = datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts


def _lat_lng(det: dict[str, Any]) -> tuple[float, float]:
    if "lat" in det and "lng" in det:
        return float(det["lat"]), float(det["lng"])
    if "latitude" in det and "longitude" in det:
        return float(det["latitude"]), float(det["longitude"])
    raise ValueError("detection requires lat/lng (or latitude/longitude)")


def sentinel_detection_to_candidate_event(
    det: dict[str, Any],
    *,
    scan_id: str = "scan",
    timestamp: datetime | None = None,
    evidence_uri: str | None = None,
    area_id: str = "singapore_strait",
) -> CandidateEvent:
    """Map one enriched ``run_cv`` detection → CandidateEvent (dark vessel only)."""
    status = str(det.get("correlation_status") or "").strip().lower()
    if status != "uncorrelated":
        raise ValueError(
            f"detection index={det.get('index')!r} is not uncorrelated "
            f"(status={det.get('correlation_status')!r})"
        )

    lat, lng = _lat_lng(det)
    idx = det.get("index", 0)
    detection_id = str(det.get("detection_id") or f"EVT-SAR-SG-{scan_id}-{idx}")
    conf = float(det.get("confidence", 0.7))
    conf = max(0.0, min(1.0, conf))

    attrs: dict[str, Any] = {
        "ais_absent": True,
        "ais_correlation": "NONE",
        "ingress": "sentinel_imagery",
        "correlation_status": "uncorrelated",
        "scan_id": scan_id,
        "detection_index": idx,
    }
    if det.get("length") is not None:
        attrs["vessel_length_m"] = float(det["length"])
        attrs["length_m"] = float(det["length"])
    if det.get("beam") is not None:
        attrs["vessel_beam_m"] = float(det["beam"])
        attrs["beam_m"] = float(det["beam"])
    if det.get("angle") is not None:
        attrs["heading_deg"] = float(det["angle"])
    chip = evidence_uri or det.get("evidence_image_uri") or det.get("cropped_chip_path")
    if chip:
        attrs["evidence_image_uri"] = str(chip)

    bbox = None
    geo = det.get("geo_bbox")
    if isinstance(geo, dict):
        bbox = CandidateEventBoundingBox(
            min_lat=float(geo["min_lat"]),
            max_lat=float(geo["max_lat"]),
            min_lon=float(geo["min_lon"]),
            max_lon=float(geo["max_lon"]),
        )

    return CandidateEvent(
        event_id=detection_id,
        timestamp=timestamp or datetime.now(UTC),
        source_id=SOURCE_ID,
        area_id=area_id,
        event_type=DARK_VESSEL_EVENT_TYPE,
        confidence=conf,
        location=CandidateEventLocation(latitude=lat, longitude=lng),
        bounding_box=bbox,
        attributes=attrs,
    )


def sentinel_run_cv_to_candidate_events(
    payload: dict[str, Any],
    *,
    scan_id: str | None = None,
    evidence_uri: str | None = None,
) -> list[CandidateEvent]:
    """Map a full ``run_cv`` JSON body → dark-vessel CandidateEvents only."""
    detections = payload.get("detections")
    if not isinstance(detections, list):
        raise ValueError("run_cv payload requires detections[] list")

    resolved_scan = str(scan_id or payload.get("scan_id") or payload.get("folder_name") or "scan")
    ts = _parse_timestamp(payload.get("timestamp"))
    chip = evidence_uri or payload.get("evidence_image_uri") or DEFAULT_CHIP_URI

    events: list[CandidateEvent] = []
    for raw in detections:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("correlation_status") or "").strip().lower() != "uncorrelated":
            continue
        events.append(
            sentinel_detection_to_candidate_event(
                raw,
                scan_id=resolved_scan,
                timestamp=ts,
                evidence_uri=chip,
            )
        )
    cluster = len(events)
    for event in events:
        event.attributes["vessel_count_est"] = cluster
    return events


def fetch_run_cv(
    *,
    base_url: str | None = None,
    scan: str | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any] | None:
    """POST ``/api/run_cv/<scan>`` on Sentinel-Imagery-Analysis. None on any failure."""
    url = resolve_sar_upstream_url(base_url)
    folder = resolve_sar_upstream_scan(scan)
    timeout = resolve_sar_upstream_timeout_s(timeout_s)
    endpoint = f"{url}/api/run_cv/{folder}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json={})
            resp.raise_for_status()
            body = resp.json()
    except (httpx.HTTPError, OSError, ValueError, TypeError):
        return None
    if not isinstance(body, dict):
        return None
    if body.get("status") == "error":
        return None
    if "detections" not in body:
        return None
    body.setdefault("scan_id", folder)
    return body


def resolve_sentinel_events(
    *,
    pull_upstream: bool = False,
    run_cv: dict[str, Any] | None = None,
    use_fixture: bool = False,
    base_url: str | None = None,
    scan: str | None = None,
    timeout_s: float | None = None,
    fixture_path: Path | None = None,
) -> tuple[list[CandidateEvent], str]:
    """Resolve dark-vessel events.

    Returns ``(events, source)`` where source is ``run_cv`` | ``upstream`` | ``fixture``.
    """
    if run_cv is not None:
        events = sentinel_run_cv_to_candidate_events(run_cv)
        return events, "run_cv"

    if pull_upstream:
        remote = fetch_run_cv(base_url=base_url, scan=scan, timeout_s=timeout_s)
        if remote is not None:
            events = sentinel_run_cv_to_candidate_events(remote)
            if events:
                return events, "upstream"
        # GLINT / Pattern B fail-safe: recorded Singapore Strait export
        payload = load_sentinel_run_cv_fixture(fixture_path)
        return sentinel_run_cv_to_candidate_events(payload), "fixture"

    if use_fixture:
        payload = load_sentinel_run_cv_fixture(fixture_path)
        return sentinel_run_cv_to_candidate_events(payload), "fixture"

    raise ValueError("Provide run_cv, pull_upstream=true, or use_sentinel_fixture=true")
