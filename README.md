# sdth-nexus-c2

SDTH 2026 C2 application: **PS 04 One Picture, Many Eyes** (contradicting sensors → COA → latency-bounded HITL → effector).

Phase 1 keeps **NexusGate core** (`core/`) and the **venue app** (`app/`) in one Python repo. Venue words (Clearbot, strait, AIS, …) stay in `app/` only.

## Quick start

```bash
uv sync
./scripts/demo.sh
```

`demo.sh` starts the Level-1 Clearbot mock on `:8000` and runs one auto-approved C2 cycle.

Manual:

```bash
uv run uvicorn app.mock_server:app --port 8000 &
uv run python -m app.main --yes          # auto-approve
uv run python -m app.main                # interactive y/n countdown
uv run python -m app.main --stub --yes   # no HTTP
```

## Layout

| Path | Role |
|------|------|
| `core/` | Future OSS NexusGate: ontology, COA, interlock, tiered policy, LatencyBoundedGate, OCSF audit, EffectorProxy |
| `app/` | Scenario, rule-based agent, Rich TUI, Clearbot REST adapter, mock server, kinematics sim, RasPi stub |
| `config/maritime_defense_policy.yaml` | Geofences / thresholds (app-owned) |

## Effector levels

1. **Mock REST** — `app/mock_server.py` (`POST /api/v1/navigate`, telemetry, emergency_stop)
2. **2D kinematics** — advances lat/lon toward waypoint after approve
3. **RasPi GPIO** — `app/adapters/raspi_hardware.py` (no-op without RPi.GPIO)

## Tests

```bash
uv run pytest -q
```

## Limits (this baseline)

- Agent is **deterministic rules**, not LLM
- No full map UI (Rich TUI only)
- Dual-key Tier 2 not implemented
- Core must remain free of venue vocabulary for later `edgesentry/nexusgate` extract
