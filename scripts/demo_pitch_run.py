#!/usr/bin/env python3
"""Phase 4: 3-minute pitch-day all-in-one demo runner (issue #75).

Narrative for VIP judging (Chief of Air Force / Chief Defence Scientist):

  Scene 1 — Air Hero (S2): OSINT 3 vs radar 1 → Amber → kinetic fast-reject
             → approve CUE_AND_IDENTIFY → field Ack < 3 s
  Scene 2 — Maritime Hero (S3): Dual-SAR ingress → dead-reckoning + Lead POI
             → APPROACH_PATROL → Ack
  Scene 3 — Quantitative Proof (Slide 11): gate <50 ms, 0 unauthorized,
             100% OCSF audit integrity

Usage:
  uv run python scripts/demo_pitch_run.py            # auto, in-process Core
  uv run python scripts/demo_pitch_run.py --step     # interactive pauses
  uv run python scripts/demo_pitch_run.py --auto     # explicit auto (default)
  ./scripts/demo_pitch_run.sh

Target wall time: < 15 s in --auto mode (in-process).
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from app import c2_server
from fastapi.testclient import TestClient
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

# Sibling script on PYTHONPATH (repo root); same pattern as tests → demo_tamper.
from scripts.benchmark import (
    GATE_P95_MS,
    ROUNDTRIP_S,
    UNAUTHORIZED_MAX,
    bench_audit_integrity,
    bench_gate_latency,
    bench_picture_to_ack,
    bench_unauthorized,
)

AUTO_TARGET_S = 15.0
ACK_TARGET_S = 3.0
GEOFENCE_COORDS = (1.2310, 103.8510)  # demo_no_go
KINETIC_INTENT = "ENGAGE_KINETIC"


class _HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...
    def get(self, url: str, **kwargs: Any) -> Any: ...


class PitchRunner:
    """Drive the three pitch scenes against in-process or live Core."""

    def __init__(
        self,
        *,
        client: _HttpClient,
        console: Console,
        step: bool,
        quiet: bool = False,
    ) -> None:
        self.client = client
        self.console = console
        self.step = step
        self.quiet = quiet
        self._failures = 0

    def _pause(self, label: str) -> None:
        if not self.step or self.quiet:
            return
        self.console.print(f"[dim]── press Enter for {label} ──[/dim]")
        with contextlib.suppress(EOFError):
            input()

    def _ok(self, msg: str) -> None:
        self.console.print(f"  [bold green]✓[/bold green] {msg}")

    def _fail(self, msg: str) -> None:
        self._failures += 1
        self.console.print(f"  [bold red]✗ FAIL[/bold red] {msg}")

    def _info(self, msg: str) -> None:
        self.console.print(f"  {msg}")

    def _reset(self) -> None:
        self.client.post("/api/admin/reset")

    def _print_warning_picture(self, finding: dict[str, Any] | None) -> None:
        if not finding:
            self._info("[dim](no finding)[/dim]")
            return
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("k", style="bold cyan")
        table.add_column("v")
        if finding.get("amber_alert"):
            table.add_row("Amber", f"[bold yellow]{finding['amber_alert']}[/bold yellow]")
        if finding.get("threat_class"):
            table.add_row("Threat", str(finding["threat_class"]))
        breakdown = finding.get("source_breakdown") or {}
        social = breakdown.get("social") or {}
        radar = breakdown.get("radar") or {}
        if social.get("claimed_count") is not None and radar.get("contact_count") is not None:
            table.add_row(
                "Count claim",
                f"[yellow]OSINT={social['claimed_count']}[/yellow] vs "
                f"[cyan]radar={radar['contact_count']}[/cyan]",
            )
        kin = breakdown.get("kinematics") or {}
        if kin:
            radius = kin.get("uncertainty_radius_m", kin.get("radius_m", "?"))
            table.add_row(
                "Kinematics",
                f"Δt={kin.get('dt_sec', '?')}s  envelope={radius} m  "
                f"in_envelope={kin.get('radar_in_envelope')}",
            )
        mismatch = finding.get("mismatch_m")
        if mismatch is not None:
            table.add_row("Mismatch", f"{mismatch:.0f} m")
        summary = finding.get("picture_summary") or finding.get("summary") or ""
        self.console.print(
            Panel(
                Group(summary, table) if summary else table,
                title="WARNING PICTURE",
                border_style="red",
            )
        )

    def _print_poi(self, coa: dict[str, Any]) -> None:
        meta = coa.get("metadata") or {}
        poi = meta.get("poi")
        if not isinstance(poi, dict):
            self._info("[dim](no Lead POI on COA)[/dim]")
            return
        coords = coa.get("target_coordinates")
        self._ok(
            f"Lead POI method={poi.get('method')}  "
            f"ETA={poi.get('eta_sec')}s  waypoint={coords}"
        )

    def _closed_loop(
        self,
        *,
        scenario_id: str,
        unit_id: str,
        expect_intent: str,
        operator_id: str = "pitch-judge",
        assert_finding: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        t0 = time.perf_counter()
        proposed = self.client.post(
            "/api/gate/proposals",
            json={"scenario_id": scenario_id, "unit_id": unit_id},
        )
        if proposed.status_code != 200:
            self._fail(f"propose HTTP {proposed.status_code}: {proposed.text[:200]}")
            return
        body = proposed.json()
        if body.get("status") != "QUEUED":
            self._fail(f"expected QUEUED, got {body.get('status')}: {body.get('reason')}")
            return
        coa = body["coa"]
        finding = body.get("finding") or {}
        intent = coa.get("intent")
        if intent != expect_intent:
            self._fail(f"intent={intent!r} (expected {expect_intent})")
        else:
            self._ok(f"QUEUED intent={intent}  coa_id={coa.get('coa_id')}")
        self._print_warning_picture(finding if isinstance(finding, dict) else None)
        if assert_finding and isinstance(finding, dict):
            assert_finding(finding)
        self._print_poi(coa)
        self._pause("operator approve")

        coa_id = coa["coa_id"]
        approved = self.client.post(
            "/api/gate/approve",
            json={"coa_id": coa_id, "decision": "y", "operator_id": operator_id},
        )
        if approved.status_code != 200 or approved.json().get("status") != "APPROVED":
            self._fail(f"approve failed: {approved.text[:200]}")
            return
        digest = (approved.json().get("token") or {}).get("digest", "")
        self._ok(f"APPROVED DecisionToken digest={digest[:16]}…")

        inbox = self.client.get("/api/recipient/inbox", params={"unit_id": unit_id})
        if inbox.status_code != 200 or inbox.json().get("count", 0) < 1:
            self._fail("inbox empty after approve")
            return
        self._ok(f"Recipient inbox pending={inbox.json()['count']}")

        ack = self.client.post(
            "/api/recipient/ack",
            json={
                "coa_id": coa_id,
                "unit_id": unit_id,
                "message": f"pitch {scenario_id} field ack",
            },
        )
        elapsed = time.perf_counter() - t0
        if ack.status_code != 200 or ack.json().get("status") != "ACKED":
            self._fail(f"ack failed: {ack.text[:200]}")
            return
        audit_hash = ack.json().get("audit_hash", "")
        if elapsed < ACK_TARGET_S:
            self._ok(f"Field Ack sealed in {elapsed:.3f}s  (target < {ACK_TARGET_S:g}s)")
        else:
            self._fail(f"Ack {elapsed:.3f}s exceeded {ACK_TARGET_S:g}s target")
        self._info(f"[dim]audit_hash={audit_hash}[/dim]")

    # ------------------------------------------------------------------
    # Scenes
    # ------------------------------------------------------------------

    def scene1_air_hero(self) -> None:
        self.console.print(Rule("[bold]Scene 1 — Air Hero (S2)[/bold]"))
        self.console.print(
            "[dim]Civilian OSINT claims 3 drones vs radar 1 track → Amber → "
            "non-kinetic CUE_AND_IDENTIFY (not kinetic overkill)[/dim]\n"
        )
        self._reset()
        self._pause("S2 propose")

        def _assert_s2(finding: dict[str, Any]) -> None:
            if finding.get("amber_alert") != "COUNT_AND_BEARING_MISMATCH":
                self._fail(f"amber={finding.get('amber_alert')!r}")
            else:
                self._ok("Amber COUNT_AND_BEARING_MISMATCH")
            bd = finding.get("source_breakdown") or {}
            social = (bd.get("social") or {}).get("claimed_count")
            radar = (bd.get("radar") or {}).get("contact_count")
            if social == 3 and radar == 1:
                self._ok(f"Discrepancy OSINT={social} vs radar={radar}")
            else:
                self._fail(f"count claim social={social} radar={radar}")

        self._closed_loop(
            scenario_id="S2",
            unit_id="CUE-NODE-01",
            expect_intent="CUE_AND_IDENTIFY",
            assert_finding=_assert_s2,
        )
        self._pause("kinetic overkill probe")

        # Deterministic interlock: kinetic tasking into no-go → REJECTED_FAST
        kinetic = self.client.post(
            "/api/gate/proposals",
            json={
                "coa": {
                    "target_entity_id": "phantom-swarm",
                    "target_coordinates": list(GEOFENCE_COORDS),
                    "intent": KINETIC_INTENT,
                    "tier": 0,
                    "confidence": 0.99,
                    "corroborating_sources": ["PANIC_SOCIAL"],
                    "raw_input_digest": "k" * 64,
                    "speed_kt": 5.0,
                },
                "unit_id": "SAM-BATTERY-01",
            },
        )
        if kinetic.status_code != 200:
            self._fail(f"kinetic probe HTTP {kinetic.status_code}")
            return
        kbody = kinetic.json()
        if kbody.get("status") == "REJECTED_FAST":
            self._ok(
                f"Kinetic overkill {KINETIC_INTENT} → REJECTED_FAST "
                f"({kbody.get('reason')})"
            )
        else:
            self._fail(f"kinetic probe status={kbody.get('status')} (expected REJECTED_FAST)")

    def scene2_maritime_hero(self) -> None:
        self.console.print(Rule("[bold]Scene 2 — Maritime Hero (S3)[/bold]"))
        self.console.print(
            "[dim]Dual-SAR (GLINT macro x SIA micro) → dark vessel → "
            "dead-reckoning + Lead POI → APPROACH_PATROL[/dim]\n"
        )
        self._reset()
        self._pause("Dual-SAR ingress")

        ingress = self.client.post(
            "/api/ingress/candidate-event",
            json={"dual_sar": True},
        )
        if ingress.status_code != 200:
            self._fail(f"dual_sar ingress HTTP {ingress.status_code}: {ingress.text[:200]}")
            return
        ibody = ingress.json()
        n_obs = ibody.get("count") or len(ibody.get("observations") or [])
        source = ibody.get("source") or "dual_sar"
        self._ok(f"Dual-SAR ingress source={source}  observations={n_obs}")

        self._pause("S3 propose")

        def _assert_s3(finding: dict[str, Any]) -> None:
            amber = finding.get("amber_alert")
            if amber == "SAR_DARK_CLUSTER_VS_AIS_SILENCE":
                self._ok(f"Amber {amber}")
            else:
                self._fail(f"amber={amber!r}")
            kin = (finding.get("source_breakdown") or {}).get("kinematics") or {}
            if kin.get("radar_in_envelope") is True or kin.get("dt_sec") is not None:
                radius = kin.get("uncertainty_radius_m", kin.get("radius_m"))
                self._ok(
                    f"Dead-reckoning Δt={kin.get('dt_sec')}s  envelope={radius} m"
                )
            else:
                self._fail("missing kinematics breakdown")

        self._closed_loop(
            scenario_id="S3",
            unit_id="USV-02",
            expect_intent="APPROACH_PATROL",
            assert_finding=_assert_s3,
        )

    def scene3_slide11(self) -> None:
        self.console.print(Rule("[bold]Scene 3 — Quantitative Proof (Slide 11)[/bold]"))
        self.console.print(
            "[dim]Gate latency · unauthorized = 0 · OCSF integrity · picture→Ack[/dim]\n"
        )
        self._pause("run scorecard")

        # Keep pitch wall-clock under 15s: skip flood stress, modest sample count.
        results = []
        results.extend(bench_gate_latency(n=40))
        results.append(bench_unauthorized())
        results.append(bench_picture_to_ack())
        results.append(bench_audit_integrity())

        table = Table(title="Slide 11 Scorecard", show_lines=False)
        table.add_column("Metric", style="bold")
        table.add_column("Measured")
        table.add_column("Target")
        table.add_column("Status")

        for m in results:
            status = "[bold green]PASS[/bold green]" if m.passed else "[bold red]FAIL[/bold red]"
            if not m.passed:
                self._failures += 1
            if isinstance(m.value, float):
                shown = f"{m.value:g} {m.unit}".strip()
            else:
                shown = f"{m.value} {m.unit}".strip()
            table.add_row(m.name, shown, m.target, status)

        self.console.print(table)
        self._info(
            f"[dim]Targets: gate p95 < {GATE_P95_MS:g} ms · "
            f"unauthorized = {UNAUTHORIZED_MAX} · "
            f"picture→Ack < {ROUNDTRIP_S:g} s · audit = 100%[/dim]"
        )

    def run_all(self) -> int:
        started = time.perf_counter()
        self.console.print(
            Panel.fit(
                "[bold]NexusGate[/bold] — Pitch-Day All-in-One Runner\n"
                "[dim]issue #75 · 3 scenes · auto < 15 s[/dim]",
                border_style="bright_blue",
            )
        )
        self.scene1_air_hero()
        self.console.print()
        self.scene2_maritime_hero()
        self.console.print()
        self.scene3_slide11()

        elapsed = time.perf_counter() - started
        self.console.print()
        self.console.print(Rule())
        if self._failures:
            self.console.print(
                f"[bold red]RESULT: {self._failures} failure(s)[/bold red]  "
                f"wall={elapsed:.2f}s"
            )
            return 1
        mode = "step" if self.step else "auto"
        budget = ""
        if not self.step:
            if elapsed < AUTO_TARGET_S:
                budget = f"  [green](under {AUTO_TARGET_S:g}s auto budget)[/green]"
            else:
                budget = f"  [yellow](WARN: exceeded {AUTO_TARGET_S:g}s auto budget)[/yellow]"
        self.console.print(
            f"[bold green]RESULT: ALL SCENES PASSED[/bold green]  "
            f"mode={mode}  wall={elapsed:.2f}s{budget}"
        )
        return 0


def _run_in_process(*, step: bool, quiet: bool, no_color: bool) -> int:
    console = Console(
        force_terminal=not no_color and not quiet,
        no_color=no_color or quiet,
        quiet=quiet,
    )
    with tempfile.TemporaryDirectory(prefix="nexusgate-pitch-") as tmp:
        audit_path = Path(tmp) / "gate.jsonl"
        c2_server._runtime = c2_server.C2Runtime(audit_path=audit_path)
        with TestClient(c2_server.app) as client:
            runner = PitchRunner(client=client, console=console, step=step, quiet=quiet)
            return runner.run_all()


def _run_against_url(*, base_url: str, step: bool, quiet: bool, no_color: bool) -> int:
    import httpx

    console = Console(
        force_terminal=not no_color and not quiet,
        no_color=no_color or quiet,
        quiet=quiet,
    )
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=15.0) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.HTTPError as exc:
            console.print(f"[red]FAIL: cannot reach Core at {base_url}: {exc}[/red]")
            return 2
        runner = PitchRunner(client=client, console=console, step=step, quiet=quiet)
        return runner.run_all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pitch-day all-in-one demo runner (issue #75)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scenes:\n"
            "  1  S2 Air Hero — Amber + kinetic REJECTED_FAST + CUE Ack\n"
            "  2  S3 Maritime — Dual-SAR + Lead POI + APPROACH_PATROL\n"
            "  3  Slide 11 scorecard — gate / unauthorized / audit\n"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--auto",
        action="store_true",
        default=True,
        help="Fully automated narrative (default)",
    )
    mode.add_argument(
        "--step",
        action="store_true",
        help="Interactive pause between beats (Enter to continue)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Live Core origin (default: in-process TestClient, no server needed)",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI / Rich color")
    parser.add_argument("--quiet", action="store_true", help="Minimal output (tests)")
    args = parser.parse_args(argv)

    step = bool(args.step)
    if args.base_url:
        return _run_against_url(
            base_url=args.base_url,
            step=step,
            quiet=args.quiet,
            no_color=args.no_color,
        )
    return _run_in_process(step=step, quiet=args.quiet, no_color=args.no_color)


if __name__ == "__main__":
    sys.exit(main())
