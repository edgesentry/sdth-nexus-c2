# LiteLLM & probabilistic interpret

**Probabilistic proposes; deterministic disposes.** App-layer LLM (or heuristic fallback) scores hypotheses and emits a candidate COA via `POST /api/interpret`. Only `LatencyBoundedGate` can approve / seal `DecisionToken`s.

| Env | Role |
|-----|------|
| `LLM_BASE_URL` | OpenAI-compatible base (`…/v1`). Unset → heuristic fallback |
| `LLM_API_KEY` | Bearer for that base (LiteLLM master key, or empty for open local endpoints) |
| `LLM_MODEL` | Model id / LiteLLM alias (default `gpt-4o-mini`) |
| `LLM_TIMEOUT_S` | HTTP timeout seconds (default `8`) |

Never commit API keys — use env / Wrangler Secrets. Samples: `.env.example` (C2) and `deploy/litellm/.env.example` (proxy).

LiteLLM is the local OpenAI-compatible front door (`:4000/v1`). CI does **not** start it. Two different kinds of secrets are involved — **do not mix them**.

```text
sdth-c2-server
  Authorization: Bearer $LLM_API_KEY     ← must equal LITELLM_MASTER_KEY
        │
        ▼
LiteLLM (:4000/v1)                       ← locked by LITELLM_MASTER_KEY
        │
        ├── Gemini     GEMINI_API_KEY
        ├── OpenAI     OPENAI_API_KEY
        ├── Anthropic  ANTHROPIC_API_KEY
        └── Fireworks  FIREWORKS_AI_API_KEY
```

## Run locally (Python)

```bash
cp deploy/litellm/.env.example deploy/litellm/.env   # set GEMINI_API_KEY
cp .env.example .env                                 # LLM_API_KEY must equal LITELLM_MASTER_KEY
uv sync --group litellm --group dev
set -a && source deploy/litellm/.env && set +a
uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000
```

Then in another terminal:

```bash
set -a && source .env && set +a
uv run sdth-c2-server
./scripts/litellm_interpret_smoke.sh
```

CI does **not** install this group (`uv sync --locked --group dev` only).

## `LITELLM_MASTER_KEY` — proxy lock

**What it is:** the password for *our* LiteLLM process, not a Google / OpenAI / Anthropic / Fireworks key.

LiteLLM’s `general_settings.master_key` (see `deploy/litellm/config.yaml`) requires every `/v1/chat/completions` call to send:

```http
Authorization: Bearer <LITELLM_MASTER_KEY>
```

Without a matching bearer token, the proxy rejects the request (typically `401`). It never leaves the laptop / venue network; vendors never see it.

LiteLLM expects this value to start with `sk-`.

| File | Variable | Role |
|------|----------|------|
| `deploy/litellm/.env` | `LITELLM_MASTER_KEY` | Sourced into the Python proxy; becomes `master_key` |
| repo-root `.env` (C2) | `LLM_API_KEY` | What `sdth-c2-server` sends as the Bearer token |

**These two strings must be identical.** Sample for local demo only: `sk-litellm-local` (in both `.env.example` files). Rotate it before a shared venue laptop.

```bash
# Proxy
LITELLM_MASTER_KEY=sk-litellm-local

# C2 — same value, different name
LLM_API_KEY=sk-litellm-local
LLM_BASE_URL=http://127.0.0.1:4000/v1
LLM_MODEL=gemini-3.8-flash
```

!!! warning "Not a vendor key"
    Setting `LITELLM_MASTER_KEY` (or `LLM_API_KEY`) to `GEMINI_API_KEY` / `OPENAI_API_KEY` / `FIREWORKS_AI_API_KEY` will not call those vendors. The proxy will either reject the client or, if they happen to match, still needs the *vendor* env vars to reach the model.

## Vendor keys — upstream billing

These are sent **by LiteLLM to the model provider**. C2 never holds them.

| Env | Provider | Used when `LLM_MODEL` is |
|-----|----------|---------------------------|
| `GEMINI_API_KEY` | Google AI Studio | `gemini-3.8-flash` (live smoke / tests) |
| `OPENAI_API_KEY` | OpenAI | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Anthropic | `claude-haiku` |
| `FIREWORKS_AI_API_KEY` | Fireworks AI | `fireworks-glm` (`fireworks_ai/glm-5p2`; any `fireworks_ai/<slug>` works) |

To use another Fireworks serverless slug (`kimi-k3`, `deepseek-v4-pro`, `qwen3p8-max`, …), change `litellm_params.model` to `fireworks_ai/<slug>` in `deploy/litellm/config.yaml` and restart the Python proxy. The C2 env stays `LLM_MODEL=fireworks-glm` if you keep the same alias, or set `LLM_MODEL` to a new alias you add.

`nexus-interpreter` tries Gemini first, then OpenAI, then Anthropic, then Fireworks, then local Ollama. Live smoke pins `gemini-3.8-flash` so a missing Gemini key does **not** silently fall through to another vendor.

## Why a master key at all?

1. **C2 talks to one URL.** Screen 1 does not need Google/OpenAI/Anthropic/Fireworks SDKs or keys.
2. **Model swap without code changes.** Change `LLM_MODEL` (or LiteLLM `config.yaml`); the Bearer token stays the proxy lock.
3. **Stop casual localhost clients.** Anyone who can hit `:4000` still needs the master key before they can spend vendor quota.

CI does not start LiteLLM. Unset `LLM_BASE_URL` → heuristic interpret; no keys required.

## Rotate / venue

1. Pick a new `sk-…` value (do not reuse a vendor key).
2. Put it in `deploy/litellm/.env` as `LITELLM_MASTER_KEY`.
3. Put the **same** value in C2 `.env` as `LLM_API_KEY`.
4. Restart the Python proxy (`uv run --group litellm litellm …`) and `sdth-c2-server`.
5. Never commit `.env`. Examples (`.env.example`) may keep `sk-litellm-local`.

Live path: [Demo Path D](demo.md#demo-path-d-live-llm-via-litellm). Interpret contract: [C2 REST](api/rest.md#post-apiinterpret).
