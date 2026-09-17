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
EFFECTOR_BASE_URL=http://127.0.0.1:8000 uv run python -m app.main --scenario S1 --yes
uv run python -m app.main --scenario S2            # interactive y/n
uv run python -m app.main --scenario S3 --stub --yes
```

## C2 REST (Two-Screen)

Screen 1 (command) + Screen 2 (recipient) loop for BattlePlan / laptop demos:

```bash
uv run sdth-c2-server   # http://127.0.0.1:8080
```

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/ontology/state` | Live tracks, observations, amber alert |
| `POST` | `/api/gate/proposals` | Queue COA (`scenario_id` or raw `coa`) |
| `POST` | `/api/gate/approve` | Operator y/n → sealed `DecisionToken` |
| `GET` | `/api/recipient/inbox?unit_id=` | Pending approved taskings |
| `POST` | `/api/recipient/ack` | Recipient ack sealed to audit chain |
| `GET` | `/api/audit/trail` | OCSF-shaped hash-chain records |

Example handshake:

```bash
curl -s -X POST localhost:8080/api/gate/proposals -H 'content-type: application/json' \
  -d '{"scenario_id":"S2","unit_id":"CUE-NODE-01"}'
curl -s -X POST localhost:8080/api/gate/approve -H 'content-type: application/json' \
  -d '{"coa_id":"<id>","decision":"y"}'
curl -s 'localhost:8080/api/recipient/inbox?unit_id=CUE-NODE-01'
curl -s -X POST localhost:8080/api/recipient/ack -H 'content-type: application/json' \
  -d '{"coa_id":"<id>","unit_id":"CUE-NODE-01"}'
```

## Layout

| Path | Role |
|------|------|
| `core/` | Future OSS NexusGate (no SDTH/Clearbot/Singapore vocabulary) |
| `app/scenarios/` | S1–S3 defense scenarios + registry |
| `app/c2_server.py` | Two-screen C2 REST (ontology / gate / recipient / audit) |
| `app/adapters/usv_rest.py` | Vendor-neutral USV REST effector (`EFFECTOR_BASE_URL`) |
| `app/` | Warning Picture TUI, mock server, kinematics, RasPi stub |
| `app/config/maritime_defense_policy.yaml` | Geofences / thresholds (app-owned) |

## Effector levels

1. **Mock REST** — `app/mock_server.py` (`EFFECTOR_BASE_URL`, default `http://127.0.0.1:8000`; `CLEARBOT_BASE_URL` still accepted)
2. **2D kinematics** — lat/lon toward waypoint after approve
3. **RasPi GPIO** — optional / no-op without hardware

`ClearbotRestAdapter` remains a thin alias of `UsvRestAdapter` for older imports.

## Tests

```bash
uv run pytest tests/unit/ -q                        # unit
uv run pytest tests/integration/ -v -m integration  # S2 + C2 two-screen / live HTTP
```

CI runs both jobs (`Unit tests` and `Integration tests`) on every push/PR.
## Limits

- Detectors are **deterministic rules**, not LLM
- No full map UI (Rich TUI only)
- Dual-key Tier 2 not implemented
- Kinetic intercept is **not** claimed (S2 cues identify only)
