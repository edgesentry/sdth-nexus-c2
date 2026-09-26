"""Deterministic interlocks: fast-reject unsafe COAs before HITL."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.coa import CourseOfAction
from core.ontology import haversine_m

CNI_FALLOUT_CODE = "SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD"
TERMINAL_INTENTS = frozenset({"TERMINAL_SAM_INTERCEPT", "OVERHEAD_KINETIC_INTERCEPT"})


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


def debris_footprint_radius_m(*, altitude_m: float = 71.0) -> float:
    """Conservative Newtonian-ish debris scatter radius for demo altitudes."""
    return max(500.0, float(altitude_m) * 8.0 + 400.0)


class DeterministicInterlock:
    def __init__(
        self,
        *,
        forbidden_zones: list[dict[str, Any]] | None = None,
        max_speed_kt: float = 40.0,
        reject_null_coordinates: bool = True,
        active_coa_ids: set[str] | None = None,
        cni_pois: list[dict[str, Any]] | None = None,
    ) -> None:
        self.forbidden_zones = forbidden_zones or []
        self.max_speed_kt = max_speed_kt
        self.reject_null_coordinates = reject_null_coordinates
        self.active_coa_ids = active_coa_ids if active_coa_ids is not None else set()
        self.cni_pois = cni_pois or []

    def set_cni_pois(self, pois: list[dict[str, Any]]) -> None:
        self.cni_pois = list(pois)

    def verify_cni_debris(self, coa: CourseOfAction) -> tuple[bool, str | None]:
        """HARD VETO terminal/overhead kinetic fire whose debris cone hits CNI buffer."""
        dangerous = (
            bool(coa.metadata.get("dangerous_proposal_draft")) or coa.intent in TERMINAL_INTENTS
        )
        if not dangerous or not self.cni_pois:
            return True, None
        lat, lon = coa.target_coordinates
        altitude = float(coa.metadata.get("altitude_m", 71.0))
        footprint = debris_footprint_radius_m(altitude_m=altitude)
        for poi in self.cni_pois:
            # Hard VETO is civilian CNI only; military POIs drive ETA flags, not debris lockout.
            if poi.get("kind") not in {"civilian_cni", None}:
                continue
            center_lat = float(poi["center_lat"])
            center_lon = float(poi["center_lon"])
            buffer_m = float(poi.get("buffer_m", 2500.0))
            d = haversine_m(lat, lon, center_lat, center_lon)
            if d <= buffer_m + footprint:
                name = poi.get("name", poi.get("poi_id", "CNI"))
                return (
                    False,
                    f"{CNI_FALLOUT_CODE}: debris cone intersects {name} "
                    f"(range {d:.0f} m ≤ buffer {buffer_m:.0f} m + footprint {footprint:.0f} m)",
                )
        return True, None

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

        ok, reason = self.verify_cni_debris(coa)
        if not ok:
            return False, reason

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
