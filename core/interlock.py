"""Deterministic interlocks: fast-reject unsafe COAs before HITL."""

from __future__ import annotations

from typing import Sequence

from core.coa import CourseOfAction


def point_in_polygon(lat: float, lon: float, polygon: Sequence[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon (lat/lon treated as planar for small zones)."""
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        intersects = ((lon_i > lon) != (lon_j > lon)) and (
            lat < (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i + 1e-15) + lat_i
        )
        if intersects:
            inside = not inside
        j = i
    return inside


class DeterministicInterlock:
    def __init__(
        self,
        *,
        forbidden_zones: list[dict] | None = None,
        max_speed_kt: float = 40.0,
        reject_null_coordinates: bool = True,
        active_coa_ids: set[str] | None = None,
    ) -> None:
        self.forbidden_zones = forbidden_zones or []
        self.max_speed_kt = max_speed_kt
        self.reject_null_coordinates = reject_null_coordinates
        self.active_coa_ids = active_coa_ids if active_coa_ids is not None else set()

    def verify(self, coa: CourseOfAction) -> tuple[bool, str | None]:
        lat, lon = coa.target_coordinates
        if self.reject_null_coordinates and lat == 0.0 and lon == 0.0:
            return False, "Null coordinates violation"

        if coa.speed_kt is not None and coa.speed_kt > self.max_speed_kt:
            return False, f"Speed limit exceeded: {coa.speed_kt} > {self.max_speed_kt} kt"

        for zone in self.forbidden_zones:
            polygon = [tuple(p) for p in zone.get("polygon", [])]
            if point_in_polygon(lat, lon, polygon):
                name = zone.get("name", "forbidden_zone")
                return False, f"Geofence violation: {name}"

        if coa.coa_id in self.active_coa_ids:
            return False, "Duplicate active task"

        # Soft duplicate: same target + intent already active
        dup_key = f"{coa.target_entity_id}:{coa.intent}:{coa.target_coordinates}"
        if dup_key in self.active_coa_ids:
            return False, "Duplicate task for target/intent"

        return True, None

    def register_active(self, coa: CourseOfAction) -> None:
        self.active_coa_ids.add(coa.coa_id)
        self.active_coa_ids.add(f"{coa.target_entity_id}:{coa.intent}:{coa.target_coordinates}")
