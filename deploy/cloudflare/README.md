# Cloudflare Containers — C2 Core (issue #18)

Worker front door + FastAPI container. **Same REST paths** as `uv run sdth-c2-server`.

Full runbook: [docs/deploy.md](../../docs/deploy.md).

```bash
npm install
npx wrangler types
npx wrangler dev                 # http://127.0.0.1:8787
npx wrangler deploy              # https://sdth-c2-core.<subdomain>.workers.dev
```

Fallback: `uv run sdth-c2-server`.
