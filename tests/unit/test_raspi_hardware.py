"""Optional RasPi GPIO blink on recipient ack (issue #20)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app import c2_server
from app.adapters.raspi_hardware import (
    RaspiHardwareAdapter,
    maybe_blink_on_ack,
    raspi_ack_blink_enabled,
    resolve_led_pin,
)
from app.c2_server import app
from fastapi.testclient import TestClient


class _FakeGPIO:
    BCM = 11
    OUT = 0

    def __init__(self) -> None:
        self.outputs: list[tuple[int, bool]] = []
        self.setmode_calls: list[int] = []
        self.setup_calls: list[tuple[int, int]] = []

    def setmode(self, mode: int) -> None:
        self.setmode_calls.append(mode)

    def setup(self, pin: int, mode: int) -> None:
        self.setup_calls.append((pin, mode))

    def output(self, pin: int, value: bool) -> None:
        self.outputs.append((pin, value))


def test_raspi_ack_blink_enabled_truthy() -> None:
    assert raspi_ack_blink_enabled({"RASPI_ACK_BLINK": "1"}) is True
    assert raspi_ack_blink_enabled({"RASPI_GPIO": "yes"}) is True
    assert raspi_ack_blink_enabled({"RASPI_ACK_BLINK": "0"}) is False
    assert raspi_ack_blink_enabled({}) is False


def test_resolve_led_pin_env() -> None:
    assert resolve_led_pin() == 17
    assert resolve_led_pin(27) == 27
    assert resolve_led_pin(env={"RASPI_LED_PIN": "22"}) == 22


@pytest.mark.asyncio
async def test_blink_noop_without_hardware() -> None:
    adapter = RaspiHardwareAdapter(auto_init=False)
    assert adapter.hardware_available is False
    tel = await adapter.blink(pulses=2, on_s=0.0, off_s=0.0)
    assert tel["blinked"] is False
    assert tel["hardware"] == "unavailable"


@pytest.mark.asyncio
async def test_blink_pulses_mock_gpio() -> None:
    gpio = _FakeGPIO()
    adapter = RaspiHardwareAdapter(led_pin=17, gpio=gpio)
    tel = await adapter.blink(pulses=2, on_s=0.0, off_s=0.0)
    assert tel["blinked"] is True
    assert tel["pulses"] == 2
    assert len(gpio.outputs) == 4  # on/off x 2
    assert gpio.setmode_calls == [gpio.BCM]
    assert gpio.setup_calls


@pytest.mark.asyncio
async def test_maybe_blink_on_ack_disabled() -> None:
    assert await maybe_blink_on_ack(enabled=False) is None


@pytest.mark.asyncio
async def test_maybe_blink_on_ack_enabled_noop() -> None:
    adapter = RaspiHardwareAdapter(auto_init=False)
    tel = await maybe_blink_on_ack(enabled=True, adapter=adapter)
    assert tel is not None
    assert tel["blinked"] is False


@pytest.mark.asyncio
async def test_dispatch_and_station_keep_with_mock_gpio() -> None:
    from core.coa import ActionTier, CourseOfAction

    gpio = _FakeGPIO()
    adapter = RaspiHardwareAdapter(gpio=gpio)
    coa = CourseOfAction(
        target_entity_id="t1",
        target_coordinates=(1.23, 103.85),
        intent="ISR_IDENTIFY_CONTACT",
        confidence=0.9,
        corroborating_sources=["A", "B"],
        raw_input_digest="a" * 64,
        speed_kt=5.0,
        tier=ActionTier.TIER_1_HITL,
    )
    receipt = await adapter.dispatch(coa)
    assert receipt.status == "DISPATCHED"
    assert receipt.telemetry["blinked"] is True

    keep = await adapter.emergency_station_keep()
    assert keep.status == "STATION_KEEP"
    assert (17, False) in gpio.outputs


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


def _approve_one(client: TestClient) -> str:
    proposed = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    coa_id = proposed.json()["coa"]["coa_id"]
    approved = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "op-1"},
    )
    assert approved.status_code == 200
    return coa_id


def test_recipient_ack_without_raspi_env(client: TestClient) -> None:
    coa_id = _approve_one(client)
    ack = client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": "CUE-NODE-01", "telemetry": {"mode": "cue"}},
    )
    assert ack.status_code == 200
    tel = ack.json()["ack"]["telemetry"]
    assert tel.get("mode") == "cue"
    assert "raspi_gpio" not in tel


def test_recipient_ack_raspi_env_noop(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RASPI_ACK_BLINK", "1")
    coa_id = _approve_one(client)
    ack = client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": "CUE-NODE-01", "telemetry": {"mode": "cue"}},
    )
    assert ack.status_code == 200
    tel = ack.json()["ack"]["telemetry"]
    assert tel["mode"] == "cue"
    # No RPi.GPIO in CI/laptop → blinked=False, but key is present when opt-in.
    assert tel["raspi_gpio"]["blinked"] is False
    assert tel["raspi_gpio"]["hardware"] == "unavailable"
