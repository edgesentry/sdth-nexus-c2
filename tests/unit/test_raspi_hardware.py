"""Optional RasPi GPIO blink on Screen 2 client after Ack (issue #20)."""

from __future__ import annotations

import pytest
from app.adapters.raspi_hardware import (
    RaspiHardwareAdapter,
    blink_on_ack_sync,
    maybe_blink_on_ack,
    raspi_ack_blink_enabled,
    resolve_led_pin,
)
from core.coa import ActionTier, CourseOfAction


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


def test_blink_on_ack_sync_disabled() -> None:
    assert blink_on_ack_sync(enabled=False) is None


def test_blink_on_ack_sync_noop() -> None:
    adapter = RaspiHardwareAdapter(auto_init=False)
    tel = blink_on_ack_sync(enabled=True, adapter=adapter)
    assert tel is not None
    assert tel["blinked"] is False


@pytest.mark.asyncio
async def test_dispatch_and_station_keep_with_mock_gpio() -> None:
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
