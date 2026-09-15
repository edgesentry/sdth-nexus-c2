"""Level 1+2 Clearbot REST adapter + optional kinematics."""

from __future__ import annotations

from typing import Any, cast

import httpx
from core.coa import CourseOfAction
from core.proxy import EffectorProxy
from core.schema import ExecutionReceipt

from app.adapters.kinematics_sim import KinematicsSim


class ClearbotRestAdapter(EffectorProxy):
    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8000",
        *,
        timeout_sec: float = 5.0,
        kinematics: KinematicsSim | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_sec = timeout_sec
        self.kinematics = kinematics or KinematicsSim(latitude=1.2300, longitude=103.8500)

    async def dispatch(self, coa: CourseOfAction) -> ExecutionReceipt:
        lat, lon = coa.target_coordinates
        payload = {
            "latitude": lat,
            "longitude": lon,
            "speed_kt": 5.0,
            "mission_id": coa.coa_id,
        }
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(f"{self.endpoint}/api/v1/navigate", json=payload)
            resp.raise_for_status()
            body: dict[str, Any] = resp.json()

        # Demo speed ~15 m/s so a ~1 km approach finishes in tens of steps
        self.kinematics.set_waypoint(lat, lon, speed_mps=15.0)
        path = self.kinematics.run_until_arrival(max_steps=200, dt_sec=1.0)
        receipt = ExecutionReceipt(
            coa_id=coa.coa_id,
            status="DISPATCHED",
            message="navigate_accepted",
            telemetry={
                "http": body,
                "path_tail": path[-5:],
                "position": {
                    "latitude": self.kinematics.latitude,
                    "longitude": self.kinematics.longitude,
                },
            },
        )
        receipt.seal()
        return receipt

    async def emergency_station_keep(self) -> ExecutionReceipt:
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(f"{self.endpoint}/api/v1/emergency_stop")
            resp.raise_for_status()
            body = resp.json()
        self.kinematics.station_keep()
        receipt = ExecutionReceipt(
            coa_id="",
            status="STATION_KEEP",
            message="emergency_station_keep",
            telemetry={"http": body},
        )
        receipt.seal()
        return receipt

    async def telemetry(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.get(f"{self.endpoint}/api/v1/telemetry")
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
