"""Capture screenshots of NexusGate verification harness for documentation."""

import os
import subprocess
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from app import c2_server
from app.c2_server import app as c2_app

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def take_screenshot(url: str, output_png: Path, width: int = 1200, height: int = 800) -> None:
    cmd = [
        CHROME_BIN,
        "--headless",
        "--disable-gpu",
        f"--window-size={width},{height}",
        f"--screenshot={output_png}",
        url,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Captured: {output_png} ({output_png.stat().st_size} bytes)")


def main() -> None:
    port = 8765
    audit_path = ROOT / ".audit" / "screenshot_gate.jsonl"
    if audit_path.exists():
        audit_path.unlink()

    c2_server._runtime = c2_server.C2Runtime(audit_path=audit_path)
    config = uvicorn.Config(c2_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(f"{base}/api/ontology/state", timeout=0.2).raise_for_status()
            break
        except Exception:
            time.sleep(0.1)

    print("Server ready at", base)

    # 1. Propose S2 via form
    res = httpx.post(
        f"{base}/verify/command/propose",
        data={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
        follow_redirects=True,
    )
    print("Propose status:", res.status_code)

    # Capture Screen 1: Command Cockpit
    screen1_png = ASSETS / "screen1_command.png"
    take_screenshot(f"{base}/verify/command", screen1_png, width=1280, height=860)

    # 2. Approve the proposal
    pending = list(c2_server.get_runtime().proposals.keys())
    if pending:
        cid = pending[0]
        app_res = httpx.post(
            f"{base}/verify/command/approve",
            data={"coa_id": cid, "decision": "APPROVE", "unit_id": "CUE-NODE-01"},
            follow_redirects=True,
        )
        print("Approved coa_id:", cid, "Status:", app_res.status_code)

    # Capture Screen 2: Recipient
    screen2_png = ASSETS / "screen2_recipient.png"
    take_screenshot(f"{base}/verify/recipient", screen2_png, width=1280, height=860)

    # Also capture Hub
    hub_png = ASSETS / "verify_hub.png"
    take_screenshot(f"{base}/verify", hub_png, width=1280, height=860)

    server.should_exit = True
    thread.join(timeout=2)
    print("Screenshots done!")


if __name__ == "__main__":
    main()
