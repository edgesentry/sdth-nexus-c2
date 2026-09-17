# C2 REST API (frozen contract)

**Status:** Phase 2 freeze · source of truth for curl / TUI / scripts and Phase 3 BattlePlan (`BASE_URL` / `C2_BASE_URL` swap only — **paths do not change**).

| Item | Value |
|------|--------|
| Server | `app/c2_server.py` |
| CLI | `uv run sdth-c2-server` |
| Default base | `http://127.0.0.1:8080` |
| Proof | `tests/unit/test_c2_server.py`, `tests/unit/test_c2_rest_contract.py`, `tests/integration/test_s2_c2_e2e.py` |

Screen 1 = command · Screen 2 = recipient. No BattlePlan required for Phase 2 demos.

## Endpoints

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/ontology/state` | Live tracks, observations, amber alert |
| `POST` | `/api/gate/proposals` | Queue COA (`scenario_id` or raw `coa`) |
| `POST` | `/api/gate/approve` | Operator y/n → sealed `DecisionToken` |
| `GET` | `/api/recipient/inbox?unit_id=` | Pending approved taskings |
| `POST` | `/api/recipient/ack` | Recipient ack sealed to audit chain |
| `GET` | `/api/audit/trail` | OCSF-shaped hash-chain records |
| `POST` | `/api/admin/reset` | Clear in-memory runtime (tests / demos) |

## Handshake (curl)

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

One-shot helper: `./scripts/picture_to_tasking.sh` (see [Demo](../demo.md)).

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

## `POST /api/gate/proposals`

### Request

Provide **either** `scenario_id` **or** raw `coa` (not neither).

```json
{
  "scenario_id": "S2",
  "unit_id": "CUE-NODE-01",
  "timeout_seconds": 30
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
export C2_BASE_URL=http://127.0.0.1:8080   # or Cloudflare HTTPS later
# BASE_URL is accepted by scripts/picture_to_tasking.py
```

Paths above are the frozen surface. UI clients must not invent alternate routes for Screen 1 / Screen 2 handshake.

!!! tip "Follow-up (Phase 3): Pydantic response models"
    Endpoints currently return ad-hoc `dict[str, Any]`, so `/openapi.json` lacks response schemas.
    Introduce response models (`OntologyStateResponse`, `ApproveResponse`, …) later to auto-validate
    outgoing payloads and enable TypeScript client generation for BattlePlan.
