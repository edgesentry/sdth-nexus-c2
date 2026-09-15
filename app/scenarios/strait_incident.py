"""PS 04-style strait incident: conflicting sensor feeds."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_strait_incident(*, now: datetime | None = None) -> list[dict[str, Any]]:
    """
    Synthetic conflicting sensors for a suspect vessel:
    - AIS reports stationary (spoof)
    - Port camera / radar report ~20 kt approach (~800 m mismatch)
    - RF log reports drone-control emissions
    """
    ts = (now or datetime.now(timezone.utc)).isoformat()
    entity = "SUSPECT_VESSEL_01"
    ais_lat, ais_lon = 1.2345, 103.8567
    radar_lat, radar_lon = 1.2395, 103.8620
    return [
        {
            "source_id": "AIS_FEED",
            "entity_id": entity,
            "latitude": ais_lat,
            "longitude": ais_lon,
            "speed_kt": 0.2,
            "heading_deg": 0.0,
            "confidence": 0.55,
            "observed_at": ts,
            "modality": "ais",
            "note": "reported_stationary",
        },
        {
            "source_id": "PORT_CAMERA_04",
            "entity_id": entity,
            "latitude": radar_lat,
            "longitude": radar_lon,
            "speed_kt": 20.0,
            "heading_deg": 215.0,
            "confidence": 0.82,
            "observed_at": ts,
            "modality": "optical",
            "note": "visual_approach",
        },
        {
            "source_id": "RADAR_01",
            "entity_id": entity,
            "latitude": radar_lat + 0.0003,
            "longitude": radar_lon + 0.0002,
            "speed_kt": 19.5,
            "heading_deg": 214.0,
            "confidence": 0.88,
            "observed_at": ts,
            "modality": "radar",
            "note": "track_approach",
        },
        {
            "source_id": "RF_SENSOR_02",
            "entity_id": entity,
            "latitude": radar_lat,
            "longitude": radar_lon,
            "speed_kt": 0.0,
            "confidence": 0.7,
            "observed_at": ts,
            "modality": "rf",
            "note": "drone_control_band",
            "band_mhz": 2400,
        },
    ]
