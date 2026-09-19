# sdth-nexus-c2

SDTH 2026 **PS 04 — One Picture, Many Eyes**: disagreeing sensors → **Warning Picture** → latency-bounded HITL → effector Ack.

> We don’t just fuse the picture. We govern the action with deterministic certainty.

| Layer | Role |
|-------|------|
| **`core/`** | NexusGate — spatial graph, deterministic interlocks, latency-bounded gate, OCSF audit |
| **`app/`** | Venue C2 — S1–S3 scenarios, REST server, Warning Picture TUI, adapters |
| **`ui/battleplan/`** | Verification WebUI (Screen 1 / Screen 2) — **not** the pitch UI; BattlePlan is out of repo |
| **`deploy/`** | LiteLLM proxy + Cloudflare Containers Worker |
| **`scripts/`** | Picture→Tasking, streamer, benchmarks, LiteLLM smoke |

## Docs map

- **[Architecture](architecture/index.md)** — Picture→Tasking closed loop
- **[Topology](architecture/topology.md)** — laptop I/O + local / Cloudflare Core
- **[C2 REST API](api/rest.md)** — Screen 1 / Screen 2 **frozen** contract (curl / TUI / verification WebUI)
- **[Data provenance](data-provenance.md)** — Synthetic vs Real-processed vs Assumed-mock
- **[Cloudflare Containers](deploy.md)** — Worker + container Core, `C2_BASE_URL`, local fallback
- **[LiteLLM](litellm.md)** — probabilistic interpret + proxy keys
- **[Scenarios](scenarios.md)** — S1–S3 + optional open feeds
- **[Demo & benchmarks](demo.md)** — two-laptop I/O (#17), verification WebUI (Path F), streamer, Picture→Tasking, Slide 11, tests
- **[Roadmap](roadmap.md)** — Phase 0–5
- **[Plan](plan.md)** — full planning source

## Quick start

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
uv run sdth-c2-server             # http://127.0.0.1:8080 (Screen 1/2 REST Core)
# Verification WebUI: cd ui/battleplan && npm run dev  (see demo.md Path F; not pitch UI)
# optional live LLM: see litellm.md + demo.md Path D
```

## Limits

- Probabilistic proposes; **deterministic gate** alone seals tokens
- Scenario detectors remain deterministic rules (LLM is optional overlay)
- **UI Boundary:** `ui/battleplan/` and console TUI are **verification harnesses only**. **BattlePlan** (external pitch UI) lives **outside this repository**
- Kinetic intercept is **not** claimed (S2 cues identify only)
- C2 has **no application DB** — runtime is in-memory; audit is jsonl; AIS history stays in SIA SQLite

Site: [edgesentry.github.io/sdth-nexus-c2](https://edgesentry.github.io/sdth-nexus-c2/) · Repo: [edgesentry/sdth-nexus-c2](https://github.com/edgesentry/sdth-nexus-c2)
