"""Bridge Indago DuckDB AIS snapshots into Sentinel-Imagery-Analysis SQLite.

Production path for SAR × AIS: Indago (aisstream.io → DuckDB) is not a Sentinel
scraper plugin. This helper copies bbox(+time) positions into Sentinel's
``vessels`` / ``vessel_locations`` tables so ``run_cv`` can correlate.

Requires either ``duckdb`` on PYTHONPATH or a sibling Indago checkout with ``uv``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_INDAGO_DUCKDB = Path.home() / ".indago" / "data" / "processed" / "ais" / "singapore.duckdb"
DEFAULT_INDAGO_ROOT = Path.home() / "work" / "edgesentry" / "indago"
DEFAULT_SENTINEL_DB = Path.home() / "work" / "Sentinel-Imagery-Analysis" / "data.db"
SOURCE_PLUGIN = "IndagoAISBridge"

_SHIP_TYPE_BY_CODE: dict[int, str] = {
    30: "Fishing",
    31: "Tug",
    32: "Tug",
    35: "Military",
    36: "Sailing",
    37: "Pleasure Craft",
    50: "Tug",
    51: "SAR",
    52: "Tug",
    53: "Tug",
    54: "Tug",
    55: "Law Enforcement",
    58: "Medical Transport",
}
for _code in range(40, 50):
    _SHIP_TYPE_BY_CODE[_code] = "High Speed Craft"
for _code in range(60, 70):
    _SHIP_TYPE_BY_CODE[_code] = "Passenger"
for _code in range(70, 80):
    _SHIP_TYPE_BY_CODE[_code] = "Cargo"
for _code in range(80, 90):
    _SHIP_TYPE_BY_CODE[_code] = "Tanker"


def resolve_duckdb_path(explicit: str | None = None) -> Path:
    raw = (explicit or os.environ.get("INDAGO_AIS_DUCKDB") or "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_INDAGO_DUCKDB
    if not path.is_file():
        raise FileNotFoundError(
            f"Indago AIS DuckDB not found: {path} "
            "(set INDAGO_AIS_DUCKDB or refresh ~/.indago/data/processed/ais/)"
        )
    return path.resolve()


def resolve_sentinel_db(explicit: str | None = None) -> Path:
    raw = (explicit or os.environ.get("SENTINEL_DATABASE_PATH") or "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_SENTINEL_DB
    if not path.is_file():
        raise FileNotFoundError(
            f"Sentinel data.db not found: {path} "
            "(set SENTINEL_DATABASE_PATH; default sibling Sentinel-Imagery-Analysis/data.db)"
        )
    return path.resolve()


def _ship_type_label(code: object) -> str | None:
    if code is None:
        return None
    try:
        return _SHIP_TYPE_BY_CODE.get(int(code))
    except (TypeError, ValueError):
        return None


def _parse_pass_time(pass_time: str | None) -> datetime | None:
    if not pass_time or not str(pass_time).strip():
        return None
    parsed = datetime.fromisoformat(str(pass_time).strip().replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _query_sql(
    bbox: list[float],
    *,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> tuple[str, list[Any]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    clauses = [
        "lat BETWEEN ? AND ?",
        "lon BETWEEN ? AND ?",
        "mmsi IS NOT NULL",
    ]
    params: list[Any] = [min_lat, max_lat, min_lon, max_lon]
    if start is not None and end is not None:
        clauses.append("timestamp BETWEEN ? AND ?")
        params.extend([start, end])
    where = " AND ".join(clauses)
    # Latest ping per MMSI inside the filter window.
    sql = f"""
        SELECT mmsi, timestamp, lat, lon, sog, cog, ship_type
        FROM (
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
            WHERE {where}
        )
        WHERE rn = 1
        ORDER BY timestamp DESC
        LIMIT ?
    """
    params.append(limit)
    return sql, params


def _rows_via_duckdb(
    duckdb_path: Path,
    sql: str,
    params: list[Any],
) -> list[dict[str, Any]]:
    import duckdb  # type: ignore[import-untyped]

    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        result = con.execute(sql, params).fetchall()
    finally:
        con.close()
    return [_row_to_dict(row) for row in result]


def _rows_via_indago_uv(
    duckdb_path: Path,
    sql: str,
    params: list[Any],
) -> list[dict[str, Any]]:
    root = Path(os.environ.get("INDAGO_ROOT", DEFAULT_INDAGO_ROOT)).expanduser()
    if not (root / "pyproject.toml").is_file():
        raise RuntimeError(
            "duckdb package missing and Indago checkout not found; "
            f"install duckdb or set INDAGO_ROOT (tried {root})"
        )
    payload = {
        "path": str(duckdb_path),
        "sql": sql,
        "params": [
            p.isoformat() if isinstance(p, datetime) else p for p in params
        ],
    }
    runner = r"""
import json, sys
import duckdb
req = json.load(sys.stdin)
con = duckdb.connect(req["path"], read_only=True)
rows = con.execute(req["sql"], req["params"]).fetchall()
con.close()
out = []
for mmsi, ts, lat, lon, sog, cog, ship_type in rows:
    out.append({
        "mmsi": str(mmsi),
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "lat": float(lat),
        "lon": float(lon),
        "sog": None if sog is None else float(sog),
        "cog": None if cog is None else float(cog),
        "ship_type": None if ship_type is None else int(ship_type),
    })
print(json.dumps(out))
"""
    proc = subprocess.run(
        ["uv", "run", "python", "-c", runner],
        cwd=str(root),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Indago uv duckdb query failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    data = json.loads(proc.stdout)
    if not isinstance(data, list):
        raise RuntimeError("unexpected Indago bridge JSON")
    return data


def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    mmsi, ts, lat, lon, sog, cog, ship_type = row
    if hasattr(ts, "isoformat"):
        ts_s = ts.isoformat()
    else:
        ts_s = str(ts)
    return {
        "mmsi": str(mmsi),
        "timestamp": ts_s,
        "lat": float(lat),
        "lon": float(lon),
        "sog": None if sog is None else float(sog),
        "cog": None if cog is None else float(cog),
        "ship_type": None if ship_type is None else int(ship_type),
    }


def fetch_indago_positions(
    bbox: list[float],
    *,
    duckdb_path: Path | None = None,
    pass_time: str | None = None,
    window_hours: float = 2.0,
    time_mode: str = "auto",
    limit: int = 2000,
) -> tuple[list[dict[str, Any]], str]:
    """Return (rows, mode_used).

    time_mode:
      - strict: pass_time ± window only (error if empty / no pass_time)
      - spatial: ignore time
      - auto: try strict window, then spatial fallback
    """
    path = duckdb_path or resolve_duckdb_path()
    mode = (time_mode or "auto").strip().lower()
    if mode not in {"auto", "strict", "spatial"}:
        raise ValueError("time_mode must be auto|strict|spatial")

    acq = _parse_pass_time(pass_time)
    start = end = None
    if mode in {"auto", "strict"} and acq is not None:
        delta = timedelta(hours=max(0.0, float(window_hours)))
        start, end = acq - delta, acq + delta

    def _run(s: datetime | None, e: datetime | None) -> list[dict[str, Any]]:
        sql, params = _query_sql(bbox, start=s, end=e, limit=limit)
        try:
            return _rows_via_duckdb(path, sql, params)
        except ImportError:
            return _rows_via_indago_uv(path, sql, params)

    if mode == "spatial" or (mode == "auto" and acq is None):
        rows = _run(None, None)
        return rows, "spatial"

    rows = _run(start, end)
    if rows:
        return rows, "strict"
    if mode == "strict":
        return [], "strict"
    rows = _run(None, None)
    return rows, "spatial-fallback"


def write_sentinel_ais(
    rows: list[dict[str, Any]],
    *,
    sentinel_db: Path | None = None,
    remap_to: str | None = None,
    source_plugin: str = SOURCE_PLUGIN,
) -> int:
    """Insert Indago rows into Sentinel SQLite. Returns inserted location count."""
    db = sentinel_db or resolve_sentinel_db()
    remap_dt = _parse_pass_time(remap_to)
    inserted = 0
    with sqlite3.connect(str(db), timeout=30) as conn:
        for row in rows:
            mmsi = str(row["mmsi"]).strip()
            if not mmsi:
                continue
            imo = f"INDAGO-{mmsi}"
            name = f"INDAGO-{mmsi}"
            vtype = _ship_type_label(row.get("ship_type"))
            conn.execute(
                """
                INSERT INTO vessels (imo, mmsi, vessel_name, vessel_type, callsign)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(imo, mmsi) DO UPDATE SET
                    vessel_name=excluded.vessel_name,
                    vessel_type=excluded.vessel_type,
                    callsign=excluded.callsign
                """,
                (imo, mmsi, name, vtype, None),
            )
            vessel_id = conn.execute(
                "SELECT id FROM vessels WHERE imo = ? AND mmsi = ?",
                (imo, mmsi),
            ).fetchone()
            if vessel_id is None:
                continue
            if remap_dt is not None:
                ts = remap_dt.isoformat()
            else:
                ts_raw = str(row["timestamp"])
                try:
                    parsed = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    if parsed.utcoffset() is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    ts = parsed.astimezone(timezone.utc).isoformat()
                except ValueError:
                    ts = ts_raw
            sog = row.get("sog")
            cog = row.get("cog")
            heading = None if cog is None else max(0.0, min(360.0, float(cog)))
            conn.execute(
                """
                INSERT INTO vessel_locations
                (vessel_id, latitude, longitude, speed, heading, timestamp, source_plugin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vessel_id[0],
                    float(row["lat"]),
                    float(row["lon"]),
                    None if sog is None else float(sog),
                    heading,
                    ts,
                    source_plugin,
                ),
            )
            inserted += 1
        conn.commit()
    return inserted


def bridge_indago_to_sentinel(
    bbox: list[float],
    *,
    pass_time: str | None = None,
    duckdb_path: str | None = None,
    sentinel_db: str | None = None,
    time_mode: str = "auto",
    window_hours: float = 2.0,
    remap_time: bool = False,
    limit: int = 2000,
) -> dict[str, Any]:
    """Fetch Indago AIS and write into Sentinel DB. Returns a summary dict."""
    ddb = resolve_duckdb_path(duckdb_path)
    sdb = resolve_sentinel_db(sentinel_db)
    rows, mode_used = fetch_indago_positions(
        bbox,
        duckdb_path=ddb,
        pass_time=pass_time,
        window_hours=window_hours,
        time_mode=time_mode,
        limit=limit,
    )
    do_remap = bool(remap_time) or (mode_used == "spatial-fallback" and bool(pass_time))
    inserted = write_sentinel_ais(
        rows,
        sentinel_db=sdb,
        remap_to=pass_time if do_remap else None,
    )
    return {
        "duckdb": str(ddb),
        "sentinel_db": str(sdb),
        "fetched": len(rows),
        "inserted": inserted,
        "time_mode_used": mode_used,
        "remapped_timestamps": do_remap,
        "source_plugin": SOURCE_PLUGIN,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bbox",
        required=True,
        help="min_lon,min_lat,max_lon,max_lat",
    )
    parser.add_argument("--pass-time", default="")
    parser.add_argument("--duckdb", default="")
    parser.add_argument("--sentinel-db", default="")
    parser.add_argument("--time-mode", default="auto", choices=["auto", "strict", "spatial"])
    parser.add_argument("--window-hours", type=float, default=2.0)
    parser.add_argument("--remap-time", action="store_true")
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args(argv)
    parts = [float(x.strip()) for x in args.bbox.split(",")]
    if len(parts) != 4:
        print("FAIL: --bbox needs 4 floats", file=sys.stderr)
        return 2
    summary = bridge_indago_to_sentinel(
        parts,
        pass_time=args.pass_time or None,
        duckdb_path=args.duckdb or None,
        sentinel_db=args.sentinel_db or None,
        time_mode=args.time_mode,
        window_hours=args.window_hours,
        remap_time=args.remap_time,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["inserted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
