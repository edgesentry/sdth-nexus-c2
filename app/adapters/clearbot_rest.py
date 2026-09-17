"""Backward-compat shim: Clearbot naming → vendor-neutral UsvRestAdapter."""

from __future__ import annotations

from app.adapters.usv_rest import UsvRestAdapter

# Historical alias used by demos / older imports.
ClearbotRestAdapter = UsvRestAdapter

__all__ = ["ClearbotRestAdapter"]
