# Demo & benchmarks

Phase 2 demos use **curl / scripts / two laptops**, plus the optional **NexusGate verification WebUI** ([#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65); Jinja2/HTMX harness at `/verify` on Core; **not** the external BattlePlan pitch UI) on the same frozen paths. Contract: [C2 REST API](api/rest.md). Topology: [Topology](architecture/topology.md) · Provenance: [Data provenance](data-provenance.md).

**Full E2E runbook (fixtures vs live SIA/GLINT):** [E2E verification](verify-e2e.md).

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
```

### Manual CLI (effector mock)

```bash
uv run uvicorn app.mock_server:app --port 8000 &
EFFECTOR_BASE_URL=http://127.0.0.1:8000 uv run python -m app.main --scenario S1 --yes
uv run python -m app.main --scenario S2            # interactive y/n
uv run python -m app.main --scenario S3 --stub --yes
```

---

## Demo Path A: Two-Laptop / Two-Terminal I/O (issue #17)

Cold-start rehearsal for Phase 2 **without UI**. Paths never change — only `C2_BASE_URL` (+ optional `C2_API_TOKEN` on Cloudflare).

| Role | Where | Job |
|------|-------|-----|
| **Core** | One host (local or Cloudflare) | `sdth-c2-server` — ontology, gate, inbox, audit |
| **Screen 1** | Command laptop | Ingress (optional) → propose → approve |
| **Screen 2** | Recipient laptop | Poll inbox → Ack |

### 0. Cold start — Core

```bash
uv sync
uv run sdth-c2-server          # http://127.0.0.1:8080
# Cloudflare instead:
#   export C2_BASE_URL=https://sdth-c2-core.<sub>.workers.dev
#   export C2_API_TOKEN='…'   # Worker Bearer (#38); see deploy.md
```

Both laptops point at the **same** Core. Local Core ignores `C2_API_TOKEN`. Set once per shell:

```bash
export C2_BASE_URL="${C2_BASE_URL:-http://127.0.0.1:8080}"
AUTH=()
[[ -n "${C2_API_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer $C2_API_TOKEN")
# jq helps pass coa_id between screens; install if missing: brew install jq
```

### 1. Screen 1 — command (ingress + gate)

```bash
# Optional reset between rehearsals (memory only; does not wipe .audit/gate.jsonl
# or .audit/ingress.jsonl)
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/admin/reset"

# After a failed demo, re-POST prior ingress without re-collecting upstream:
#   uv run python scripts/replay_ingress.py --reset
# Truncate the replay log between rehearsals (optional):
#   uv run python scripts/replay_ingress.py --clear

# Optional ingress (skip for minimal S2 handshake — proposals load the scenario)
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/ingress/open-feed" \
  -H 'content-type: application/json' -d '{"feed":"all","use_fixture":true}'
# S3 SAR path (Pitch-1 assumed fixture):
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/ingress/candidate-event" \
  -H 'content-type: application/json' -d '{"use_fixture":true}'
# S3 SAR path (Sentinel Singapore Strait fixture — issue #47):
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/ingress/candidate-event" \
  -H 'content-type: application/json' -d '{"use_sentinel_fixture":true}'
# S3 GLINT macro (Assumed-mock fixture — issue #55):
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/ingress/candidate-event" \
  -H 'content-type: application/json' -d '{"use_glint_fixture":true}'
# S3 GLINT pull (start mock first: uv run sdth-mock-glint → :5051):
# curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/ingress/candidate-event" \
#   -H 'content-type: application/json' -d '{"pull_glint":true}'
# S3 Dual-SAR (GLINT × SIA fixtures — issue #56):
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/ingress/candidate-event" \
  -H 'content-type: application/json' -d '{"dual_sar":true}'

# Propose (loads S2 Warning Picture + queues COA). Capture coa_id:
PROP=$(curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/gate/proposals" \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"S2","unit_id":"CUE-NODE-01"}')
echo "$PROP" | jq '{coa_id: .coa.coa_id, amber: .finding.amber_alert, threat: .finding.threat_class}'
COA_ID=$(echo "$PROP" | jq -r '.coa.coa_id')
# Tell Screen 2 the same COA_ID (chat / shared terminal / sticky note).

# Operator approve → sealed DecisionToken
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/gate/approve" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"decision\":\"y\",\"operator_id\":\"screen1\"}"
```

Optional Pitch-2 overlay on Screen 1 (never seals tokens by itself):

```bash
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/interpret" \
  -H 'content-type: application/json' -d '{"scenario_id":"S2","force_heuristic":true}'
# or one-hop: proposals with "interpret":true (LiteLLM if Core has LLM_BASE_URL)
```

### 2. Screen 2 — recipient (inbox + ack)

```bash
export C2_BASE_URL="${C2_BASE_URL:-http://127.0.0.1:8080}"   # same Core as Screen 1
AUTH=()
[[ -n "${C2_API_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer $C2_API_TOKEN")
COA_ID='…'   # from Screen 1
UNIT_ID=CUE-NODE-01

curl -s "${AUTH[@]}" "$C2_BASE_URL/api/recipient/inbox?unit_id=$UNIT_ID" | jq .
curl -s "${AUTH[@]}" -X POST "$C2_BASE_URL/api/recipient/ack" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"unit_id\":\"$UNIT_ID\",\"message\":\"screen2 ack\"}"

# Optional stretch (#20): blink on this laptop/Pi (not on Cloudflare Core)
# RASPI_ACK_BLINK=1 uv run python scripts/raspi_ack_blink.py
```

### 3. Either screen — audit seal

```bash
curl -s "${AUTH[@]}" "$C2_BASE_URL/api/audit/trail" \
  | jq --arg id "$COA_ID" \
    '.records[] | select(.activity_name=="recipient_ack" and .metadata.coa_id==$id) | {activity_name, time}'
```

Expect a `recipient_ack` for that `coa_id` within **< 3 s** of approve on a local Core.

**One-shot shortcut** (same hops, automated): `./scripts/picture_to_tasking.sh` — fine for CI; use Screen 1/2 curl above for the live two-laptop rehearsal.

Endpoint table: [C2 REST API](api/rest.md).

---

## Demo Path F: NexusGate Verification WebUI (Phase 2 — issue #65; not pitch UI) {#demo-path-f-nexusgate-verification-webui-phase-2--issue-65-not-pitch-ui}

Browser Screen 1 / Screen 2 served by Core itself (Jinja2/HTMX at `/verify`). **Not** the external BattlePlan pitch UI. No Node/Next.js required.

**SIA server is not required** for this path — Screen 1 “Ingress Sentinel / Dual-SAR fixture” uses repo fixtures. Live SIA (`:5050`) / GLINT mock (`:5051`) are optional. Details: [E2E verification](verify-e2e.md).

```bash
uv run sdth-c2-server
# open http://127.0.0.1:8080/verify
# Screen 1: /verify/command · Screen 2: /verify/recipient (two tabs)
```

| Step | Where | Action |
|------|-------|--------|
| 1 | Screen 1 `/verify/command` | Propose `S2` → Approve |
| 2 | Screen 2 `/verify/recipient` | Auto-poll inbox (HTMX 2s) → Ack |
| 3 | Optional | Screen 1 → Ingress Dual-SAR / Sentinel fixture → evidence chips |

Invariant: the UI never seals tokens — only Core `POST /api/gate/approve` does.

---

## Demo Path: Sentinel-Imagery-Analysis → C2 (issue #47)

In-house SAR × AIS dark-vessel **ingress** (HTTP / fixture payloads into C2). Architecture: [SAR Pipeline](architecture/sar_pipeline.md). Upstream is a **sibling checkout** (`~/work/Sentinel-Imagery-Analysis`) — not a submodule.

**SIA is data linkage, not a required always-on C2 service.** Default demos use the Singapore Strait fixture (no SIA process). Running `python app.py` on `:5050` is only for live `pull_upstream`. Full matrix: [E2E verification](verify-e2e.md).

**Pattern A (CI / venue primary)** — recorded Singapore Strait `run_cv` fixture (**no SIA server**):

```bash
uv run sdth-c2-server
uv run python scripts/sentinel_ingress_smoke.py
# or:
curl -s -X POST http://127.0.0.1:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' -d '{"use_sentinel_fixture":true}'
```

**Pattern B** — local upstream on `:5050`, C2 on `:8080`; unreachable upstream falls back to the same fixture:

```bash
# Terminal A (sibling repo)
cd ~/work/Sentinel-Imagery-Analysis && python app.py   # PORT=5050

# Terminal B
export SAR_UPSTREAM_URL=http://127.0.0.1:5050
export SAR_UPSTREAM_SCAN=<your_scan_folder>
uv run sdth-c2-server
uv run python scripts/sentinel_ingress_smoke.py --pull
```

Only `correlation_status == "uncorrelated"` detections become `UNANNOUNCED_DARK_VESSEL` with `ais_absent=true`.

### AIS correlate then C2 (live scan)

Without AIS in Sentinel’s DB, every detection stays `uncorrelated`. Pick an **AIS source profile**, re-run `run_cv`, then push only dark vessels to C2.

AIS is ingested **by SIA itself** (`POST /api/ingest_ais` / plugins) into **SIA local SQLite** (`data.db`). C2 never stores raw AIS.

| `--ais-source` | When | What happens |
|----------------|------|----------------|
| **`demo`** (default; alias `friends`) | Pitch / venue with network | Sentinel `AISFriendsPlugin` live bbox scrape → SIA SQLite |
| **`offline`** (alias `mock`) | CI / airplane | Sentinel `MockAISPlugin` synthetic tracks → SIA SQLite |

- **demo** — live community HTTP API via Sentinel’s scraper registry. Omits historical `pass_time` on ingest (live feeds have no Sep-2026 pings); `run_cv` still correlates spatially.
- **offline** — synthetic AIS for CI / zero-network.

```bash
# Prerequisites
#   Terminal A: cd ~/work/Sentinel-Imagery-Analysis && python app.py   # :5050, COP_* in .env
#   Terminal B: uv run sdth-c2-server                                   # :8080

# Demo (recommended for pitch)
uv run python scripts/sentinel_ais_correlate.py \
  --scan 20260916_224721_162544676155 \
  --ais-source demo \
  --ingest-c2 --reset-c2

# Offline / CI
uv run python scripts/sentinel_ais_correlate.py \
  --scan 20260916_224721_162544676155 \
  --ais-source offline --ingest-c2
```

| Flag | Role |
|------|------|
| `--scan` / `SAR_UPSTREAM_SCAN` | Sentinel scan folder under `static/output/` |
| `--ais-source` | `demo` \| `offline` (env `AIS_SOURCE`) |
| `--plugin` | Override Sentinel scraper name |
| `--skip-ais-ingest` | Reuse AIS already in Sentinel DB |
| `--ais-correlation-distance` | Match radius in meters (default 100) |
| `--ingest-c2` | `POST /api/ingress/candidate-event` with raw `run_cv` |
| `--reset-c2` | Clear Core ontology before ingest |
| `--save-run-cv PATH` | Write raw `run_cv` JSON for inspection |

Manual equivalent (demo / offline scrapers only):

```bash
# 1) AIS for scan bbox + pass time (acquisition datetime)
curl -s -X POST http://127.0.0.1:5050/api/ingest_ais \
  -H 'content-type: application/json' \
  -d '{"bbox":[103.8,1.22,103.9,1.3],"plugin":"AISFriendsPlugin","pass_time":"2026-09-16T22:47:21Z"}'

# 2) CV + correlate
curl -s -X POST http://127.0.0.1:5050/api/run_cv/<scan_folder> \
  -H 'content-type: application/json' \
  -d '{"threshold":40,"dem_land_mask_enabled":false,"ais_correlation_distance":100}'

# 3) Dark vessels only → C2 (or use the script --ingest-c2)
```

After a successful correlate, `correlated_count` rises and `uncorrelated_count` (C2 dark-vessel count) falls.

---

## Demo Path B: 19-Event Temporal Streamer

Play T-60s → T-00s sensor ingress incrementally (PS 04 temporal alignment), not a one-shot `build_events()` dump:

```bash
uv run python scripts/stream_events.py                  # S2 hero, local ontology
uv run python scripts/stream_events.py --scenario S1
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

---

## Demo Path C: UI-less Picture→Tasking Demo (Pitch-4)

One-shot S2 loop: **Warning Picture → approve → inbox → Ack → audit**. Prints each hop and asserts `recipient_ack` is sealed in the OCSF hash chain. Local target: approve→ack **< 3 s**.

```bash
./scripts/picture_to_tasking.sh          # starts local sdth-c2-server, then runs demo
# or two terminals:
uv run sdth-c2-server                    # Terminal A
uv run python scripts/picture_to_tasking.py   # Terminal B

C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev C2_API_TOKEN='…' \
  ./scripts/picture_to_tasking.sh
# Cloudflare down:
uv run sdth-c2-server && unset C2_BASE_URL C2_API_TOKEN && ./scripts/picture_to_tasking.sh

INTERPRET=1 ./scripts/picture_to_tasking.sh   # interpreter overlay (LiteLLM if Core has LLM_BASE_URL)
```

`BASE_URL` is accepted as an alias of `C2_BASE_URL` by the Python client.

---

## Demo Path D: Live LLM via LiteLLM

**Probabilistic proposes; deterministic disposes.** Stands up LiteLLM as the OpenAI-compatible front door and proves `POST /api/interpret` returns `source: "llm"`. CI stays LLM-free (heuristic fallback when `LLM_BASE_URL` is unset or LiteLLM is down).

Keys, aliases, and master-key rules: **[LiteLLM](litellm.md)**.

```bash
cp deploy/litellm/.env.example deploy/litellm/.env   # set GEMINI_API_KEY for live smoke
cp .env.example .env
uv sync --group litellm
set -a && source deploy/litellm/.env && set +a
uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000
# other terminal:
./scripts/litellm_interpret_smoke.sh                 # S2 → source == "llm" via gemini-3.8-flash
```

---

## Demo Path E: Cloudflare Containers Core (Pitch-day HTTPS)

Same handshake over a Worker → container singleton (`getByName("demo")`). Runbook: [Cloudflare Containers](deploy.md).

```bash
cd deploy/cloudflare && npm install && cp .dev.vars.example .dev.vars && npx wrangler dev
# other terminal (shared Bearer from .dev.vars / wrangler secret):
C2_BASE_URL=http://127.0.0.1:8787 C2_API_TOKEN=dev-shared-c2-token ./scripts/picture_to_tasking.sh

# after `npx wrangler deploy` (+ C2_API_TOKEN secret):
C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev C2_API_TOKEN='…' \
  ./scripts/picture_to_tasking.sh
```

Cloudflare down → `uv run sdth-c2-server` (do not set `C2_BASE_URL` / `C2_API_TOKEN`). Auth: [deploy.md](deploy.md#shared-bearer-auth-issue-38).

---

## Effector levels

1. **Mock REST** — `app/mock_server.py` (`EFFECTOR_BASE_URL`, default `http://127.0.0.1:8000`; `CLEARBOT_BASE_URL` still accepted)
2. **2D kinematics** — lat/lon toward waypoint after approve
3. **RasPi GPIO** — optional secondary proof on Ack (issue #20)

### Optional RasPi Ack blink (stretch, Screen 2 client)

GPIO runs on the **recipient laptop / RasPi**, not inside Core (Cloudflare has no GPIO).

```bash
# After a successful Screen 2 Ack (curl or script) on the Pi-side machine:
export RASPI_ACK_BLINK=1          # or RASPI_GPIO=1
# export RASPI_LED_PIN=17         # BCM pin; default 17
uv run python scripts/raspi_ack_blink.py

# Or one-shot demo (blinks locally after Core returns ACKED):
RASPI_ACK_BLINK=1 ./scripts/picture_to_tasking.sh
```

- hardware present → `blinked: true` (LED pulsed)
- no `RPi.GPIO` / no Pi → `blinked: false`, `hardware: unavailable` (no-op; CI-safe)
- unset env → no blink attempt

CLI Level-3 dispatch path: `./scripts/raspi-run.sh` (same adapter).

`ClearbotRestAdapter` remains a thin alias of `UsvRestAdapter` for older imports.

---

## Slide 11 benchmarks

Prove gate latency, fail-closed unauthorized rejects, picture-to-ack, and audit integrity:

```bash
uv run python scripts/benchmark.py
uv run python scripts/benchmark.py --tracks 150   # Pitch-3 flood size
uv run python scripts/benchmark.py --help
```

| Metric | Target |
|--------|--------|
| Gate latency (p95) | < 50 ms (100 COA evals) |
| Interlock fast-reject (p95) | < 5 ms |
| Unauthorized taskings | 0 (geofence / speed / duplicate / timeout) |
| Track-flood stress (gate p95) | < 50 ms under **100+** synthetic tracks |
| Track-flood unauthorized | 0 under flood |
| Picture-to-Ack roundtrip | < 3.0 s |
| Audit trace integrity | 100% hash-chain |

Exits non-zero if any metric misses its target (CI + live demo). Pitch-3 flood is on by default (`--skip-stress` to omit).

---

## Tests

```bash
uv run pytest tests/unit/ -q                        # unit
uv run pytest tests/integration/ -v -m integration  # S2 + C2 two-screen / live HTTP
uv run python scripts/stream_events.py --fast       # 19-step temporal playback
uv run python scripts/benchmark.py                  # Slide 11 proof
uv run python scripts/sentinel_ingress_smoke.py     # Sentinel fixture ingress (#47)
uv run python scripts/sentinel_ais_correlate.py --help  # AIS → run_cv → optional C2
./scripts/litellm_interpret_smoke.sh                # live LiteLLM (optional; not in CI)
```

CI runs unit, integration, benchmark, and streamer (`--fast`) jobs on every push/PR.

## Local docs preview

```bash
pip install "mkdocs-material>=9.5,<10"
mkdocs serve
```
