# LiteLLM keys

LiteLLM sits in front of vendor APIs. Two different kinds of secrets are involved — **do not mix them**.

```text
sdth-c2-server
  Authorization: Bearer $LLM_API_KEY     ← must equal LITELLM_MASTER_KEY
        │
        ▼
LiteLLM (:4000/v1)                       ← locked by LITELLM_MASTER_KEY
        │
        ├── Gemini     GEMINI_API_KEY
        ├── OpenAI     OPENAI_API_KEY
        └── Anthropic  ANTHROPIC_API_KEY
```

## `LITELLM_MASTER_KEY` — proxy lock

**What it is:** the password for *our* LiteLLM process, not a Google / OpenAI / Anthropic key.

LiteLLM’s `general_settings.master_key` (see `deploy/litellm/config.yaml`) requires every `/v1/chat/completions` call to send:

```http
Authorization: Bearer <LITELLM_MASTER_KEY>
```

Without a matching bearer token, the proxy rejects the request (typically `401`). It never leaves the laptop / venue network; vendors never see it.

LiteLLM expects this value to start with `sk-`.

| File | Variable | Role |
|------|----------|------|
| `deploy/litellm/.env` | `LITELLM_MASTER_KEY` | Injected into the Compose container; becomes `master_key` |
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
    Setting `LITELLM_MASTER_KEY` (or `LLM_API_KEY`) to `GEMINI_API_KEY` / `OPENAI_API_KEY` will not call Gemini or OpenAI. The proxy will either reject the client or, if they happen to match, still needs the *vendor* env vars to reach the model.

## Vendor keys — upstream billing

These are sent **by LiteLLM to the model provider**. C2 never holds them.

| Env | Provider | Used when `LLM_MODEL` is |
|-----|----------|---------------------------|
| `GEMINI_API_KEY` | Google AI Studio | `gemini-3.8-flash` (live smoke / tests) |
| `OPENAI_API_KEY` | OpenAI | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Anthropic | `claude-haiku` |

`nexus-interpreter` tries Gemini first, then OpenAI, then Anthropic, then local Ollama. Live smoke pins `gemini-3.8-flash` so a missing Gemini key does **not** silently fall through to another vendor.

## Why a master key at all?

1. **C2 talks to one URL.** Screen 1 does not need Google/OpenAI/Anthropic SDKs or keys.
2. **Model swap without code changes.** Change `LLM_MODEL` (or LiteLLM `config.yaml`); the Bearer token stays the proxy lock.
3. **Stop casual localhost clients.** Anyone who can hit `:4000` still needs the master key before they can spend vendor quota.

CI does not start LiteLLM. Unset `LLM_BASE_URL` → heuristic interpret; no keys required.

## Rotate / venue

1. Pick a new `sk-…` value (do not reuse a vendor key).
2. Put it in `deploy/litellm/.env` as `LITELLM_MASTER_KEY`.
3. Put the **same** value in C2 `.env` as `LLM_API_KEY`.
4. Restart Compose and `sdth-c2-server`.
5. Never commit `.env`. Examples (`.env.example`) may keep `sk-litellm-local`.

Live path: [Demo Path D](demo.md#demo-path-d-live-llm-via-litellm). Interpret contract: [C2 REST](api/rest.md#post-apiinterpret).
