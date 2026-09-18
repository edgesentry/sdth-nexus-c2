# Cloudflare Containers (C2 Core)

**Phase 2 deliverable (issue #18).** Same frozen REST contract as local `sdth-c2-server`. Screen 1 / Screen 2 stay on laptops; only the Core moves to a public HTTPS URL.

Fallback when Cloudflare is down or Wi-Fi is hostile: `uv run sdth-c2-server`.

## Topology

```text
Laptop Screen 1  ──HTTPS──►  Worker  ──getByName("demo")──►  Container (FastAPI / uv)
Laptop Screen 2  ──HTTPS──►     │
                                └── Durable Object SQLite: OCSF audit snapshot
                                    (container disk is ephemeral)
```

| Layer | Role |
|-------|------|
| Worker | Front door. Routes every request to the **`demo`** singleton container. |
| Container | `app/c2_server.py` on `:8080` (`C2_HOST=0.0.0.0`). |
| DO storage | After mutating POSTs, the Worker copies `GET /api/audit/trail` into SQLite and hydrates `PUT /api/admin/audit/snapshot` on container start. |
| Local Core | CI default and pitch-day fallback (`uv run sdth-c2-server`). |

Paths do not change. Point clients with `C2_BASE_URL`.

## Prerequisites

- Docker Desktop (or another Docker-compatible engine) running — required for image build
- Node.js 22+ and npm
- Cloudflare account with **Containers** enabled (Workers paid / Containers beta)
- API token (or `npx wrangler login`) with **`containers:write`** in addition to Workers write
- Wrangler login: `npx wrangler login` or `CLOUDFLARE_API_TOKEN`

## Local: `wrangler dev`

From `deploy/cloudflare/`:

```bash
cd deploy/cloudflare
npm install
cp .dev.vars.example .dev.vars   # optional LLM overlay
npx wrangler types
npx wrangler dev                 # http://127.0.0.1:8787
```

In another terminal, from the repo root:

```bash
curl -s http://127.0.0.1:8787/health
C2_BASE_URL=http://127.0.0.1:8787 ./scripts/picture_to_tasking.sh
```

First request after sleep pays a 2–3s container cold start. Subsequent handshake hops use the warm singleton.

## Deploy

```bash
cd deploy/cloudflare
npm install
npx wrangler types
npx wrangler deploy
```

Wrangler prints the workers.dev URL, for example:

```text
https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev
```

Record that URL as `C2_BASE_URL`. A token that only has `workers:write` (no `containers:write`) can upload the Worker but **cannot** publish the container image — add the Containers write scope, then re-run `npx wrangler deploy`.

Optional LLM overlay (heuristic is the default if these are unset):

```bash
npx wrangler secret put LLM_BASE_URL    # public OpenAI-compatible …/v1
npx wrangler secret put LLM_API_KEY
# LLM_MODEL is a wrangler var (default gemini-3.8-flash)
```

Laptop handshake against the deployed Core:

```bash
export C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev
curl -s "$C2_BASE_URL/health"
./scripts/picture_to_tasking.sh
```

## Fallback (zero-internet / Cloudflare down)

```bash
uv run sdth-c2-server          # http://127.0.0.1:8080
./scripts/picture_to_tasking.sh
```

Do **not** set `C2_BASE_URL` (or point it at `http://127.0.0.1:8080`). CI always uses this path.

## Operational endpoints (not frozen Screen 1/2 contract)

| Method | Path | Role |
|--------|------|------|
| `GET` | `/health` | Readiness (Docker / `wrangler dev` / scripts) |
| `PUT` | `/api/admin/audit/snapshot` | Hydrate OCSF jsonl after ephemeral disk reset |

Frozen handshake: [C2 REST API](api/rest.md).

## Instance sizing

`basic` (¼ vCPU, 1 GiB) · `max_instances = 1` · `sleepAfter = 30m`. Raise the instance type in `wrangler.jsonc` if the image OOMs.
