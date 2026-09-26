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
| **`S2_osint_swarm`** | **Air Corridor Swarm Contradiction** | OSINT social media chatter (3 drones claimed) vs gap-filler radar (1 contact); EO blur | `CUE_AND_IDENTIFY` (Non-Kinetic Verification) |

### Core Demonstration Highlights

* **1. `S1_trojan` (Tri-Service Disagreement & CNI Safety Guardrail):**  
  Demonstrates cross-domain contradiction resolution across Navy, Air Force, and Army sensors.  
  `SDTH-Sensor-Simulation` JSONL $\rightarrow$ Navy AIS (6.1 kt tug) vs Coastal Radar (120.4 kt UAV) velocity mismatch $\rightarrow$ Air ESM $\cap$ Army EW Line of Bearing (AoA) launch triangulation onto mothership *Happy Tug 8* $\rightarrow$ Hard VETO of terminal SAM engagement directly over Jurong Island petrochemical complex (`SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD`) $\rightarrow$ Enforced failsafe roll-over to **Option B** dual tasking (Air Force GBAD offshore kinetic engagement + Navy PCG mothership interdiction).

* **2. `S3_sar_ais` (Space SAR Ground Truth × AIS Dark Vessel Corroboration & Dynamic Intercept):**  
  Demonstrates unmasking non-emitting vessels and bridging satellite temporal latency to tactical response.  
  Connects macro space-based SAR scene-difference alerts (GLINT) and micro OBB metrology (SIA) to tactical C2 tasking. Solves 15-minute satellite orbital latency via dynamic **Reachable Ellipse** dead-reckoning and coastal radar handoff $\rightarrow$ Computes dynamic lead-pursuit **Point of Interception (POI)** collision kinematics rather than dispatching units to stale historical coordinates $\rightarrow$ Authorizes and dispatches Approach Patrol USV.

* **3. `S2_osint_swarm` (Cognitive Disinformation Filter & Anti-Overreaction):**  
  Demonstrates filtering unverified civilian social reports against multi-modal physical sensor reality.  
  Ingests unstructured crowdsourced recon text ("3 inbound drones heading north") via semantic parser (`osint_text`) $\rightarrow$ Evaluates against military 3D gap-filler radar (1 contact) and EW RF spectrum silence (`COUNT_AND_BEARING_MISMATCH`) $\rightarrow$ Prevents panic and kinetic missile exhaustion against phantom targets $\rightarrow$ Restricts response to sealed non-kinetic `CUE_AND_IDENTIFY` electro-optical camera slewing before weapon release.

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

### 4. `S2_osint_swarm` — Air Corridor OSINT Swarm vs. Radar Contradiction

```
[T-00:00: Panic & Disinformation Ingress]
  • Social / Recon Chatter: Civilian eyewitness text claims "3 inbound swarm drones heading north."
       │
       ▼
[T+00:04: Objective Contradiction Gating]
  • Sensor Cross-Check: Military gap-filler radar holds only 1 contact (1.2 km north); EO/IR confirms high blur;
    RF spectrum is completely silent with no civil ADS-B broadcast.
       │
       ▼
[T+00:07: Preventing Kinetic Over-Reaction]
  • The contradiction engine triggers COUNT_AND_BEARING_MISMATCH (Social claims 3 vs Radar holds 1).
  • Prevents launching costly surface-to-air missiles against phantom swarm targets.
  • Authorizes sealed CUE_AND_IDENTIFY tasking to slew electro-optical verification pods before weapon release.
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
| **Social / Recon Text** | `S2_osint_swarm` | **Synthetic** (`osint_text` parser #59) | Semantic extraction of crowdsourced claims vs sensor ground truth |
| **Coastal 3D Radar** | `S1_trojan`, `S3_sar_ais`, `S1_ais_spoof`, `S2_osint_swarm` | **Synthetic** | Kinematic velocity mismatch (120 kt vs 6 kt), bearing lock, count/bearing mismatch |
| **Coastal CCTV / EOIR** | `S1_trojan`, `S1_ais_spoof`, `S2_osint_swarm` | **Synthetic** | Optical silhouette verification, thermal delta, low-confidence blur |
| **Maritime AIS** | `S1_trojan`, `S1_ais_spoof`, `S3_sar_ais` | Synthetic (S1) / SIA Real-processed / Indago DuckDB (S3) | Commercial declaration, spoofing detection, background traffic |
| **Air ESM & Army EW** | `S1_trojan`, `S2_osint_swarm` | **Synthetic** | Line of Bearing (AoA) intersection, FHSS emitter triangulation |
| **ADS-B** | `S2_osint_swarm` | **Synthetic** (+ optional open air fixture) | Empty air sector confirmation |
