"""Load marun-sensor-simulation / CI fixture JSONL for Nexus scenarios."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "s1_trojan_scenario.jsonl"
DEFAULT_POIS = ROOT / "tests" / "fixtures" / "s1_trojan_pois.json"
DEFAULT_S2_FIXTURE = ROOT / "tests" / "fixtures" / "s2_osint_swarm_scenario.jsonl"
SIBLING_EXPORT = ROOT.parent / "marun-sensor-simulation" / "exports"

_SCENARIO_FILES: dict[str, str] = {
    "S1_trojan": "s1_trojan_scenario.jsonl",
    "S2_osint_swarm": "s2_osint_swarm_scenario.jsonl",
}


def resolve_export_dir() -> Path:
    env = os.environ.get("MARUN_EXPORT_DIR")
    if env:
        return Path(env)
    if (SIBLING_EXPORT / "s1_trojan_scenario.jsonl").is_file() or (
        SIBLING_EXPORT / "s2_osint_swarm_scenario.jsonl"
    ).is_file():
        return SIBLING_EXPORT
    return DEFAULT_FIXTURE.parent


def _read_jsonl(target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def load_jsonl(path: Path | None = None) -> list[dict[str, Any]]:
    """Load S1_trojan canonical JSONL (legacy helper)."""
    target = path or (resolve_export_dir() / "s1_trojan_scenario.jsonl")
    if not target.is_file():
        target = DEFAULT_FIXTURE
    return _read_jsonl(target)


def load_scenario_jsonl(
    scenario_id: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Load scenario events from marun exports or Nexus CI fixtures.

    Nexus-shape rows may carry ``t_offset_sec``; those are re-stamped to
    ``observed_at`` relative to ``now`` (default: UTC now).
    """
    filename = _SCENARIO_FILES.get(scenario_id)
    if filename is None:
        raise KeyError(f"no marun export mapping for scenario {scenario_id!r}")

    export_dir = resolve_export_dir()
    target = export_dir / filename
    if not target.is_file():
        fallback = ROOT / "tests" / "fixtures" / filename
        if fallback.is_file():
            target = fallback
        elif scenario_id == "S1_trojan":
            target = DEFAULT_FIXTURE
        elif scenario_id == "S2_osint_swarm":
            target = DEFAULT_S2_FIXTURE
        else:
            raise FileNotFoundError(f"missing scenario export: {filename}")

    rows = _read_jsonl(target)
    anchor = now or datetime.now(UTC)
    stamped: list[dict[str, Any]] = []
    for row in rows:
        ev = dict(row)
        if "t_offset_sec" in ev:
            offset = float(ev.pop("t_offset_sec"))
            ev["observed_at"] = (anchor + timedelta(seconds=offset)).isoformat()
        stamped.append(ev)
    return stamped


def load_pois(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or (resolve_export_dir() / "pois.json")
    if not target.is_file():
        target = DEFAULT_POIS
    payload: Any = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"expected POI list in {target}, got {type(payload).__name__}")
    return [row for row in payload if isinstance(row, dict)]
