# Demo & benchmarks

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
```

## Demo Path A: Two-Screen C2 REST Closed Loop

Starts the central C2 server connecting Screen 1 (Command Cockpit) and Screen 2 (Field Recipient):

```bash
uv run sdth-c2-server   # http://127.0.0.1:8080
```

Drive the closed loop via curl (see [C2 REST API — frozen contract](api/rest.md)) or, in Phase 3, the BattlePlan Next.js frontend:
1. Submit proposal (`POST /api/gate/proposals`)
2. Operator approves/denies (`POST /api/gate/approve`)
3. Recipient retrieves token (`GET /api/recipient/inbox?unit_id=...`)
4. Recipient sends signed Ack (`POST /api/recipient/ack`)
5. Verify OCSF audit log (`GET /api/audit/trail`)

## Demo Path B: 19-Event Temporal Streamer

Demonstrates temporal alignment (PS 04 §2-03) and amber contradiction flagging across a 19-step timeline (T-60s to T-00s) directly in the terminal:

```bash
uv run python scripts/stream_events.py                     # default S2 hero scenario
uv run python scripts/stream_events.py --scenario S1       # S1 sea spoof scenario
uv run python scripts/stream_events.py --fast              # run without sleep delays
```

## Demo Path C: UI-less Picture→Tasking Demo (Pitch-4)

Runs a complete one-shot automated loop: **Warning Picture → approve → inbox → Ack → audit** against local or remote Core (`C2_BASE_URL`):

```bash
./scripts/picture_to_tasking.sh                      # starts local server, runs S2 loop, verifies <3s
```

Or run manually against an already running server:

```bash
uv run python scripts/picture_to_tasking.py          # asserts token and signed Ack in OCSF audit
INTERPRET=1 ./scripts/picture_to_tasking.sh          # interpreter overlay (LiteLLM if Core has LLM_BASE_URL)
```

## Demo Path D: Live LLM via LiteLLM

**Probabilistic proposes; deterministic disposes.** Stands up LiteLLM as the OpenAI-compatible front door and proves `POST /api/interpret` returns `source: "llm"`. CI stays LLM-free (heuristic fallback when `LLM_BASE_URL` is unset or LiteLLM is down).

```bash
cp deploy/litellm/.env.example deploy/litellm/.env   # set GEMINI_API_KEY for live smoke
cp .env.example .env
docker compose -f deploy/litellm/docker-compose.yml up -d
./scripts/litellm_interpret_smoke.sh                 # S2 → source == "llm" via gemini-3.8-flash
```

| Env (C2) | Value |
|----------|--------|
| `LLM_BASE_URL` | `http://127.0.0.1:4000/v1` |
| `LLM_API_KEY` | LiteLLM master key (`LITELLM_MASTER_KEY`, sample `sk-litellm-local`) — **not** a Gemini/OpenAI key; see [LiteLLM keys](litellm.md) |
| `LLM_MODEL` | `gemini-3.8-flash` (live smoke). Also `gpt-4o-mini`, `claude-haiku`, or `nexus-interpreter` |

| Provider | Alias | Key |
|----------|--------|-----|
| Google Gemini | `gemini-3.8-flash` | `GEMINI_API_KEY` |
| OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku` | `ANTHROPIC_API_KEY` |

Never commit keys. What `LITELLM_MASTER_KEY` is, and how it differs from `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: [LiteLLM keys](litellm.md). Agent Router / Envoy AI Gateway remains Phase 5.

## Effector levels

1. **Mock REST** — `app/mock_server.py` (`EFFECTOR_BASE_URL`)
2. **2D kinematics** — lat/lon toward waypoint after approve
3. **RasPi GPIO** — optional / no-op without hardware

## Slide 11 benchmarks

```bash
uv run python scripts/benchmark.py
uv run python scripts/benchmark.py --tracks 150   # Pitch-3 flood size
```

| Metric | Target |
|--------|--------|
| Gate latency (p95) | < 50 ms (100 COA evals) |
| Interlock fast-reject (p95) | < 5 ms |
| Unauthorized taskings | 0 |
| Track-flood stress (gate p95) | < 50 ms under **100+** synthetic tracks |
| Track-flood unauthorized | 0 (geofence / speed / null under flood) |
| Picture-to-Ack roundtrip | < 3.0 s |
| Audit trace integrity | 100% hash-chain |

Exits non-zero if any metric misses its target (CI + live demo). Pitch-3 flood is on by default (`--skip-stress` to omit).

## Tests

```bash
uv run pytest tests/unit/ -q
uv run pytest tests/integration/ -v -m integration
```

## Local docs preview

```bash
pip install "mkdocs-material>=9.5,<10"
mkdocs serve
```
