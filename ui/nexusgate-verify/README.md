# NexusGate Verify (Phase 2 — issue #65)

In-repo **verification harness** for NexusGate Screen 1 / Screen 2 on the frozen C2 REST contract.
**Not** the external BattlePlan pitch UI.

Paths match curl / TUI / `scripts/picture_to_tasking.sh` — only `NEXT_PUBLIC_C2_BASE_URL` (+ optional Bearer) changes.

## Quick start

```bash
# Terminal A — Core
uv run sdth-c2-server

# Terminal B — NexusGate verify UI
cd ui/nexusgate-verify
cp .env.example .env.local   # optional
npm install
npm run dev                  # http://127.0.0.1:3000
```

Open **Screen 1 · Command** and **Screen 2 · Recipient** in two tabs (or two laptops).

1. Screen 1: Propose `S2` → Approve  
2. Screen 2: Poll inbox → Ack  
3. Optional S3: Screen 1 → Ingress Dual-SAR / Sentinel fixture → open evidence chip modal

Cloudflare:

```bash
export NEXT_PUBLIC_C2_BASE_URL=https://sdth-c2-core.<sub>.workers.dev
export NEXT_PUBLIC_C2_API_TOKEN='…'
npm run dev
```

## Invariants

- UI never seals DecisionTokens — only `POST /api/gate/approve` on Core does
- Interpret is propose-only
- Evidence chips are served from Core `/static/fixtures/` (demo fixtures)

Docs: [Demo Path F](../../docs/demo.md#demo-path-f-nexusgate-verification-webui-phase-2--issue-65-not-pitch-ui) · [REST](../../docs/api/rest.md) · [#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65)
