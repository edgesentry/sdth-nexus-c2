# Demo & benchmarks

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
```

## Demo Path A: Two-Laptop / Two-Terminal I/O (issue #17)

Cold-start rehearsal for Phase 2 **without UI**. Topology: [Topology](architecture/topology.md) · plan §4.2: [Plan §4.2](plan.md#42-cloudflare-containers-phase-2). Full curl copy-paste lives in the repo [README — Laptop I/O runbook](https://github.com/edgesentry/sdth-nexus-c2#laptop-io-runbook-issue-17). Contract shapes: [C2 REST API](api/rest.md).

| Role | Machine | Actions |
|------|---------|---------|
| **Core** | Shared host | `uv run sdth-c2-server` **or** Cloudflare `C2_BASE_URL` (+ `C2_API_TOKEN`) |
| **Screen 1** | Command laptop | Optional ingress → `POST /api/gate/proposals` → `POST /api/gate/approve` |
| **Screen 2** | Recipient laptop | `GET /api/recipient/inbox` → `POST /api/recipient/ack` |

```bash
# Core (once)
uv run sdth-c2-server   # http://127.0.0.1:8080

# Both laptops / terminals — same Core origin
export C2_BASE_URL="${C2_BASE_URL:-http://127.0.0.1:8080}"
AUTH=()
[[ -n "${C2_API_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer $C2_API_TOKEN")
```

**Screen 1**

```bash
PROP=$(curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/gate/proposals" \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"S2","unit_id":"CUE-NODE-01"}')
COA_ID=$(echo "$PROP" | jq -r '.coa.coa_id')
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/gate/approve" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"decision\":\"y\"}"
# hand $COA_ID to Screen 2
```

**Screen 2**

```bash
curl -s "${AUTH[@]}" "$C2_BASE_URL/api/recipient/inbox?unit_id=CUE-NODE-01" | jq .
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/recipient/ack" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"unit_id\":\"CUE-NODE-01\"}"
curl -s "${AUTH[@]}" "$C2_BASE_URL/api/audit/trail" | jq 'length'
```

Cloudflare uses the **same paths** — only swap `C2_BASE_URL` / `C2_API_TOKEN` ([deploy.md](deploy.md)). Phase 3 will drive the same hops from BattlePlan instead of curl.

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
C2_BASE_URL=https://sdth-c2-core.<subdomain>.workers.dev ./scripts/picture_to_tasking.sh
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
uv sync --group litellm
set -a && source deploy/litellm/.env && set +a
uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000
# other terminal:
./scripts/litellm_interpret_smoke.sh                 # S2 → source == "llm" via gemini-3.8-flash
```

| Env (C2) | Value |
|----------|--------|
| `LLM_BASE_URL` | `http://127.0.0.1:4000/v1` |
| `LLM_API_KEY` | LiteLLM master key (`LITELLM_MASTER_KEY`, sample `sk-litellm-local`) — **not** a Gemini/OpenAI key; see [LiteLLM keys](litellm.md) |
| `LLM_MODEL` | `gemini-3.8-flash` (live smoke). Also `gpt-4o-mini`, `claude-haiku`, `fireworks-glm`, or `nexus-interpreter` |

| Provider | Alias | Key |
|----------|--------|-----|
| Google Gemini | `gemini-3.8-flash` | `GEMINI_API_KEY` |
| OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku` | `ANTHROPIC_API_KEY` |
| Fireworks AI | `fireworks-glm` | `FIREWORKS_AI_API_KEY` |

Never commit keys. What `LITELLM_MASTER_KEY` is, and how it differs from vendor keys: [LiteLLM keys](litellm.md). Agent Router / Envoy AI Gateway remains Phase 5.

## Demo Path E: Cloudflare Containers Core (Pitch-day HTTPS)

Same handshake over a Worker → container singleton (`getByName("demo")`). Runbook: [Cloudflare Containers](deploy.md).

```bash
cd deploy/cloudflare && npm install && cp .dev.vars.example .dev.vars && npx wrangler dev
# other terminal (shared Bearer from .dev.vars / wrangler secret):
C2_BASE_URL=http://127.0.0.1:8787 C2_API_TOKEN=dev-shared-c2-token ./scripts/picture_to_tasking.sh

# after `npx wrangler deploy` (+ C2_API_TOKEN secret):
C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev C2_API_TOKEN='…' ./scripts/picture_to_tasking.sh
```

Cloudflare down → `uv run sdth-c2-server` (do not set `C2_BASE_URL` / `C2_API_TOKEN`). Auth: [deploy.md](deploy.md#shared-bearer-auth-issue-38).

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
