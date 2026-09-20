"""SAR dead-reckoning projection and reachability envelopes (issue #57).

Bridge historical space-based SAR (T - dt) to coastal radar at t_now without
shared MMSI. See docs/architecture/sar_pipeline.md.
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
