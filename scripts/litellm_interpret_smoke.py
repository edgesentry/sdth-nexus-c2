#!/usr/bin/env python3
"""Pitch-2 follow-on: live LiteLLM interpret smoke (issue #32).

POSTs S2 to /api/interpret and asserts source == "llm" with hypotheses.
Does **not** require Docker itself — point C2 at an already-running LiteLLM:

  LLM_BASE_URL=http://127.0.0.1:4000/v1
  LLM_API_KEY=<LITELLM_MASTER_KEY>
  LLM_MODEL=nexus-interpreter
  uv run sdth-c2-server

  uv run python scripts/litellm_interpret_smoke.py

One-shot (starts LiteLLM compose + local C2): ./scripts/litellm_interpret_smoke.sh

CI stays LLM-free. Heuristic fallback remains the default when LiteLLM is down.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import httpx

DEFAULT_BASE = "http://127.0.0.1:8080"
DEFAULT_SCENARIO = "S2"


def _base_url(cli: str | None) -> str:
    return (
        (cli or "").strip()
        or os.environ.get("C2_BASE_URL", "").strip()
        or os.environ.get("BASE_URL", "").strip()
        or DEFAULT_BASE
    ).rstrip("/")


def evaluate_interpret_response(body: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, detail). Live path must be LLM-sourced and never seal a token."""
    status = body.get("status")
    if status != "INTERPRETED":
        return False, f"expected status=INTERPRETED, got {status}"

    source = body.get("source")
    if source != "llm":
        error = body.get("error") or "unset LLM_BASE_URL / LiteLLM down / heuristic fallback"
        return False, f"expected source=llm, got {source!r} ({error})"

    hypotheses = body.get("hypotheses") or []
    if not isinstance(hypotheses, list) or len(hypotheses) < 1:
        return False, "hypotheses is empty (live LLM must return at least one)"

    if "token" in body:
        return False, "interpreter must never seal a DecisionToken"

    model = body.get("model") or "?"
    labels = [str(h.get("label", "")) for h in hypotheses if isinstance(h, dict)]
    return True, f"source=llm model={model} hypotheses={len(hypotheses)} labels={labels[:4]}"


def run_smoke(
    *,
    base_url: str,
    scenario_id: str,
    timeout_s: float,
) -> int:
    print("=" * 60)
    print("NexusGate — LiteLLM live interpret smoke")
    print(f"  Core URL   : {base_url}")
    print(f"  Scenario   : {scenario_id}")
    print("  Expect     : source == llm  (probabilistic proposes; gate disposes)")
    print("=" * 60)

    with httpx.Client(base_url=base_url, timeout=timeout_s) as client:
        try:
            resp = client.post(
                "/api/interpret",
                json={"scenario_id": scenario_id, "force_heuristic": False},
            )
        except httpx.ConnectError as exc:
            print(f"FAIL: cannot reach Core at {base_url}: {exc}", file=sys.stderr)
            print(
                "Start local Core with LiteLLM env:\n"
                "  LLM_BASE_URL=http://127.0.0.1:4000/v1 \\\n"
                "  LLM_API_KEY=sk-litellm-local \\\n"
                "  LLM_MODEL=nexus-interpreter \\\n"
                "  uv run sdth-c2-server\n"
                "Or run ./scripts/litellm_interpret_smoke.sh",
                file=sys.stderr,
            )
            return 2

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(f"FAIL: HTTP {exc.response.status_code}: {exc.response.text[:400]}", file=sys.stderr)
            return 1

        body = resp.json()
        ok, detail = evaluate_interpret_response(body)
        print(f"  {detail}")
        if body.get("picture_summary"):
            print(f"  picture    : {body['picture_summary']}")
        if not ok:
            print(f"FAIL: {detail}", file=sys.stderr)
            return 1

    print("PASS: live LLM interpret path (no DecisionToken)")
    print("-" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke S2 → POST /api/interpret and assert source == llm",
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
        "--timeout",
        type=float,
        default=float(os.environ.get("LLM_TIMEOUT_S", "30")),
        help="HTTP timeout seconds (default 30; LLM roundtrip is slower than the gate)",
    )
    args = parser.parse_args(argv)
    return run_smoke(
        base_url=_base_url(args.base_url),
        scenario_id=args.scenario,
        timeout_s=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
