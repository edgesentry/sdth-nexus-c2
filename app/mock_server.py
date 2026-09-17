"""Level 1: Vendor-neutral USV mock REST server (FastAPI)."""

from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="USV REST Mock", version="0.1.0")

_state: dict[str, Any] = {
    "latitude": 1.2300,
    "longitude": 103.8500,
    "heading_deg": 90.0,
    "speed_kt": 0.0,
    "mode": "idle",
    "last_waypoint": None,
    "emergency": False,
}


class NavigateRequest(BaseModel):
    latitude: float
    longitude: float
    speed_kt: float = 5.0
    mission_id: str | None = None


class TelemetryResponse(BaseModel):
    latitude: float
    longitude: float
    heading_deg: float
    speed_kt: float
    mode: str
    last_waypoint: dict[str, Any] | None = None
    emergency: bool = False


@app.post("/api/v1/navigate")
async def navigate(req: NavigateRequest) -> dict[str, Any]:
    _state["last_waypoint"] = req.model_dump()
    _state["mode"] = "navigating"
    _state["speed_kt"] = req.speed_kt
    _state["emergency"] = False
    # Instant accept; Level 2 kinematics advances position elsewhere / on poll
    return {"status": "accepted", "waypoint": req.model_dump()}


@app.get("/api/v1/telemetry", response_model=TelemetryResponse)
async def telemetry() -> TelemetryResponse:
    return TelemetryResponse(**_state)


@app.post("/api/v1/emergency_stop")
async def emergency_stop() -> dict[str, Any]:
    _state["mode"] = "station_keep"
    _state["speed_kt"] = 0.0
    _state["emergency"] = True
    return {"status": "station_keep"}


def cli_main() -> None:
    uvicorn.run("app.mock_server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    cli_main()
