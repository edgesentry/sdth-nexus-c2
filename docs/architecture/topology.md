# Topology

**Input and Ack stay on laptops.** Core runs locally (`sdth-c2-server`) or, in Phase 2, on **Cloudflare Containers** with the same REST paths.

```text
Laptop Screen 1: Command Cockpit             NexusGate C2 Core (Local / Cloudflare)         Laptop Screen 2: Field Recipient
  - Next.js UI / TUI / curl            →      - Ingest & SpatialEntityGraph              ←    - GET /api/recipient/inbox
  - POST /api/gate/proposals (COA)     →      - Deterministic Interlock & Gate (<50ms)   →    - POST /api/recipient/ack
  - POST /api/gate/approve (Operator)  →      - Sealed DecisionToken & OCSF Audit        →    - [Optional] mock effector / USV
```

| Role | Where | What |
|------|-------|------|
| **Screen 1 (Command)** | Laptop | BattlePlan Next.js UI / TUI / curl, operator approval/denial |
| **C2 Core** | Local *or* Cloudflare | `app/c2_server.py` — ontology graph, gate, token sealing, inbox, OCSF audit |
| **Screen 2 (Recipient)** | Laptop | Recipient node polling inbox (`/api/recipient/inbox`) and submitting signed Ack (`/api/recipient/ack`) |

## Cloudflare (Phase 2)

Same REST contract over HTTPS. Recommended stack:

| Layer | Choice | Why |
|-------|--------|-----|
| Runtime | Cloudflare Containers + Worker front door | Keep FastAPI / `uv` |
| Routing | Worker → Container singleton | Shared `C2Runtime` for demo |
| Persistence | Durable Object / R2 for audit | Container disk is ephemeral |
| Fallback | Local `sdth-c2-server` | Pitch-day / CI |

Point clients with `C2_BASE_URL` / `BASE_URL` — paths do not change.
