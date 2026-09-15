"""Rich TUI operator console with countdown HITL."""

from __future__ import annotations

import asyncio
import contextlib
import sys

from rich.console import Console
from rich.panel import Panel

console = Console()


async def prompt_operator_decision(
    *,
    message: str,
    asset_label: str,
    timeout_seconds: float,
    queue: asyncio.Queue[str],
    auto_decision: str | None = None,
) -> None:
    """
    Push operator decision into queue.
    If auto_decision is set (tests/demo noninteractive), enqueue immediately.
    Otherwise read stdin with a countdown display.
    """
    if auto_decision is not None:
        console.print(Panel(f"{message}\nAuto decision: {auto_decision}", title="HITL"))
        await queue.put(auto_decision)
        return

    remaining = timeout_seconds
    console.print(
        Panel(
            f"[bold red]Mismatch detected![/bold red]\n"
            f"{message}\n\n"
            f"Dispatch [cyan]{asset_label}[/cyan]? "
            f"Remaining {remaining:.1f}s  [y/n]",
            title="Operator Gate",
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
