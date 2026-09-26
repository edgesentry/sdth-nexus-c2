# Multi-Domain Defense Scenarios

## 🌐 The Tri-Service Multi-Domain Unification Narrative

In modern littoral-maritime defense, sovereign security relies on unifying siloed sensor networks across **Army (IDTF)**, **Navy (RSN / PCG)**, **Air Force (RSAF)**, and **Space Reconnaissance (GLINT SAR)**:

1. **Army (IDTF):** Coastal CCTV and ground EW monitor shorelines, but lack visibility into maritime launch origins or radar tracking over water.
2. **Navy (RSN / PCG):** Monitors commercial maritime traffic via AIS, but cannot detect transponder spoofing, concealed launch rails, or low-RCS air incursions on its own.
3. **Air Force (RSAF):** Tracks fast-moving air radar contacts, but struggles to differentiate sea clutter/civilian drones from hostile loitering munitions without maritime context or emitter triangulation.
4. **Space Recon (GLINT SAR):** Captures physical hull dimensions and orbital radar backscatter, providing an unalterable ground truth against spoofed declarations.

**NexusGate** ingests these disparate streams into a unified data core, triggers deterministic contradiction checks, and dispatches coordinated multi-service tasking (Air Force GBAD kinetic intercept + Navy PCG mothership interdiction).

> **Core Architectural Principle:** Do not fuse disparate tracks into one hallucinated "super-track." Preserve raw modality boundaries, surface deterministic kinematic and spatial contradictions, and enforce mathematical safety interlocks before human commanders authorize action.

---

## 🎯 Scenarios Realizing the Narrative

To demonstrate and rigorously verify this multi-domain integration, NexusGate implements distinct app-layer scenarios under `app/scenarios/`. Each scenario builds synthetic multi-vendor observations **without shared track IDs**, detects a Finding, surfaces contradiction badges, and proposes a Tier-1 COA:

| Scenario ID | Title | Contradiction / Conflict | Tasking / Resolution |
|-------------|-------|--------------------------|----------------------|
| **`S1_trojan`** | **Trojan Mothership (Hero Scenario)** | Navy Happy Tug AIS ~6 kt vs coastal radar ~120 kt UAS; Air/Army EW LOB triangulation; terminal SAM over Jurong CNI is hard-VETO'd | Guardrail → `OFFSHORE_INTERCEPT_RF_SOFTKILL` (Option B) |
| **`S3_sar_ais`** | **Shipping Lane & Coastal Anomaly** | Space-based SAR anomaly diff (GLINT macro + SIA micro) vs thin AIS; coastal radar joined via dead-reckoned reachability envelope (#57) | `APPROACH_PATROL` (Dynamic Lead-Pursuit) |
| **`S1_ais_spoof`** | **Sea Approach** | Stationary AIS transponder vs ~20 kt radar/EO contact (~850 m mismatch) | `ISR_IDENTIFY_CONTACT` |
| **`S2_osint_swarm`** | **Air Corridor** | OSINT social claims (3 drones) vs radar (1 contact); EO blur; RF silence | `CUE_AND_IDENTIFY` |

### Core Demonstration Highlights

* **`S1_trojan` (Tri-Service Disagreement & CNI Safety Guardrail):**
  Demonstrates cross-domain contradiction resolution ([#116](https://github.com/edgesentry/sdth-nexus-c2/issues/116)):
  SensorSim (`SDTH-Sensor-Simulation`) JSONL → Navy AIS vs Coastal Radar velocity mismatch amber → Air ESM ∩ Army EW LOB launch triangulation → Hard VETO of terminal SAM over Jurong CNI (`SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD`) → Enforced offshore Option B dual tasking (Air GBAD + PCG interdiction).

* **`S3_sar_ais` (Space SAR × AIS Dark Vessel Corroboration):**
  Connects macro space-based SAR scene-difference alerts (GLINT) and micro OBB metrology (SIA) to tactical C2 tasking via dead-reckoning kinematics ([#57](https://github.com/edgesentry/sdth-nexus-c2/issues/57)) and lead-pursuit interception ([#58](https://github.com/edgesentry/sdth-nexus-c2/issues/58)) (see [SAR Pipeline Architecture](architecture/sar_pipeline.md)).

> **S3 Cognitive Load Compression (Dual-SAR × Dual-AIS):**  
> Resolves the core maritime dilemma (*"SAR detects returns, AIS indicates normal traffic: is it clutter, a dark vessel, or latency?"*) across three decoupled tiers:
> 1. **GLINT (Macro SAR)**: Cues anomalous corridor sectors without requiring AIS.
> 2. **SIA (Micro SAR × AIS)**: Correlates with pass-time AIS snapshot (T - Δt) to isolate dark vessels and extract OBB metrology (L/B/θ).
> 3. **NexusGate ← Indago (Tactical C2)**: Overlays live background traffic (T ≈ 0) and computes dynamic lead-pursuit POI, allowing the Commander to authorize a mathematically verified Amber Warning Picture rather than manually cross-referencing raw sensor feeds.

---

## 🚀 End-to-End Execution & Verification

For hands-on execution, operational commands, and live CUI/UI workflows across these scenarios, refer to the complete runbook:

👉 **[End-to-End Verification & Operator Runbook (`verify-e2e.md`)](verify-e2e.md)**

* **Workflow 1:** Automated end-to-end test execution (`pytest`, `picture_to_tasking`).
* **Workflow 2:** Screen 1 (ARCHVIEW MapLibre) & Screen 2 (BattlePlan / Verify UI) integration.
* **Workflow 3a:** `S3` hero scenario pitch replay and Indago DuckDB live AIS overlay.
* **Workflow 3b:** `s1_trojan` tri-service disagreement, CNI guardrail hard-VETO, and Option B dual tasking.

## Modalities

Provenance labels (**Synthetic** / **Real-processed** / **Assumed-mock**): [Data provenance](data-provenance.md).

| Modality | Scenarios | Provenance | Role in contradiction |
|----------|-----------|------------|------------------------|
| Space-based SAR (SIA micro) | S3 | Real-processed or fixture | Dark vessels, OBB + chip |
| Space-based SAR (GLINT macro) | S3 | Assumed-mock → live Phase 4 | Corridor-scale anomaly |
| Social / recon text | S2 | **Synthetic** (`osint_text` parser #59) | Exaggerated then filtered count claims |
| Gap-filler radar | S1–S3 | **Synthetic** | Count / bearing disagree |
| EO / optical | S1, S2 | **Synthetic** | Low-confidence blur |
| AIS | S1, S3 | S1 Synthetic; S3 via **SIA** Real-processed (`demo`) or MockAIS | Spoof / dark-vessel filter |
| RF | S1, S2 | **Synthetic** | Silent / emitter cue |
| ADS-B | S2 | **Synthetic** (+ optional open air fixture) | Empty sector |

## Optional open feeds (issues #16, #70)

Synthetic S1–S3 remain the primary demo. Opt in to open AIS (data.gov.sg-shaped) and/or open air (ADS-B-style) feeds for pitch realism. Phase 2 introduces optional live polling ([#70](https://github.com/edgesentry/sdth-nexus-c2/issues/70)) with automated deterministic fallback to fixtures.

```bash
# CLI (additive on top of --scenario; fixture-backed)
uv run python -m app.main --scenario S2 --stub --yes --open-feed ais,air
# or: OPEN_FEED=all uv run python -m app.main --scenario S2 --stub --yes

# REST (does not replace scenario ingest; use_fixture=true or false with live polling)
curl -s -X POST localhost:8080/api/ingress/open-feed \
  -H 'content-type: application/json' \
  -d '{"feed":"all","use_fixture":true}'
```

Fixtures: `tests/fixtures/open_ais_datagovsg.json`, `tests/fixtures/open_air_traffic.json`.  
Also: `OPEN_FEED=ais,air` / `--open-feed` / `POST /api/ingress/open-feed` — additive only. Live military coastal radar / tactical EO remain Phase 5.

## Temporal streamer

`scripts/stream_events.py` plays a 19-step timeline (T-60s → T-00s) for demo fidelity beyond static fixtures. Commands and step bands: [Demo Path B](demo.md#demo-path-b-19-event-temporal-streamer).
