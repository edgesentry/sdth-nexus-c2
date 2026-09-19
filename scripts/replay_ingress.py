#!/usr/bin/env python3
"""Re-POST append-only ingress records after ``/api/admin/reset`` (issue #54).

Reads ``.audit/ingress.jsonl`` (or ``INGRESS_REPLAY_PATH``) and re-plays each
payload to the recorded endpoint. Does **not** touch ``.audit/gate.jsonl``.

  uv run sdth-c2-server
  # ... demo fails after some CandidateEvent POSTs ...
  uv run python scripts/replay_ingress.py --reset
  uv run python scripts/replay_ingress.py --clear   # truncate jsonl only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "http://127.0.0.1:8080"
DEFAULT_LOG = ROOT / ".audit" / "ingress.jsonl"


def _headers() -> dict[str, str]:
    token = os.environ.get("C2_API_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _default_log_path() -> Path:
    override = os.environ.get("INGRESS_REPLAY_PATH")
    if override:
        return Path(override)
    return DEFAULT_LOG


def _join_url(base: str, endpoint: str) -> str:
    """Join base + endpoint regardless of leading/trailing slash."""
    return f"{base.rstrip('/')}/{endpoint.lstrip('/')}"


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON ({exc})") from exc
            if not isinstance(loaded, dict):
                raise ValueError(f"{path}:{line_no}: expected object")
            out.append(loaded)
    return out


def clear_log(path: Path) -> None:
    """Truncate the ingress replay log (demo hygiene; not gate authority)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def replay(
    *,
    base_url: str,
    records: list[dict[str, Any]],
    reset: bool,
    timeout: float,
) -> int:
    base = base_url.rstrip("/")
    headers = _headers()
    with httpx.Client(timeout=timeout) as client:
        if reset:
            resp = client.post(_join_url(base, "/api/admin/reset"), headers=headers)
            resp.raise_for_status()
            print(f"reset → {resp.json().get('status', resp.status_code)}")

        ok = 0
        for i, rec in enumerate(records, start=1):
            endpoint = str(rec.get("endpoint") or "/api/ingress/candidate-event")
            payload = rec.get("payload")
            if not isinstance(payload, dict):
                print(f"SKIP {i}: missing payload object", file=sys.stderr)
                continue
            url = _join_url(base, endpoint)
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                print(
                    f"FAIL {i}: {endpoint} → {resp.status_code} {resp.text}",
                    file=sys.stderr,
                )
                return 1
            body = resp.json()
            print(
                f"  OK {i}/{len(records)} source={rec.get('source')} "
                f"status={body.get('status')} count={body.get('count')}"
            )
            ok += 1
    print(f"RESULT: replayed {ok}/{len(records)} ingress record(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("C2_BASE_URL", DEFAULT_BASE),
        help="C2 Core base URL (default C2_BASE_URL or localhost:8080)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=_default_log_path(),
        help="Ingress jsonl path (default INGRESS_REPLAY_PATH or .audit/ingress.jsonl)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="POST /api/admin/reset before replaying (memory only; keeps jsonl)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate the ingress jsonl and exit (no replay; demo hygiene)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout seconds",
    )
    args = parser.parse_args(argv)

    if args.clear:
        clear_log(args.log)
        print(f"cleared {args.log}")
        return 0

    records = load_records(args.log)
    if not records:
        print(f"FAIL: no records in {args.log}", file=sys.stderr)
        return 1
    print(f"replaying {len(records)} record(s) from {args.log} → {args.base_url}")
    try:
        return replay(
            base_url=args.base_url,
            records=records,
            reset=args.reset,
            timeout=args.timeout,
        )
    except httpx.HTTPError as exc:
        print(f"FAIL: HTTP error ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
