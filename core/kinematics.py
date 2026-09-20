"""SAR dead-reckoning projection, reachability envelopes, and lead-pursuit POI.

Bridge historical space-based SAR (T - dt) to coastal radar at t_now without
shared MMSI (#57). Replace static tasking coords with lead-pursuit intercept
waypoints + ETA for APPROACH_PATROL / CUE_AND_IDENTIFY (#58).
See docs/architecture/sar_pipeline.md and docs/roadmap.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import cos, hypot, radians, sin, tan
from typing import Any

from core.ontology import haversine_m
from core.schema import Observation

SPACE_SAR_MODALITY = "space_sar"
RADAR_MODALITY = "radar"

KT_TO_MPS = 0.514444
M_PER_DEG_LAT = 111_320.0

# Merchant-band defaults: v_est is the midpoint of [v_min, v_max].
DEFAULT_V_MIN_KT = 4.0
DEFAULT_V_MAX_KT = 18.0
DEFAULT_V_EST_KT = 12.0
DEFAULT_SIGMA_NAV_M = 250.0
DEFAULT_HEADING_SIGMA_DEG = 20.0
# Documented SAR latency band (30 min … 4 h); refuse association beyond this.
MAX_DT_SEC = 4.0 * 3600.0

DEFAULT_V_MIN_MPS = DEFAULT_V_MIN_KT * KT_TO_MPS
DEFAULT_V_MAX_MPS = DEFAULT_V_MAX_KT * KT_TO_MPS
DEFAULT_V_EST_MPS = DEFAULT_V_EST_KT * KT_TO_MPS


def kt_to_mps(knots: float) -> float:
    return knots * KT_TO_MPS


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _heading_of(obs: Observation) -> float | None:
    if obs.heading_deg is not None:
        return float(obs.heading_deg)
    raw = obs.attributes.get("heading_deg", obs.attributes.get("angle"))
    if raw is None or raw == "":
        return None
    return float(raw)


def _speed_mps_of(obs: Observation) -> float:
    if obs.speed_mps > 1e-9:
        return float(obs.speed_mps)
    raw = obs.attributes.get("speed_kt")
    if raw is not None and float(raw) > 1e-9:
        return kt_to_mps(float(raw))
    return DEFAULT_V_EST_MPS


def uncertainty_radius_m(
    dt_sec: float,
    *,
    v_min_mps: float = DEFAULT_V_MIN_MPS,
    v_max_mps: float = DEFAULT_V_MAX_MPS,
    sigma_nav_m: float = DEFAULT_SIGMA_NAV_M,
) -> float:
    """R(dt) = |dt| * (v_max - v_min) / 2 + sigma_nav."""
    return abs(dt_sec) * (v_max_mps - v_min_mps) / 2.0 + sigma_nav_m


def displace_m(
    latitude: float,
    longitude: float,
    heading_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    """Equirectangular destination (heading 0=N, 90=E). Singapore-scale demo."""
    heading = radians(heading_deg)
    m_per_deg_lon = M_PER_DEG_LAT * cos(radians(latitude))
    d_north = distance_m * cos(heading)
    d_east = distance_m * sin(heading)
    return (
        latitude + d_north / M_PER_DEG_LAT,
        longitude + d_east / max(m_per_deg_lon, 1e-6),
    )


def enu_offset_m(
    lat0: float,
    lon0: float,
    lat1: float,
    lon1: float,
) -> tuple[float, float]:
    """North / east metres from (lat0, lon0) to (lat1, lon1)."""
    m_per_deg_lon = M_PER_DEG_LAT * cos(radians(lat0))
    d_north = (lat1 - lat0) * M_PER_DEG_LAT
    d_east = (lon1 - lon0) * m_per_deg_lon
    return d_north, d_east


@dataclass(frozen=True, slots=True)
class ProjectedContact:
    latitude: float
    longitude: float
    origin_latitude: float
    origin_longitude: float
    heading_deg: float | None
    speed_mps: float
    dt_sec: float
    radius_m: float
    along_m: float
    cross_m: float

    def as_breakdown(self) -> dict[str, Any]:
        return {
            "dt_sec": self.dt_sec,
            "projected_latitude": self.latitude,
            "projected_longitude": self.longitude,
            "uncertainty_radius_m": self.radius_m,
            "along_m": self.along_m,
            "cross_m": self.cross_m,
            "heading_deg": self.heading_deg,
            "speed_mps": self.speed_mps,
        }


def project_dead_reckoning(
    latitude: float,
    longitude: float,
    *,
    heading_deg: float | None,
    speed_mps: float,
    dt_sec: float,
    v_min_mps: float = DEFAULT_V_MIN_MPS,
    v_max_mps: float = DEFAULT_V_MAX_MPS,
    sigma_nav_m: float = DEFAULT_SIGMA_NAV_M,
    heading_sigma_deg: float = DEFAULT_HEADING_SIGMA_DEG,
) -> ProjectedContact:
    """Project p_sar + dt * v_est and attach the reachability ellipse."""
    if heading_deg is None:
        radius = abs(dt_sec) * v_max_mps + sigma_nav_m
        return ProjectedContact(
            latitude=latitude,
            longitude=longitude,
            origin_latitude=latitude,
            origin_longitude=longitude,
            heading_deg=None,
            speed_mps=speed_mps,
            dt_sec=dt_sec,
            radius_m=radius,
            along_m=radius,
            cross_m=radius,
        )

    traveled = speed_mps * dt_sec
    lat_p, lon_p = displace_m(latitude, longitude, heading_deg, traveled)
    along = uncertainty_radius_m(
        dt_sec, v_min_mps=v_min_mps, v_max_mps=v_max_mps, sigma_nav_m=sigma_nav_m
    )
    cross = sigma_nav_m + abs(traveled) * tan(radians(heading_sigma_deg))
    return ProjectedContact(
        latitude=lat_p,
        longitude=lon_p,
        origin_latitude=latitude,
        origin_longitude=longitude,
        heading_deg=heading_deg,
        speed_mps=speed_mps,
        dt_sec=dt_sec,
        radius_m=along,
        along_m=max(along, 1.0),
        cross_m=max(cross, 1.0),
    )


def project_observation(
    observation: Observation,
    t_now: datetime,
    *,
    v_min_mps: float = DEFAULT_V_MIN_MPS,
    v_max_mps: float = DEFAULT_V_MAX_MPS,
    sigma_nav_m: float = DEFAULT_SIGMA_NAV_M,
    heading_sigma_deg: float = DEFAULT_HEADING_SIGMA_DEG,
) -> ProjectedContact:
    dt_sec = (_as_utc(t_now) - _as_utc(observation.observed_at)).total_seconds()
    return project_dead_reckoning(
        observation.latitude,
        observation.longitude,
        heading_deg=_heading_of(observation),
        speed_mps=_speed_mps_of(observation),
        dt_sec=dt_sec,
        v_min_mps=v_min_mps,
        v_max_mps=v_max_mps,
        sigma_nav_m=sigma_nav_m,
        heading_sigma_deg=heading_sigma_deg,
    )


def in_reachability_envelope(
    projected: ProjectedContact,
    latitude: float,
    longitude: float,
) -> bool:
    """True when the point lies inside E(dt) (ellipse if heading known, else disc)."""
    d_north, d_east = enu_offset_m(projected.latitude, projected.longitude, latitude, longitude)
    if projected.heading_deg is None:
        return hypot(d_north, d_east) <= projected.radius_m

    heading = radians(projected.heading_deg)
    along = d_north * cos(heading) + d_east * sin(heading)
    cross = -d_north * sin(heading) + d_east * cos(heading)
    return (along / projected.along_m) ** 2 + (cross / projected.cross_m) ** 2 <= 1.0


def _sar_and_radar(a: Observation, b: Observation) -> tuple[Observation, Observation] | None:
    if a.modality == SPACE_SAR_MODALITY and b.modality == RADAR_MODALITY:
        return a, b
    if b.modality == SPACE_SAR_MODALITY and a.modality == RADAR_MODALITY:
        return b, a
    return None


def associate_kinematically(a: Observation, b: Observation) -> bool:
    """True when a SAR/radar pair matches via the dead-reckoned envelope."""
    pair = _sar_and_radar(a, b)
    if pair is None:
        return False
    sar, radar = pair
    dt_sec = abs((_as_utc(radar.observed_at) - _as_utc(sar.observed_at)).total_seconds())
    if dt_sec > MAX_DT_SEC:
        return False
    projected = project_observation(sar, radar.observed_at)
    return in_reachability_envelope(projected, radar.latitude, radar.longitude)


def projected_separation_m(a: Observation, b: Observation) -> float | None:
    """Haversine from radar to the SAR contact projected to the radar clock."""
    pair = _sar_and_radar(a, b)
    if pair is None:
        return None
    sar, radar = pair
    projected = project_observation(sar, radar.observed_at)
    return haversine_m(projected.latitude, projected.longitude, radar.latitude, radar.longitude)


# ---------------------------------------------------------------------------
# Lead-pursuit Point of Interception (issue #58)
# ---------------------------------------------------------------------------

# Demo own-platform defaults (matches UsvRestAdapter kinematics start + cruise).
DEFAULT_OWN_LATITUDE = 1.2300
DEFAULT_OWN_LONGITUDE = 103.8500
DEFAULT_OWN_SPEED_MPS = 15.0
# Cap lead-along-track fallback so cue waypoints stay inside the pitch window.
MAX_LEAD_FALLBACK_SEC = 600.0


@dataclass(frozen=True, slots=True)
class LeadPursuitPOI:
    """Intercept waypoint + ETA for effector / cue tasking."""

    latitude: float
    longitude: float
    eta_sec: float
    method: str
    contact_latitude: float
    contact_longitude: float
    contact_heading_deg: float | None
    contact_speed_mps: float
    own_latitude: float
    own_longitude: float
    own_speed_mps: float
    range_at_intercept_m: float

    def as_metadata(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "eta_sec": round(self.eta_sec, 3),
            "method": self.method,
            "range_at_intercept_m": round(self.range_at_intercept_m, 1),
            "contact_snapshot": {
                "latitude": self.contact_latitude,
                "longitude": self.contact_longitude,
                "heading_deg": self.contact_heading_deg,
                "speed_mps": round(self.contact_speed_mps, 3),
            },
            "own_platform": {
                "latitude": self.own_latitude,
                "longitude": self.own_longitude,
                "speed_mps": self.own_speed_mps,
            },
        }


def _collision_course_eta_sec(
    range_north_m: float,
    range_east_m: float,
    vt_north_mps: float,
    vt_east_mps: float,
    own_speed_mps: float,
) -> float | None:
    """Smallest t > 0 where |R + Vt t| = Vo t (constant-speed collision course)."""
    r2 = range_north_m * range_north_m + range_east_m * range_east_m
    if r2 < 1.0:
        return 0.0
    if own_speed_mps <= 1e-9:
        return None

    dot = range_north_m * vt_north_mps + range_east_m * vt_east_mps
    vt2 = vt_north_mps * vt_north_mps + vt_east_mps * vt_east_mps
    a = vt2 - own_speed_mps * own_speed_mps
    b = 2.0 * dot
    c = r2

    if abs(a) < 1e-9:
        # |Vt| ≈ Vo → linear: 2 (R·Vt) t + |R|² = 0
        if abs(b) < 1e-9:
            return None
        t = -c / b
        return t if t > 1e-9 else None

    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return None
    sqrt_disc = disc**0.5
    candidates = [(-b + sqrt_disc) / (2.0 * a), (-b - sqrt_disc) / (2.0 * a)]
    positive = [t for t in candidates if t > 1e-9]
    return min(positive) if positive else None


def compute_lead_pursuit_poi(
    contact_latitude: float,
    contact_longitude: float,
    *,
    contact_heading_deg: float | None,
    contact_speed_mps: float,
    own_latitude: float = DEFAULT_OWN_LATITUDE,
    own_longitude: float = DEFAULT_OWN_LONGITUDE,
    own_speed_mps: float = DEFAULT_OWN_SPEED_MPS,
    max_lead_sec: float = MAX_LEAD_FALLBACK_SEC,
) -> LeadPursuitPOI:
    """Replace static historical coords with a lead-pursuit intercept waypoint.

    Prefer a constant-speed collision-course solution. When the own platform
    cannot catch the contact (or heading is unknown), fall back to projecting
    the contact along-track for ``min(range/Vo, max_lead_sec)``.
    """
    range_m = haversine_m(own_latitude, own_longitude, contact_latitude, contact_longitude)
    own_speed = max(own_speed_mps, 1e-6)

    if contact_heading_deg is None or contact_speed_mps <= 1e-9:
        eta = range_m / own_speed
        return LeadPursuitPOI(
            latitude=contact_latitude,
            longitude=contact_longitude,
            eta_sec=eta,
            method="static_contact",
            contact_latitude=contact_latitude,
            contact_longitude=contact_longitude,
            contact_heading_deg=contact_heading_deg,
            contact_speed_mps=contact_speed_mps,
            own_latitude=own_latitude,
            own_longitude=own_longitude,
            own_speed_mps=own_speed_mps,
            range_at_intercept_m=range_m,
        )

    r_north, r_east = enu_offset_m(own_latitude, own_longitude, contact_latitude, contact_longitude)
    heading = radians(contact_heading_deg)
    vt_north = contact_speed_mps * cos(heading)
    vt_east = contact_speed_mps * sin(heading)

    eta_cc = _collision_course_eta_sec(r_north, r_east, vt_north, vt_east, own_speed)
    if eta_cc is not None and eta_cc <= max_lead_sec:
        poi_lat, poi_lon = displace_m(
            contact_latitude, contact_longitude, contact_heading_deg, contact_speed_mps * eta_cc
        )
        return LeadPursuitPOI(
            latitude=poi_lat,
            longitude=poi_lon,
            eta_sec=eta_cc,
            method="collision_course",
            contact_latitude=contact_latitude,
            contact_longitude=contact_longitude,
            contact_heading_deg=contact_heading_deg,
            contact_speed_mps=contact_speed_mps,
            own_latitude=own_latitude,
            own_longitude=own_longitude,
            own_speed_mps=own_speed_mps,
            range_at_intercept_m=own_speed * eta_cc,
        )

    lead_sec = min(range_m / own_speed, max_lead_sec)
    poi_lat, poi_lon = displace_m(
        contact_latitude,
        contact_longitude,
        contact_heading_deg,
        contact_speed_mps * lead_sec,
    )
    intercept_range = haversine_m(own_latitude, own_longitude, poi_lat, poi_lon)
    return LeadPursuitPOI(
        latitude=poi_lat,
        longitude=poi_lon,
        eta_sec=intercept_range / own_speed,
        method="lead_along_track",
        contact_latitude=contact_latitude,
        contact_longitude=contact_longitude,
        contact_heading_deg=contact_heading_deg,
        contact_speed_mps=contact_speed_mps,
        own_latitude=own_latitude,
        own_longitude=own_longitude,
        own_speed_mps=own_speed_mps,
        range_at_intercept_m=intercept_range,
    )
