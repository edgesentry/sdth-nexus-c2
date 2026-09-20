# Roadmap

| Phase | Focus | Status |
|-------|--------|--------|
| **0** | Core foundations (graph, interlock, gate, audit) | Done |
| **1** | S1–S3, C2 REST, streamer, benchmarks | Done |
| **2** | Backend closed loop & operational core (+ NexusGate verify UI) | **Active (partial)** — #47 / #54 / #55 / #56 / #60 / #65 done; open: [#57](https://github.com/edgesentry/sdth-nexus-c2/issues/57)–[#59](https://github.com/edgesentry/sdth-nexus-c2/issues/59) |
| **3** | Pitch-facing UI polish (external BattlePlan) | Planned — in-repo verify harness = Phase 2 [#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65) (`ui/nexusgate-verify/`) |
| **4** | Pitch-day polish, Team 02 GLINT **live** integration & fallback | Planned (Sep 25–27) |
| **5** | Post-hackathon sovereign PoC (live sensors, field USV) | Planned |

> **UI Boundary:** **BattlePlan** = external **pitch UI** (outside this repo). This repo’s `ui/nexusgate-verify/` + TUI are a **verification harness** only. Pitch deliverable = deterministic gate + interlock, not a presentation chrome in-tree.

> **Data provenance:** See [Data provenance](data-provenance.md) (Synthetic / Real-processed / Assumed-mock).

## Core C2 Functions Beyond UI Display

In **SDTH 2026 PS 04 ("One Picture, Many Eyes")**, a C2 system dies if it only renders pins and radar chips on a map. NexusGate executes five core non-UI operational functions:

1. **Temporal Kinematic Projection (`core/kinematics.py`)** — *planned Phase 2*: bridge SAR latency ($T - \Delta t$) to coastal radar ($T - 0$) via dead-reckoning envelopes.
2. **Dual-SAR Multi-Fidelity Arbitration (`app/adapters/dual_sar.py`)** — *planned Phase 2*: fuse **GLINT** macro (Assumed-mock → live) with **SIA** micro OBB metrology.
3. **OSINT Text Parser (`app/adapters/osint_text.py`)** — *planned Phase 2*: extract counts/bearings from Synthetic social text (S2); not a live SNS API.
4. **Deterministic Interlocks (<5ms Fast-Reject)** — **done**: geofence, speed, duplicate suppression.
5. **Dynamic Intercept Vectoring & Cryptographic Audit** — audit **done**; lead-pursuit **POI** *planned Phase 2*.

## Operational Gaps & Phase 2 (remaining)

| Domain / Gap | Operational Problem | Phase 2 work |
|---|---|---|
| **Ingress replay** | Demo failure loses the CandidateEvent stream | ✅ `.audit/ingress.jsonl` + `scripts/replay_ingress.py` (#54) |
| **GLINT mock** | Team 02 schema not final | ✅ HTTP stub `:5051` + `glint_client`; swap on handover |
| **Dual-SAR** | GLINT and SIA ingested without joint rules | ✅ `app/adapters/dual_sar.py` (#56) |
| **SAR Time-Delta** | Static SAR coords fail on moving ships | `core/kinematics.py` |
| **OSINT parse** | S2 social counts hardcoded beside the text | `app/adapters/osint_text.py` |
| **Tasking geometry** | Effector sent to static historical coords | POI in `core/coa.py` / `app/agent.py` |
| **NexusGate verify UI** | Curl-only loop is hard to rehearse live | ✅ `ui/nexusgate-verify/` Screen 1/2 (#65) |

## Phase 2 pitch cores (demo fidelity)

| Point | Phase 2 implementation | Phase 5 raise |
|-------|------------------------|---------------|
| Multimodal & Kinematics | Synthetic tactical sensors + Real-processed SIA(+AIS) + Assumed-mock GLINT + Dual-SAR (#56) + kinematics (open) | Live coastal + multi-constellation SAR |
| Probabilistic | LLM / heuristic → hypotheses + COA; LiteLLM (#32, done) | Production CV + hardened LLM |
| Deterministic gate | Stress 100+ tracks; p95 < 50ms, unauthorized=0 (done) | Air-gap, dual-key Tier-2 |
| Picture→Tasking | Closed loop + POI (open) + Screen 2 Ack <3.0s | Field USV |
| Sovereign interlock | OCSF + Cloudflare Containers (done) | Stronger seal (Ed25519) |

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
