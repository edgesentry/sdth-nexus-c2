# sdth-nexus-c2

SDTH 2026 C2 application: **PS 04 One Picture, Many Eyes** — disagreeing sensors → **warning picture** → latency-bounded HITL → effector.

**NexusGate core** (`core/`) and the **venue app** (`app/`) live in one Python repo. Venue / defense narrative words stay in `app/` only.

**Phases:** Phase 1 done · **Phase 2** = backend closed loop (no UI) · Phase 3 = BattlePlan UI · Phase 4 = pitch day · Phase 5 = post-hackathon. See [`PLAN.md`](PLAN.md).

**Topology:** Core runs locally (`sdth-c2-server`) and, in Phase 2, on **Cloudflare Containers** (same REST paths). **Ingress/command and recipient Ack stay on laptops** either way.

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

Screen 1 (command laptop: curl / TUI; BattlePlan in Phase 3) + Screen 2 (recipient laptop) against local Core. Point clients at a Cloudflare URL later without changing paths.

```bash
uv run sdth-c2-server   # http://127.0.0.1:8080
```

Laptop I/O (Phase 2 — no UI):

1. **Screen 1 / command:** start Core, `POST /api/gate/proposals` then `POST /api/gate/approve` (or run `scripts/stream_events.py` / TUI).
2. **Screen 2 / recipient:** `GET /api/recipient/inbox?unit_id=…` then `POST /api/recipient/ack`.
3. **Audit check:** `GET /api/audit/trail`.

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

### Picture→Tasking demo (no UI)

One-shot S2 loop: **Warning Picture → approve → inbox → Ack → audit** (Pitch-4 / issue #24). Prints each hop and asserts `recipient_ack` is sealed in the OCSF hash chain. Local target: approve→ack **< 3 s**.

```bash
./scripts/picture_to_tasking.sh          # starts local sdth-c2-server, then runs demo
# or two terminals:
uv run sdth-c2-server                    # Terminal A (Screen 1+2 share Core)
uv run python scripts/picture_to_tasking.py   # Terminal B
```

Point at a remote Core later without changing paths:

```bash
C2_BASE_URL=https://your-c2.example.com ./scripts/picture_to_tasking.sh
# aliases: BASE_URL also accepted by the Python client
```

## Layout

| Path | Role |
|------|------|
| `core/` | Future OSS NexusGate (no SDTH/Clearbot/Singapore vocabulary) |
| `app/scenarios/` | S1–S3 defense scenarios + registry |
| `app/c2_server.py` | Two-screen C2 REST (ontology / gate / recipient / audit) |
| `app/adapters/usv_rest.py` | Vendor-neutral USV REST effector (`EFFECTOR_BASE_URL`) |
| `scripts/picture_to_tasking.py` | UI-less Picture→Tasking demo (`C2_BASE_URL` / `BASE_URL`) |
| `app/` | Warning Picture TUI, mock server, kinematics, RasPi stub |
| `app/config/maritime_defense_policy.yaml` | Geofences / thresholds (app-owned) |

## Effector levels

1. **Mock REST** — `app/mock_server.py` (`EFFECTOR_BASE_URL`, default `http://127.0.0.1:8000`; `CLEARBOT_BASE_URL` still accepted)
2. **2D kinematics** — lat/lon toward waypoint after approve
3. **RasPi GPIO** — optional / no-op without hardware

`ClearbotRestAdapter` remains a thin alias of `UsvRestAdapter` for older imports.

## 19-event temporal streamer

Play T-60s → T-00s sensor ingress incrementally (PS 04 temporal alignment), not a one-shot `build_events()` dump:

```bash
uv run python scripts/stream_events.py                  # S2 hero, local ontology
uv run python scripts/stream_events.py --fast           # no inter-step sleep
uv run python scripts/stream_events.py --mode print     # JSONL steps
uv run python scripts/stream_events.py --help
```

| Steps | Band |
|-------|------|
| 01–05 | Early recon / social rumors / sparse radar |
| 06–10 | Coastal radar lock + optical slew |
| 11–15 | EO blur + Amber contradiction (S2) |
| 16–19 | Warning Picture → HITL → tasking/ack cue |

## Slide 11 benchmarks

Prove gate latency, fail-closed unauthorized rejects, picture-to-ack, and audit integrity:

```bash
uv run python scripts/benchmark.py
uv run python scripts/benchmark.py --help
```

Exits non-zero if any metric misses its target (suitable for live demo / CI).

| Metric | Target |
|--------|--------|
| Gate latency (p95) | < 50 ms (100 COA evals) |
| Interlock fast-reject (p95) | < 5 ms |
| Unauthorized taskings | 0 (geofence / speed / duplicate / timeout) |
| Picture-to-Ack roundtrip | < 3.0 s |
| Audit trace integrity | 100% hash-chain |

## Tests

```bash
uv run pytest tests/unit/ -q                        # unit
uv run pytest tests/integration/ -v -m integration  # S2 + C2 two-screen / live HTTP
uv run python scripts/stream_events.py --fast       # 19-step temporal playback
uv run python scripts/benchmark.py                  # Slide 11 proof
```

CI runs unit, integration, and benchmark jobs on every push/PR.
## Limits

- Detectors are **deterministic rules**, not LLM
- No full map UI (Rich TUI only)
- Dual-key Tier 2 not implemented
- Kinetic intercept is **not** claimed (S2 cues identify only)
