#!/usr/bin/env python3
"""Launch USV REST mock on :8000.

    uv run python scripts/mock_server.py
    # or: uv run sdth-mock-effector
"""

from __future__ import annotations

from mocks.usv import cli_main

if __name__ == "__main__":
    cli_main()
