# Roadmap

| Phase | Focus | Status |
|-------|--------|--------|
| **0** | Core foundations (graph, interlock, gate, audit) | Done |
| **2** | Backend closed loop & operational core (+ NexusGate verify UI) | **Active (partial)** — #47 / #54 / #55 / #56 / #57 / #58 / #59 / #60 / #65 / #70 done |
| **3** | Pitch-facing UI polish (external BattlePlan) | Planned — in-repo verify harness = Phase 2 [#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65) (`/verify`) |
| **4** | Pitch-day polish, Team 02 GLINT **live** integration & fallback | Planned (Sep 25–27) |
| **5** | Post-hackathon sovereign PoC (live sensors, field USV) | Planned |

> **UI Boundary:** **BattlePlan** = external **pitch UI** (outside this repo). This repo’s `/verify` (Jinja2/HTMX on Core) + TUI are a **verification harness** only. Pitch deliverable = deterministic gate + interlock, not a presentation chrome in-tree.

> **Data provenance:** See [Data provenance](data-provenance.md) (Synthetic / Real-processed / Assumed-mock).

## Core C2 Functions Beyond UI Display

In **SDTH 2026 PS 04 ("One Picture, Many Eyes")**, a C2 system dies if it only renders pins and radar chips on a map. NexusGate executes five core non-UI operational functions:

1. **Temporal Kinematic Projection (`core/kinematics.py`)** — **done** [#57](https://github.com/edgesentry/sdth-nexus-c2/issues/57): bridge SAR latency ($T - \Delta t$) to coastal radar ($T - 0$) via dead-reckoning envelopes.
2. **Dual-SAR Multi-Fidelity Arbitration (`app/adapters/dual_sar.py`)** — **done** [#56](https://github.com/edgesentry/sdth-nexus-c2/issues/56): fuse **GLINT** macro (Assumed-mock → live) with **SIA** micro OBB metrology.
3. **OSINT Text Parser (`app/adapters/osint_text.py`)** — extract counts/bearings from Synthetic social text (S2); not a live SNS API ([#59](https://github.com/edgesentry/sdth-nexus-c2/issues/59)).
4. **Deterministic Interlocks (<5ms Fast-Reject)** — **done**: geofence, speed, duplicate suppression.
5. **Dynamic Intercept Vectoring & Cryptographic Audit** — audit **done**; lead-pursuit **POI** **done** [#58](https://github.com/edgesentry/sdth-nexus-c2/issues/58).

## Operational Gaps & Phase 2 (remaining)

| Domain / Gap | Operational Problem | Phase 2 work |
|---|---|---|
| **Ingress replay** | Demo failure loses the CandidateEvent stream | ✅ `.audit/ingress.jsonl` + `scripts/replay_ingress.py` (#54) |
| **GLINT mock** | Team 02 schema not final | ✅ HTTP stub `:5051` + `glint_client`; swap on handover |
| **Dual-SAR** | GLINT and SIA ingested without joint rules | ✅ `app/adapters/dual_sar.py` (#56) |
| **SAR Time-Delta** | Static SAR coords fail on moving ships | ✅ `core/kinematics.py` (#57) |
| **OSINT parse** | S2 social counts from `intel_text` via `osint_text` (#59), hardcoded fallback | Done |
| **Live open feeds** | Fixtures lack live realism for Singapore Strait pitch | ✅ Indago DuckDB / live / fixture ladder (#70) |
| **Tasking geometry** | Effector sent to static historical coords | ✅ lead-pursuit POI + ETA (#58) |
| **NexusGate verify UI** | Curl-only loop is hard to rehearse live | ✅ `/verify` Jinja2/HTMX on Core (#65) |

## Phase 2 pitch cores (demo fidelity)

| Point | Phase 2 implementation | Phase 5 raise |
|-------|------------------------|---------------|
| Multimodal & Kinematics | Synthetic tactical sensors + Real-processed SIA(+AIS) + Assumed-mock GLINT + Dual-SAR (#56) + kinematics (#57) + optional live open-feed ([#70](https://github.com/edgesentry/sdth-nexus-c2/issues/70)) | Live coastal + multi-constellation SAR |
| Probabilistic | LLM / heuristic → hypotheses + COA; LiteLLM (#32, done) | Production CV + hardened LLM |
| Deterministic gate | Stress 100+ tracks; p95 < 50ms, refusal coverage `n/n` (done) | Air-gap, dual-key Tier-2 |
| Picture→Tasking | Closed loop + POI (#58) + Screen 2 Ack <3.0s + **total decision time A/B** | Field USV |
| Sovereign interlock | OCSF + Cloudflare Containers (done) + **UNCLOS Art. 111 continuity ledger** | BLAKE3 + Ed25519 via `edgesentry-rs`; tribunal-grade evidence review |

> Metric phrasing revised 2026-09-21: `unauthorized=0` and `100% audit integrity` withdrawn in favour of `n/n` coverage and broken-link counts, and the primary metric moved to total decision time. See [PLAN §5](plan.md#5-quantitative-operational-benchmarks-slide-11-proof).

## Demo-day & Hackathon Execution (Phase 4: Sep 25–27)

1. **Day 1 (Fri 25 Sep) — Team 02 GLINT Live Cross-Team Integration**:
   - Meet Team 02 (GLINT) at NUS Enterprise Level 2 workspace.
   - Verify live GLINT REST / MCP API against `CandidateEvent` schema (replace Assumed-mock).
   - Live stream into C2 (`POST /api/ingress/candidate-event`).
   - Fallback: SIA `:5050` or Singapore Strait golden fixture.
2. **Day 1 Evening — End-to-End Playthroughs**: S2 air contradiction; S3 dual-SAR + kinematics → POI → Ack.
3. **Day 2 (Sat 26 Sep) — Preliminary Cut Selection**.
4. **Day 3 (Sun 27 Sep) — VIP Finalist Pitch** + Slide 11 live.

Full checklist: [Plan](plan.md).
