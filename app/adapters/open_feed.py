"""Optional demo-grade open feeds → core Observations (issue #16).

Normalizes open AIS (data.gov.sg-shaped) and open air (ADS-B-style) snapshots
into southbound sensor dicts, then ``normalize_sensor_event``.

Live coastal polling is Phase 5. CI and default demos stay on synthetic S1-S3;
opt in via CLI ``--open-feed``, env ``OPEN_FEED``, or ``POST /api/ingress/open-feed``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from core.schema import Observation

from app.adapters.southbound_sensor import normalize_sensor_event

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AIS_FIXTURE = ROOT / "tests" / "fixtures" / "open_ais_datagovsg.json"
DEFAULT_AIR_FIXTURE = ROOT / "tests" / "fixtures" / "open_air_traffic.json"

FeedKind = Literal["ais", "air"]
FEED_KINDS: tuple[FeedKind, ...] = ("ais", "air")


def parse_open_feed_selection(raw: str | None) -> list[FeedKind]:
    """Parse ``ais``, ``air``, ``ais,air``, or ``all`` into ordered unique kinds."""
    if raw is None:
        return []
    text = raw.strip().lower()
    if not text or text in {"0", "false", "off", "none"}:
        return []
    if text in {"1", "true", "on", "all", "*"}:
        return list(FEED_KINDS)
    out: list[FeedKind] = []
    for part in text.replace(";", ",").split(","):
        token = part.strip()
        if not token:
            continue
        if token in {"ais", "open_ais", "datagovsg", "data.gov.sg"}:
            kind: FeedKind = "ais"
        elif token in {"air", "open_air", "adsb", "ads-b"}:
            kind = "air"
        else:
            raise ValueError(f"Unknown open feed '{token}' (expected ais, air, or all)")
        if kind not in out:
            out.append(kind)
    return out


def open_feeds_from_env(env: dict[str, str] | None = None) -> list[FeedKind]:
    bag = env if env is not None else os.environ
    return parse_open_feed_selection(bag.get("OPEN_FEED"))


def load_open_ais_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_AIS_FIXTURE
    with fixture_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def load_open_air_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_AIR_FIXTURE
    with fixture_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def load_open_feed_fixture(feed: FeedKind, path: Path | None = None) -> dict[str, Any]:
    if feed == "ais":
        return load_open_ais_fixture(path)
    if feed == "air":
        return load_open_air_fixture(path)
    raise ValueError(f"Unknown open feed: {feed}")


def open_ais_to_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map data.gov.sg-shaped vessel snapshot → southbound sensor dicts."""
    vessels = payload.get("vessels")
    if not isinstance(vessels, list) or not vessels:
        raise ValueError("open AIS payload requires a non-empty vessels[] list")

    feed_source = str(payload.get("source", "open_ais"))
    events: list[dict[str, Any]] = []
    for idx, raw in enumerate(vessels):
        if not isinstance(raw, dict):
            raise ValueError(f"vessels[{idx}] must be an object")
        try:
            lat = float(raw["latitude"])
            lon = float(raw["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"vessels[{idx}] requires numeric latitude/longitude") from exc

        mmsi = str(raw.get("mmsi") or raw.get("id") or f"vessel-{idx}")
        name = str(raw.get("name") or mmsi)
        events.append(
            {
                "observation_id": f"open-ais-{mmsi}",
                "source_id": f"OPEN_AIS_{mmsi}",
                "entity_id": name,
                "latitude": lat,
                "longitude": lon,
                "speed_kt": float(raw.get("speed_kt", 0.0)),
                "heading_deg": raw.get("heading_deg"),
                "confidence": float(raw.get("confidence", 0.7)),
                "observed_at": raw.get("timestamp") or payload.get("retrieved_at"),
                "modality": "ais",
                "ingress": "open_feed",
                "feed": "open_ais",
                "feed_source": feed_source,
                "schema_version": str(payload.get("schema_version", "0.1.0")),
                "mmsi": mmsi,
                "ship_type": raw.get("ship_type"),
                "vessel_name": name,
            }
        )
    return events


def open_air_to_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map open air / ADS-B-style snapshot → southbound sensor dicts."""
    aircraft = payload.get("aircraft")
    if not isinstance(aircraft, list) or not aircraft:
        raise ValueError("open air payload requires a non-empty aircraft[] list")

    feed_source = str(payload.get("source", "open_air"))
    events: list[dict[str, Any]] = []
    for idx, raw in enumerate(aircraft):
        if not isinstance(raw, dict):
            raise ValueError(f"aircraft[{idx}] must be an object")
        try:
            lat = float(raw["latitude"])
            lon = float(raw["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"aircraft[{idx}] requires numeric latitude/longitude") from exc

        icao = str(raw.get("icao24") or raw.get("id") or f"ac-{idx}")
        callsign = str(raw.get("callsign") or icao).strip() or icao
        speed = raw.get("velocity_kt", raw.get("speed_kt", 0.0))
        events.append(
            {
                "observation_id": f"open-air-{icao}",
                "source_id": f"OPEN_AIR_{icao.upper()}",
                "entity_id": callsign,
                "latitude": lat,
                "longitude": lon,
                "speed_kt": float(speed),
                "heading_deg": raw.get("heading_deg"),
                "confidence": float(raw.get("confidence", 0.65)),
                "observed_at": raw.get("timestamp") or payload.get("retrieved_at"),
                "modality": "adsb",
                "ingress": "open_feed",
                "feed": "open_air",
                "feed_source": feed_source,
                "schema_version": str(payload.get("schema_version", "0.1.0")),
                "icao24": icao,
                "callsign": callsign,
                "altitude_m": raw.get("altitude_m"),
            }
        )
    return events


def open_feed_to_events(feed: FeedKind, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if feed == "ais":
        return open_ais_to_events(payload)
    if feed == "air":
        return open_air_to_events(payload)
    raise ValueError(f"Unknown open feed: {feed}")


def open_feed_to_observations(
    feed: FeedKind,
    payload: dict[str, Any] | None = None,
    *,
    use_fixture: bool = False,
    fixture_path: Path | None = None,
) -> list[Observation]:
    """Normalize one open feed into Observations via ``normalize_sensor_event``."""
    if use_fixture:
        data = load_open_feed_fixture(feed, fixture_path)
    elif payload is not None:
        data = payload
    else:
        raise ValueError("Provide payload or use_fixture=True")
    return [normalize_sensor_event(event) for event in open_feed_to_events(feed, data)]


def observations_from_open_feeds(
    feeds: list[FeedKind] | None = None,
    *,
    use_fixture: bool = True,
) -> list[Observation]:
    """Load selected fixture feeds (default: env ``OPEN_FEED`` or empty)."""
    selected = feeds if feeds is not None else open_feeds_from_env()
    out: list[Observation] = []
    for feed in selected:
        out.extend(open_feed_to_observations(feed, use_fixture=use_fixture))
    return out
