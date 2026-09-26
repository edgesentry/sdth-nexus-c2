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

## 🎯 Scenarios Realizing the Narrative

| Scenario ID | Operational Title | Primary Contradiction | Final Resolution |
|-------------|-------------------|-----------------------|------------------|
| **`S1_trojan`** | **Trojan Mothership (Hero Scenario)** | Navy Happy Tug AIS ~6 kt vs coastal radar ~120 kt UAS; Air/Army EW LOB triangulation | Guardrail CNI VETO → `OFFSHORE_INTERCEPT_RF_SOFTKILL` (Option B) |
| **`S3_sar_ais`** | **Shipping Lane & Coastal Anomaly** | Space-based SAR anomaly diff (GLINT macro + SIA micro) vs thin AIS; dead-reckoned reachability envelope | `APPROACH_PATROL` (Dynamic Lead-Pursuit) |
| **`S1_ais_spoof`** | **Sea Approach Incursion** | Stationary AIS transponder vs ~20 kt radar/EO contact (~850 m spatial divergence) | `ISR_IDENTIFY_CONTACT` |
| **`S2_osint_swarm`** | **Transnational OSINT & Autonomous Shahed Swarm** | Cross-border civilian OSINT (~50 Shahed claimed) vs gap-filler radar (clutter blindspots); RF-silent autonomous GPS navigation | `CUE_AND_IDENTIFY` → `GNSS_DENIAL_AND_GBAD_CUE` |

### Core Demonstration Highlights

* **1. `S1_trojan` (Tri-Service Disagreement & CNI Safety Guardrail):**  
  Demonstrates cross-domain contradiction resolution across Navy, Air Force, and Army sensors.  
  `SDTH-Sensor-Simulation` JSONL $\rightarrow$ Navy AIS (6.1 kt tug) vs Coastal Radar (120.4 kt UAV) velocity mismatch $\rightarrow$ Air ESM $\cap$ Army EW Line of Bearing (AoA) launch triangulation onto mothership *Happy Tug 8* $\rightarrow$ Hard VETO of terminal SAM engagement directly over Jurong Island petrochemical complex (`SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD`) $\rightarrow$ Enforced failsafe roll-over to **Option B** dual tasking (Air Force GBAD offshore kinetic engagement + Navy PCG mothership interdiction).

* **2. `S3_sar_ais` (Space SAR Ground Truth × AIS Dark Vessel Corroboration & Dynamic Intercept):**  
  Demonstrates unmasking non-emitting vessels and bridging satellite temporal latency to tactical response.  
  Connects macro space-based SAR scene-difference alerts (GLINT) and micro OBB metrology (SIA) to tactical C2 tasking. Solves 15-minute satellite orbital latency via dynamic **Reachable Ellipse** dead-reckoning and coastal radar handoff $\rightarrow$ Computes dynamic lead-pursuit **Point of Interception (POI)** collision kinematics rather than dispatching units to stale historical coordinates $\rightarrow$ Authorizes and dispatches Approach Patrol USV.

* **3. `S2_osint_swarm` (Transnational OSINT & Autonomous Swarm Corroboration):**  
  Demonstrates cross-referencing crowdsourced foreign eyewitness feeds with military sensors to defeat pre-programmed, RF-silent saturation swarms.  
  Foreign coastal civilians across the border post social media video/audio of ~50 delta-wing loitering munitions (Shahed-136 class) with distinct moped engine signatures heading toward Singapore $\rightarrow$ Ground EW and ESM confirm **complete RF silence** (no C2 control link detected, indicating the swarm exceeds remote-control line-of-sight and operates entirely on autonomous pre-programmed GPS/INS waypoints) $\rightarrow$ Coastal 3D gap-filler radar detects only an intermittent cluster (4 contacts) due to sea-clutter and terrain masking (`COUNT_AND_BEARING_MISMATCH` with blindspot awareness) $\rightarrow$ NexusGate fuses the OSINT azimuth corridor, acoustic engine profiles, and radar kinematics to invalidate standard RF C2 jamming (useless against autonomous flight), dynamically cues EO/IR pods, and initiates GPS denial/spoofing alongside GBAD point-defense vectoring.

---

## ⏱️ Operational Chronicles: Chronological Storylines

### 1. `S1_trojan` — The Trojan Mothership & Loitering Munition Incursion (Hero)

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
  • Space SAR Anchor: Orbital radar backscatter reveals a 12m linear aft-deck metallic anomaly (pneumatic rail).
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

### 2. `S3_sar_ais` — Space SAR Ground Truth × AIS Dark Vessel Corroboration

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

### 3. `S1_ais_spoof` — Sea Approach Adversarial AIS Spoof

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

### 4. `S2_osint_swarm` — Transnational OSINT & Autonomous Shahed Swarm Contradiction

```
[T-00:00: Transnational OSINT & Eyewitness Ingress]
  • Cross-Border Civilian Feeds: Overseas coastal residents post phone footage/audio to social media (X/TikTok/Telegram):
    "Massive swarm (>50 delta-wing drones) flying low across the strait; loud lawnmower/moped buzz heading toward Singapore."
  • Semantic & Spatial Parser: Ingests unstructured OSINT text, extracts corridor bearing (~248°), velocity (~105 kt),
    and estimated count (~50 Shahed-136 class airframes). Initial status: unverified civilian report.
       │
       ▼
[T+00:03: RF-Silence Gating & Autonomous Navigation Lock]
  • Passive EW & Air ESM: Ground spectrum sensors scan across 433 MHz, 900 MHz, 2.4 GHz, and 5.8 GHz bands.
  • Deterministic Finding (RF_SILENT_AUTONOMOUS): Zero command-and-control (C2) RF emissions or video telemetry detected.
    The swarm is flying well beyond direct remote-control line-of-sight range.
  • Flight Mode Assessment: Confirms pre-programmed GPS/INS waypoint navigation.
    Automated safety interlock disallows futile C2 soft-kill jamming (which only affects manual/tethered RF drones).
       │
       ▼
[T+00:05: Multi-Modal Sensor Cross-Reference (Radar × Acoustics × EO/IR)]
  • Radar Clutter & Blindspot Resolution: Coastal gap-filler 3D radar detects only 4 intermittent low-RCS contacts
    due to low-altitude sea-clutter and island masking. Rather than dismissing the ~50-drone OSINT report as false panic,
    NexusGate correlates radar contacts with the OSINT ingress vector, confirming an ingress swarm masked by altitude.
  • Coastal Acoustic Arrays: Triangulates the characteristic low-frequency 2-stroke moped acoustic signature along the vector.
  • Coastal EO/IR Slewing: Slaved cameras lock onto high-speed delta-wing silhouettes breaking through thermal haze.
       │
       ▼
[T+00:07: Coordinated Swarm Countermeasure Tasking (C2 Resolution)]
  • Anti-Exhaustion Gating: Prevents blind expenditure of high-value SAM interceptors against dispersed saturation wings.
  • Countermeasure Dispatch:
      ➔ Electronic Warfare: Triggers local GNSS spoofing / directional satellite jamming to induce INS drift.
      ➔ Air Force GBAD: Directs automated point-defense autocannons and short-range C-UAS kinetic interceptors (CUE_AND_ENGAGE)
         onto the pre-calculated waypoint corridor before impact on critical infrastructure.
```

---

## 🚀 End-to-End Execution & Operator Runbook

For complete commands, automated test pipelines, and interactive CUI/UI operations across these scenarios, refer directly to:

👉 **[End-to-End Verification & Operator Runbook (`verify-e2e.md`)](verify-e2e.md)**

* **Workflow 1:** Automated end-to-end regression (`pytest tests/`, `scripts/picture_to_tasking.py`).
* **Workflow 2:** Screen 1 (ARCHVIEW MapLibre) & Screen 2 (BattlePlan / Verify UI) live integration.
* **Workflow 3a:** `S3_sar_ais` hero scenario replay with Indago DuckDB live AIS traffic overlay.
* **Workflow 3b:** `S1_trojan` tri-service disagreement, CNI guardrail hard-VETO, and Option B dual tasking.

---

## 📡 Sensor Modalities & Provenance

Provenance labels (**Synthetic** / **Real-processed** / **Assumed-mock**): [Data provenance](data-provenance.md).

| Modality | Scenarios | Provenance | Role in Contradiction |
|----------|-----------|------------|------------------------|
| **Space SAR (SIA micro)** | `S3_sar_ais` | Real-processed / Fixture | Dark vessel extraction, OBB metrology, image chip |
| **Space SAR (GLINT macro)** | `S3_sar_ais`, `S1_trojan` | Assumed-mock / Live API | Corridor-scale backscatter anomaly, aft-deck launch rail |
| **Social / Recon Text** | `S2_osint_swarm` | **Synthetic** (`osint_text` parser #59) | Crowdsourced foreign eyewitness video/text ingestion, swarm count (~50) & ingress azimuth extraction |
| **Coastal 3D Radar** | `S1_trojan`, `S3_sar_ais`, `S1_ais_spoof`, `S2_osint_swarm` | **Synthetic** | Kinematic velocity mismatch (120 kt vs 6 kt), bearing lock, low-altitude clutter & intermittent contacts |
| **Coastal CCTV / EOIR** | `S1_trojan`, `S1_ais_spoof`, `S2_osint_swarm` | **Synthetic** | Optical silhouette verification, delta-wing thermal delta, visual verification pod slaving |
| **Coastal Acoustic Array** | `S2_osint_swarm` | **Synthetic** | Triangulates low-frequency 2-stroke moped acoustic signature of Shahed-136 engines |
| **Maritime AIS** | `S1_trojan`, `S1_ais_spoof`, `S3_sar_ais` | Synthetic (S1) / SIA Real-processed / Indago DuckDB (S3) | Commercial declaration, spoofing detection, background traffic |
| **Air ESM & Army EW** | `S1_trojan`, `S2_osint_swarm` | **Synthetic** | AoA intersection (S1); RF silence detection proving pre-programmed GPS/INS autonomy over remote control (S2) |
| **ADS-B** | `S2_osint_swarm` | **Synthetic** (+ optional open air fixture) | Empty air sector confirmation |
