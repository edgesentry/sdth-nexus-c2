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
| **Screen 2 (Recipient)** | Laptop | Recipient node polling inbox (`/api/recipient/inbox`) and submitting signed Ack (`/api/recipient/ack`). Runs as a **separate OS process** so the Ack is genuinely received. ~~RasPi GPIO blink (#20)~~ **excluded from the demo path (2026-09-17)** |

Phase 2 cold-start curl rehearsal (two laptops / two terminals, no UI): [Demo Path A](../demo.md#demo-path-a-two-laptop-two-terminal-io-issue-17). Phase 2 NexusGate verification UI ([#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65)): [Demo Path F](../demo.md#demo-path-f-nexusgate-verification-webui-phase-2--issue-65-not-pitch-ui) (`/verify` on Core). Plan context: [§4.2 Cloudflare Containers](../plan.md#42-cloudflare-containers-phase-2).

## Cloudflare (Phase 2)

Same REST contract over HTTPS. Recommended stack:

| Layer | Choice | Why |
|-------|--------|-----|
| Runtime | Cloudflare Containers + Worker front door | Keep FastAPI / `uv` |
| Routing | Worker → Container singleton | Shared `C2Runtime` for demo |
| Persistence | Durable Object / R2 for audit | Container disk is ephemeral |
| Fallback | Local `sdth-c2-server` | Pitch-day / CI |

Point clients with `C2_BASE_URL` / `BASE_URL` — paths do not change.

## Deploy (issue #18)

Worker front door → container singleton `getByName("demo")`. Audit jsonl is snapshotted into Durable Object SQLite because container disk resets on sleep.

```bash
cd deploy/cloudflare
npm install
npx wrangler dev                 # http://127.0.0.1:8787
npx wrangler deploy              # prints https://sdth-c2-core.<subdomain>.workers.dev
```

```bash
C2_BASE_URL=https://sdth-c2-core.<subdomain>.workers.dev ./scripts/picture_to_tasking.sh
```

Cloudflare down or venue Wi-Fi dead: `uv run sdth-c2-server` (CI default). Full runbook: [Cloudflare Containers](../deploy.md).
