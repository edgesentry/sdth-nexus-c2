# PLAN — sdth-nexus-c2 (PS 04)

> Canonical planning source for this repo (MkDocs / GitHub Pages).

**Status:** Phase 2 venue app (Backend closed loop & Cloudflare Core) · Phase 5 = post-hackathon sovereign PoC · **2026-09-17 Updated**  
**Challenge:** SDTH 2026 **PS 04 — One Picture, Many Eyes** (From Picture to Tasking)  
**Product face:** Project NexusGate (core gate) + venue Command and Control (C2) app  
**Target Reviewers:** DSTA, MINDEF/SAF C4I, EDTH, NUS Defense Tech Venture Lab  
**Architecture Consensus (2026-09-17 Team Decision):** Purely software-driven digital C2 application running on standard laptops. Physical robotics/hardware excluded from primary hackathon deliverables to guarantee execution within the 48-hour window. Effectors are generic REST/simulated endpoints (`UsvRestAdapter` / simulated recipient nodes).

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
| **Social Media OSINT / Text Intel** | **S2** | Unstructured text summary (Instagram/Telegram/Recon) | Exaggerated social reports ("20 drones incoming") filtered down to 3 Shahed-136 drones heading to Objective Bravo at T+4 min |
| **Coastal / Gap-Filler Radar** | S1–S3 | 2D/3D kinematic contacts | Disagrees in count (sees 1 contact) or bearing (+1,200m north) |
| **EO / Optical Camera** | S1, S2 | Visual bearings, YOLO bounding box | Obscured blur, low confidence (0.42), unable to verify independently |
| **AIS / Open AIS** | S1, S3 | Manipulable / delayed cooperative stream | Spoofed stationary contact, or stale lane density pattern break |
| **RF Spectrum** | S1, S2 | Passive RF scan / CUAS emitter detection | Silent signature (confirms cheap drone) or control band near contact |
| **ADS-B Sector** | S2 | Transponder air picture | Missing squawk (empty sector confirmation) |

### 2.2 19-Event Temporal Progression (Slide 09)

To demo temporal alignment (PS 04 §2-03) and avoid static toy data, the scenario engine supports **19-step temporal playback** (`scripts/stream_events.py`):
1. **Events 01–05 (T-60s to T-45s):** Early reconnaissance chatter, social media rumors, and sparse radar blips.
2. **Events 06–10 (T-40s to T-25s):** Coastal radar locks high-speed inbound track; optical cameras slew to cue area.
3. **Events 11–15 (T-20s to T-10s):** EO/IR detects low-confidence blur; Corroboration Engine flags **Amber Contradiction Alert** (Social/Recon reports 3, Radar sees 1 at divergent bearing).
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
| **S3** | **Shipping Lane SPOF — Pattern Break** | Slide 02, 06 | Thin open AIS density (<0.40) while coastal radar spots uncorrelated inbound | Mismatch ≥2,000m → `APPROACH_PATROL` → Pattern verification patrol |

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
│ Screen 2 / Edge Node: Recipient Console (Simulated Laptop)  │
│  - GET  /api/recipient/inbox   (Fetch signed tasking order) │
│  - POST /api/recipient/ack     (Return signed receipt ack)  │
│  - [Optional] RasPi 5 GPIO     (Secondary stretch demo)     │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 REST Endpoints

The unified server provides 7 endpoints (5 core operational + 1 audit inspection + 1 test admin reset):

1. `GET /api/ontology/state`
   - Returns live tracks, observations, and discrepancy details (count mismatch, coordinate divergence, amber alerts).
2. `POST /api/gate/proposals`
   - Ingests candidate COA proposal into the operator approval queue.
3. `POST /api/gate/approve`
   - Operator approves/denies proposal. Generates sealed `DecisionToken`.
4. `GET /api/recipient/inbox?unit_id={unit_id}`
   - Recipient node retrieves pending approved taskings.
5. `POST /api/recipient/ack`
   - Recipient submits signed acknowledgment with timestamp and hardware/software signature, sealed to `.audit/gate.jsonl`.
6. `GET /api/audit/trail`
   - Returns current OCSF hash chain records for real-time audit inspection.
7. `POST /api/admin/reset`
   - Clears in-memory runtime state for automated tests and repeatable demo rehearsals without wiping disk audit files.

---

## 5. Quantitative Operational Benchmarks (Slide 11 Proof)

The pitch deck commits to 4 rigorous engineering metrics:

| Metric | Target | Verification Method (`scripts/benchmark.py`) |
|--------|--------|-----------------------------------------------|
| **Gate Latency (p95)** | **< 50 ms** | 100 synthetic COA evaluations; measure gate transit time (interlock fast-reject < 5ms). |
| **Unauthorized Taskings** | **0** | Stress-test with invalid geofences, speed breaches, duplicate IDs, and timeout expiries. All must fail safe. |
| **Picture-to-Ack Roundtrip** | **< 3.0 s** | End-to-end benchmark from operator approval through recipient inbox poll and signed Ack submission. |
| **Audit Trace Integrity** | **100% OCSF** | Cryptographic audit chain verification traversing all records; verify no broken hashes or missing links. |

---

## 6. Phased Execution Roadmap

### Phase 0: Core Foundations (Completed)
- [x] Spatial entity graph (`core/ontology.py`) with distance association without shared track IDs.
- [x] Deterministic interlocks (`core/interlock.py`) for geofence and speed violations.
- [x] Latency-bounded gate (`core/gate.py`) with timeout fallback to station-keep.
- [x] OCSF-compliant append-only hash audit logger (`core/audit.py`).
- [x] Basic S1, S2, S3 scenario stubs.

### Phase 1: MVP Synthetic Scenarios & C2 REST Loop (Completed)
- [x] **S2 Hero Scenario Polish:** Add `intel_text` social media / recon input, count discrepancy (3 vs 1), and low-confidence EO blur (0.42) triggering `COUNT_AND_BEARING_MISMATCH` Amber Alert.
- [x] **Vendor-Neutral Effector Adapter:** Implement `app/adapters/usv_rest.py` with `EFFECTOR_BASE_URL` (backward-compat shim for Clearbot).
- [x] **Unified C2 REST Server:** Implement `app/c2_server.py` with the 7 endpoints supporting the Next.js Command UI on Screen 1 and simulated Recipient on Screen 2.
- [x] **19-Event Temporal Streamer:** Implement `scripts/stream_events.py` for T-60s to T-00s event playback.
- [x] **Automated Benchmark Suite:** Implement `scripts/benchmark.py` verifying Slide 11 performance metrics.

### Phase 2: Backend Closed Loop & Cloudflare Core Deployment (Active Focus)
- [ ] Validate end-to-end backend closed loop via curl / automated scripts without frontend dependency.
- [ ] Containerize C2 server for optional **Cloudflare Containers** deployment while retaining identical REST contract.
- [ ] Establish hardened fallback to local `sdth-c2-server` for zero-internet venue reliability.
- [x] **Pitch-3 Deterministic gate stress:** `scripts/benchmark.py` floods ontology with 100+ tracks and mixed COAs; asserts gate p95 < 50 ms and unauthorized = 0 (issue #23).

### Phase 3: BattlePlan UI Integration on Frozen REST Contract (Planned)
- [ ] Integrate the Next.js BattlePlan UI with `app/c2_server.py` (two-screen software handshake).
- [ ] Wire **demo-grade** open feeds (`data.gov.sg` / open air traffic) as optional ingress — synthetic S1–S3 remain the primary story.
- [ ] (Optional Stretch) Laptop-side RasPi GPIO blink as secondary proof — not required for pitch.

### Phase 4: Pitch-Day Polish & Live Demonstration (Planned)
Hackathon-completeable only. Anything that needs field hardware, real AI pipelines, or sovereign buyers → Phase 5.
- [ ] Run rehearsals for 3-minute hackathon pitch & live software demonstration.
- [ ] Verify 4 commitments on live screen: multimodal contradiction, deterministic gate, Picture→Tasking loop, immutable audit.

### Phase 5: Post-Hackathon → Sovereign PoC (Planned)
Maps to the 9-month NUS Defence Tech Venture Lab bridge. Owns the pitch points Phase 4 cannot close.

| Pitch point | Phase 5 deliverable |
|-------------|---------------------|
| **1. Multimodal integration** | Live coastal AIS + optical (+ RF when available); multi-vendor association under real latency / spoof pressure |
| **2. Probabilistic interpretation** | App-layer LLM + CV pipeline: text intel extraction, YOLO/EO blur, hypothesis COAs — still gated by Core |
| **3. Deterministic gate** | Air-gapped Core hardening; 1,000+ track swarm stress; dual-key Tier-2; sub-50ms under load |
| **4. Picture→Tasking** | Controlled-water USV / Clearbot field trial; production recipient adapters; optional RasPi forward outpost as primary edge Ack |
| **5. Sovereign interlock** | DSTA/SAF C4 evaluation sandbox add-on; OCSF + stronger crypto seal (e.g. Ed25519); Agent Governance & Safety Interlock Evaluation SOW |

Checklist:
- [ ] **Probabilistic App Layer:** Local LLM / CV ingestion → candidate COAs; Core remains zero-hallucination gate.
- [ ] **Live Sensor Harness:** Singapore coastal streams (AIS, optical, open air) beyond demo stubs; adversarial / spoof cases.
- [ ] **Swarm & Latency Stress:** Air-gapped Core vs synthetic 1,000+ track flood; gate p95 & unauthorized=0 under load.
- [ ] **Field Effector Trial:** Joint USV / MPA-style trial — signed token → physical or near-physical Ack.
- [ ] **Legacy / Prime Bridges:** STANAG / Link-16 / JSON-RPC adapters (read-only or gated write) for prime C2 adjacency.
- [ ] **Sovereign Sandbox + SOW:** Deploy as gateway add-on in DSTA/MINDEF testbed; first evaluation PoC contract narrative.

```text
Phase 0–2 (core & backend)     Phase 3–4 (UI & demo day)    Phase 5 (lab → field → buyer)
Synthetic Many Eyes + Gate  →  Two-screen software loop  →  Live AI + USV + sovereign PoC
```

---

## 7. Success Criteria (Demo Day — Phase 4)

1. **Slide 04 Live Validation:** Run S2; prove that Civilian Social/Recon (3) vs Radar (1) vs EO/IR (blur) triggers Amber Discrepancy Alert rather than a hallucinated unified picture.
2. **Two-Screen Handshake:** Command approves tasking on Screen 1; Recipient receives token and presses Ack on Screen 2 (laptop); Ack is sealed in OCSF audit log within 3 seconds.
3. **Benchmarked Reliability:** Present live execution results from `scripts/benchmark.py` proving <50ms gate latency, 0 unauthorized taskings, and 100% audit integrity.
4. **Judge Defense:** Confidently answer MINDEF/DSTA: *"We do not build sensors or shooters. We build the deterministic sovereign interlock that governs action when sensors disagree."*

### Phase 5 Success Criteria (Post-Demo)

1. **Probabilistic × Deterministic in production path:** LLM/CV proposes; Core never approves uncorroborated kinetic / high-impact tasking.
2. **Field Picture-to-Ack:** Live or near-live coastal ingress → operator approve → USV/edge Ack under controlled trial.
3. **Buyer-shaped PoC:** DSTA/SAF sandbox evaluation SOW scoped as *Agent Governance & Safety Interlock*, not full C2 replacement.
