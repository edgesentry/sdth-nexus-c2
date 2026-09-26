# Admin, Audit & Diagnostics API

**Status:** Operational · Diagnostic and audit verification endpoints for the Nexus C2 runtime.

Core tactical handshake endpoints are documented in **[C2 REST API](rest.md)**. Data schemas are documented in **[Shared Schemas](schemas.md)**.

---

## 1. Runtime State Reset

### `POST /api/admin/reset`

Clears the in-memory `SpatialEntityGraph`, resets active proposals, flushes pending recipient taskings, and restores the C2 engine to clean zero-state. Useful between automated test runs and live scenario pitch transitions.

**Request**
```bash
curl -sf -X POST http://127.0.0.1:8080/api/admin/reset | jq .
```

**Response `200`**
```json
{
  "status": "RESET_OK",
  "cleared_tracks": 1,
  "cleared_observations": 6,
  "cleared_proposals": 1,
  "cleared_taskings": 1,
  "service_view": "all"
}
```

---

## 2. Health & Liveness Checks

### `GET /health`

Liveness and component readiness check.

**Request**
```bash
curl -sf http://127.0.0.1:8080/health | jq .
```

**Response `200`**
```json
{
  "status": "OK",
  "service": "sdth-nexus-c2",
  "version": "0.2.0",
  "uptime_sec": 42.5
}
```

---

## 3. Cryptographic Audit Administration

> [!NOTE]
> Tamper injection endpoints require `C2_DEMO_TAMPER=1` in the server environment. When disabled, tamper requests return `403 Forbidden`.

### `PUT /api/admin/audit/snapshot`

Replaces the on-disk OCSF JSON Lines log (`.audit/gate.jsonl`). Used by the Cloudflare Worker orchestration layer to hydrate the immutable hash chain following an ephemeral container disk reset. **Does not** mint or seal new `DecisionToken`s.

**Request**
```bash
curl -sf -X PUT http://127.0.0.1:8080/api/admin/audit/snapshot \
  -H 'content-type: application/json' \
  -d '{"records": [{"class_name": "Security Finding", "hash": "...", "prev_hash": "..."}]}'
```

**Response `200`**
```json
{
  "status": "restored",
  "count": 1
}
```

---

### `POST /api/admin/audit/tamper`

*Demo-only (Issue #88).* Simulates adversarial tampering with the on-disk audit trail to demonstrate Slide 11 tamper detection and non-repudiation invariants. Snapshots the current OCSF trail, flips one character in a sealed record (without updating hashes), and optionally corrupts the external EDS sidecar. Does **not** mint tokens.

**Request**
```bash
curl -sf -X POST http://127.0.0.1:8080/api/admin/audit/tamper | jq .
```

**Response `200`**
```json
{
  "status": "tampered",
  "index": 1,
  "ocsf": {
    "ok": false,
    "total": 4,
    "broken": 1,
    "break_index": 1,
    "reason": "hash mismatch",
    "summary": "broken links: 1 of 4",
    "label": "1 of 4"
  },
  "eds_corrupted": false
}
```

**Error Responses**
- `403 Forbidden`: `C2_DEMO_TAMPER` environment variable is not set to `1`.
- `400 Bad Request`: Fewer than 2 sealed records exist in the audit log.

---

### `POST /api/admin/audit/restore`

*Demo-only (Issue #88).* Restores the pre-tamper OCSF log (+ EDS sidecar state) from the backup snapshot created during the last tamper injection.

**Request**
```bash
curl -sf -X POST http://127.0.0.1:8080/api/admin/audit/restore | jq .
```

**Response `200`**
```json
{
  "status": "restored",
  "count": 4,
  "ocsf": {
    "ok": true,
    "broken": 0,
    "summary": "broken links: 0 of 4"
  }
}
```

**Error Responses**
- `400 Bad Request`: No pre-tamper snapshot is available to restore.

---

### `POST /api/admin/audit/reverify`

*Demo-only (Issue #88).* Traverses the entire OCSF SHA-256 hash chain in-process. When an EDS sidecar and the `eds` binary are installed, also executes out-of-process `eds audit verify-chain` for hardware-grade verification.

**Request**
```bash
curl -sf -X POST http://127.0.0.1:8080/api/admin/audit/reverify | jq .
```

**Response `200`**
```json
{
  "status": "verified",
  "path": "sha256",
  "ocsf": {
    "ok": true,
    "summary": "broken links: 0 of 4"
  },
  "eds": null
}
```
