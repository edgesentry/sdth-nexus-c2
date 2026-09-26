# C2 REST API (frozen contract)

**Status:** Phase 2 freeze · source of truth for curl / TUI / scripts and NexusGate verify UI (`/verify` (Jinja2/HTMX on `sdth-c2-server`); `BASE_URL` / `C2_BASE_URL` swap only — **paths do not change**).

Scenario IDs and pitch order: **[scenarios.md](../scenarios.md)** (Pillar 1 `S2_osint_swarm` → Pillar 2 `S1_trojan` → Pillar 3 `S3_sar_ais`). Use **full** registry IDs — shorthand `S2` / `S3` is not accepted by Core.

| Item | Value |
|------|--------|
| Server | `app/c2_server.py` |
| CLI | `uv run sdth-c2-server` |
| Default base | `http://127.0.0.1:8080` (local) or `C2_BASE_URL` (Cloudflare HTTPS) |
| Proof | `tests/unit/test_c2_server.py`, `tests/unit/test_c2_rest_contract.py`, `tests/integration/test_s2_c2_e2e.py`, `tests/integration/test_archview_contract_e2e.py` |

Screen 1 = command · Screen 2 = recipient. No BattlePlan required for Phase 2 demos.

> **API Documentation Suite:**
> - **[Core C2 REST API](rest.md)** (this document): Command & Recipient handshake, Gating, DecisionTokens, and Audit trails.
> - **[Upstream Ingress & Feeds](ingress.md)**: CandidateEvent wire format, SAR anomalies, GLINT mock, and open AIS/air streams.
> - **[Shared Schemas & Data Types](schemas.md)**: Canonical object definitions for `CourseOfAction`, `DecisionToken`, `Finding`, and tracks.
> - **[Admin & Diagnostics](admin.md)**: Zero-state reset, health probes, and OCSF audit chain tamper verification.

## Endpoints

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/ontology/state` | Live tracks, observations, amber alert |
| `POST` | `/api/interpret` | Probabilistic propose: hypotheses + candidate COA (**never seals**) |
| `POST` | `/api/ingress/candidate-event` | Upstream CandidateEvent / Dual-SAR / GLINT / SIA → Observations |
| `POST` | `/api/ingress/open-feed` | Optional open AIS / open air → Observations (fixture or payload) |
| `POST` | `/api/gate/proposals` | Queue COA (`scenario_id`, raw `coa`, or `interpret:true`) |
| `POST` | `/api/gate/demo-evaluate-with-guardrail` | Pillar 2: CNI VETO Option A → queue Option B for HITL |
| `POST` | `/api/gate/approve` | Operator y/n → sealed `DecisionToken` |
| `GET` | `/api/recipient/inbox?unit_id=` | Pending approved taskings |
| `POST` | `/api/recipient/ack` | Recipient ack sealed to audit chain |
| `GET` | `/api/audit/trail` | OCSF-shaped hash-chain records |
| `GET` | `/api/audit/health` | Hash-chain integrity summary (`verified` / `broken` / `count` / `label`) |
| `POST` | `/api/admin/reset` | Clear in-memory runtime (tests / demos) |

Operational (not frozen handshake): `GET /health`, `PUT /api/admin/audit/snapshot`, `POST /api/admin/audit/tamper|restore|reverify` (demo-only; `C2_DEMO_TAMPER=1`), `GET /static/fixtures/*` (demo evidence chips for BattlePlan) — see [Cloudflare Containers](../deploy.md) · [Demo Path F](../demo.md#demo-path-f-nexusgate-verification-webui-phase-2--issue-65-not-pitch-ui).

Local Core enables CORS for browser consoles (`C2_CORS_ORIGINS`; default includes `localhost:3000` NexusGate verify UI, `localhost:3001` ARCHVIEW Vite, and `localhost:5173` generic Vite). Prefer a Vite proxy for ARCHVIEW local dev; CORS is for direct-origin demos. Cloudflare Worker attaches CORS headers on all responses (including Bearer `401`).

## Handshake (curl)

Two-laptop / two-terminal cold start (Screen 1 propose+approve, Screen 2 inbox+ack): [Demo Path A](../demo.md#demo-path-a-two-laptop-two-terminal-io-issue-17). Compact single-shell form:

```bash
uv run sdth-c2-server

curl -s -X POST localhost:8080/api/gate/proposals \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"S2_osint_swarm","unit_id":"CUE-NODE-01"}'

curl -s -X POST localhost:8080/api/gate/approve \
  -H 'content-type: application/json' \
  -d '{"coa_id":"<id>","decision":"y"}'

curl -s 'localhost:8080/api/recipient/inbox?unit_id=CUE-NODE-01'

curl -s -X POST localhost:8080/api/recipient/ack \
  -H 'content-type: application/json' \
  -d '{"coa_id":"<id>","unit_id":"CUE-NODE-01"}'

curl -s localhost:8080/api/audit/trail
```

One-shot helper: `./scripts/picture_to_tasking.sh` (see [Demo](../demo.md)). Cloudflare: same paths via `C2_BASE_URL` + Bearer ([deploy.md](../deploy.md)).

---

## `GET /api/ontology/state`

No body. Returns the live ontology snapshot after the last successful scenario load / proposal.

**Response `200`**

```json
{
  "scenario_id": "S2_osint_swarm",
  "tracks": [
    {
      "track_id": "OSINT-SWARM-CLAIM",
      "latitude": 1.3618,
      "longitude": 103.99,
      "speed_mps": 46.3,
      "confidence": 0.84,
      "source_ids": ["CIVILIAN_SOCIAL_RECON", "GAP_FILLER_RADAR"],
      "modalities": ["social", "radar"],
      "updated_at": "2026-09-17T15:11:50.207304+00:00",
      "attributes": {}
    }
  ],
  "observations": [
    {
      "observation_id": "<uuid>",
      "source_id": "CIVILIAN_SOCIAL_RECON",
      "entity_hint": "OSINT-SWARM-CLAIM",
      "latitude": 1.351,
      "longitude": 103.99,
      "altitude_m": null,
      "speed_mps": 0.0,
      "heading_deg": null,
      "confidence": 0.55,
      "observed_at": "2026-09-17T15:11:07.207304Z",
      "modality": "social",
      "attributes": {},
      "raw_digest": "<hex>"
    }
  ],
  "amber_alert": {
    "alert": "COUNT_AND_BEARING_MISMATCH",
    "threat_class": "attritable_air_incursion",
    "mismatch_m": 1200.9,
    "picture_summary": "…",
    "source_breakdown": {},
    "scenario_id": "S2_osint_swarm"
  },
  "pending_proposals": ["<coa_id>"],
  "inbox_depth": 0
}
```

Cold start: `scenario_id` / `amber_alert` are `null`; `tracks` / `observations` / `pending_proposals` are empty; `inbox_depth` is `0`.

!!! note "Field naming: `alert` vs `amber_alert`"
    Ontology envelope (`GET /api/ontology/state` → `amber_alert`) uses the key **`alert`** for the contradiction class
    (see `app/c2_server.py`). The serialized `Finding` on proposals uses **`amber_alert`** for the same string value
    (`app/scenarios/base.py`). Phase 3 UI must bind both names — do not assume one schema for both payloads.

---

## `POST /api/interpret`

Probabilistic app-layer propose (Pitch-2). Returns scored hypotheses + a **candidate** COA.
**Never seals a `DecisionToken`.** Core gate remains the only authority that can approve.

### Request

```json
{
  "scenario_id": "S2_osint_swarm",
  "timeout_seconds": 5.0,
  "force_heuristic": true
}
```

| Field | Notes |
|-------|--------|
| `scenario_id` | Required. Loads scenario events → Finding → interpreter |
| `force_heuristic` | Skip LLM even if `LLM_BASE_URL` is set |
| `timeout_seconds` | Passed through to candidate COA construction |

Env: `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_TIMEOUT_S`. Unset or failed LLM → heuristic fallback.

Live path (issue #32): point C2 at LiteLLM (`deploy/litellm/`):

```bash
set -a && source deploy/litellm/.env && set +a
uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000
# other terminal:
export LLM_BASE_URL=http://127.0.0.1:4000/v1
export LLM_API_KEY=sk-litellm-local          # must equal LITELLM_MASTER_KEY (proxy lock, not Gemini)
export LLM_MODEL=gemini-3.8-flash
uv run sdth-c2-server
./scripts/litellm_interpret_smoke.sh          # asserts source == "llm" (Gemini 3.8 Flash)
```

OpenAI (`gpt-4o-mini` / `OPENAI_API_KEY`), Anthropic (`claude-haiku` / `ANTHROPIC_API_KEY`), Google Gemini (`gemini-3.8-flash` / `GEMINI_API_KEY`), and Fireworks (`fireworks-glm` / `FIREWORKS_AI_API_KEY`) are LiteLLM **upstream** backends. `LLM_API_KEY` is the proxy lock (`LITELLM_MASTER_KEY`) — see [LiteLLM keys](../litellm.md). Live smoke pins Gemini.

**Probabilistic proposes; deterministic disposes** — this endpoint never seals a `DecisionToken`. See [Demo Path D](../demo.md#demo-path-d-live-llm-via-litellm).

### Response `200`

```json
{
  "status": "INTERPRETED",
  "source": "heuristic",
  "model": null,
  "error": null,
  "hypotheses": [
    {
      "label": "sensor_contradiction",
      "claim": "Amber COUNT_AND_BEARING_MISMATCH: …",
      "confidence": 0.8,
      "supports_threat": true,
      "modality_hints": ["social", "radar"]
    }
  ],
  "confidence": 0.8,
  "picture_summary": "…",
  "adversarial_hypothesis": "…",
  "candidate_coa": { "...": "CourseOfAction" },
  "finding": { "...": "Finding" }
}
```

Feed `candidate_coa` into `POST /api/gate/proposals` — gate may still `REJECTED_FAST`.

---

## `POST /api/gate/demo-evaluate-with-guardrail`

Pillar 2 (`S1_trojan`) demo path: load the scenario as a dangerous terminal-SAM draft,
run live CNI debris interlocks (HARD VETO), and queue enforced Option B for HITL approve.
Plain `POST /api/gate/proposals` with `S1_trojan` returns `REJECTED_FAST` by design.

### Request

```json
{
  "scenario_id": "S1_trojan",
  "unit_id": "GBAD-RSAF-01",
  "navy_unit_id": "PCG-PT-44"
}
```

### Response `200`

```json
{
  "status": "GUARDRAIL_VETO_OPTION_B_QUEUED",
  "veto_code": "SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD",
  "veto_reason": "…",
  "fallback_coa": {
    "coa_id": "<uuid>",
    "intent": "OFFSHORE_INTERCEPT_RF_SOFTKILL"
  },
  "finding": { "…": "Finding" },
  "queued_for": ["GBAD-RSAF-01", "PCG-PT-44"]
}
```

Authorize with `POST /api/gate/approve` on `fallback_coa.coa_id`. Full curl: [verify-e2e.md](../verify-e2e.md) Workflow 3b.

---

## `POST /api/gate/proposals`

### Request

Provide **either** `scenario_id` **or** raw `coa` (not neither). Optional `interpret:true` runs the
probabilistic interpreter first, then queues its candidate COA (response may include `hypotheses`).

```json
{
  "scenario_id": "S2_osint_swarm",
  "unit_id": "CUE-NODE-01",
  "timeout_seconds": 30,
  "interpret": true,
  "force_heuristic": true
}
```

Raw COA (fields from `core.coa.CourseOfAction`):

```json
{
  "coa": {
    "target_entity_id": "x",
    "target_coordinates": [1.35, 103.85],
    "intent": "ISR_IDENTIFY_CONTACT",
    "confidence": 0.9,
    "corroborating_sources": ["A", "B"],
    "raw_input_digest": "<64-char hex>",
    "speed_kt": 5.0,
    "tier": 1,
    "timeout_seconds": 5.0
  },
  "unit_id": "USV-01"
}
```

Defaults: `unit_id=ISR-NODE-01`; `timeout_seconds` falls back to policy default.

### Responses `200`

| `status` | When | Notes |
|----------|------|--------|
| `QUEUED` | Tier-1 HITL passed interlocks | Awaiting `POST /api/gate/approve` |
| `APPROVED` | Tier-0 autonomous | Token sealed; inbox already populated |
| `REJECTED_FAST` | Deterministic interlock fail | Sealed deny token; nothing queued |

**`QUEUED`**

```json
{
  "status": "QUEUED",
  "coa": { "coa_id": "<uuid>", "tier": 1, "intent": "GNSS_DENIAL_AND_GBAD_CUE", "…": "…" },
  "finding": {
    "scenario_id": "S2_osint_swarm",
    "amber_alert": "COUNT_AND_BEARING_MISMATCH",
    "threat_class": "attritable_air_incursion",
    "mismatch_m": 1200.9,
    "picture_summary": "…",
    "source_breakdown": {}
  }
}
```

**`APPROVED`** (Tier-0 autonomous — inbox already populated; no separate approve call)

```json
{
  "status": "APPROVED",
  "coa": { "coa_id": "<uuid>", "tier": 0, "…": "…" },
  "token": {
    "token_id": "<uuid>",
    "coa_id": "<uuid>",
    "verdict": "APPROVED",
    "issued_at": "…",
    "operator_id": "autonomous",
    "reason": "tier0_auto",
    "digest": "<sha256 hex>"
  },
  "finding": null
}
```

**`REJECTED_FAST`**

```json
{
  "status": "REJECTED_FAST",
  "reason": "Geofence…",
  "coa": { "coa_id": "<uuid>", "…": "…" },
  "token": {
    "token_id": "<uuid>",
    "coa_id": "<uuid>",
    "verdict": "REJECTED_FAST",
    "issued_at": "…",
    "operator_id": null,
    "reason": "Geofence…",
    "digest": "<sha256 hex>"
  }
}
```

### Errors

| Code | Detail |
|------|--------|
| `400` | Neither `scenario_id` nor `coa` |
| `404` | Scenario loads but yields no finding |

---

## `POST /api/gate/approve`

### Request

```json
{
  "coa_id": "<uuid>",
  "decision": "y",
  "operator_id": "operator"
}
```

`decision`: `y` / `yes` / `approve` / `approved` **or** `n` / `no` / `deny` / `denied` / `reject` / `rejected`.  
Default `operator_id`: `"operator"`.

### Response `200`

```json
{
  "status": "APPROVED",
  "coa": { "coa_id": "<uuid>", "…": "…" },
  "token": {
    "token_id": "<uuid>",
    "coa_id": "<uuid>",
    "verdict": "APPROVED",
    "issued_at": "…",
    "operator_id": "operator",
    "reason": "operator_approve",
    "digest": "<sha256 hex>"
  }
}
```

On approve, a tasking is written to the recipient inbox (`status: PENDING_ACK`).

**`REJECTED_OPERATOR`** (operator deny — no inbox entry)

```json
{
  "status": "REJECTED_OPERATOR",
  "coa": { "coa_id": "<uuid>", "…": "…" },
  "token": {
    "token_id": "<uuid>",
    "coa_id": "<uuid>",
    "verdict": "REJECTED_OPERATOR",
    "issued_at": "…",
    "operator_id": "operator",
    "reason": "operator_deny",
    "digest": "<sha256 hex>"
  }
}
```

### Errors

| Code | Detail |
|------|--------|
| `400` | `decision` not approve/deny |
| `404` | No pending proposal for `coa_id` |

---

## `GET /api/recipient/inbox`

### Query

| Param | Required | Description |
|-------|----------|-------------|
| `unit_id` | yes | Recipient unit; must match proposal `unit_id` |

### Response `200`

```json
{
  "unit_id": "CUE-NODE-01",
  "count": 1,
  "taskings": [
    {
      "coa": { "coa_id": "<uuid>", "…": "…" },
      "token": { "digest": "<hex>", "verdict": "APPROVED", "…": "…" },
      "unit_id": "CUE-NODE-01",
      "issued_at": "…",
      "status": "PENDING_ACK"
    }
  ]
}
```

Acked COAs are omitted (`count` drops to `0` after a successful ack).

---

## `POST /api/recipient/ack`

### Request

```json
{
  "coa_id": "<uuid>",
  "unit_id": "CUE-NODE-01",
  "message": "on station",
  "telemetry": { "mode": "cue" },
  "status": "ACKED",
  "signature": null
}
```

Optional `signature`: if omitted, server seals a SHA-256 over `{coa_id, unit_id, status, time}`.  
Defaults: `status=ACKED`, `message=""`, `telemetry={}`.

### Response `200`

```json
{
  "status": "ACKED",
  "ack": {
    "ack_id": "<uuid>",
    "coa_id": "<uuid>",
    "unit_id": "CUE-NODE-01",
    "status": "ACKED",
    "message": "on station",
    "telemetry": { "mode": "cue" },
    "signature": "<hex>",
    "token_digest": "<hex>",
    "acked_at": "…"
  },
  "audit_hash": "<hex>"
}
```

Appends OCSF activity `recipient_ack` on the hash chain (`GET /api/audit/trail`).

**Optional stretch (issue #20):** GPIO blink is a **Screen 2 client** concern (`RASPI_ACK_BLINK=1` → `scripts/raspi_ack_blink.py` or `picture_to_tasking`), not Core. Cloudflare / local Core leave Ack telemetry unchanged unless the client sends fields in the request body.

### Errors

| Code | Detail |
|------|--------|
| `403` | `unit_id` does not match tasking |
| `404` | No inbox item for `coa_id` |

---

## `GET /api/audit/trail`

No body. Reads `.audit/gate.jsonl` (path may differ under tests).

### Response `200`

```json
{
  "count": 4,
  "path": ".audit/gate.jsonl",
  "records": [
    {
      "class_name": "Security Finding",
      "activity_name": "recipient_ack",
      "severity": "High",
      "time": "…",
      "metadata": {},
      "prev_hash": "<64 hex>",
      "hash": "<64 hex>"
    }
  ]
}
```

Typical activity names in a full handshake: `coa_proposed` → `gate_decision` → `tasking_issued` → `recipient_ack` (plus `coa_rejected_fast` / `coa_auto_approved` when applicable). Chain: record `i.prev_hash ==` record `i-1.hash`; genesis `prev_hash` is `0` × 64.

---

## `GET /api/audit/health`

No body. Same semantics as the NexusGate verify UI `_ocsf_health` pill, exposed as frozen REST so ARCHVIEW does not scrape `/verify`.

### Response `200`

```json
{
  "verified": true,
  "broken": 0,
  "count": 4,
  "label": "0 of 4"
}
```

| Field | Type | Notes |
|-------|------|--------|
| `verified` | boolean | `true` when the SHA-256 OCSF chain walks clean |
| `broken` | number | Count of integrity errors (0 when verified) |
| `count` | number | Total audit records (`verify_audit_chain` total) |
| `label` | string | Display string, e.g. `"0 of 4"` / `"1 of 4"` |

Vite proxy remains the preferred local path for ARCHVIEW; this endpoint is for the audit health pill (and direct-origin demos via CORS).

---

## `POST /api/admin/reset`

No body.

### Response `200`

```json
{ "status": "reset" }
```

Clears in-memory ontology, findings, proposals, inbox, ack sets, and soft-duplicate interlock keys. **Does not** wipe disk audit (`.audit/gate.jsonl`). If that file’s hash chain is broken (e.g. head truncated), Core quarantines it to `gate.jsonl.broken-<UTC>` on startup and starts a fresh genesis chain.

---

## `GET /health`

Operational readiness (Docker smoke, `wrangler dev`, laptop scripts). **Not** part of the frozen Screen 1/2 handshake.

**Response `200`**

```json
{ "status": "ok" }
```

---

## Operational & Admin Endpoints

Operational diagnostics, zero-state resets, and audit tampering simulation endpoints are documented in **[Admin & Diagnostics API](admin.md)**.

| Endpoint | Method | Role |
|----------|--------|------|
| `/health` | `GET` | Container / CLI readiness probe |
| `/api/admin/reset` | `POST` | Reset graph, proposals, and taskings to zero-state |
| `/api/admin/audit/snapshot` | `PUT` | Hydrate on-disk OCSF log (Cloudflare Worker cold start) |
| `/api/admin/audit/tamper` | `POST` | Simulate audit hash chain tampering (`C2_DEMO_TAMPER=1`) |
| `/api/admin/audit/restore` | `POST` | Restore pre-tamper OCSF audit snapshot (`C2_DEMO_TAMPER=1`) |
| `/api/admin/audit/reverify` | `POST` | Re-verify in-process SHA-256 + out-of-process EDS sidecar |

Full request/response examples and error modes: **[Admin & Diagnostics Documentation](admin.md)**.

---

## Shared types (stable fields)

Complete field descriptions, data constraints, and model specifications are documented in **[Shared Schemas & Data Types](schemas.md)**.

- **[`CourseOfAction`](schemas.md#1-courseofaction-coa)**: Proposed tactical action with action tier (`0` auto / `1` single-operator / `2` dual-key), timeout, confidence, and safety invariants.
- **[`DecisionToken`](schemas.md#2-decisiontoken-token)**: Cryptographically sealed authorization token (SHA-256) issued strictly by Nexus Gate upon operator approval.
- **[`Finding`](schemas.md#3-finding-proposal-finding)**: Probabilistic threat interpretation, spatial mismatch, amber alert classification, and multi-sensor evidence breakdown.
- **[`Track`](schemas.md#4-track-ontologytracks)**: Live fused or segregated entity track in the `SpatialEntityGraph`.
- **[`Observation`](schemas.md#5-observation-ontologyobservations)**: Atomic sensor measurement or intelligence report ingested from radar, AIS, SAR, acoustic, or OSINT feeds.
- **[`AckRecord`](schemas.md#6-ackrecord-ack-on-recipient-response)**: Closed-loop execution acknowledgment returned by assigned field effectors.

TypeScript interface definitions: [`archview-types.ts`](archview-types.ts).

---

## Client binding (Phase 3)

```bash
export C2_BASE_URL=http://127.0.0.1:8080
# or Cloudflare:
# export C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev
# BASE_URL is accepted by scripts/picture_to_tasking.py
```

Paths above are the frozen surface. UI clients must not invent alternate routes for Screen 1 / Screen 2 handshake.

### ARCHVIEW connection

ARCHVIEW (external repo, Vite on **`127.0.0.1:3001`**) talks to Core on **`:8080`** via the frozen REST above.

| Topic | Guidance |
|-------|----------|
| Preferred local path | Vite `server.proxy` toward Core `:8080` (avoids CORS). Direct browser → Core is supported via default `C2_CORS_ORIGINS` (`:3001` included). |
| Proxy collision | ARCHVIEW already proxies `/api` → its own evidence BFF (`:3102`). Do **not** replace that wholesale — use path splits (`/api/ontology/*`, `/api/gate/*`, `/api/audit/*`, `/api/recipient/*`, `/static/fixtures`) or a `/c2` prefix to Core (#95). |
| Polling | 1–2 s poll of ontology / audit health. No WebSocket on Core for this epic. |
| Field naming | Ontology amber object uses **`alert`**; Finding uses string **`amber_alert`**. Approve body uses **`operator_id`** (effector `unit_id` is set at proposals / inbox). |
| TypeScript contract | Hand-written [`archview-types.ts`](archview-types.ts) — copy/import into ARCHVIEW; do not generate from `/openapi.json` (responses are still `dict[str, Any]`). After Core contract changes, re-copy/patch into ARCHVIEW (`src/nexusgate/archview-types.ts`), preserve ARCHVIEW-only types (`LeadPoi`, `ProposalRequest`), then `npm run typecheck`. |
| Token seal | DecisionToken / OCSF chain use **SHA-256** digests for this epic (not Ed25519/BLAKE3). |
| Hero S3 rehearsal | [Path ARCHVIEW](../verify-e2e.md#path-archview-hero-s3--issue-99) (#99) — Screen-1 ARCHVIEW + Screen-2 abort (`/verify/recipient` or curl). |

!!! tip "Follow-up (Phase 3): Pydantic response models"
    Endpoints currently return ad-hoc `dict[str, Any]`, so `/openapi.json` lacks response schemas.
    Introduce response models (`OntologyStateResponse`, `ApproveResponse`, …) later to auto-validate
    outgoing payloads and enable TypeScript client generation for BattlePlan.

---

## Upstream Ingress Contract (Assumed CandidateEvent Specification)

Upstream sensor ingress specifications, candidate event wire payloads, and open feeds are fully detailed in **[Upstream Ingress & Feeds](ingress.md)**.

- **`POST /api/ingress/candidate-event`**: Macro intelligence ingress for space-based SAR scene-difference anomaly evidence, Sentinel-1 micro CV detections, and GLINT mock integration. Supports offline fixtures, upstream polling, and Dual-SAR composite corroboration.
- **`POST /api/ingress/open-feed`**: Optional open AIS (Indago DuckDB / live / fixture) or open air (ADS-B) sensor streams.
- **Wire format & field mappings**: Complete `CandidateEvent` v1.3.0 schema and mapping table to `Observation` entities.

See **[Upstream Ingress & Feeds Documentation](ingress.md)** for wire payloads, curl commands, and replay scripts.
