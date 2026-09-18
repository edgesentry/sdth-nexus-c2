# sdth-nexus-c2

SDTH 2026 C2 application: **PS 04 One Picture, Many Eyes** — disagreeing sensors → **warning picture** → latency-bounded HITL → effector.

**Docs:** [edgesentry.github.io/sdth-nexus-c2](https://edgesentry.github.io/sdth-nexus-c2/) (MkDocs Material · `mkdocs serve` locally)

**NexusGate core** (`core/`) and the **venue app** (`app/`) live in one Python repo. Venue / defense narrative words stay in `app/` only.

**Phases:** Phase 1 done · **Phase 2** = backend closed loop (no UI) · Phase 3 = BattlePlan UI · Phase 4 = pitch day · Phase 5 = post-hackathon. See [`docs/plan.md`](docs/plan.md).

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
| **S3** | Shipping Lane & Coastal Anomaly — SAR vs AIS | Space SAR dark cluster vs thin AIS; coastal radar cue; approach patrol |

Each run prints a **WARNING PICTURE** (threat class, minutes of warning, sources, “if false collapses when…”) before the gate.

## Manual

```bash
uv run uvicorn app.mock_server:app --port 8000 &
EFFECTOR_BASE_URL=http://127.0.0.1:8000 uv run python -m app.main --scenario S1 --yes
uv run python -m app.main --scenario S2            # interactive y/n
uv run python -m app.main --scenario S3 --stub --yes
```

## C2 REST (Two-Screen) — frozen contract

Screen 1 (command laptop: curl / TUI; BattlePlan in Phase 3) + Screen 2 (recipient laptop) against local Core. Point clients at a Cloudflare URL later without changing paths.

**Contract freeze (issue #15):** request/response shapes live in [`docs/api/rest.md`](docs/api/rest.md) (also on [GitHub Pages](https://edgesentry.github.io/sdth-nexus-c2/api/rest/)). CI guards required keys via `tests/unit/test_c2_rest_contract.py`.

```bash
uv run sdth-c2-server   # http://127.0.0.1:8080
```

Laptop I/O (Phase 2 — no UI):

1. **Screen 1 / command:** start Core, `POST /api/gate/proposals` then `POST /api/gate/approve` (or run `scripts/stream_events.py` / TUI).
2. **Screen 2 / recipient:** `GET /api/recipient/inbox?unit_id=…` then `POST /api/recipient/ack`.
3. **Audit check:** `GET /api/audit/trail`.
4. **Demo reset (optional):** `POST /api/admin/reset` (clears memory; does not wipe `.audit/gate.jsonl`).

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/ontology/state` | Live tracks, observations, amber alert |
| `POST` | `/api/interpret` | Probabilistic propose: hypotheses + candidate COA (no token) |
| `POST` | `/api/ingress/candidate-event` | Upstream macro SAR CandidateEvent → `space_sar` Observation |
| `POST` | `/api/gate/proposals` | Queue COA (`scenario_id`, raw `coa`, or `interpret:true`) |
| `POST` | `/api/gate/approve` | Operator y/n → sealed `DecisionToken` |
| `GET` | `/api/recipient/inbox?unit_id=` | Pending approved taskings |
| `POST` | `/api/recipient/ack` | Recipient ack sealed to audit chain |
| `GET` | `/api/audit/trail` | OCSF-shaped hash-chain records |
| `POST` | `/api/admin/reset` | Clear in-memory runtime (tests / demos) |

Example handshake:

```bash
# Optional Pitch-2: probabilistic propose (never seals tokens)
curl -s -X POST localhost:8080/api/interpret -H 'content-type: application/json' \
  -d '{"scenario_id":"S2","force_heuristic":true}'

curl -s -X POST localhost:8080/api/gate/proposals -H 'content-type: application/json' \
  -d '{"scenario_id":"S2","unit_id":"CUE-NODE-01"}'
# or interpreter → gate in one hop:
# -d '{"scenario_id":"S2","unit_id":"CUE-NODE-01","interpret":true}'
curl -s -X POST localhost:8080/api/gate/approve -H 'content-type: application/json' \
  -d '{"coa_id":"<id>","decision":"y"}'
curl -s 'localhost:8080/api/recipient/inbox?unit_id=CUE-NODE-01'
curl -s -X POST localhost:8080/api/recipient/ack -H 'content-type: application/json' \
  -d '{"coa_id":"<id>","unit_id":"CUE-NODE-01"}'
curl -s localhost:8080/api/audit/trail
```

### Probabilistic interpreter (Pitch-2)

**Probabilistic proposes; deterministic disposes.** App-layer LLM (or heuristic fallback) scores hypotheses and emits a candidate COA. Only `LatencyBoundedGate` can approve / seal `DecisionToken`s.

| Env | Role |
|-----|------|
| `LLM_BASE_URL` | OpenAI-compatible base (`…/v1`). Unset → heuristic fallback |
| `LLM_API_KEY` | Bearer token (optional for local endpoints) |
| `LLM_MODEL` | Model id (default `gpt-4o-mini`) |
| `LLM_TIMEOUT_S` | HTTP timeout seconds (default `8`) |

Never commit API keys — use env / Wrangler Secrets. Sample: `.env.example` (C2) and `deploy/litellm/.env.example` (proxy).

### Live LLM via LiteLLM (Pitch-2 follow-on)

**Probabilistic proposes; deterministic disposes.** LiteLLM is the local OpenAI-compatible front door (`:4000/v1`). CI does **not** start it — unset `LLM_BASE_URL` keeps the heuristic path green.

```text
sdth-c2-server  ──LLM_BASE_URL──►  LiteLLM (:4000/v1)
                                        │
                                        ├── Google Gemini 3.8 Flash  (live smoke / tests)
                                        ├── OpenAI / Anthropic / Fireworks
                                        └── Ollama / vLLM (offline venue)
```

```bash
cp deploy/litellm/.env.example deploy/litellm/.env   # set GEMINI_API_KEY (tests) or OPENAI/ANTHROPIC
cp .env.example .env                                 # C2 → LiteLLM mapping (LLM_MODEL=gemini-3.8-flash)
uv sync --group litellm
set -a && source deploy/litellm/.env && set +a
uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000
./scripts/litellm_interpret_smoke.sh                 # S2 → source == "llm" via gemini-3.8-flash
# closed loop with interpreter overlay:
INTERPRET=1 ./scripts/picture_to_tasking.sh
```

| Provider | LiteLLM alias (`LLM_MODEL`) | Upstream env |
|----------|-----------------------------|--------------|
| **Google Gemini** | `gemini-3.8-flash` (live smoke default) | `GEMINI_API_KEY` |
| OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku` | `ANTHROPIC_API_KEY` |
| Fireworks AI | `fireworks-glm` | `FIREWORKS_AI_API_KEY` |
| Venue alias | `nexus-interpreter` (Gemini → OpenAI → Anthropic → Fireworks → Ollama) | whichever backend is configured |

| Env | Role |
|-----|------|
| `LLM_BASE_URL` | `http://127.0.0.1:4000/v1` |
| `LLM_API_KEY` | Same string as `LITELLM_MASTER_KEY` (proxy lock, **not** a vendor key) |
| `LLM_MODEL` | `gemini-3.8-flash` for tests; `nexus-interpreter` for venue fallbacks |

LiteLLM down / no key → existing heuristic demo still works. What the master key is: [`docs/litellm.md`](docs/litellm.md). Agent Router / Envoy is Phase 5.

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
| `app/c2_server.py` | Two-screen C2 REST (ontology / interpret / gate / recipient / audit) |
| `app/llm_interpreter.py` | Pitch-2 probabilistic propose (LLM + heuristic fallback) |
| `deploy/litellm/` | LiteLLM OpenAI-compatible front door (`config.yaml` + Python `uv --group litellm`) |
| `app/adapters/usv_rest.py` | Vendor-neutral USV REST effector (`EFFECTOR_BASE_URL`) |
| `app/adapters/sar_candidate_event.py` | Assumed CandidateEvent → `space_sar` Observation (Pitch-1) |
| `scripts/picture_to_tasking.py` | UI-less Picture→Tasking demo (`C2_BASE_URL` / `BASE_URL`; `--interpret`) |
| `scripts/litellm_interpret_smoke.py` | Live S2 `/api/interpret` smoke (`source == "llm"`) |
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
| Track-flood stress (p95) | < 50 ms under 100+ synthetic tracks (Pitch-3) |
| Track-flood unauthorized | 0 under flood |
| Picture-to-Ack roundtrip | < 3.0 s |
| Audit trace integrity | 100% hash-chain |

## Tests

```bash
uv run pytest tests/unit/ -q                        # unit
uv run pytest tests/integration/ -v -m integration  # S2 + C2 two-screen / live HTTP
uv run python scripts/stream_events.py --fast       # 19-step temporal playback
uv run python scripts/benchmark.py                  # Slide 11 proof
./scripts/litellm_interpret_smoke.sh                # live LiteLLM (optional; not in CI)
```

CI runs unit, integration, and benchmark jobs on every push/PR.

## Limits

- **Probabilistic proposes, deterministic disposes** — app LLM/heuristic may suggest COAs; Core gate alone seals tokens
- Scenario detectors remain deterministic rules (LLM is optional overlay)
- No full map UI (Rich TUI only)
- Dual-key Tier 2 not implemented
- Kinetic intercept is **not** claimed (S2 cues identify only)
