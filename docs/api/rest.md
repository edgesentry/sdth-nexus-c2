# C2 REST API (frozen contract)

**Status:** Phase 2 freeze · source of truth for curl / TUI / scripts and Phase 3 BattlePlan (`BASE_URL` / `C2_BASE_URL` swap only — **paths do not change**).

| Item | Value |
|------|--------|
| Server | `app/c2_server.py` |
| CLI | `uv run sdth-c2-server` |
| Default base | `http://127.0.0.1:8080` (local) or `C2_BASE_URL` (Cloudflare HTTPS) |
| Proof | `tests/unit/test_c2_server.py`, `tests/unit/test_c2_rest_contract.py`, `tests/integration/test_s2_c2_e2e.py` |

Screen 1 = command · Screen 2 = recipient. No BattlePlan required for Phase 2 demos.

## Endpoints

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/ontology/state` | Live tracks, observations, amber alert |
| `POST` | `/api/interpret` | Probabilistic propose: hypotheses + candidate COA (**never seals**) |
| `POST` | `/api/ingress/candidate-event` | Upstream assumed CandidateEvent → `space_sar` Observation |
| `POST` | `/api/ingress/open-feed` | Optional open AIS / open air → Observations (fixture or payload) |
| `POST` | `/api/gate/proposals` | Queue COA (`scenario_id`, raw `coa`, or `interpret:true`) |
| `POST` | `/api/gate/approve` | Operator y/n → sealed `DecisionToken` |
| `GET` | `/api/recipient/inbox?unit_id=` | Pending approved taskings |
| `POST` | `/api/recipient/ack` | Recipient ack sealed to audit chain |
| `GET` | `/api/audit/trail` | OCSF-shaped hash-chain records |
| `POST` | `/api/admin/reset` | Clear in-memory runtime (tests / demos) |

Operational (not frozen handshake): `GET /health`, `PUT /api/admin/audit/snapshot`, `GET /static/fixtures/*` (demo evidence chips for BattlePlan) — see [Cloudflare Containers](../deploy.md) · [Demo Path F](../demo.md#demo-path-f-nexusgate-verification-webui-phase-2--issue-65-not-pitch-ui).

Local Core enables CORS for BattlePlan (`C2_CORS_ORIGINS`, default `localhost:3000`). Cloudflare Worker attaches CORS headers on all responses (including Bearer `401`).

## Handshake (curl)

Two-laptop / two-terminal cold start (Screen 1 propose+approve, Screen 2 inbox+ack): [Demo Path A](../demo.md#demo-path-a-two-laptop-two-terminal-io-issue-17). Compact single-shell form:

```bash
uv run sdth-c2-server

curl -s -X POST localhost:8080/api/gate/proposals \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"S2","unit_id":"CUE-NODE-01"}'

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
  "scenario_id": "S2",
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
    "scenario_id": "S2"
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
  "scenario_id": "S2",
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

## `POST /api/gate/proposals`

### Request

Provide **either** `scenario_id` **or** raw `coa` (not neither). Optional `interpret:true` runs the
probabilistic interpreter first, then queues its candidate COA (response may include `hypotheses`).

```json
{
  "scenario_id": "S2",
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
  "coa": { "coa_id": "<uuid>", "tier": 1, "intent": "CUE_AND_IDENTIFY", "…": "…" },
  "finding": {
    "scenario_id": "S2",
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

## `POST /api/admin/reset`

No body.

### Response `200`

```json
{ "status": "reset" }
```

Clears in-memory ontology, findings, proposals, inbox, and ack sets. **Does not** wipe disk audit (`.audit/gate.jsonl`).

---

## `GET /health`

Operational readiness (Docker smoke, `wrangler dev`, laptop scripts). **Not** part of the frozen Screen 1/2 handshake.

**Response `200`**

```json
{ "status": "ok" }
```

---

## `PUT /api/admin/audit/snapshot`

Replace on-disk OCSF jsonl. Used by the Cloudflare Worker to hydrate the hash chain after ephemeral container disk reset. **Does not** mint `DecisionToken`s.

**Request**

```json
{ "records": [ { "class_name": "Security Finding", "hash": "…", "prev_hash": "…" } ] }
```

**Response `200`**

```json
{ "status": "restored", "count": 1 }
```

---

## Shared types (stable fields)

### `CourseOfAction` (`coa`)

| Field | Type | Notes |
|-------|------|--------|
| `coa_id` | string (uuid) | Client must echo into approve / ack |
| `tier` | `0` \| `1` \| `2` | Tier-0 may auto-approve |
| `target_entity_id` | string | |
| `target_coordinates` | `[lat, lon]` | |
| `intent` | string | e.g. `CUE_AND_IDENTIFY` |
| `timeout_seconds` | number | HITL window |
| `confidence` | number | |
| `corroborating_sources` | string[] | |
| `raw_input_digest` | string | |
| `speed_kt` | number \| null | Interlock input |
| `pre_conditions` / `post_conditions` / `invariants` / `metadata` | object | Opaque to clients |

### `DecisionToken` (`token`)

| Field | Type | Notes |
|-------|------|--------|
| `token_id` | string | |
| `coa_id` | string | |
| `verdict` | string | `APPROVED` / `REJECTED_FAST` / `REJECTED_OPERATOR` / … |
| `issued_at` | ISO-8601 | |
| `operator_id` | string \| null | |
| `reason` | string \| null | |
| `digest` | string | SHA-256 seal; empty only before seal |

### `Finding` (proposal `finding`)

| Field | Type | Notes |
|-------|------|--------|
| `scenario_id` | string | |
| `track_id` | string | |
| `threat_class` | string | |
| `warning_minutes_est` | number | |
| `mismatch_m` | number | |
| `confidence` | number | |
| `picture_summary` | string | |
| `adversarial_hypothesis` | string | |
| `spoof_sources` / `approach_sources` / `other_sources` | string[] | |
| `message` | string | |
| `amber_alert` | string \| null | Contradiction class — **not** the ontology key `alert` |
| `source_breakdown` | object | Modality → claim map |

### Track (`ontology.tracks[]`)

| Field | Type | Notes |
|-------|------|--------|
| `track_id` | string | |
| `latitude` / `longitude` | number | |
| `speed_mps` | number | |
| `confidence` | number | |
| `source_ids` | string[] | |
| `modalities` | string[] | e.g. `social`, `radar`, `optical` |
| `updated_at` | ISO-8601 \| null | |
| `attributes` | object | Opaque |

### Observation (`ontology.observations[]`)

| Field | Type | Notes |
|-------|------|--------|
| `observation_id` | string | |
| `source_id` | string | |
| `entity_hint` | string | |
| `latitude` / `longitude` | number | |
| `altitude_m` | number \| null | |
| `speed_mps` | number | |
| `heading_deg` | number \| null | |
| `confidence` | number | |
| `observed_at` | ISO-8601 | |
| `modality` | string | |
| `attributes` | object | |
| `raw_digest` | string | |

### AckRecord (`ack` on recipient ack response)

| Field | Type | Notes |
|-------|------|--------|
| `ack_id` | string (uuid) | |
| `coa_id` / `unit_id` | string | |
| `status` | string | usually `ACKED` |
| `message` | string | |
| `telemetry` | object | |
| `signature` | string | Client-supplied or server-sealed SHA-256 |
| `token_digest` | string | From the sealed DecisionToken |
| `acked_at` | ISO-8601 | |

---

## Client binding (Phase 3)

```bash
export C2_BASE_URL=http://127.0.0.1:8080
# or Cloudflare:
# export C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev
# BASE_URL is accepted by scripts/picture_to_tasking.py
```

Paths above are the frozen surface. UI clients must not invent alternate routes for Screen 1 / Screen 2 handshake.

!!! tip "Follow-up (Phase 3): Pydantic response models"
    Endpoints currently return ad-hoc `dict[str, Any]`, so `/openapi.json` lacks response schemas.
    Introduce response models (`OntologyStateResponse`, `ApproveResponse`, …) later to auto-validate
    outgoing payloads and enable TypeScript client generation for BattlePlan.

---

## Upstream Ingress Contract (Assumed CandidateEvent Specification)

The 7 core endpoints above govern the **downstream C2 decision, gating, and recipient handshake** and remain frozen.

For **upstream macro intelligence ingress** (such as space-based SAR scene-difference anomaly evidence), the C2 engine assumes an open, typed `CandidateEvent` payload structure (pending final schema file handover). This enables continuous, non-blocking development via local fixtures and mock adapters.

### Assumed Wire Payload (`CandidateEvent` v1.3.0)

```json
{
  "event_id": "evt_sar_20260918_001",
  "timestamp": "2026-09-18T14:30:00Z",
  "source_id": "SPACE_SAR_SCENE_DIFF",
  "area_id": "malacca_strait_sector_b",
  "event_type": "UNANNOUNCED_DARK_VESSEL_CLUSTER",
  "confidence": 0.88,
  "location": {
    "latitude": 1.254,
    "longitude": 103.812
  },
  "bounding_box": {
    "min_lat": 1.250,
    "max_lat": 1.258,
    "min_lon": 103.808,
    "max_lon": 103.816
  },
  "attributes": {
    "vessel_count_est": 2,
    "ais_correlation": "NONE",
    "diff_metric": "intensity_ratio_anomaly",
    "sar_pass_id": "S1_20260918_PASS_42"
  }
}
```

### Ingress to Observation Mapping

When ingested (either via upstream REST pull, optional `POST /api/ingress/candidate-event`, or local scenario fixture), the adapter maps the payload into an internal `Observation` entity:

| `CandidateEvent` Field | Internal `Observation` Target | Notes |
|------------------------|-------------------------------|-------|
| `event_id` | `observation_id` | Unique ingress identifier |
| `source_id` | `source_id` | e.g. `SPACE_SAR_SCENE_DIFF` |
| `event_type` | `entity_hint` | Used for track correlation |
| `location.latitude` | `latitude` | Spatial point |
| `location.longitude` | `longitude` | Spatial point |
| `confidence` | `confidence` | Normalized (0.0 to 1.0) |
| `timestamp` | `observed_at` | Ingress observation time |
| `"space_sar"` | `modality` | Explicit modality tag |
| `bounding_box` + `attributes` | `attributes` | Preserved for audit & operator display |

### Operational Assumptions
1. **Retrospective & Periodic Ingress:** The payload represents a discrete, verified evidence package derived from satellite passes, not a high-frequency live video feed.
2. **Non-Blocking Loose Coupling:** The C2 platform operates 100% stand-alone using synthetic fixture equivalents (`tests/fixtures/candidate_event_assumed.json`) if live upstream services are offline during hackathon operations.
3. **Transport Interfaces:** Supported via HTTP REST (`GET` pull or `POST` push) and compatible with Model Context Protocol (MCP) tool querying.

### `POST /api/ingress/candidate-event`

Push an assumed CandidateEvent, load the Pitch-1 offline fixture, ingest
**Sentinel-Imagery-Analysis** dark vessels (issue #47), pull **GLINT** Assumed-mock
(issue #55), or **Dual-SAR** corroborate GLINT × SIA (issue #56):

```bash
# Pitch-1 assumed CandidateEvent fixture
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"use_fixture":true}'

# Singapore Strait Sentinel run_cv fixture (uncorrelated only)
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"use_sentinel_fixture":true}'

# Pattern B: pull sibling upstream (default http://127.0.0.1:5050); fixture if down
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"pull_upstream":true}'

# GLINT Assumed-mock fixture (no HTTP)
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"use_glint_fixture":true}'

# GLINT pull (default http://127.0.0.1:5051); assumed fixture if down
#   uv run sdth-mock-glint   # or: uv run python scripts/mock_glint_server.py
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"pull_glint":true}'

# Dual-SAR: GLINT macro × SIA micro fixtures → composite (issue #56)
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"dual_sar":true}'

# Dual-SAR pull both; GLINT down → SIA/fixture fail-safe
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"pull_dual_sar":true}'
```

| Field | Role |
|-------|------|
| `event` | Assumed CandidateEvent v1.3.0 object |
| `use_fixture` | Load `tests/fixtures/candidate_event_assumed.json` |
| `use_sentinel_fixture` | Map `tests/fixtures/sentinel_run_cv_sg_strait.json` → dark vessels |
| `pull_upstream` | `POST {SAR_UPSTREAM_URL}/api/run_cv/{SAR_UPSTREAM_SCAN}`; on failure use sentinel fixture |
| `run_cv` | Raw Sentinel `run_cv` JSON body (push) |
| `use_glint_fixture` | Load assumed CandidateEvent via GLINT client (tags `ingress=glint`) |
| `pull_glint` | `GET {GLINT_BASE_URL}/api/candidate-event`; on failure use assumed fixture |
| `dual_sar` | Corroborate GLINT × SIA fixtures via `app/adapters/dual_sar.py` |
| `pull_dual_sar` | Pull GLINT + SIA; corroborate when aligned; fail-safe to SIA/fixture |

Response `200`: `{ "status": "INGESTED", "observation": {...}, "observations": [...], "track_id": "...", "track_ids": [...], "count": N, "source": "fixture|upstream|run_cv|event|glint|glint_fixture|dual_sar|sia_only" }` — never seals a DecisionToken.

On success, the raw request body is also appended to `.audit/ingress.jsonl` (`received_at`, `source`, `endpoint`, `payload`) for demo replay. Write failures are logged as warnings and **do not** fail ingress. This file is **not** the OCSF gate chain (that remains `.audit/gate.jsonl`). Re-run with:

```bash
uv run python scripts/replay_ingress.py --reset
# Optional demo hygiene (truncate jsonl only; does not touch gate.jsonl):
# uv run python scripts/replay_ingress.py --clear
```

### `POST /api/ingress/open-feed`

Optional demo-grade open AIS (data.gov.sg-shaped) or open air (ADS-B-style) ingress. Synthetic S1–S3 remain primary; this path is additive. Never seals a DecisionToken.

```bash
curl -s -X POST localhost:8080/api/ingress/open-feed \
  -H 'content-type: application/json' \
  -d '{"feed":"all","use_fixture":true}'
```

| Field | Role |
|-------|------|
| `feed` | `ais`, `air`, `all`, or comma list |
| `use_fixture` | Load `tests/fixtures/open_ais_datagovsg.json` / `open_air_traffic.json` |
| `payload` | Raw snapshot for a **single** feed (`ais` or `air`) |

Response `200`: `{ "status": "INGESTED", "feeds": [...], "count": N, "items": [{ "feed", "observation", "track_id" }, ...] }`.

| Open AIS field | Observation |
|----------------|-------------|
| `vessels[].mmsi` | `source_id` / `observation_id` |
| `vessels[].latitude/longitude` | position |
| `vessels[].speed_kt` | speed (via southbound) |
| — | `modality=ais`, `attributes.ingress=open_feed` |

| Open air field | Observation |
|----------------|-------------|
| `aircraft[].icao24` | `source_id` / `observation_id` |
| `aircraft[].callsign` | `entity_hint` |
| `aircraft[].velocity_kt` | speed |
| — | `modality=adsb`, `attributes.ingress=open_feed` |
