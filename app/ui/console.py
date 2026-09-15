"""Rich TUI: Warning Picture + latency-bounded HITL."""

from __future__ import annotations

import asyncio
import contextlib
import sys

from core.coa import CourseOfAction
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.scenarios.base import Finding, Scenario

console = Console()


def render_warning_picture(
    scenario: Scenario,
    finding: Finding,
    coa: CourseOfAction,
) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("k", style="bold cyan")
    table.add_column("v")
    table.add_row("Scenario", f"{scenario.id} — {scenario.title}")
    table.add_row("Threat class", finding.threat_class)
    table.add_row("Warning window", f"~{finding.warning_minutes_est:.0f} minutes")
    table.add_row("Confidence", f"{finding.confidence:.2f}")
    table.add_row("Mismatch", f"{finding.mismatch_m:.0f} m")
    table.add_row("Approach sources", ", ".join(finding.approach_sources) or "—")
    table.add_row("Manipulable / spoof", ", ".join(finding.spoof_sources) or "—")
    table.add_row("Other", ", ".join(finding.other_sources) or "—")
    table.add_row("Recommended COA", f"{coa.intent} → {coa.target_coordinates}")
    table.add_row("If false, collapses when", finding.adversarial_hypothesis)

    from rich.console import Group

    console.print(
        Panel(
            Group(finding.picture_summary, table),
            title="WARNING PICTURE — One Picture, Many Eyes",
            border_style="red",
        )
    )
    console.print(f"[dim]{scenario.narrative}[/dim]\n")


async def prompt_operator_decision(
    *,
    message: str,
    asset_label: str,
    timeout_seconds: float,
    queue: asyncio.Queue[str],
    auto_decision: str | None = None,
    finding: Finding | None = None,
    scenario: Scenario | None = None,
    coa: CourseOfAction | None = None,
) -> None:
    if scenario is not None and finding is not None and coa is not None:
        render_warning_picture(scenario, finding, coa)
    elif message:
        console.print(Panel(message, title="Finding"))

    if auto_decision is not None:
        console.print(Panel(f"Auto decision: {auto_decision}", title="HITL"))
        await queue.put(auto_decision)
        return

    remaining = timeout_seconds
    console.print(
        Panel(
            f"Task [cyan]{asset_label}[/cyan] now?\n"
            f"Remaining {remaining:.1f}s  [y/n]\n"
            f"[dim]Timeout → fail-closed STATION_KEEP[/dim]",
            title="Operator Gate — Picture to Tasking",
        )
    )

    loop = asyncio.get_running_loop()

    async def countdown() -> None:
        nonlocal remaining
        while remaining > 0:
            await asyncio.sleep(0.1)
            remaining = max(0.0, remaining - 0.1)
            console.print(f"  … {remaining:.1f}s left", end="\r")

    countdown_task = asyncio.create_task(countdown())
    try:
        line = await asyncio.wait_for(
            loop.run_in_executor(None, sys.stdin.readline),
            timeout=timeout_seconds,
        )
        decision = (line or "n").strip().lower() or "n"
    except TimeoutError:
        decision = "timeout"
    finally:
        countdown_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await countdown_task

    if decision == "timeout":
        return
    await queue.put(decision)
