"""SDTH C2 cycle: scenario → ontology → agent COA → HITL gate → effector."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from rich.console import Console

from app.adapters.clearbot_rest import ClearbotRestAdapter
from app.adapters.southbound_sensor import normalize_sensor_event
from app.agent import find_first_contradiction_coa
from app.scenarios.strait_incident import build_strait_incident
from app.ui.console import prompt_operator_decision
from core.audit import AuditLogger
from core.coa import GateVerdict
from core.gate import LatencyBoundedGate
from core.ontology import SpatialEntityGraph
from core.policy import TieredPolicy
from core.stub import StubEffector

console = Console()

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "maritime_defense_policy.yaml"


async def run_c2_cycle(
    *,
    policy_path: Path = DEFAULT_POLICY,
    clearbot_base_url: str | None = None,
    audit_path: Path | None = None,
    auto_decision: str | None = None,
    use_stub: bool = False,
    gate_timeout_sec: float | None = None,
) -> GateVerdict:
    policy = TieredPolicy.from_yaml(policy_path)
    agent_cfg = policy.raw.get("agent", {})
    timeout = gate_timeout_sec or policy.default_timeout_seconds

    audit = AuditLogger(audit_path or ROOT / ".audit" / "gate.jsonl")
    graph = SpatialEntityGraph()

    events = build_strait_incident()
    observations = [normalize_sensor_event(e) for e in events]
    graph.ingest_many(observations)
    audit.append("observations_ingested", "Info", {"count": len(observations)})

    result = find_first_contradiction_coa(
        graph,
        mismatch_m_threshold=float(agent_cfg.get("position_mismatch_m_threshold", 500.0)),
        spoof_speed_kt_threshold=float(agent_cfg.get("spoof_speed_kt_threshold", 1.0)),
        approach_speed_kt_min=float(agent_cfg.get("approach_speed_kt_min", 10.0)),
        timeout_seconds=timeout,
    )
    if result is None:
        console.print("[yellow]No contradiction found; nothing to task.[/yellow]")
        audit.append("no_contradiction", "Info", {})
        return GateVerdict.REJECTED_FAST

    finding, coa = result
    coa = policy.apply_defaults(coa)
    console.print(f"[bold]Finding:[/bold] {finding.message}")
    console.print(
        f"COA {coa.coa_id[:8]}… tier={coa.tier.name} "
        f"target={coa.target_coordinates} conf={coa.confidence:.2f}"
    )
    audit.append(
        "coa_proposed",
        "Medium",
        {
            "coa_id": coa.coa_id,
            "tier": coa.tier.value,
            "confidence": coa.confidence,
            "sources": coa.corroborating_sources,
            "raw_input_digest": coa.raw_input_digest,
        },
    )

    gate = LatencyBoundedGate(timeout_sec=timeout, interlock=policy.interlock)
    queue: asyncio.Queue[str] = asyncio.Queue()
    prompt_task = asyncio.create_task(
        prompt_operator_decision(
            message=finding.message,
            asset_label="Clearbot USV-01",
            timeout_seconds=timeout,
            queue=queue,
            auto_decision=auto_decision,
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
        },
    )
    console.print(f"[bold]Gate verdict:[/bold] {verdict.value}")

    if use_stub:
        effector = StubEffector()
    else:
        base = clearbot_base_url or os.environ.get("CLEARBOT_BASE_URL", "http://127.0.0.1:8000")
        effector = ClearbotRestAdapter(endpoint=base)

    if verdict == GateVerdict.APPROVED:
        receipt = await effector.dispatch(coa)
        policy.interlock.register_active(coa)
        audit.append("dispatch", "High", {"receipt": receipt.model_dump(mode="json")})
        console.print(f"[green]Dispatched[/green]: {receipt.status} {receipt.message}")
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
    parser = argparse.ArgumentParser(description="SDTH Nexus C2 demo cycle")
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
            policy_path=args.policy,
            clearbot_base_url=args.clearbot_url,
            audit_path=args.audit,
            auto_decision=auto,
            use_stub=args.stub,
            gate_timeout_sec=args.timeout,
        )
    )
    raise SystemExit(0 if verdict in {GateVerdict.APPROVED, GateVerdict.TIMED_OUT_FALLBACK, GateVerdict.REJECTED_OPERATOR} else 1)


if __name__ == "__main__":
    cli_main()
