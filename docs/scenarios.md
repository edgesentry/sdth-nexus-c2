# Multi-Domain Defense Scenarios

## 🌐 The Tri-Service Multi-Domain Unification Narrative

In modern hybrid littoral-maritime defense, sovereign security depends on breaking sensor silos across **Army (IDTF)**, **Navy (RSN / PCG)**, **Air Force (RSAF)**, and **Space Reconnaissance (GLINT SAR)**:

1. **Army (IDTF):** Monitors coastal perimeters via CCTV and ground EW, but lacks visibility over the maritime launch origin or over-water air radar tracking.
2. **Navy (RSN / PCG):** Monitors commercial shipping via AIS, but cannot detect transponder spoofing, concealed deck rails, or low-RCS air incursions on its own.
3. **Air Force (RSAF):** Tracks fast-moving radar contacts, but struggles to differentiate sea clutter or civilian drones from hostile loitering munitions without maritime context or RF emitter triangulation.
4. **Space Recon (GLINT SAR):** Captures physical hull dimensions and orbital radar backscatter, providing an unalterable ground truth anchor against spoofed declarations.

**NexusGate** unifies these asynchronous, disparate streams into a canonical track core, executes deterministic contradiction checks, and dispatches coordinated multi-service tasking (Air Force GBAD kinetic intercept + Navy PCG mothership interdiction).

> **Core Architectural Creed:** Do not fuse disparate tracks into one hallucinated "super-track." Preserve raw modality boundaries, surface deterministic kinematic and spatial contradictions, and enforce mathematical safety interlocks before human commanders authorize action.

---

## 🏛️ The Three Operational Pillars

> **Primary hero is airborne `S2_osint_swarm`. Maritime secondary track is `S1_trojan` (tri-service + GLINT hull anchor) then `S3_sar_ais` (GLINT macro × SIA × AIS dark vessel). marun `scenario_02_conflicting` is a legacy fusion bench, not Nexus S2.**

### Pillar Hierarchy (Scenario Sequence)

| Rank | Nexus ID | Role | GLINT Usage |
|------|----------|------|-------------|
| **1 (Primary Hero)** | **`S2_osint_swarm`** | In-flight OSINT ~50 × radar 4 / RF silence → GNSS denial + GBAD (Cognitive / Autonomous Saturation / Anti-Exhaustion) | **Not used** (Air domain & social sensor) |
| **2** | **`S1_trojan`** | Maritime + Land/Air: AIS vs coastal radar, CNI VETO, Option B (Tri-service contradiction + spatial SAR mothership lock) | **Used** — Mothership aft-deck / hull spatial anchor (already in narrative & export) |
| **3** | **`S3_sar_ais`** | Dark vessel: Dual-SAR × thin AIS → Approach Patrol (Orbital latency → reachable ellipse → USV intercept) | **Primary showcase** — macro cluster (`:5051` / live) + SIA micro |

*Auxiliary baseline*: `S1_ais_spoof` serves as a lightweight baseline outside the three pillars (no GLINT).

---

### GLINT Integration Flow

```text
Pitch / E2E Sequence
  S2 (no GLINT)                    ← Cognitive cue / Autonomous saturation / Anti-exhaustion
       │
  S1_trojan (+GLINT stub/live)     ← Tri-service mismatch + Spatial SAR deck rail lock
       │
  S3_sar_ais (+GLINT macro + SIA)  ← Orbital latency → Reachable ellipse → Lead pursuit USV
```

- **Trojan (Pillar 2):** GLINT is not the primary contradiction trigger, but a **physical anchor** (aft-deck rail verification). Offline uses fixture; demo supports mock `:5051`.
- **S3 (Pillar 3):** GLINT is the **ingress event** (corridor-scale anomaly). SIA extracts micro OBB, and Nexus calculates kinematics / COA. This is the primary GLINT integration showcase.

---

### Data Alignment with marun

| Data Feed | Storage Location | Role & Provenance |
|-----------|------------------|-------------------|
| **S2 Synthetic** (OSINT / radar 4 / acoustic / RF silent) | marun `exports/s2_osint_swarm_scenario.jsonl` | Canonical export (*`scenario_02_conflicting` is a legacy fusion bench, not Nexus S2*) |
| **Trojan Maritime + Land/Air + GLINT row** | Existing `synthetic_maritime_data/` → `exports/s1_trojan_*` | Canonical multi-service export |
| **S3 Coastal AIS / Radar** | marun optional; **GLINT macro / SIA chip owned by Nexus / Team 02 / SIA** | Ingress feeds + live/fixture endpoints |

---

## 🎯 Scenarios Realizing the Narrative

| Scenario ID | Operational Title | Primary Contradiction | Final Resolution |
|-------------|-------------------|-----------------------|------------------|
| **`S2_osint_swarm`** *(Pillar 1 - Primary)* | **Airborne OSINT & Autonomous Shahed Swarm** | In-flight civilian passenger OSINT (~50 Shahed spotted) vs gap-filler radar (clutter blindspots); RF-silent autonomous GPS navigation | `CUE_AND_IDENTIFY` → `GNSS_DENIAL_AND_GBAD_CUE` |
| **`S1_trojan`** *(Pillar 2)* | **Trojan Mothership (Tri-Service Contradiction)** | Navy Happy Tug AIS ~6 kt vs coastal radar ~120 kt UAS; Air/Army EW LOB triangulation + GLINT aft-deck anchor | Guardrail CNI VETO → `OFFSHORE_INTERCEPT_RF_SOFTKILL` (Option B) |
| **`S3_sar_ais`** *(Pillar 3)* | **Shipping Lane & Dark Vessel (Dual-SAR)** | Space-based SAR anomaly diff (GLINT macro + SIA micro) vs thin AIS; dead-reckoned reachability envelope | `APPROACH_PATROL` (Dynamic Lead-Pursuit) |
| `S1_ais_spoof` *(Auxiliary)* | **Sea Approach Incursion** | Stationary AIS transponder vs ~20 kt radar/EO contact (~850 m spatial divergence) | `ISR_IDENTIFY_CONTACT` |

### Core Demonstration Highlights

* **1. `S2_osint_swarm` (Airborne Passenger OSINT & Multi-Stage Swarm Corroboration — Pillar 1 Primary Hero):**  
  Demonstrates how unverified civilian social reports serve as an initial trigger, progressively cross-referenced with military sensors to uncover an intentional saturation attack.  
  A civilian passenger aboard a commercial flight bound for Japan accidentally spots a massive swarm of ~50 unknown delta-wing drones flying low below the aircraft and posts smartphone video/photos to social media without knowing where they were or where the drones are headed → NexusGate uses this OSINT post as an early-warning cue and initiates phased multi-modal sensor correlation → Ground EW/ESM detects complete RF silence, proving the drones exceed remote-control line-of-sight and navigate autonomously on pre-programmed GPS/INS waypoints (invalidating standard RF C2 jamming) → Coastal 3D gap-filler radar detects only 4 intermittent contacts due to low-altitude sea clutter, but coastal acoustic arrays and EO/IR cameras confirm the low-flying swarm → NexusGate extrapolates the autonomous waypoint trajectory, revealing the true operational picture: a 50-drone saturation ingress targeting Singapore critical infrastructure → Directs local GNSS denial alongside GBAD point-defense cueing (anti-exhaustion doctrine).

* **2. `S1_trojan` (Tri-Service Disagreement & CNI Safety Guardrail — Pillar 2):**  
  Demonstrates cross-domain contradiction resolution across Navy, Air Force, and Army sensors anchored by Space SAR.  
  `SDTH-Sensor-Simulation` JSONL → Navy AIS (6.1 kt tug) vs Coastal Radar (120.4 kt UAV) velocity mismatch → Air ESM ∩ Army EW Line of Bearing (AoA) launch triangulation onto mothership *Happy Tug 8* → GLINT orbital SAR provides hull spatial anchor (12m linear aft-deck rail) → Hard VETO of terminal SAM engagement directly over Jurong Island petrochemical complex (`SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD`) → Enforced failsafe roll-over to **Option B** dual tasking (Air Force GBAD offshore kinetic engagement + Navy PCG mothership interdiction).

* **3. `S3_sar_ais` (Space SAR Ground Truth × AIS Dark Vessel Corroboration & Dynamic Intercept — Pillar 3):**  
  Demonstrates unmasking non-emitting vessels and bridging satellite temporal latency to tactical response via GLINT macro corridor alert and SIA micro metrology.  
  Connects macro space-based SAR scene-difference alerts (GLINT `:5051`/live) and micro OBB metrology (SIA `:5050`) to tactical C2 tasking. Solves 15-minute satellite orbital latency via dynamic **Reachable Ellipse** dead-reckoning and coastal radar handoff → Computes dynamic lead-pursuit **Point of Interception (POI)** collision kinematics rather than dispatching units to stale historical coordinates → Authorizes and dispatches Approach Patrol USV.

---

## ⏱️ Operational Chronicles: Chronological Storylines

### 1. `S2_osint_swarm` — Airborne Passenger OSINT & Autonomous Shahed Swarm Contradiction (Pillar 1 Primary)

```
[Stage 1 (T-00:00): Unknowing Civilian Passenger OSINT Trigger]
  • Commercial In-Flight Sighting: A civilian passenger departing on a commercial flight bound for Japan glances
    out the cabin window, spots an eerie formation of ~50 delta-wing drones cruising low below the aircraft,
    and uploads smartphone video and photos to social media (X/TikTok):
    "Just saw a massive swarm of tiny delta drones flying low below our flight! What on earth is that?! #ufo #drones"
  • Zero Geographic / Target Context: The post contains no specific coordinates or country names; the passenger has
    no knowledge of where the drones originated or where they are headed.
  • NexusGate Semantic Trigger: Ingests the viral passenger upload via computer vision and semantic parsing,
    extracting an early cue: ~50 Shahed-class airframes, estimated flight vector ~248° at ~105 kt.
    Initial status: unverified civilian airborne observation.
       │
       ▼
[Stage 2 (T+00:03): RF-Silence Gating & Autonomous Flight Profiling]
  • Military Spectrum Scan: Ground EW arrays and Air Force ESM sweep 433 MHz, 900 MHz, 2.4 GHz, and 5.8 GHz.
  • Deterministic Finding (RF_SILENT_AUTONOMOUS): Zero command-and-control (C2) link or video telemetry detected.
    The swarm is flying well beyond direct remote-control line-of-sight range.
  • Control Mode Lock: Proves pre-programmed GPS/INS waypoint flight.
    Enforces tactical interlock: disallows conventional RF C2 jamming (which is useless against autonomous guidance).
       │
       ▼
[Stage 3 (T+00:05): Multi-Sensor Correlation & Blindspot Penetration]
  • Radar Low-Altitude Clutter: Coastal 3D gap-filler radar detects only 4 intermittent, low-RCS blips due to
    sea clutter and island terrain masking (OSINT 50 vs Radar 4 contradiction).
  • Acoustic Triangulation: Coastal acoustic listening arrays isolate the distinctive low-frequency two-stroke
    moped engine harmonic along the reported ingress corridor, confirming multiple airframes inside radar blindspots.
  • EO/IR Slaved Acquisition: Long-range thermal cameras slew to cue and detect delta-wing silhouettes cutting through night haze.
       │
       ▼
[Stage 4 (T+00:07): Kinematic Trajectory Extrapolation — Revealing the Big Picture]
  • Intent & Target Unveiling: NexusGate's kinematic engine projects the autonomous waypoint vector forward.
    The projected flight corridor intersects Jurong Island petrochemical complex and western air defense sectors.
  • Common Operating Picture (COP): Assembles the full operational picture from the passenger's aerial snapshot:
    "Not a random anomaly, but a 50-unit autonomous pre-programmed saturation raid inbound for Singapore CNI."
       │
       ▼
[Stage 5 (T+00:09): Coordinated Swarm Countermeasure Tasking (C2 Resolution)]
  • Anti-Exhaustion Gating: Prevents launching multi-million-dollar SAM interceptors blindly against 50 attritable airframes.
  • Closed-Loop Countermeasure Dispatch:
      ➔ Electronic Warfare: Initiates localized GNSS denial / satellite spoofing to degrade INS waypoint accuracy.
      ➔ Air Force GBAD: Directs automated point-defense autocannons and short-range C-UAS interceptors (CUE_AND_ENGAGE)
         to establish a kinetic engagement kill-box along the confirmed ingress choke point.
```

---

### 2. `S1_trojan` — The Trojan Mothership & Loitering Munition Incursion (Pillar 2)

```
[T-00:00: Siloed Blindness]
  Navy (AIS): "HAPPY TUG 8" proceeding eastbound at 6.1 kt. Status: routine commercial harbor craft.
  Air Force (Radar): Fast radar blip (120.4 kt, Alt 71m, RCS 0.035 m²). Status: unconfirmed / possible sea-clutter.
  Army (CCTV & EW): Perimeter camera locks silhouette; ground RF detects 2.4 GHz tactical link. Launch origin: unknown.
       │
       ▼
[T+00:05: Deterministic Contradiction & Launch Origin Lock]
  • Kinematic Decoupling: Radar velocity (120.4 kt) vs AIS velocity (6.1 kt) diverge from the exact same coordinates.
  • LOB Triangulation: Air Force ESM (135.2°) and Army EW (195.4°) Lines of Bearing intersect cleanly on Happy Tug 8.
  • Space SAR Anchor (GLINT): Orbital radar backscatter reveals a 12m linear aft-deck metallic anomaly (pneumatic rail).
       │
       ▼
[T+00:08: Threat Intent & Terminal Impact ETA]
  • Trajectory extrapolation locks onto POI-01 (Jurong Island Petrochemical Complex).
  • Terminal Impact Clock: 184 seconds to catastrophic impact on pressurized ethylene & crude oil tank farms.
       │
       ▼
[T+00:10: Dangerous AI Proposal vs. Deterministic Guardrail VETO]
  • AI raw recommendation (Option A): Proposes terminal SPYDER SAM missile engagement directly overhead Jurong Island.
  • Deterministic Ballistic Engine: Computes falling debris scatter cone (Newtonian gravity + wind vector).
  • HARD VETO (SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD): Detonating directly over CNI would rain burning propellant
    and shrapnel into tank farms, triggering a multi-billion dollar industrial catastrophe. Option A is locked out.
       │
       ▼
[T+00:12: Enforced Failsafe Roll-Over & Coordinated Dual Tasking]
  • Safe Roll-Over (Option B): Mandates Offshore Intercept (>1,200m seaward) + Shoreline Directional RF Soft-Kill.
  • Closed-Loop Dual Dispatch:
      ➔ Air Force GBAD: Tasked to execute offshore kinetic missile engagement over open water.
      ➔ Navy PCG (PT-44): Dispatched to intercept and board the Trojan mothership Happy Tug 8.
```

---

### 3. `S3_sar_ais` — Space SAR Ground Truth × AIS Dark Vessel Corroboration (Pillar 3)

```
[T-15:00: Upstream Strategic SAR Pass]
  • Orbit Sweep: GLINT SAR space pass over the Singapore Strait detects an anomalous backscatter cluster.
  • Spatial Difference: High-RCS metallic hull returns present, but zero correlating AIS transponder signals.
       │
       ▼
[T-05:00: Micro Metrology & Reachability Dead-Reckoning]
  • SIA Fine-Grain SAR: Extracts Oriented Bounding Box (OBB) metrology: Length 82m, Beam 16m, Heading 074°.
  • Kalman Temporal Extrapolation: Because satellite data is 15 minutes old, NexusGate projects the dark vessel's
    kinematics into a dynamic Reachable Ellipse at current simulation time T_now.
       │
       ▼
[T-00:00: Tactical Radar Handoff & Dynamic Intercept Tasking]
  • Sensor Handoff: Coastal gap-filler radar detects a high-speed contact inside the predicted reachable ellipse.
    The system binds the 15-minute-old satellite ground truth to the live radar contact without needing an MMSI.
  • Indago Background Traffic: DuckDB AIS stream overlays surrounding civilian shipping lanes.
  • Lead-Pursuit Intercept: Computes optimal Point of Interception (POI) and dispatches Approach Patrol USV-02.
```

---

### 4. `S1_ais_spoof` — Sea Approach Adversarial AIS Spoof (Auxiliary Baseline)

```
[T-00:00: Fictitious Calm]
  • AIS Broadcast: Vessel reports stationary coordinates inside the southern fairway anchorage.
       │
       ▼
[T+00:03: Physical Discrepancy Detected]
  • Multi-Modal Contradiction: Coastal radar and long-range EO cameras track a 20-knot inbound watercraft,
    revealing an 850-meter geodetic divergence from the declared stationary AIS transponder.
       │
       ▼
[T+00:06: Sovereign Decision Gate]
  • NexusGate surfaces amber SEA_APPROACH_DECEPTION alert (8 minutes of warning).
  • Rejects kinetic action on spoofed coordinates; issues Tier-1 COA: ISR_IDENTIFY_CONTACT to cue interceptor USV.
```

---

## 🚀 End-to-End Execution & Operator Runbook

For complete commands, automated test pipelines, and interactive CUI/UI operations across these scenarios, refer directly to:

👉 **[End-to-End Verification & Operator Runbook (`verify-e2e.md`)](verify-e2e.md)**

* **Workflow 1:** Automated end-to-end regression (`pytest tests/`, `scripts/picture_to_tasking.py`).
* **Workflow 2:** Screen 1 (ARCHVIEW MapLibre) & Screen 2 (BattlePlan / Verify UI) live integration.
* **Workflow 3a:** `S2_osint_swarm` primary hero scenario (airborne passenger OSINT, radar clutter contradiction, RF silence, and GNSS denial/GBAD anti-exhaustion cueing).
* **Workflow 3b:** `S1_trojan` tri-service disagreement, GLINT aft-deck anchor, CNI guardrail hard-VETO, and Option B dual tasking.
* **Workflow 3c:** `S3_sar_ais` dark vessel scenario replay with GLINT macro cluster, SIA micro SAR metrology, and Indago DuckDB live AIS traffic overlay.

---

## 📡 Sensor Modalities & Provenance

Provenance labels (**Synthetic** / **Real-processed** / **Assumed-mock**): [Data provenance](data-provenance.md).

| Modality | Scenarios | Provenance | Role in Contradiction |
|----------|-----------|------------|------------------------|
| **Space SAR (SIA micro)** | `S3_sar_ais` | Real-processed / Fixture | Dark vessel extraction, OBB metrology, image chip |
| **Space SAR (GLINT macro)** | `S3_sar_ais`, `S1_trojan` | Assumed-mock / Live API | Corridor-scale backscatter anomaly, aft-deck launch rail |
| **Social / Recon Text** | `S2_osint_swarm` | **Synthetic** (`osint_text` parser #59) | Civilian passenger in-flight video/photo ingestion (passenger on a Japan-bound flight spots unknown swarm without knowing location or destination); acts as early warning trigger |
| **Coastal 3D Radar** | `S1_trojan`, `S3_sar_ais`, `S1_ais_spoof`, `S2_osint_swarm` | **Synthetic** | Kinematic velocity mismatch (120 kt vs 6 kt), bearing lock, low-altitude clutter & intermittent contacts |
| **Coastal CCTV / EOIR** | `S1_trojan`, `S1_ais_spoof`, `S2_osint_swarm` | **Synthetic** | Optical silhouette verification, delta-wing thermal delta, visual verification pod slaving |
| **Coastal Acoustic Array** | `S2_osint_swarm` | **Synthetic** | Triangulates low-frequency 2-stroke moped acoustic signature of Shahed-136 engines |
| **Maritime AIS** | `S1_trojan`, `S1_ais_spoof`, `S3_sar_ais` | Synthetic (S1) / SIA Real-processed / Indago DuckDB (S3) | Commercial declaration, spoofing detection, background traffic |
| **Air ESM & Army EW** | `S1_trojan`, `S2_osint_swarm` | **Synthetic** | AoA intersection (S1); RF silence detection proving pre-programmed GPS/INS autonomy over remote control (S2) |
| **ADS-B** | `S2_osint_swarm` | **Synthetic** (+ optional open air fixture) | Empty air sector confirmation |
