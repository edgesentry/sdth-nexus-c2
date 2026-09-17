# sdth-nexus-c2

SDTH 2026 C2 application: **PS 04 One Picture, Many Eyes** — disagreeing sensors → **warning picture** → latency-bounded HITL → effector.

Phase 1 keeps **NexusGate core** (`core/`) and the **venue app** (`app/`) in one Python repo. Venue / defense narrative words stay in `app/` only.

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
```

## Defense scenarios (app-layer)

| ID | Title | Story |
|----|-------|--------|
| **S1** | Sea Approach — Adversarial AIS Spoof | Sea approaches; manipulable AIS vs radar/EO; vendor IDs not shared; ISR USV identify |
| **S2** | Air Corridor — Shahed Swarm Contradiction | Social/recon claims 3; radar sees 1 (~1.2 km N); EO blur 0.42; amber count+bearing; cue/identify |
| **S3** | Shipping Lane SPOF — Pattern Break | Open AIS thins; uncorrelated coastal radar; approach patrol |

Each run prints a **WARNING PICTURE** (threat class, minutes of warning, sources, “if false collapses when…”) before the gate.

## Manual

```bash
uv run uvicorn app.mock_server:app --port 8000 &
uv run python -m app.main --scenario S1 --yes
uv run python -m app.main --scenario S2            # interactive y/n
uv run python -m app.main --scenario S3 --stub --yes
```

## Layout

| Path | Role |
|------|------|
| `core/` | Future OSS NexusGate (no SDTH/Clearbot/Singapore vocabulary) |
| `app/scenarios/` | S1–S3 defense scenarios + registry |
| `app/` | Warning Picture TUI, Clearbot REST, mock server, kinematics, RasPi stub |
| `app/config/maritime_defense_policy.yaml` | Geofences / thresholds (app-owned) |

## Effector levels

1. **Mock REST** — `app/mock_server.py`
2. **2D kinematics** — lat/lon toward waypoint after approve
3. **RasPi GPIO** — optional / no-op without hardware

## Tests

```bash
uv run pytest tests/ -q
```

## Limits

- Detectors are **deterministic rules**, not LLM
- No full map UI (Rich TUI only)
- Dual-key Tier 2 not implemented
- Kinetic intercept is **not** claimed (S2 cues identify only)
