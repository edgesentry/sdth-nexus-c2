#!/usr/bin/env python3
"""Pitch-4: UI-less Picture→Tasking demo (Warning Picture → Ack → audit).

One-shot closed loop against `sdth-c2-server` (local or Cloudflare):

  1. Screen 1 — POST /api/gate/proposals  (S2 Warning Picture)
  2. Screen 1 — POST /api/gate/approve
  3. Screen 2 — GET  /api/recipient/inbox
  4. Screen 2 — POST /api/recipient/ack
  5. Audit    — GET  /api/audit/trail     (assert recipient_ack sealed)

Target: picture-to-ack wall time < 3.0 s when Core is local.

Usage:
  # Terminal A
  uv run sdth-c2-server

  # Terminal B (or one-shot via scripts/picture_to_tasking.sh)
  uv run python scripts/picture_to_tasking.py
  C2_BASE_URL=https://your-c2.example.com uv run python scripts/picture_to_tasking.py

Env:
  C2_BASE_URL / BASE_URL  Core origin (default http://127.0.0.1:8080)
  C2_API_TOKEN            Optional Bearer for Cloudflare Worker front door (#38)
  UNIT_ID                 Recipient unit (default CUE-NODE-01)
  SCENARIO                Scenario id (default S2)
  RASPI_ACK_BLINK         Optional: blink GPIO on Screen 2 after Ack (#20)

Optional live LLM (issue #32): pass --interpret so proposals use POST interpret:true.
Core must be started with LLM_BASE_URL pointing at LiteLLM; otherwise heuristic is used.
Probabilistic proposes; the gate still disposes (never skip HITL)."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import time
from typing import Any

import httpx
from app.adapters.raspi_hardware import blink_on_ack_sync

ROUNDTRIP_TARGET_S = 3.0
DEFAULT_BASE = "http://127.0.0.1:8080"
DEFAULT_UNIT = "CUE-NODE-01"
DEFAULT_SCENARIO = "S2_osint_swarm"


def _base_url(cli: str | None) -> str:
    return (
        (cli or "").strip()
        or os.environ.get("C2_BASE_URL", "").strip()
        or os.environ.get("BASE_URL", "").strip()
        or DEFAULT_BASE
    ).rstrip("/")


def _client_headers() -> dict[str, str]:
    """Bearer for Cloudflare Worker auth; empty for local sdth-c2-server."""
    token = os.environ.get("C2_API_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _print_hop(step: int, title: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"\n[{step}] {title}{suffix}")


def _print_warning_picture(finding: dict[str, Any] | None) -> None:
    if not finding:
        print("  (no finding payload)")
        return
    print("  ┌─ WARNING PICTURE ─────────────────────────")
    print(f"  │ amber      : {finding.get('amber_alert')}")
    print(f"  │ threat     : {finding.get('threat_class')}")
    print(f"  │ scenario   : {finding.get('scenario_id')}")
    mismatch = finding.get("mismatch_m")
    if mismatch is not None:
        print(f"  │ mismatch_m : {mismatch}")
    summary = finding.get("picture_summary") or finding.get("summary")
    if summary:
        print(f"  │ summary    : {summary}")
    breakdown = finding.get("source_breakdown") or {}
    if breakdown:
        for src, payload in breakdown.items():
            print(f"  │ source[{src}]: {payload}")
    print("  └────────────────────────────────────────────")


def _coa_id_in_record(rec: dict[str, Any], coa_id: str) -> bool:
    meta = rec.get("metadata") or {}
    if not isinstance(meta, dict):
        return False
    if meta.get("coa_id") == coa_id:
        return True
    coa = meta.get("coa")
    if isinstance(coa, dict) and coa.get("coa_id") == coa_id:
        return True
    token = meta.get("token")
    return isinstance(token, dict) and token.get("coa_id") == coa_id


def _verify_ack_in_trail(trail: dict[str, Any], coa_id: str) -> tuple[bool, str]:
    """Confirm this coa's recipient_ack is sealed on a contiguous hash segment.

    Full-trail genesis checks can fail when an old ``gate.jsonl`` was truncated
    at the head (orphan ``prev_hash`` on record[0]). In that case we still
    require the handshake segment for *this* ``coa_id`` to link correctly.
    """
    records = trail.get("records") or []
    if not records:
        return False, "audit trail empty"

    related = [i for i, rec in enumerate(records) if _coa_id_in_record(rec, coa_id)]
    ack_hits = sum(1 for i in related if records[i].get("activity_name") == "recipient_ack")
    if ack_hits < 1:
        return False, f"no recipient_ack for coa_id={coa_id} in audit trail"

    # Prefer a clean full chain from genesis.
    prev = "0" * 64
    full_ok = True
    for rec in records:
        if rec.get("prev_hash") != prev:
            full_ok = False
            break
        prev = rec.get("hash") or ""
    if full_ok:
        return True, f"recipient_ack sealed ({ack_hits} record(s)); chain ok ({len(records)} links)"

    # Session segment: consecutive links covering this coa's events.
    start, end = min(related), max(related)
    for i in range(start, end + 1):
        expected = "0" * 64 if i == 0 else records[i - 1].get("hash")
        if records[i].get("prev_hash") != expected:
            return False, f"broken hash chain at record[{i}] (session segment)"
    return (
        True,
        f"recipient_ack sealed ({ack_hits} record(s)); "
        f"session chain ok (records[{start}:{end + 1}]; older trail has a break)",
    )


def run_demo(
    *,
    base_url: str,
    scenario_id: str,
    unit_id: str,
    operator_id: str,
    timeout_s: float,
    require_roundtrip: bool,
    interpret: bool = False,
    force_heuristic: bool = False,
) -> int:
    print("=" * 60)
    print("NexusGate — Picture→Tasking demo (no UI)")
    print(f"  Core URL   : {base_url}")
    print(f"  Scenario   : {scenario_id}")
    print(f"  Unit       : {unit_id}")
    print(f"  Auth       : {'Bearer C2_API_TOKEN' if _client_headers() else 'none (local)'}")
    print(f"  Roundtrip  : < {ROUNDTRIP_TARGET_S:g} s (local target)")
    print("=" * 60)

    with httpx.Client(base_url=base_url, timeout=timeout_s, headers=_client_headers()) as client:
        # Optional reset so re-runs are clean when talking to a sticky Core.
        with contextlib.suppress(httpx.HTTPError):
            client.post("/api/admin/reset")

        _print_hop(1, "Screen 1 — propose COA (Warning Picture)")
        t_picture = time.perf_counter()
        proposal: dict[str, Any] = {"scenario_id": scenario_id, "unit_id": unit_id}
        if interpret:
            proposal["interpret"] = True
            if force_heuristic:
                proposal["force_heuristic"] = True
        proposed = client.post("/api/gate/proposals", json=proposal)
        proposed.raise_for_status()
        body = proposed.json()
        status = body.get("status")
        if status != "QUEUED":
            print(f"  FAIL: expected QUEUED, got {status}: {body.get('reason')}")
            return 1
        coa = body["coa"]
        coa_id = coa["coa_id"]
        finding = body.get("finding")
        print(f"  status={status}  coa_id={coa_id}  intent={coa.get('intent')}")
        if interpret:
            src = body.get("interpreter_source")
            err = body.get("interpreter_error")
            n_hyp = len(body.get("hypotheses") or [])
            print(f"  interpret  : source={src} hypotheses={n_hyp} error={err}")
        _print_warning_picture(finding)

        _print_hop(2, "Screen 1 — operator approve")
        t_approve = time.perf_counter()
        approved = client.post(
            "/api/gate/approve",
            json={"coa_id": coa_id, "decision": "y", "operator_id": operator_id},
        )
        approved.raise_for_status()
        approve_body = approved.json()
        if approve_body.get("status") != "APPROVED":
            print(f"  FAIL: expected APPROVED, got {approve_body.get('status')}")
            return 1
        digest = (approve_body.get("token") or {}).get("digest")
        print(f"  status=APPROVED  token.digest={digest}")

        _print_hop(3, "Screen 2 — recipient inbox")
        inbox = client.get("/api/recipient/inbox", params={"unit_id": unit_id})
        inbox.raise_for_status()
        inbox_body = inbox.json()
        count = inbox_body.get("count", 0)
        print(f"  unit_id={unit_id}  pending={count}")
        if count < 1:
            print("  FAIL: inbox empty after approve")
            return 1

        _print_hop(4, "Screen 2 — recipient Ack")
        ack = client.post(
            "/api/recipient/ack",
            json={
                "coa_id": coa_id,
                "unit_id": unit_id,
                "message": "picture_to_tasking demo ack",
            },
        )
        ack.raise_for_status()
        ack_body = ack.json()
        if ack_body.get("status") != "ACKED":
            print(f"  FAIL: expected ACKED, got {ack_body.get('status')}")
            return 1
        t_ack = time.perf_counter()
        print(f"  status=ACKED  audit_hash={ack_body.get('audit_hash')}")

        # Screen 2 laptop / RasPi edge only — Core (incl. Cloudflare) never GPIO (#20).
        gpio = blink_on_ack_sync()
        if gpio is not None:
            print(f"  raspi_gpio  blinked={gpio.get('blinked')}  hardware={gpio.get('hardware')}")

        _print_hop(5, "Audit trail — assert Ack sealed")
        trail = client.get("/api/audit/trail")
        trail.raise_for_status()
        trail_body = trail.json()
        ok, detail = _verify_ack_in_trail(trail_body, coa_id)
        print(f"  records={trail_body.get('count')}  {detail}")
        if not ok:
            print(f"  FAIL: {detail}")
            return 1

    picture_to_ack = t_ack - t_picture
    approve_to_ack = t_ack - t_approve
    print("\n" + "-" * 60)
    print(f"Picture → Ack  : {picture_to_ack:.3f} s  (propose → ack)")
    print(f"Approve → Ack  : {approve_to_ack:.3f} s  (Slide 11 style)")
    print(f"Target         : < {ROUNDTRIP_TARGET_S:g} s")
    if require_roundtrip and approve_to_ack >= ROUNDTRIP_TARGET_S:
        print("FAIL: roundtrip exceeded target (is Core remote / cold?)")
        return 1
    if approve_to_ack >= ROUNDTRIP_TARGET_S:
        print("WARN: roundtrip exceeded local target (Cloudflare / network OK for demo)")
    else:
        print("PASS: Ack sealed in OCSF audit chain within target")
    print("-" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UI-less Picture→Tasking demo (Warning Picture → Ack → audit)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"C2 Core origin (env C2_BASE_URL / BASE_URL; default {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--scenario",
        default=os.environ.get("SCENARIO", DEFAULT_SCENARIO),
        help=f"Scenario id (default {DEFAULT_SCENARIO})",
    )
    parser.add_argument(
        "--unit-id",
        default=os.environ.get("UNIT_ID", DEFAULT_UNIT),
        help=f"Recipient unit id (default {DEFAULT_UNIT})",
    )
    parser.add_argument(
        "--operator-id",
        default="demo-operator",
        help="Operator id stamped on DecisionToken",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout seconds (default 10)",
    )
    parser.add_argument(
        "--require-roundtrip",
        action="store_true",
        help=f"Exit non-zero if approve→ack >= {ROUNDTRIP_TARGET_S:g}s",
    )
    parser.add_argument(
        "--interpret",
        action="store_true",
        help="Queue via interpret:true (live LiteLLM if Core has LLM_BASE_URL)",
    )
    parser.add_argument(
        "--force-heuristic",
        action="store_true",
        help="With --interpret, skip LLM even if LiteLLM is configured",
    )
    args = parser.parse_args(argv)
    base = _base_url(args.base_url)
    try:
        return run_demo(
            base_url=base,
            scenario_id=args.scenario,
            unit_id=args.unit_id,
            operator_id=args.operator_id,
            timeout_s=args.timeout,
            require_roundtrip=args.require_roundtrip,
            interpret=args.interpret,
            force_heuristic=args.force_heuristic,
        )
    except httpx.ConnectError as exc:
        print(f"FAIL: cannot reach Core at {base}: {exc}", file=sys.stderr)
        print(
            "Start local Core:  uv run sdth-c2-server\n"
            "Or set C2_BASE_URL to your Cloudflare / remote Core URL.",
            file=sys.stderr,
        )
        return 2
    except httpx.HTTPError as exc:
        print(f"FAIL: HTTP error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
