"""Synthetic OSINT / social recon text → count & bearing (issue #59).

Not a live SNS API. Extracts ``claimed_count`` (and optional bearing / objective)
from demo intel strings used by S2. Prefer filtered estimates over exaggerated
lead numbers (e.g. ``~20 … filtered OSINT estimate 3`` → 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_FILTERED_COUNT = re.compile(
    r"(?:filtered\s+(?:osint\s+)?estimate|osint\s+estimate|estimate(?:d)?)"
    r"\s*[:=]?\s*~?\s*(\d{1,3})",
    re.IGNORECASE,
)
_AIRFRAME_COUNT = re.compile(
    r"\b(\d{1,3})\s*"
    r"(?:shahed(?:-\d+)?(?:\s+class)?|airframes?|drones?|uavs?|contacts?)\b",
    re.IGNORECASE,
)
_BARE_TILDE_COUNT = re.compile(r"~(\d{1,3})\b")
_BEARING = re.compile(
    r"\b(?:bearing|heading|hdg|brg)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*°?",
    re.IGNORECASE,
)
_CARDINAL_BEARING = re.compile(
    r"\b(?:from|due)\s+the\s+"
    r"(north(?:east|west)?|south(?:east|west)?|east|west|"
    r"ne|nw|se|sw|n|s|e|w)\b",
    re.IGNORECASE,
)
_TOWARD_OBJECTIVE = re.compile(
    r"\btoward(?:s)?\s+([A-Za-z][A-Za-z0-9][A-Za-z0-9 \-]{0,40}?)(?=[,.;]|T\+|$)",
    re.IGNORECASE,
)

_CARDINALS: dict[str, float] = {
    "n": 0.0,
    "north": 0.0,
    "ne": 45.0,
    "northeast": 45.0,
    "e": 90.0,
    "east": 90.0,
    "se": 135.0,
    "southeast": 135.0,
    "s": 180.0,
    "south": 180.0,
    "sw": 225.0,
    "southwest": 225.0,
    "w": 270.0,
    "west": 270.0,
    "nw": 315.0,
    "northwest": 315.0,
}


@dataclass(frozen=True)
class OsintParseResult:
    """Structured extract from Synthetic social / recon text."""

    claimed_count: int | None = None
    bearing_deg: float | None = None
    objective: str | None = None
    raw_count_match: str | None = None
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.claimed_count is not None or self.bearing_deg is not None


def parse_osint_text(
    text: str | None,
    *,
    fallback_count: int | None = None,
) -> OsintParseResult:
    """Parse intel text → count / bearing. Never raises on bad input."""
    if text is None or not str(text).strip():
        return OsintParseResult(
            claimed_count=fallback_count,
            notes=("empty_text",) if fallback_count is not None else ("empty_text", "no_fallback"),
        )

    raw = str(text).strip()
    notes: list[str] = []
    count: int | None = None
    raw_match: str | None = None

    filtered = _FILTERED_COUNT.search(raw)
    if filtered:
        count = int(filtered.group(1))
        raw_match = filtered.group(0)
        notes.append("filtered_estimate")
    else:
        airframe = _AIRFRAME_COUNT.search(raw)
        if airframe:
            count = int(airframe.group(1))
            raw_match = airframe.group(0)
            notes.append("airframe_count")
        else:
            tilde = _BARE_TILDE_COUNT.search(raw)
            if tilde:
                count = int(tilde.group(1))
                raw_match = tilde.group(0)
                notes.append("tilde_count")

    if count is not None and not (1 <= count <= 500):
        notes.append("count_out_of_range")
        count = None
        raw_match = None

    if count is None and fallback_count is not None:
        count = fallback_count
        notes.append("fallback_count")

    bearing: float | None = None
    bearing_m = _BEARING.search(raw)
    if bearing_m:
        bearing = float(bearing_m.group(1)) % 360.0
        notes.append("bearing_numeric")
    else:
        cardinal_m = _CARDINAL_BEARING.search(raw)
        if cardinal_m:
            key = cardinal_m.group(1).lower().replace("-", "")
            bearing = _CARDINALS.get(key)
            if bearing is not None:
                notes.append("bearing_cardinal")

    objective: str | None = None
    obj_m = _TOWARD_OBJECTIVE.search(raw)
    if obj_m:
        objective = " ".join(obj_m.group(1).split())
        notes.append("objective")

    return OsintParseResult(
        claimed_count=count,
        bearing_deg=bearing,
        objective=objective,
        raw_count_match=raw_match,
        notes=tuple(notes),
    )


def enrich_social_event(
    event: dict[str, Any],
    *,
    fallback_count: int | None = 3,
) -> dict[str, Any]:
    """Return a copy with ``claimed_count`` / bearing filled from ``intel_text``.

    Existing explicit ``claimed_count`` wins unless missing/invalid. Hardcoded
    scenario fallback applies when parse fails (issue #59).
    """
    out = dict(event)
    text = out.get("intel_text")
    existing = out.get("claimed_count")
    existing_n: int | None
    try:
        existing_n = int(existing) if existing is not None else None
    except (TypeError, ValueError):
        existing_n = None

    parsed = parse_osint_text(
        str(text) if text is not None else None,
        fallback_count=fallback_count if existing_n is None else None,
    )

    if existing_n is None and parsed.claimed_count is not None:
        out["claimed_count"] = parsed.claimed_count
    elif existing_n is None and fallback_count is not None:
        out["claimed_count"] = fallback_count
        out.setdefault("osint_parse_notes", ["hardcoded_fallback"])

    if parsed.bearing_deg is not None and out.get("bearing_deg") is None:
        out["bearing_deg"] = parsed.bearing_deg
    if parsed.objective and not out.get("objective"):
        out["objective"] = parsed.objective
    if parsed.notes:
        out["osint_parse_notes"] = list(parsed.notes)
    if parsed.raw_count_match:
        out["osint_raw_count_match"] = parsed.raw_count_match
    return out
