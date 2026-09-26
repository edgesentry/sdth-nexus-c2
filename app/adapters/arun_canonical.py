"""Load Arun / marun-sensor-simulation canonical JSONL for s1_trojan."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "s1_trojan_scenario.jsonl"
DEFAULT_POIS = ROOT / "tests" / "fixtures" / "s1_trojan_pois.json"
SIBLING_EXPORT = ROOT.parent / "marun-sensor-simulation" / "exports"


def resolve_export_dir() -> Path:
    env = os.environ.get("MARUN_EXPORT_DIR")
    if env:
        return Path(env)
    if (SIBLING_EXPORT / "s1_trojan_scenario.jsonl").is_file():
        return SIBLING_EXPORT
    return DEFAULT_FIXTURE.parent


def load_jsonl(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or (resolve_export_dir() / "s1_trojan_scenario.jsonl")
    if not target.is_file():
        target = DEFAULT_FIXTURE
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def load_pois(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or (resolve_export_dir() / "pois.json")
    if not target.is_file():
        target = DEFAULT_POIS
    payload: Any = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"expected POI list in {target}, got {type(payload).__name__}")
    return [row for row in payload if isinstance(row, dict)]
