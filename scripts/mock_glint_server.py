#!/usr/bin/env python3
"""Launch GLINT Assumed-mock on :5051 (issue #55).

uv run python scripts/mock_glint_server.py
# or: uv run sdth-mock-glint
"""

from __future__ import annotations

from mocks.glint import cli_main

if __name__ == "__main__":
    cli_main()
