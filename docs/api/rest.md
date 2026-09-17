# C2 REST API

Unified server: `app/c2_server.py` · CLI: `uv run sdth-c2-server` · default `http://127.0.0.1:8080`.

Screen 1 = command · Screen 2 = recipient. BattlePlan (Phase 3) and curl/TUI share this contract.

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

## Proposal body

```json
{
  "scenario_id": "S2",
  "unit_id": "CUE-NODE-01",
  "timeout_seconds": 30
}
```

Or supply a raw `coa` object instead of `scenario_id`. Fast interlock failures return `REJECTED_FAST` with a sealed token; Tier-1 HITL returns `QUEUED`.

## Approve body

```json
{
  "coa_id": "<uuid>",
  "decision": "y",
  "operator_id": "operator"
}
```

`decision`: `y` / `yes` / `approve` or `n` / `no` / `deny`.

## Ack body

```json
{
  "coa_id": "<uuid>",
  "unit_id": "CUE-NODE-01",
  "message": "on station",
  "telemetry": {}
}
```

Ack is appended as `recipient_ack` on the OCSF hash chain (`GET /api/audit/trail`).

## Admin reset

```bash
curl -s -X POST localhost:8080/api/admin/reset
```

Response:
```json
{"status": "reset"}
```

Clears in-memory ontology graph, findings, active proposals, inbox, and ack sets. This provides a clean slate for test suites and live demo reruns without deleting disk audit records (`.audit/gate.jsonl`).
