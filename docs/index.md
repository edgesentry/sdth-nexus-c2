# sdth-nexus-c2

SDTH 2026 **PS 04 — One Picture, Many Eyes**: disagreeing sensors → **Warning Picture** → latency-bounded HITL → effector Ack.

> We don’t just fuse the picture. We govern the action with deterministic certainty.

| Layer | Role |
|-------|------|
| **`core/`** | NexusGate — spatial graph, deterministic interlocks, latency-bounded gate, OCSF audit |
| **`app/`** | Venue C2 — S1–S3 scenarios, REST server, Warning Picture TUI, adapters |

## Docs map

- **[Architecture](architecture/index.md)** — Picture→Tasking closed loop
- **[Topology](architecture/topology.md)** — laptop I/O + local / Cloudflare Core
- **[C2 REST API](api/rest.md)** — Screen 1 / Screen 2 **frozen** contract (curl / TUI / Phase 3)
- **[Cloudflare Containers](deploy.md)** — Worker + container Core, `C2_BASE_URL`, local fallback
- **[LiteLLM](litellm.md)** — Python proxy, `LITELLM_MASTER_KEY` vs vendor keys
- **[Scenarios](scenarios.md)** — S1 sea spoof · S2 air corridor (hero) · S3 SAR vs AIS
- **[Demo & benchmarks](demo.md)** — quick start, streamer, Slide 11 metrics, live LiteLLM
- **[Roadmap](roadmap.md)** — Phase 0–5
- **[Plan](plan.md)** — full planning source

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
uv run sdth-c2-server             # http://127.0.0.1:8080 (Screen 1/2 REST Core)
# optional live LLM: uv sync --group litellm && uv run --group litellm litellm --config deploy/litellm/config.yaml --port 4000
#                    ./scripts/litellm_interpret_smoke.sh
```

Site: [edgesentry.github.io/sdth-nexus-c2](https://edgesentry.github.io/sdth-nexus-c2/) · Repo: [edgesentry/sdth-nexus-c2](https://github.com/edgesentry/sdth-nexus-c2)
