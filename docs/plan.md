# PLAN — sdth-nexus-c2 (PS 04)

> Canonical planning source for this repo (MkDocs / GitHub Pages).

**Status:** Phase 2 **active (partial)** — SIA #47 / Cloudflare / gate loop / ingress replay (#54) / AIS via SIA only (#60) / GLINT Assumed-mock (#55) / Dual-SAR (#56) / **NexusGate verification WebUI (#65)** / **SAR kinematics (#57)** / **Dynamic Intercept POI (#58)** / **OSINT text parser (#59)** done · Phase 3 = external BattlePlan polish · Phase 5 = post-hackathon sovereign PoC · **2026-09-20 Updated** · Provenance: [data-provenance.md](data-provenance.md)  
**Challenge:** SDTH 2026 **PS 04 — One Picture, Many Eyes** (From Picture to Tasking)  
**Product face:** Project NexusGate (core gate) + venue Command and Control (C2) app  
**Target Reviewers:** DSTA, MINDEF/SAF C4I, EDTH, NUS Defense Tech Venture Lab  
**Architecture Consensus (2026-09-17 Team Decision):** Purely software-driven digital C2 application running on standard laptops. Physical robotics/hardware excluded from primary hackathon deliverables to guarantee execution within the 48-hour window. Effectors are generic REST/simulated endpoints (`UsvRestAdapter` / simulated recipient nodes) — **kept as separate OS processes**, never in-process calls, so the Ack link in the audit chain is not self-dealt.

**Domain Lock (2026-09-20 Team Decision):** **100% maritime** — Singapore Strait vessel incursions, dark vessels, contraband / STS. **Air and drone-swarm scenarios are formally out of scope.** S2 remains in the repo as a reusable discrepancy mechanism, **not as a pitch scenario**.

**Scope Revision (2026-09-21):** §5 benchmarks rewritten — `0` / `100%` absolutes withdrawn, primary metric moved from gate latency to **total decision time with an A/B baseline**. Three items added to Phase 2: `edgesentry-rs` crypto core, **UNCLOS Art. 111 continuity ledger**, and the A/B instrumentation. Strategy-side companion (cut list · forbidden phrasings · abort conditions): [`app-dev-plan-nexus-c2.md`](https://github.com/edgesentry/edgesentry-commercial/blob/main/docs/strategy/sdth2026/app-dev-plan-nexus-c2.md) in `edgesentry-commercial`.

---

## 1. Executive Summary & One-Line Closed Loop

> **"We don’t just fuse the picture. We govern the action with deterministic certainty."**

The fatal bottleneck identified in PS 04 is the **Picture-to-Tasking gap**:
> *“The path from a merged display to somebody tasking something is where these systems die, and it is almost never the part that gets built.”*

NexusGate solves this via a dual-layer architecture:
1. **Probabilistic Interpretation (App Layer / LLM Reasoning):** Flexible ingestion of conflicting, unlabelled, and noisy sensor feeds (social media OSINT, uncorroborated radar, obscured optical).
2. **Deterministic Verification & Hard Gating (Core Engine):** Zero-hallucination kinematic checks, mathematical multi-source corroboration, latency-bounded human authorization, and immutable cryptographic audit.

### The Complete End-to-End Closed Loop (Slides 08, 09, 10)

```text
Multi-Source Ingress (Civilian Social Media/Recon, Coastal Radar, EO/IR Blur, AIS, RF)
        │
        ▼ (SpatialEntityGraph — correlation without shared IDs)
Discrepancy Detection & Amber Flagging (Count & Bearing Mismatch)
        │
        ▼
WARNING PICTURE (Threat class, tactical minutes, adversarial hypothesis)
        │
        ▼
Latency-Bounded Operator Gate (Default = Deny on timeout / geofence)
        │
        ├── [Approved] ──► Cryptographic DecisionToken (BLAKE3/SHA256)
        │                       │
        │                       ▼
        │             Recipient Node / Edge Asset (Screen 2 / Generic USV REST)
        │                       │
        │                       ▼
        │             Field Acknowledgment (Ack Event)
        │                       │
        ▼                       ▼
   Append to Immutable OCSF Audit Chain (<3s Picture-to-Ack Roundtrip)
```

---

## 2. Inputs / Outputs / Decisions

### 2.1 Multi-Modal Ingress (The Many Eyes)

Synthetic multi-vendor observations without shared track IDs:

| Modality | Used in | Characteristics | Role in Contradiction |
|----------|---------|-----------------|-----------------------|
| **Space-based SAR Anomaly Ingress** | **S3** | Macro scene-difference anomaly evidence (all-weather radar satellite diff over sea lanes, integrated via in-house Sentinel-1 SAR × AIS correlation pipeline or external cross-track feeds; see [SAR Pipeline](architecture/sar_pipeline.md)) | Flags unannounced vessel clusters or dark ships (AIS-silent) where optical sensors are blind |
| **Social Media OSINT / Text Intel** | **S2** | Unstructured text summary (Instagram/Telegram/Recon) | Exaggerated social reports ("20 drones incoming") filtered down to 3 Shahed-136 drones heading to Objective Bravo at T+4 min |
| **Coastal / Gap-Filler Radar** | S1–S3 | 2D/3D kinematic contacts | Disagrees in count (sees 1 contact) or bearing (+1,200m north) |
| **EO / Optical Camera** | S1, S2 | Visual bearings, YOLO bounding box | Obscured blur, low confidence (0.42), unable to verify independently |
| **AIS / Open AIS** | S1, S3 | Manipulable / delayed cooperative stream | Spoofed stationary contact, or stale lane density pattern break |
| **RF Spectrum** | S1, S2 | Passive RF scan / CUAS emitter detection | Silent signature (confirms cheap drone) or control band near contact |
| **ADS-B Sector** | S2 | Transponder air picture | Missing squawk (empty sector confirmation) |

### 2.2 19-Event Temporal Progression (Slide 09)

To demo temporal alignment (PS 04 §2-03) and avoid static toy data, the scenario engine supports **19-step temporal playback** (`scripts/stream_events.py`):
1. **Events 01–05 (T-60s to T-45s):** Early reconnaissance chatter, social media rumors, sparse radar blips, or macro space-based SAR difference alerts.
2. **Events 06–10 (T-40s to T-25s):** Coastal radar locks high-speed inbound track; optical cameras slew to cue area.
3. **Events 11–15 (T-20s to T-10s):** EO/IR detects low-confidence blur; Corroboration Engine flags **Amber Contradiction Alert** (Social/Recon reports 3, Radar sees 1 at divergent bearing; or SAR sees vessel cluster while AIS is silent).
4. **Events 16–19 (T-05s to T-00s):** Operator console displays Warning Picture; countdown triggers; operator authorizes investigation tasking; recipient confirms ack.

### 2.3 Intermediate Output — Warning Picture (`Finding`)

Printed in TUI and served over API before the gate. Answers: *what is wrong, how many minutes, which sources disagree, and what must be false for the threat to collapse*:

| Field | Meaning |
|-------|---------|
| `threat_class` | e.g. `attritable_air_incursion` / `sea_approach_deception` / `lane_spof_break` |
| `warning_minutes_est` | Tactical warning time remaining (e.g. 4.0 min for air raid, 8.0 min for sea) |
| `mismatch_m` | Spatial disagreement distance between sensor tracks |
| `confidence` | Rule-composed score (0.0 to 1.0) |
| `picture_summary` | Single coherent operational summary |
| `adversarial_hypothesis` | "If source X is false..." (PS 04 §2-05 style) |
| `amber_alert` | Contradiction classification (e.g. `COUNT_AND_BEARING_MISMATCH`) |
| `source_breakdown` | Discrepant sources grouped by modality and claim |

### 2.4 Decision Path & Execution

```text
build_events()  →  SpatialEntityGraph
        →  detect() → Finding | None
        →  build_coa() → CourseOfAction (Tier-1 HITL)
        →  LatencyBoundedGate.evaluate()
              fast-reject (<5ms) → Geofence / Speed / Duplicate violation
              approve (<50ms)   → DecisionToken → Dispatch to Recipient
              deny / timeout    → Default = Deny (Station Keep / Safe Hold)
        →  Recipient Node receives token → Actuates waypoint/ack → Returns Ack
        →  AuditLogger seals both Token & Ack into OCSF Hash Chain
```

---

## 3. Defense Scenarios Specification (1:1 Alignment with Pitch Deck & Team Consensus)

| ID | Title | Pitch Slide | Tactical Conflict | Decision → Tasking |
|----|-------|-------------|-------------------|--------------------|
| **S1** | **Sea Approach — Adversarial AIS Spoof** | Slide 01, 06 | Manipulable stationary AIS vs ~20 kt radar/EO approach (~850m mismatch) | Mismatch ≥500m → `ISR_IDENTIFY_CONTACT` → Generic Coastal ISR USV |
| **S2** | **Air Corridor — Shahed Swarm Contradiction** | **Slide 04 (Hero)** | **Civilian social media / recon reports 3 drones; radar sees 1 contact 1,200m north; EO/IR shows blur (0.42 conf); RF silent; no ADS-B** | Count & bearing contradiction → Amber Alert → `CUE_AND_IDENTIFY` (Non-kinetic investigation) |
| **S3** | **Shipping Lane & Coastal Anomaly — SAR Difference vs AIS** | Slide 02, 06 | Space-based SAR scene difference flags unannounced cluster with OBB physical metrology (length, beam, heading) and radar image chip while coastal AIS is silent/thin (<0.40) | Mismatch / Dark Cluster → `APPROACH_PATROL` → Tactical patrol & USV interceptor dispatch (visual review via radar chip popup) |

---

## 4. Two-Screen Closed-Loop Architecture & REST API Contract

To support the **BattlePlan Next.js Command Cockpit** and recipient nodes on standard laptops, the backend provides a unified C2 REST server (`app/c2_server.py`):

```text
┌─────────────────────────────────────────────────────────────┐
│ Screen 1: Command Cockpit (Next.js UI / Console TUI)        │
│  - GET  /api/ontology/state    (Live tracks & Amber Alerts) │
│  - POST /api/gate/proposals    (Submit candidate COA)       │
│  - POST /api/gate/approve      (Operator decision)          │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Project NexusGate C2 Core (app/c2_server.py)                │
│  - LatencyBoundedGate (<50ms)  - Deterministic Interlock     │
│  - DecisionToken Issuer        - OCSF Hash Audit Logger     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Screen 2: Recipient Console (separate OS process, same box) │
│  - GET  /api/recipient/inbox   (Fetch signed tasking order) │
│  - POST /api/recipient/ack     (Return signed receipt ack)  │
│  - [RasPi 5 GPIO = excluded from demo path, 2026-09-17]     │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 REST Endpoints

The unified server provides **8** endpoints (5 core operational + 1 probabilistic interpret + 1 audit inspection + 1 test admin reset):

1. `GET /api/ontology/state`
   - Returns live tracks, observations, and discrepancy details (count mismatch, coordinate divergence, amber alerts).
2. `POST /api/interpret`
   - App-layer probabilistic propose: hypotheses + candidate COA (**never seals** `DecisionToken`; Pitch-2).
3. `POST /api/gate/proposals`
   - Ingests candidate COA proposal into the operator approval queue (`scenario_id`, raw `coa`, or `interpret:true`).
4. `POST /api/gate/approve`
   - Operator approves/denies proposal. Generates sealed `DecisionToken`.
5. `GET /api/recipient/inbox?unit_id={unit_id}`
   - Recipient node retrieves pending approved taskings.
6. `POST /api/recipient/ack`
   - Recipient submits signed acknowledgment with timestamp and hardware/software signature, sealed to `.audit/gate.jsonl`.
7. `GET /api/audit/trail`
   - Returns current OCSF hash chain records for real-time audit inspection.
8. `POST /api/admin/reset`
   - Clears in-memory runtime state for automated tests and repeatable demo rehearsals without wiping disk audit files.

Operational (not frozen Screen 1/2): `GET /health` (readiness) and `PUT /api/admin/audit/snapshot` (hydrate OCSF jsonl after ephemeral disk reset).

### 4.2 Cloudflare Containers (Phase 2)

Optional public Core. **Same REST paths** as local `sdth-c2-server`. Ingress / Ack stay on laptops.

| Layer | Choice | Why |
|-------|--------|-----|
| Runtime | Cloudflare Containers + Worker front door | Keep FastAPI / `uv` (no Python Workers rewrite) |
| Routing | Worker → `getByName("demo")` singleton | Shared in-memory `C2Runtime` for the venue demo |
| Persistence | Durable Object SQLite snapshot of OCSF jsonl | Container disk is ephemeral |
| Secrets | Wrangler Secrets (`LLM_API_KEY`, optional `LLM_BASE_URL`) | Never commit keys |
| Fallback | Local `uv run sdth-c2-server` | Pitch-day / CI / zero-internet |

Verify: `wrangler dev` + `C2_BASE_URL=http://127.0.0.1:8787 ./scripts/picture_to_tasking.sh`. Production: merge to `main` → GitHub Action **Deploy Cloudflare**. Runbook: [Cloudflare Containers](deploy.md).

---

## 5. Quantitative Operational Benchmarks (Slide 11 Proof)

**Revised 2026-09-21.** The previous table led with gate latency and claimed `0` and `100%`. Both were withdrawn: unfalsifiable absolutes invite exactly the audit a defence judge will run, and gate latency is the wrong headline because **the human decision loop, not the machine, is where the picture-to-tasking gap lives**. Full rationale: **[research §9 (canonical, `edgesentry-commercial`)](https://github.com/edgesentry/edgesentry-commercial/blob/main/docs/strategy/sdth2026/research-maritime-cop-to-tasking-gap.md)** — *not* the older English summary in this repo ([see its staleness notice](research-maritime-cop-to-tasking-gap.md)).

Every metric below carries an explicit statement of what it **cannot** show. State the limit before a judge asks.

| # | Metric | Target | Verification | What it cannot show |
|---|--------|--------|--------------|---------------------|
| **1 ★** | **Total Decision Time (primary)** | Report measured median + spread, **no pre-committed number** | t0 = `CandidateEvent` ingress, t1 = operator approval committed. **A/B against a deliberately inconvenient manual baseline** (read coordinates off a second screen and retype them — the swivel-chair procedure). 30 trials. | n≈4 operators, synthetic scenarios, operators who built the system. **Not a claim about trained watchkeepers under real stress.** |
| 2 | Effector Ack Roundtrip | < 3.0 s | Operator approval → recipient inbox poll → signed Ack, with `mocks/usv.py` running as a **separate OS process** on localhost. | Laptop-local, no radio link, no contested spectrum. Says nothing about field latency. |
| 3 | Gate Transit Latency (p95) | < 50 ms | 100 synthetic COA evaluations; interlock fast-reject < 5 ms. | **Demoted to secondary.** Machine latency was never the bottleneck; it is table stakes, not a differentiator. |
| 4 | Deterministic Refusal Coverage | **Report `n/n` passed, never "0 unauthorized"** | Invalid geofences, speed breaches, duplicate IDs, timeout expiry. Each must fail safe. | Near-tautological: the gate refuses what it was written to refuse. **Does not cover multi-sensor collusion, or a plausible-but-wrong COA that violates no rule.** |
| 5 | Audit Chain Verifiability | **Report broken-link count (expect 0 of n records), never "100% integrity"** | `eds audit verify-chain` recomputes the chain **in a separate binary** from the one that wrote it. | Detects tampering; **does not prevent it**. Append-only on a local filesystem — an attacker with write access can truncate the tail. |
| 6 | Tracking Continuity (UNCLOS Art. 111) | Zero unexplained gaps across asset handoffs in the demo run | Ledger records every handoff (from / to · timestamp · gap seconds); `/verify` surfaces it. | Continuity of **our own records**, not a legal finding. Court admissibility is untested. |

**Do not say** "BLAKE3" until `edgesentry-rs` is wired (`core/audit.py` is SHA-256 today), "it ran on real hardware" (laptop only), or "100% / zero" for anything above.

---

## 6. Phased Execution Roadmap

### Phase 0: Core Foundations (Completed)
- [x] Spatial entity graph (`core/ontology.py`) with distance association without shared track IDs.
- [x] Deterministic interlocks (`core/interlock.py`) for geofence and speed violations.
- [x] Latency-bounded gate (`core/gate.py`) with timeout fallback to station-keep.
- [x] OCSF-compliant append-only hash audit logger (`core/audit.py`).
- [x] Basic S1, S2, S3 scenario stubs.

### Phase 1: MVP Synthetic Scenarios & C2 REST Loop (Completed)
- [x] **S2 Scenario Polish** (⛔ *was "Hero" — demoted 2026-09-20 when the air domain was dropped; mechanism reused by maritime scenarios*)**:** Add `intel_text` social media / recon input, count discrepancy (3 vs 1), and low-confidence EO blur (0.42) triggering `COUNT_AND_BEARING_MISMATCH` Amber Alert.
- [x] **Vendor-Neutral Effector Adapter:** Implement `app/adapters/usv_rest.py` with `EFFECTOR_BASE_URL` (backward-compat shim for Clearbot).
- [x] **Unified C2 REST Server:** Implement `app/c2_server.py` with the 7 endpoints supporting the Next.js Command UI on Screen 1 and simulated Recipient on Screen 2.
- [x] **19-Event Temporal Streamer:** Implement `scripts/stream_events.py` for T-60s to T-00s event playback.
- [x] **Automated Benchmark Suite:** Implement `scripts/benchmark.py` verifying Slide 11 performance metrics.

### Phase 2: Backend Closed Loop & Operational Core (Active — Partial)

Phase 2 delivers thin / demo-fidelity slices of the pitch pillars (backend closed loop). Production CV, live field hardware, and full swarm loads remain Phase 5. Provenance labels: [Data provenance](data-provenance.md).

**Done:**

- [x] **Pitch-4 Picture→Tasking demo script:** `scripts/picture_to_tasking.py` + `scripts/picture_to_tasking.sh` (issue #24).
- [x] **Pitch-3 Deterministic gate stress:** `scripts/benchmark.py` (issue #23).
- [x] **Pitch-2 Probabilistic interpreter:** `app/llm_interpreter.py` + `POST /api/interpret` (issue #22).
- [x] **Pitch-2 follow-on LiteLLM live path:** (issue #32).
- [x] **Pitch-1 Multimodal demo harness & SAR CandidateEvent adapter:** (issue #25).
- [x] **In-house SAR pipeline (SIA) & fixture fail-safe:** `app/adapters/sentinel_imagery.py` + Singapore Strait fixture (issue #47). AIS via **SIA ingest only** (`demo` / `offline`) → SIA local SQLite.
- [x] **Optional open-feed ingress:** (issue #16).
- [x] Validate backend closed loop via curl / scripts (`scripts/picture_to_tasking.sh`).
- [x] Cloudflare Containers + local fallback (issue #18).
- [x] Laptop I/O runbook (issue #17); ~~RasPi stretch (issue #20)~~ **excluded from the demo path (2026-09-17)**; CI green (issue #19).

**Remaining (track via GitHub `phase-2` issues):**

- [x] **Ingress event replay log** (#54): append-only `.audit/ingress.jsonl` + `scripts/replay_ingress.py` (not gate authority).
- [x] **GLINT Assumed-mock HTTP stub + client** (#55): `:5051` / `mocks/glint.py` + `scripts/mock_glint_server.py` + `app/adapters/glint_client.py`; schema swap on Team 02 handover (live = Phase 4).
- [x] **Dual-SAR Multi-Fidelity Corroborator** (#56): `app/adapters/dual_sar.py` — GLINT macro × SIA micro; fail-safe to SIA/fixture.
- [x] **Temporal Kinematic Dead-Reckoning** (#57): `core/kinematics.py` — SAR $T-\Delta t$ → coastal radar $T-0$.
- [x] **Dynamic Intercept POI** (#58): lead-pursuit waypoint + ETA in `core/kinematics.py` / `core/coa.py` / `app/agent.py`.
- [x] **OSINT text parser** (#59): `app/adapters/osint_text.py` — Synthetic social text → count/bearing for S2 (no SNS API).
- [x] **Live open-feed AIS / ADS-B adapter** ([#70](https://github.com/edgesentry/sdth-nexus-c2/issues/70)): `app/adapters/open_feed.py` (Indago DuckDB / live poll / fixture fallback) for Singapore Strait pitch realism.
- [x] **AIS via SIA ingest only** (#60): `demo` / `offline` plugins → SIA local SQLite (no alternate AIS bridge).
- [x] **NexusGate verification WebUI** (#65): `/verify` (Jinja2/HTMX on `sdth-c2-server`) Screen 1/2 harness on frozen REST (not external BattlePlan pitch UI).

**Added 2026-09-21 — the only remaining work that changes what we can claim.** Everything above proves the loop runs; these three prove it is *worth* running. Strategy rationale, cut list, and abort conditions: [app-dev-plan-nexus-c2.md](https://github.com/edgesentry/edgesentry-commercial/blob/main/docs/strategy/sdth2026/app-dev-plan-nexus-c2.md).

- [x] **Cryptographic core via `edgesentry-rs`** (`core/audit_eds.py`): `ctypes` → `libedgesentry_bridge` for BLAKE3 + Ed25519 writes; `eds audit verify-chain` as a **separate process** for verification. Consume, do not fork. **Never reimplement `postcard` in Python** — `AuditRecord::hash()` is `blake3(postcard(record))`, and a wrong reimplementation succeeds on write and only fails at verification. Fallback if `ctypes` stalls: CLI subprocess for verify; on macOS 27+ rebuild a loadable dylib via `scripts/build_eds_bridge_dylib.sh`. Benchmark #5.
- [ ] **Tracking Continuity Ledger (UNCLOS Art. 111)** ★: per `track_id`, record every asset handoff (from / to · timestamp · gap seconds) so non-interruption of pursuit is machine-assertable and machine-verifiable. One row on `/verify`. Benchmark #6. *Why it matters: "the AI flagged it" loses in an international tribunal; "pursuit was never interrupted, here is the chain" does not.*
- [ ] **Total Decision Time A/B** ★ (extend `app/bench_stress.py` + one manual path in `app/ui/console.py`): t0 → t1 instrumentation plus the swivel-chair baseline. Benchmark #1. *The existing p95 measures machine latency only and cannot answer "does it work?".*

### Phase 3: External BattlePlan polish (Not in-repo pitch UI)
> **UI Boundary:** **BattlePlan** = external pitch UI (**outside this repo**). In-repo NexusGate verification harness is **Phase 2** ([#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65), done).

Harness delivered at `/verify` on `sdth-c2-server` (Jinja2/HTMX; no Node):

- [x] Screen 1 `/verify/command` + Screen 2 `/verify/recipient` (#65).
- [x] Evidence chips via `/static/fixtures/` (`evidence_image_uri`) (#65).
- [x] Dual-SAR / Sentinel fixture ingress on Screen 1 (#65 / #56).
- [x] Optional open feeds (Phase 2 / issue #16).
- [x] ~~RasPi GPIO blink stretch (issue #20)~~ — **excluded from the demo path** (2026-09-17). Code stays in `app/adapters/raspi_hardware.py`; edge deployment is a design claim only. Never say "it ran on real hardware."

### Phase 4: Pitch-Day Polish & Hackathon Live Demonstration (Planned: Sep 25–27)
Hackathon-completeable only. Anything that needs field hardware, real AI pipelines, or sovereign buyers → Phase 5.
- [ ] **Team 02 GLINT Live Cross-Team Integration (Day 1 - Fri 25 Sep)**:
  - Connect with Team 02 (GLINT) at NUS Enterprise i³ Building Level 2 workspace.
  - Verify live GLINT REST / MCP API endpoint against `CandidateEvent v1.3.0` schema.
  - Validate live stream into C2 (`POST /api/ingress/candidate-event`).
  - Verify zero-risk fallback: seamless switch to in-house SIA (`:5050`) or local Singapore Strait golden fixture if network degrades.
- [ ] **End-to-End Operational Playthroughs (Day 1 Evening)**:
  - **Hero = maritime.** Scenario S3 / S1: Dual-SAR (GLINT + SIA) + kinematic projection vs coastal radar $\to$ Intercept POI Tasking $\to$ Ack, then **continuity ledger across the handoff**.
  - ⛔ **S2 is no longer the hero.** The [2026-09-20 team decision](https://github.com/edgesentry/edgesentry-commercial/blob/main/docs/strategy/sdth2026/meeting-20260920-sdth-planning.md) formally **dropped the air / drone domain** (100% maritime — Singapore Strait vessel incursions). `s2_air_corridor_attritable.py` stays in the repo because the **discrepancy mechanism (count / bearing mismatch) is domain-agnostic and reused by the maritime scenarios**, but it must not be pitched. Maritime scenario definition is owned by S2 John Teoh (due 9/22).
- [ ] **Preliminary Judging Cut (Day 2 - Sat 26 Sep)**:
  - Deliver preliminary pitch to qualify in the Top ~20 of 37 two-day teams.
- [ ] **VIP Judging Panel Pitch (Day 3 - Sun 27 Sep)**:
  - Live 3-minute pitch before MG Kelvin Fan (Chief of Air Force), Mr Tan Peng Yam (Chief Defence Scientist, MINDEF), Prof Quek Tong Boon, and MINDEF/DSTA leadership.
  - Live demonstration of the **revised** §5 benchmarks: **measured total decision time vs manual baseline (lead with this)**, < 3.0 s Ack, < 50 ms gate transit, `n/n` refusal coverage, chain re-verified by a separate binary, continuity ledger with no unexplained gaps. **State each limitation before being asked.**
- [ ] **Validate the inter-agency premise with DSTA / RSN on site (Day 2 morning)**: our claim that authority hand-offs depend on committee procedure is **our inference, not sourced from public material**. If it is wrong, the pitch subject shifts from "inter-agency coordination" to "delegation and evidence inside a single agency" — too late to discover on Sunday.

### Phase 5: Post-Hackathon → Sovereign PoC (Planned)
Maps to the 9-month NUS Defence Tech Venture Lab bridge. Owns the pitch points Phase 4 cannot close.

| Pitch point | Phase 5 deliverable |
|-------------|---------------------|
| **1. Multimodal integration** | Multi-constellation SAR (Sentinel-1, ICEYE, Capella) + live coastal AIS + 3D radar + EO/IR slew-to-cue; GPU-accelerated Rotated Object Detection (Rotated DETR / YOLOv8-OBB); multi-vendor IMM-PDAF association under latency/spoof pressure (see [Target Production Architecture](architecture/sar_pipeline.md#3-target-production-sovereign-architecture)) |
| **2. Probabilistic interpretation** | App-layer LLM + CV pipeline: text intel extraction, YOLO/EO blur, hypothesis COAs — still gated by Core |
| **3. Deterministic gate** | Air-gapped Core hardening; 1,000+ track swarm stress; dual-key Tier-2; sub-50ms under load |
| **4. Picture→Tasking** | Controlled-water USV / Clearbot field trial; production recipient adapters; optional RasPi forward outpost as primary edge Ack |
| **5. Sovereign interlock** | DSTA/SAF C4 evaluation sandbox add-on; OCSF + stronger crypto seal (e.g. Ed25519); Agent Governance & Safety Interlock Evaluation SOW; tactical data link integration (Link 16, Link 22, STANAG 4586) |

Checklist:
- [ ] **Probabilistic App Layer:** Local LLM / CV ingestion → candidate COAs; Core remains zero-hallucination gate.
- [ ] **Live Sensor Harness:** Singapore coastal streams (AIS, optical, open air) beyond demo stubs; adversarial / spoof cases.
- [ ] **Swarm & Latency Stress:** Air-gapped Core vs synthetic 1,000+ track flood; gate p95 & `n/n` refusal coverage under load.
- [ ] **Field Effector Trial:** Joint USV / MPA-style trial — signed token → physical or near-physical Ack.
- [ ] **Legacy / Prime Bridges:** STANAG / Link-16 / JSON-RPC adapters (read-only or gated write) for prime C2 adjacency.
- [ ] **Sovereign Sandbox + SOW:** Deploy as gateway add-on in DSTA/MINDEF testbed; first evaluation PoC contract narrative.

```text
Phase 0–2 (core & backend)     Phase 3–4 (UI & demo day)    Phase 5 (lab → field → buyer)
Synthetic Many Eyes + Gate  →  Two-screen software loop  →  Live AI + USV + sovereign PoC
```

---

## 7. Success Criteria (Demo Day — Phase 4)

1. **Discrepancy, not false consensus:** run a **maritime** scenario (S3 / S1) and show that conflicting sources raise an Amber Discrepancy Alert instead of a hallucinated unified picture. Do **not** claim discrepancy detection is novel — it is already standard in commercial and military systems. What is ours is **what happens after the cue**.
2. **Two-Screen Handshake:** Command approves tasking on Screen 1; Recipient receives token and presses Ack on Screen 2, with the recipient running as a **separate OS process**; Ack sealed in the OCSF audit log within 3 seconds.
3. **Measured, not asserted:** present live results from `scripts/benchmark.py` — **lead with total decision time vs the manual baseline**, then Ack roundtrip, gate transit, `n/n` refusal coverage, and a chain re-verified by a separate binary. Report numbers actually measured; if the A/B does not produce data by Saturday evening, **say it is unmeasured and present the measurement design** rather than substituting a machine-latency number.
4. **Continuity under law:** show the UNCLOS Art. 111 ledger — every asset handoff with its gap — and name the limit: this is continuity of our records, not a legal finding.
5. **Judge Defense:** answer MINDEF/DSTA with: *"We do not build sensors or shooters. We build the deterministic sovereign interlock that governs action when sensors disagree."* Acknowledge that **SMCC already cut threat assessment from hours to minutes**; our claim is confined to the segment after the cue.

**Fallback if Saturday runs short:** drop the A/B and ship the continuity ledger alone. It is the one deliverable neither Palantir nor Anduril demonstrates, and it is the one that lands with a former MINDEF Deputy Secretary (Policy).

### Phase 5 Success Criteria (Post-Demo)

1. **Probabilistic × Deterministic in production path:** LLM/CV proposes; Core never approves uncorroborated kinetic / high-impact tasking.
2. **Field Picture-to-Ack:** Live or near-live coastal ingress → operator approve → USV/edge Ack under controlled trial.
3. **Buyer-shaped PoC:** DSTA/SAF sandbox evaluation SOW scoped as *Agent Governance & Safety Interlock*, not full C2 replacement.
