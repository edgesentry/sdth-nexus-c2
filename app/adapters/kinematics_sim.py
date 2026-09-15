"""Level 2: simple 2D kinematics toward a waypoint."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class KinematicsSim:
    latitude: float
    longitude: float
    speed_mps: float = 2.5
    heading_deg: float = 0.0
    waypoint: tuple[float, float] | None = None
    history: list[tuple[float, float]] = field(default_factory=list)

    def set_waypoint(self, lat: float, lon: float, speed_mps: float | None = None) -> None:
        self.waypoint = (lat, lon)
        if speed_mps is not None:
            self.speed_mps = speed_mps

    def station_keep(self) -> None:
        self.waypoint = None
        self.speed_mps = 0.0

    def step(self, dt_sec: float = 1.0) -> tuple[float, float]:
        if self.waypoint is None or self.speed_mps <= 0:
            self.history.append((self.latitude, self.longitude))
            return self.latitude, self.longitude

        tlat, tlon = self.waypoint
        # Approximate meters per degree at equator-ish for demo
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(self.latitude))
        d_north = (tlat - self.latitude) * m_per_deg_lat
        d_east = (tlon - self.longitude) * m_per_deg_lon
        dist = math.hypot(d_north, d_east)
        if dist < 1.0:
            self.latitude, self.longitude = tlat, tlon
            self.waypoint = None
            self.speed_mps = 0.0
            self.history.append((self.latitude, self.longitude))
            return self.latitude, self.longitude

        step_m = min(self.speed_mps * dt_sec, dist)
        self.latitude += (d_north / dist) * step_m / m_per_deg_lat
        self.longitude += (d_east / dist) * step_m / max(m_per_deg_lon, 1e-6)
        self.heading_deg = (math.degrees(math.atan2(d_east, d_north)) + 360.0) % 360.0
        self.history.append((self.latitude, self.longitude))
        return self.latitude, self.longitude

    def run_until_arrival(self, max_steps: int = 120, dt_sec: float = 1.0) -> list[tuple[float, float]]:
        for _ in range(max_steps):
            if self.waypoint is None:
                break
            self.step(dt_sec)
        return list(self.history)
