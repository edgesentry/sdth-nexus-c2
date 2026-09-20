"""Optional open feeds → core Observations (issues #16, #70).

Normalizes open AIS and open air snapshots into southbound sensor dicts.

Source ladder for AIS (#70):
  Indago DuckDB → optional live poll → golden fixture

Default demos / CI stay fixture-backed. Opt in via ``OPEN_FEED``,
``OPEN_FEED_SOURCE``, ``INDAGO_DUCKDB_PATH``, or ``POST /api/ingress/open-feed``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from core.schema import Observation

from app.adapters.southbound_sensor import normalize_sensor_event

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AIS_FIXTURE = ROOT / "tests" / "fixtures" / "open_ais_datagovsg.json"
DEFAULT_AIR_FIXTURE = ROOT / "tests" / "fixtures" / "open_air_traffic.json"

# Indago ais_rotate "singapore" bbox already covers Malacca; for C2 pitch we
# prefer a tighter Singapore Strait window when sampling T-0 tracks.
DEFAULT_INDAGO_BBOX = (1.15, 103.55, 1.48, 104.15)  # lat_min, lon_min, lat_max, lon_max
DEFAULT_INDAGO_LIMIT = 80
DEFAULT_INDAGO_MAX_AGE_HOURS = 6.0

FeedKind = Literal["ais", "air"]
FEED_KINDS: tuple[FeedKind, ...] = ("ais", "air")
OpenFeedSource = Literal["auto", "indago", "live", "fixture"]
SOURCE_CHOICES: tuple[OpenFeedSource, ...] = ("auto", "indago", "live", "fixture")


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


def parse_open_feed_source(raw: str | None) -> OpenFeedSource:
    if raw is None or not str(raw).strip():
        return "auto"
    text = str(raw).strip().lower()
    if text in SOURCE_CHOICES:
        return text  # type: ignore[return-value]
    if text in {"duckdb", "indago_duckdb", "local"}:
        return "indago"
    raise ValueError(f"Unknown open-feed source '{raw}' (expected auto|indago|live|fixture)")


def open_feeds_from_env(env: dict[str, str] | None = None) -> list[FeedKind]:
    bag = env if env is not None else os.environ
    return parse_open_feed_selection(bag.get("OPEN_FEED"))


def open_feed_source_from_env(env: dict[str, str] | None = None) -> OpenFeedSource:
    bag = env if env is not None else os.environ
    return parse_open_feed_source(bag.get("OPEN_FEED_SOURCE"))


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


def resolve_indago_duckdb_path(
    explicit: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
) -> Path | None:
    """Resolve Indago AIS DuckDB path (env → raw stream → processed)."""
    bag = env if env is not None else os.environ
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit).expanduser())
    env_path = bag.get("INDAGO_DUCKDB_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())
    home = Path.home()
    candidates.extend(
        [
            home / ".indago" / "data" / "raw" / "ais" / "singapore.duckdb",
            home / ".indago" / "data" / "processed" / "ais" / "singapore.duckdb",
        ]
    )
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def load_open_ais_from_indago(
    path: Path | None = None,
    *,
    limit: int = DEFAULT_INDAGO_LIMIT,
    bbox: tuple[float, float, float, float] | None = DEFAULT_INDAGO_BBOX,
    max_age_hours: float | None = DEFAULT_INDAGO_MAX_AGE_HOURS,
) -> dict[str, Any]:
    """Query latest per-MMSI AIS positions from an Indago DuckDB snapshot."""
    import duckdb

    db_path = path or resolve_indago_duckdb_path()
    if db_path is None:
        raise FileNotFoundError(
            "Indago DuckDB not found (set INDAGO_DUCKDB_PATH or place "
            "~/.indago/data/raw/ais/singapore.duckdb)"
        )

    where: list[str] = []
    params: list[Any] = []
    if bbox is not None:
        lat_min, lon_min, lat_max, lon_max = bbox
        where.append("lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?")
        params.extend([lat_min, lat_max, lon_min, lon_max])
    if max_age_hours is not None and max_age_hours > 0:
        # DuckDB interval literal — avoid parameterized INTERVAL (pytz/engine quirks).
        hours = max(1, int(max_age_hours))
        where.append(f"timestamp >= (CURRENT_TIMESTAMP - INTERVAL '{hours}' HOUR)")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        WITH ranked AS (
            SELECT
                mmsi,
                timestamp,
                lat,
                lon,
                sog,
                cog,
                ship_type,
                ROW_NUMBER() OVER (PARTITION BY mmsi ORDER BY timestamp DESC) AS rn
            FROM ais_positions
            {where_sql}
        )
        SELECT
            r.mmsi,
            r.timestamp,
            r.lat,
            r.lon,
            r.sog,
            r.cog,
            r.ship_type,
            vm.name AS vessel_name
        FROM ranked r
        LEFT JOIN vessel_meta vm ON vm.mmsi = r.mmsi
        WHERE r.rn = 1
        ORDER BY r.timestamp DESC
        LIMIT ?
    """
    params.append(int(limit))

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    vessels: list[dict[str, Any]] = []
    for mmsi, ts, lat, lon, sog, cog, ship_type, vessel_name in rows:
        if lat is None or lon is None:
            continue
        if hasattr(ts, "astimezone"):
            ts_utc = ts.astimezone(UTC)
            stamp = ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        vessels.append(
            {
                "mmsi": str(mmsi),
                "name": str(vessel_name or mmsi),
                "latitude": float(lat),
                "longitude": float(lon),
                "speed_kt": float(sog or 0.0),
                "heading_deg": float(cog) if cog is not None else None,
                "ship_type": str(ship_type) if ship_type is not None else None,
                "timestamp": stamp,
                "confidence": 0.82,
            }
        )

    if not vessels:
        raise ValueError(f"Indago DuckDB {db_path} returned no AIS rows for the query window")

    return {
        "feed": "open_ais",
        "source": f"indago:{db_path.name}",
        "schema_version": "0.1.0",
        "retrieved_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Latest per-MMSI positions from Indago DuckDB (issue #70).",
        "indago_path": str(db_path),
        "vessel_count": len(vessels),
        "vessels": vessels,
    }


def load_open_ais_from_live(*, timeout_sec: float = 8.0) -> dict[str, Any]:
    """Optional live poll (data.gov.sg vessel positions). Raises on failure."""
    import httpx

    url = os.environ.get(
        "OPEN_AIS_LIVE_URL",
        "https://api.data.gov.sg/v1/transport/vessel-locations",
    )
    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.get(url)
        resp.raise_for_status()
        body = resp.json()

    if isinstance(body, dict) and isinstance(body.get("vessels"), list):
        payload = dict(body)
        payload.setdefault("source", "data.gov.sg/live")
        payload.setdefault("feed", "open_ais")
        payload.setdefault("schema_version", "0.1.0")
        payload.setdefault("retrieved_at", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return payload

    features = body.get("features") if isinstance(body, dict) else None
    if not isinstance(features, list) or not features:
        raise ValueError("live AIS response missing vessels[] / features[]")

    vessels: list[dict[str, Any]] = []
    for idx, feat in enumerate(features):
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
        geom = feat.get("geometry") if isinstance(feat.get("geometry"), dict) else {}
        coords = geom.get("coordinates") if isinstance(geom.get("coordinates"), list) else None
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        mmsi = str(props.get("mmsi") or props.get("MMSI") or f"live-{idx}")
        vessels.append(
            {
                "mmsi": mmsi,
                "name": str(props.get("name") or props.get("ship_name") or mmsi),
                "latitude": lat,
                "longitude": lon,
                "speed_kt": float(props.get("speed_kt") or props.get("sog") or 0.0),
                "heading_deg": props.get("heading_deg") or props.get("cog"),
                "ship_type": props.get("ship_type"),
                "timestamp": props.get("timestamp")
                or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "confidence": 0.75,
            }
        )
    if not vessels:
        raise ValueError("live AIS response produced zero vessels")
    return {
        "feed": "open_ais",
        "source": "data.gov.sg/live",
        "schema_version": "0.1.0",
        "retrieved_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vessels": vessels,
    }


def resolve_open_ais_payload(
    *,
    source: OpenFeedSource = "auto",
    payload: dict[str, Any] | None = None,
    use_fixture: bool = False,
    duckdb_path: Path | None = None,
    limit: int = DEFAULT_INDAGO_LIMIT,
) -> tuple[dict[str, Any], str]:
    """Return (payload, resolved_source) using the #70 fallback ladder."""
    if payload is not None:
        return payload, "payload"
    if use_fixture or source == "fixture":
        return load_open_ais_fixture(), "fixture"

    errors: list[str] = []
    order: list[OpenFeedSource]
    allow_fallback = True
    if source == "auto":
        order = ["indago", "live", "fixture"]
    elif source == "indago":
        order = ["indago"]
        allow_fallback = False
    elif source == "live":
        order = ["live"]
        allow_fallback = False
    else:
        order = ["fixture"]

    for step in order:
        try:
            if step == "indago":
                data = load_open_ais_from_indago(duckdb_path, limit=limit)
                return data, "indago"
            if step == "live":
                data = load_open_ais_from_live()
                return data, "live"
            data = load_open_ais_fixture()
            return data, "fixture"
        except Exception as exc:
            errors.append(f"{step}: {exc}")
            logger.info("open AIS source %s failed: %s", step, exc)
            if not allow_fallback:
                break

    if allow_fallback and "fixture" not in {e.split(":", 1)[0] for e in errors}:
        try:
            return load_open_ais_fixture(), "fixture"
        except Exception as exc:
            errors.append(f"fixture: {exc}")

    raise ValueError("open AIS source ladder exhausted: " + " | ".join(errors))


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
                "speed_kt": float(speed if speed is not None else 0.0),
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
    source: OpenFeedSource | None = None,
    duckdb_path: Path | None = None,
    limit: int = DEFAULT_INDAGO_LIMIT,
) -> tuple[list[Observation], str]:
    """Normalize one open feed into Observations.

    Returns ``(observations, resolved_source)``.
    """
    # Legacy #16: use_fixture alone (no source) always means golden fixture.
    if use_fixture and payload is None and source is None:
        data = load_open_feed_fixture(feed, fixture_path)
        return [normalize_sensor_event(e) for e in open_feed_to_events(feed, data)], "fixture"

    if feed == "ais":
        data, resolved = resolve_open_ais_payload(
            source=source or open_feed_source_from_env(),
            payload=payload,
            use_fixture=use_fixture,
            duckdb_path=duckdb_path,
            limit=limit,
        )
        return [normalize_sensor_event(e) for e in open_ais_to_events(data)], resolved

    if use_fixture:
        data = load_open_feed_fixture(feed, fixture_path)
        return [normalize_sensor_event(e) for e in open_feed_to_events(feed, data)], "fixture"
    if payload is not None:
        return [normalize_sensor_event(e) for e in open_feed_to_events(feed, payload)], "payload"
    raise ValueError("Provide payload or use_fixture=True for air feed")


def observations_from_open_feeds(
    feeds: list[FeedKind] | None = None,
    *,
    use_fixture: bool = True,
    source: OpenFeedSource | None = None,
) -> list[Observation]:
    """Load selected feeds (default: env ``OPEN_FEED`` or empty)."""
    selected = feeds if feeds is not None else open_feeds_from_env()
    out: list[Observation] = []
    for feed in selected:
        obs, _resolved = open_feed_to_observations(
            feed,
            use_fixture=use_fixture,
            source=source,
        )
        out.extend(obs)
    return out
