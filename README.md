# sdth-nexus-c2

SDTH 2026 C2 application: **PS 04 One Picture, Many Eyes** — disagreeing sensors → **warning picture** → latency-bounded HITL → effector.

**Docs:** [edgesentry.github.io/sdth-nexus-c2](https://edgesentry.github.io/sdth-nexus-c2/) · source in [`docs/`](docs/) · local preview: `mkdocs serve`

**NexusGate** (`core/`) + venue app (`app/`) in one repo. Venue / defense vocabulary stays in `app/` only.

**Phases:** 1–2 done · **3** verification WebUI (`ui/battleplan/`; external BattlePlan pitch UI is out of repo) · 4 pitch day · 5 post-hackathon → [`docs/plan.md`](docs/plan.md)

**Topology:** Core is local (`uv run sdth-c2-server`) or **Cloudflare Containers**. Ingress / Ack stay on laptops. → [`docs/deploy.md`](docs/deploy.md) · [`docs/architecture/topology.md`](docs/architecture/topology.md)

## Quick start

CLI demo (no long-running server):

```bash
uv sync
./scripts/demo.sh                 # default SCENARIO=S1
SCENARIO=S2 ./scripts/demo.sh
uv run python -m app.main --scenario S3 --stub --yes
```

REST Core + verification WebUI (two terminals):

```bash
# Terminal A — Core
uv run sdth-c2-server             # http://127.0.0.1:8080  (pitch-day / CI fallback)

# Terminal B — verification WebUI (Screen 1/2 harness; not external pitch UI)
cd ui/battleplan && npm install && npm run dev
```

Point clients at Cloudflare with the **same REST paths**:

```bash
export C2_BASE_URL=https://sdth-c2-core.<YOUR_SUBDOMAIN>.workers.dev
export C2_API_TOKEN='…'           # shared Worker Bearer — docs/deploy.md
./scripts/picture_to_tasking.sh   # or two-laptop curl: docs/demo.md
```

## Docs map

| Topic | Doc |
|-------|-----|
| Two-laptop I/O, demos, benchmarks, tests | [`docs/demo.md`](docs/demo.md) |
| Frozen C2 REST contract | [`docs/api/rest.md`](docs/api/rest.md) |
| Scenarios S1–S3 + open feeds | [`docs/scenarios.md`](docs/scenarios.md) |
| Space SAR / SIA pipeline | [`docs/architecture/sar_pipeline.md`](docs/architecture/sar_pipeline.md) |
| Cloudflare Containers + Bearer | [`docs/deploy.md`](docs/deploy.md) |
| LiteLLM / probabilistic interpret | [`docs/litellm.md`](docs/litellm.md) |
| Roadmap / plan | [`docs/roadmap.md`](docs/roadmap.md) · [`docs/plan.md`](docs/plan.md) |

## Layout

| Path | Role |
|------|------|
| `core/` | NexusGate (no SDTH/Clearbot/Singapore vocabulary) |
| `app/` | Scenarios, C2 REST, TUI, adapters, policy YAML |
| `ui/battleplan/` | Phase 3 verification WebUI (Screen 1 / Screen 2); external BattlePlan pitch UI is out of repo |
| `deploy/litellm/` | LiteLLM front door |
| `deploy/cloudflare/` | Worker + Containers (`sdth-c2-core`) |
| `scripts/` | `picture_to_tasking`, `stream_events`, `benchmark`, LiteLLM smoke |

## Tests

```bash
uv run pytest tests/unit/ -q
uv run pytest tests/integration/ -v -m integration
uv run python scripts/benchmark.py
```

CI runs unit, integration, and benchmark on every push/PR. Live LiteLLM smoke is optional (not in CI).

## Limits

- Probabilistic proposes; **deterministic gate** alone seals tokens
- In-repo verification WebUI is demo-grade (no full map / GIS); dual-key Tier 2 not implemented
- Kinetic intercept is **not** claimed (S2 cues identify only)
