# LiteLLM front door (Pitch-2)

OpenAI-compatible proxy for `POST /api/interpret`. **Probabilistic proposes; deterministic Core gate still disposes.** CI stays LLM-free (heuristic fallback).

```text
sdth-c2-server  ──LLM_BASE_URL──►  LiteLLM (:4000/v1)
                                        │
                                        ├── Google Gemini 3.8 Flash  (live smoke / tests)
                                        ├── OpenAI / Anthropic
                                        └── Ollama / vLLM (offline demo)
```

## Start

```bash
cp deploy/litellm/.env.example deploy/litellm/.env   # set GEMINI_API_KEY for tests
cp .env.example .env                                 # LLM_MODEL=gemini-3.8-flash
docker compose -f deploy/litellm/docker-compose.yml up -d
./scripts/litellm_interpret_smoke.sh                 # S2 → source == "llm"
```

| Provider | `LLM_MODEL` | Env |
|----------|-------------|-----|
| Google Gemini | `gemini-3.8-flash` | `GEMINI_API_KEY` |
| OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku` | `ANTHROPIC_API_KEY` |
| Venue alias | `nexus-interpreter` | Gemini → OpenAI → Anthropic → Ollama |

Live smoke pins `gemini-3.8-flash` (no silent vendor swap). Venue / zero-internet: `ollama pull llama3.1 && ollama serve`.

`LITELLM_MASTER_KEY` is the proxy lock (copied to C2 as `LLM_API_KEY`). It is **not** `GEMINI_API_KEY`. Full write-up: [LiteLLM keys](../../docs/litellm.md).

See [Demo Path D](../../docs/demo.md#demo-path-d-live-llm-via-litellm).
