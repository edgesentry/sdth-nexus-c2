# sdth-nexus-c2

SDTH 2026 **PS 04 — One Picture, Many Eyes**: disagreeing sensors → **Warning Picture** → latency-bounded HITL → effector Ack.

> We don’t just fuse the picture. We govern the action with deterministic certainty.

| Layer | Role |
|-------|------|
| **`core/`** | NexusGate — spatial graph, deterministic interlocks, latency-bounded gate, OCSF audit |
| **`app/`** | Venue C2 — S1–S3 scenarios, REST server, Warning Picture TUI, adapters |
| **`ui/battleplan/`** | Phase 3 Next.js Screen 1 / Screen 2 BattlePlan client |
| **`deploy/`** | LiteLLM proxy + Cloudflare Containers Worker |
| **`scripts/`** | Picture→Tasking, streamer, benchmarks, LiteLLM smoke |

## Docs map

- **[Architecture](architecture/index.md)** — Picture→Tasking closed loop
- **[Topology](architecture/topology.md)** — laptop I/O + local / Cloudflare Core
- **[C2 REST API](api/rest.md)** — Screen 1 / Screen 2 **frozen** contract (curl / TUI / Phase 3)
- **[Cloudflare Containers](deploy.md)** — Worker + container Core, `C2_BASE_URL`, local fallback
- **[LiteLLM](litellm.md)** — probabilistic interpret + proxy keys
- **[Scenarios](scenarios.md)** — S1–S3 + optional open feeds
- **[Demo & benchmarks](demo.md)** — two-laptop I/O (#17), BattlePlan (Path F), streamer, Picture→Tasking, Slide 11, tests
- **[Roadmap](roadmap.md)** — Phase 0–5
- **[Plan](plan.md)** — full planning source

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
uv run sdth-c2-server             # http://127.0.0.1:8080 (Screen 1/2 REST Core)
# BattlePlan UI: cd ui/battleplan && npm run dev  (see demo.md Path F)
# optional live LLM: see litellm.md + demo.md Path D
```

## Limits

- Probabilistic proposes; **deterministic gate** alone seals tokens
- Scenario detectors remain deterministic rules (LLM is optional overlay)
- BattlePlan is demo-grade (no full map / GIS); dual-key Tier 2 not implemented
- Kinetic intercept is **not** claimed (S2 cues identify only)

Site: [edgesentry.github.io/sdth-nexus-c2](https://edgesentry.github.io/sdth-nexus-c2/) · Repo: [edgesentry/sdth-nexus-c2](https://github.com/edgesentry/sdth-nexus-c2)
