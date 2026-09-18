# Cloudflare Containers — C2 Core (issue #18)

Worker front door + FastAPI container. **Same REST paths** as `uv run sdth-c2-server`.

Full runbook: [docs/deploy.md](../../docs/deploy.md).

**Production:** merge to `main` → GitHub Action `Deploy Cloudflare` (`wrangler deploy`). Secrets: `CLOUDFLARE_API_TOKEN` (+ `containers:write`), `CLOUDFLARE_ACCOUNT_ID`, optional `C2_API_TOKEN` (shared Bearer, issue #38).

```bash
npm install
cp .dev.vars.example .dev.vars   # set C2_API_TOKEN
npx wrangler types
npx wrangler secret put C2_API_TOKEN   # production shared Bearer
npx wrangler dev                 # http://127.0.0.1:8787
npx wrangler deploy              # manual; prefer Actions on main
```

Fallback: `uv run sdth-c2-server`.
