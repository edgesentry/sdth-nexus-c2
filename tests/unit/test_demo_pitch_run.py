"""Pitch-day all-in-one demo runner (issue #75)."""

from __future__ import annotations

import contextlib
import io
import time

from scripts.demo_pitch_run import AUTO_TARGET_S, main


def test_pitch_runner_auto_under_budget() -> None:
    t0 = time.perf_counter()
    rc = main(["--auto", "--quiet", "--no-color"])
    elapsed = time.perf_counter() - t0
    assert rc == 0, "pitch runner reported failures"
    assert elapsed < AUTO_TARGET_S, f"auto mode {elapsed:.2f}s >= {AUTO_TARGET_S}s"


def test_pitch_runner_cli_help() -> None:
    buf = io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stdout(buf):
        main(["--help"])
    out = buf.getvalue().lower()
    assert "scene" in out or "pitch" in out
