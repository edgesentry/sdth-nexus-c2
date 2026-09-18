# LiteLLM front door (Pitch-2)

OpenAI-compatible proxy for `POST /api/interpret`. **Probabilistic proposes; deterministic Core gate still disposes.** CI stays LLM-free (heuristic fallback).

```text
sdth-c2-server  ──LLM_BASE_URL──►  LiteLLM (:4000/v1)
                                        │
                                        ├── OpenAI / Anthropic
                                        └── Ollama / vLLM (offline demo)
```

## Start

```bash
cp deploy/litellm/.env.example deploy/litellm/.env   # set OPENAI_API_KEY (or run Ollama)
cp .env.example .env                                 # C2 → LiteLLM mapping
docker compose -f deploy/litellm/docker-compose.yml up -d
./scripts/litellm_interpret_smoke.sh                 # S2 → source == "llm"
```

Venue / zero-internet: `ollama pull llama3.1 && ollama serve`. Alias `nexus-interpreter` falls back to `ollama-llama3` when OpenAI fails.

See [Demo Path D](../../docs/demo.md#demo-path-d-live-llm-via-litellm).
