"""Picture→Tasking demo script: Warning Picture → Ack → audit (issue #24)."""

from __future__ import annotations

import importlib.util
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import httpx
import pytest
import uvicorn
from app import c2_server
from app.c2_server import app as c2_app

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _load_demo() -> ModuleType:
    path = ROOT / "scripts" / "picture_to_tasking.py"
    spec = importlib.util.spec_from_file_location("picture_to_tasking", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def live_c2(tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "p2t_gate.jsonl")
    config = uvicorn.Config(c2_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            httpx.get(f"{base}/api/ontology/state", timeout=0.2).raise_for_status()
            break
        except (httpx.HTTPError, OSError):
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("C2 server failed to start")
    try:
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_picture_to_tasking_demo_script(live_c2: str) -> None:
    demo = _load_demo()
    code = demo.run_demo(
        base_url=live_c2,
        scenario_id="S2",
        unit_id="CUE-NODE-01",
        operator_id="ci",
        timeout_s=5.0,
        require_roundtrip=True,
    )
    assert code == 0


def test_picture_to_tasking_interpret_heuristic(live_c2: str) -> None:
    """--interpret against Core without LiteLLM still closes the loop via heuristic."""
    demo = _load_demo()
    code = demo.run_demo(
        base_url=live_c2,
        scenario_id="S2",
        unit_id="CUE-NODE-01",
        operator_id="ci",
        timeout_s=5.0,
        require_roundtrip=True,
        interpret=True,
        force_heuristic=True,
    )
    assert code == 0
