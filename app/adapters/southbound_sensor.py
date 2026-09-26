"""Southbound: normalize venue sensor payloads into core Observations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import cos, radians, sin
from typing import Any

from core.schema import Observation

M_PER_DEG_LAT = 111_320.0
DEMO_DAY = datetime(2026, 9, 25, tzinfo=UTC)


def kt_to_mps(knots: float) -> float:
    return knots * 0.514444


def polar_to_latlon(
    site_lat: float,
    site_lon: float,
    azimuth_deg: float,
    range_km: float,
) -> tuple[float, float]:
    """Site-relative azimuth (0=N) + range → WGS84 (equirectangular)."""
    distance_m = range_km * 1000.0
    heading = radians(azimuth_deg)
    m_per_deg_lon = M_PER_DEG_LAT * cos(radians(site_lat))
    d_north = distance_m * cos(heading)
    d_east = distance_m * sin(heading)
    return (
        site_lat + d_north / M_PER_DEG_LAT,
        site_lon + d_east / max(m_per_deg_lon, 1e-6),
    )


def _observed_at_from_row(row: dict[str, Any]) -> datetime:
    if row.get("observed_at"):
        raw = row["observed_at"]
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if "time_s" in row:
        return DEMO_DAY + timedelta(seconds=float(row["time_s"]))
    if row.get("timestamp"):
        h, m, s = str(row["timestamp"]).split(":")
        return DEMO_DAY.replace(hour=int(h), minute=int(m), second=int(s))
    return datetime.now(UTC)


def canonical_row_to_event(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map one SensorSim canonical JSONL row into a normalize_sensor_event dict."""
    source = str(row.get("source", ""))
    service = str(row.get("service", "")).lower()
    sensor_id = str(row.get("sensor_id", source or "UNKNOWN"))
    observed_at = _observed_at_from_row(row)

    lat = row.get("lat", row.get("latitude", row.get("center_lat")))
    lon = row.get("lon", row.get("longitude", row.get("center_lon")))
    if lat is None or lon is None:
        site_lat = row.get("site_lat")
        site_lon = row.get("site_lon")
        az = row.get("azimuth_deg")
        rng = row.get("range_km")
        if site_lat is not None and site_lon is not None and az is not None and rng is not None:
            lat, lon = polar_to_latlon(float(site_lat), float(site_lon), float(az), float(rng))
        elif site_lat is not None and site_lon is not None and row.get("bearing_deg") is not None:
            # LOB-only: place a synthetic point 15 km along bearing for ontology display
            lat, lon = polar_to_latlon(
                float(site_lat), float(site_lon), float(row["bearing_deg"]), 15.0
            )
        elif site_lat is not None and site_lon is not None and source == "ARMY_CCTV":
            lat, lon = float(site_lat), float(site_lon)
        else:
            return None

    speed_kt = float(
        row.get(
            "sog_knots",
            row.get("velocity_knots", row.get("speed_kt", 0.0)),
        )
        or 0.0
    )
    heading = row.get("cog_deg", row.get("heading_deg", row.get("azimuth_deg")))
    modality = {
        "NAVY_AIS": "ais",
        "NAVY_COASTAL_RADAR": "radar",
        "SPACE_SAR": "space_sar",
        "AIR_RADAR": "radar",
        "AIR_EOIR": "optical",
        "AIR_EW": "rf",
        "ARMY_EOIR": "optical",
        "ARMY_EW": "rf",
        "ARMY_CCTV": "optical",
    }.get(source, "generic")

    entity = str(
        row.get("mmsi")
        or row.get("track_id")
        or row.get("emitter_id")
        or row.get("candidate_id")
        or row.get("camera_id")
        or sensor_id
    )

    attrs = {
        k: v
        for k, v in row.items()
        if k
        not in {
            "lat",
            "lon",
            "latitude",
            "longitude",
            "center_lat",
            "center_lon",
            "sog_knots",
            "velocity_knots",
            "speed_kt",
            "cog_deg",
            "heading_deg",
            "observed_at",
            "time_s",
            "timestamp",
        }
    }
    attrs["service"] = service or attrs.get("service")
    attrs["source"] = source
    attrs["time_s"] = row.get("time_s")

    return {
        "source_id": sensor_id,
        "entity_id": entity,
        "latitude": float(lat),
        "longitude": float(lon),
        "speed_kt": speed_kt,
        "heading_deg": float(heading) if heading is not None else None,
        "confidence": float(row.get("confidence", 0.75)),
        "observed_at": observed_at.isoformat(),
        "modality": modality,
        **attrs,
    }


def normalize_sensor_event(event: dict[str, Any]) -> Observation:
    """Convert a dict sensor event into a domain Observation."""
    # Accept SensorSim canonical rows directly.
    if "service" in event and "source" in event and "latitude" not in event and "lat" in event:
        converted = canonical_row_to_event(event)
        if converted is None:
            raise ValueError("Unable to geolocate canonical sensor row")
        event = converted
    elif "service" in event and "source" in event and event.get("latitude") is None:
        converted = canonical_row_to_event(event)
        if converted is not None:
            event = converted

    observed_at = event.get("observed_at")
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    elif observed_at is None:
        observed_at = datetime.now(UTC)

    speed_kt = float(event.get("speed_kt", 0.0))
    obs_kwargs: dict[str, Any] = {
        "source_id": str(event["source_id"]),
        "entity_hint": str(event.get("entity_id", event["source_id"])),
        "latitude": float(event["latitude"]),
        "longitude": float(event["longitude"]),
        "speed_mps": kt_to_mps(speed_kt),
        "heading_deg": event.get("heading_deg"),
        "confidence": float(event.get("confidence", 0.5)),
        "observed_at": observed_at,
        "modality": str(event.get("modality", "generic")),
        "attributes": {
            "speed_kt": speed_kt,
            **{
                k: v
                for k, v in event.items()
                if k
                not in {
                    "source_id",
                    "entity_id",
                    "observation_id",
                    "latitude",
                    "longitude",
                    "speed_kt",
                    "heading_deg",
                    "confidence",
                    "observed_at",
                    "modality",
                }
            },
        },
    }
    if event.get("observation_id"):
        obs_kwargs["observation_id"] = str(event["observation_id"])
    obs = Observation(**obs_kwargs)
    obs.ensure_digest()
    return obs
