"""SDTH C2 cycle: defense scenario → ontology → COA → HITL → effector."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from core.audit import AuditLogger
from core.coa import GateVerdict
from core.gate import LatencyBoundedGate
from core.ontology import SpatialEntityGraph
from core.policy import TieredPolicy
from core.proxy import EffectorProxy
from core.stub import StubEffector
from rich.console import Console

from app.adapters.clearbot_rest import ClearbotRestAdapter
from app.adapters.southbound_sensor import normalize_sensor_event
from app.scenarios.base import get_scenario, list_scenario_ids
from app.ui.console import prompt_operator_decision

console = Console()

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
DEFAULT_POLICY = APP_DIR / "config" / "maritime_defense_policy.yaml"


async def run_c2_cycle(
    *,
    scenario_id: str = "S1",
    policy_path: Path = DEFAULT_POLICY,
    clearbot_base_url: str | None = None,
    audit_path: Path | None = None,
    auto_decision: str | None = None,
    use_stub: bool = False,
    gate_timeout_sec: float | None = None,
) -> GateVerdict:
    scenario = get_scenario(scenario_id)
    policy = TieredPolicy.from_yaml(policy_path)
    timeout = gate_timeout_sec or policy.default_timeout_seconds

    audit = AuditLogger(audit_path or ROOT / ".audit" / "gate.jsonl")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)

    events = scenario.build_events()
    observations = [normalize_sensor_event(e) for e in events]
    graph.ingest_many(observations)
    audit.append(
        "observations_ingested",
        "Info",
        {"count": len(observations), "scenario": scenario.id},
    )

    finding = scenario.detect(graph)
    if finding is None:
        console.print(f"[yellow]No warning picture for {scenario.id}; nothing to task.[/yellow]")
        audit.append("no_finding", "Info", {"scenario": scenario.id})
        return GateVerdict.REJECTED_FAST

    coa = scenario.build_coa(graph, finding, timeout_seconds=timeout)
    coa = policy.apply_defaults(coa)
    audit.append(
        "coa_proposed",
        "Medium",
        {
            "scenario": scenario.id,
            "coa_id": coa.coa_id,
            "tier": coa.tier.value,
            "intent": coa.intent,
            "confidence": coa.confidence,
            "sources": coa.corroborating_sources,
            "raw_input_digest": coa.raw_input_digest,
            "picture_summary": finding.picture_summary,
            "adversarial_hypothesis": finding.adversarial_hypothesis,
        },
    )

    gate = LatencyBoundedGate(timeout_sec=timeout, interlock=policy.interlock)
    queue: asyncio.Queue[str] = asyncio.Queue()
    prompt_task = asyncio.create_task(
        prompt_operator_decision(
            message=finding.picture_summary,
            asset_label=scenario.asset_label,
            timeout_seconds=timeout,
            queue=queue,
            auto_decision=auto_decision,
            finding=finding,
            scenario=scenario,
            coa=coa,
        )
    )

    verdict, token = await gate.evaluate(coa, queue)
    await prompt_task
    audit.append(
        "gate_decision",
        "High",
        {
            "coa_id": coa.coa_id,
            "verdict": verdict.value,
            "token": token.model_dump(mode="json"),
            "scenario": scenario.id,
        },
    )
    console.print(f"[bold]Gate verdict:[/bold] {verdict.value}")

    if use_stub:
        effector: EffectorProxy = StubEffector()
    else:
        base = clearbot_base_url or os.environ.get("CLEARBOT_BASE_URL", "http://127.0.0.1:8000")
        effector = ClearbotRestAdapter(endpoint=base)

    if verdict == GateVerdict.APPROVED:
        receipt = await effector.dispatch(coa)
        policy.interlock.register_active(coa)
        audit.append("dispatch", "High", {"receipt": receipt.model_dump(mode="json")})
        console.print(f"[green]Dispatched[/green]: {receipt.status} · {coa.intent}")
        if not use_stub and hasattr(effector, "kinematics"):
            pos = (effector.kinematics.latitude, effector.kinematics.longitude)
            console.print(f"Sim position after path: {pos}")
    elif verdict == GateVerdict.TIMED_OUT_FALLBACK:
        receipt = await effector.emergency_station_keep()
        audit.append("station_keep", "High", {"receipt": receipt.model_dump(mode="json")})
        console.print(f"[yellow]Timeout → station-keep[/yellow]: {receipt.message}")
    else:
        console.print(f"[red]No dispatch[/red] ({verdict.value})")

    return verdict


def cli_main() -> None:
    parser = argparse.ArgumentParser(description="SDTH Nexus C2 — defense scenarios")
    parser.add_argument(
        "--scenario",
        default=os.environ.get("SCENARIO", "S1"),
        choices=list_scenario_ids(),
        help="Defense scenario id (default S1)",
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--clearbot-url", default=os.environ.get("CLEARBOT_BASE_URL"))
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument("--yes", action="store_true", help="Auto-approve HITL")
    parser.add_argument("--no", action="store_true", help="Auto-deny HITL")
    parser.add_argument("--stub", action="store_true", help="Use StubEffector (no HTTP)")
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()

    auto = None
    if args.yes:
        auto = "y"
    elif args.no:
        auto = "n"

    verdict = asyncio.run(
        run_c2_cycle(
            scenario_id=args.scenario,
            policy_path=args.policy,
            clearbot_base_url=args.clearbot_url,
            audit_path=args.audit,
            auto_decision=auto,
            use_stub=args.stub,
            gate_timeout_sec=args.timeout,
        )
    )
    raise SystemExit(
        0
        if verdict
        in {GateVerdict.APPROVED, GateVerdict.TIMED_OUT_FALLBACK, GateVerdict.REJECTED_OPERATOR}
        else 1
    )


if __name__ == "__main__":
    cli_main()
