#!/usr/bin/env python3
"""19-event temporal streamer (T-60s -> T-00s) for PS 04 temporal alignment demos.

Feeds the ontology incrementally (not one-shot build_events()), runs detect each
step, and prints Warning Picture / HITL / tasking cues in the final band.

Usage:
  uv run python scripts/stream_events.py
  uv run python scripts/stream_events.py --scenario S2 --interval 0.25
  uv run python scripts/stream_events.py --mode print          # JSONL to stdout
  uv run python scripts/stream_events.py --fast                # no sleep
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from typing import Any

from app.adapters.southbound_sensor import normalize_sensor_event
from app.scenarios.base import Finding, get_scenario
from app.scenarios.temporal import StreamStep, build_stream_timeline
from core.ontology import SpatialEntityGraph


def _finding_brief(finding: Finding | None) -> dict[str, Any] | None:
    if finding is None:
        return None
    return {
        "amber_alert": finding.amber_alert,
        "threat_class": finding.threat_class,
        "mismatch_m": round(finding.mismatch_m, 1),
        "warning_minutes_est": finding.warning_minutes_est,
        "picture_summary": finding.picture_summary,
    }


def _play_local(
    steps: list[StreamStep],
    *,
    scenario_id: str,
    interval: float,
    show_coa: bool,
) -> int:
    scenario = get_scenario(scenario_id)
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    amber_step: int | None = None
    last_finding: Finding | None = None

    print("=" * 72)
    print(f"  Temporal stream - scenario={scenario_id}  steps={len(steps)}")
    print("  T-60s -> T-00s incremental ontology ingest")
    print("=" * 72)

    for step in steps:
        if step.events:
            obs = [normalize_sensor_event(e) for e in step.events]
            graph.ingest_many(obs)

        finding = scenario.detect(graph)
        if finding is not None and amber_step is None:
            amber_step = step.step
        last_finding = finding

        mods = sorted({str(e.get("modality", "?")) for e in step.events}) if step.events else []
        amber = finding.amber_alert if finding else "-"
        print(
            f"  [{step.step:02d}/19] T-{step.t_minus_s:02d}s  "
            f"band={step.band:<22}  +{len(step.events)} evt  "
            f"mods={mods or '-'}  amber={amber}"
        )
        print(f"           {step.label}")

        if step.band == "warning_tasking":
            if step.label == "warning_picture_ready" and finding is not None:
                print("           --- WARNING PICTURE ---")
                print(f"           {finding.picture_summary}")
            elif step.label == "hitl_gate_countdown":
                print("           HITL cue: LatencyBoundedGate countdown (Default=Deny)")
            elif step.label == "tasking_proposal_cue" and finding is not None and show_coa:
                coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
                print(f"           COA cue: intent={coa.intent} coa_id={coa.coa_id}")
            elif step.label == "recipient_ack_cue":
                print("           Recipient cue: approve -> inbox -> signed Ack")

        if interval > 0:
            time.sleep(interval)

    print("-" * 72)
    print(f"  observations={len(graph.observations)}  tracks={len(graph.all_tracks())}")
    if amber_step is not None:
        print(f"  first Amber at step {amber_step:02d}  ({_finding_brief(last_finding)})")
    else:
        print("  Amber: not raised (unexpected for S2 full timeline)")
        return 1
    if scenario_id.upper() == "S2" and amber_step is not None and amber_step < 11:
        print("  FAIL: Amber fired before band 11-15")
        return 1
    print("  RESULT: timeline complete")
    print("=" * 72)
    return 0


def _play_print(steps: list[StreamStep], *, scenario_id: str) -> int:
    for step in steps:
        record = {
            "scenario_id": scenario_id,
            "step": step.step,
            "t_minus_s": step.t_minus_s,
            "band": step.band,
            "label": step.label,
            "events": step.events,
        }
        print(json.dumps(record, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Play 19-step T-60s->T-00s sensor timeline into the ontology.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Bands:\n"
            "  01-05  early recon / social rumors / sparse radar\n"
            "  06-10  coastal radar lock + optical slew\n"
            "  11-15  EO blur + Amber contradiction (S2)\n"
            "  16-19  Warning Picture -> HITL -> tasking/ack cue\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        default="S2",
        help="Scenario id (default S2 hero timeline; S1/S3 spread build_events)",
    )
    parser.add_argument(
        "--mode",
        choices=("local", "print"),
        default="local",
        help="local=ingest+detect; print=JSONL steps to stdout",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.15,
        help="Seconds between steps in local mode (default 0.15)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="No sleep between steps",
    )
    parser.add_argument(
        "--no-coa",
        action="store_true",
        help="Skip building COA in the tasking-cue step",
    )
    parser.add_argument(
        "--t0",
        default=None,
        help="ISO8601 anchor for T-00 (default: now UTC)",
    )
    args = parser.parse_args(argv)

    t0 = datetime.fromisoformat(args.t0.replace("Z", "+00:00")) if args.t0 else datetime.now(UTC)
    steps = build_stream_timeline(args.scenario, t0=t0)
    if len(steps) != 19:
        print(f"error: expected 19 steps, got {len(steps)}", file=sys.stderr)
        return 2

    interval = 0.0 if args.fast else max(0.0, args.interval)
    if args.mode == "print":
        return _play_print(steps, scenario_id=args.scenario)
    return _play_local(
        steps,
        scenario_id=args.scenario,
        interval=interval,
        show_coa=not args.no_coa,
    )


if __name__ == "__main__":
    sys.exit(main())
