# Defense scenarios

App-layer scenarios under `app/scenarios/`. Each run builds synthetic multi-vendor observations **without shared track IDs**, detects a Finding, and proposes a Tier-1 COA.

| ID | Title | Conflict | Tasking |
|----|-------|----------|---------|
| **S1** | Sea Approach — Adversarial AIS Spoof | Stationary AIS vs ~20 kt radar/EO (~850 m) | `ISR_IDENTIFY_CONTACT` |
| **S2** | Air Corridor — Shahed Swarm Contradiction | Social claims 3; radar 1 (~1.2 km N); EO blur 0.42; RF silent; no ADS-B | Amber `COUNT_AND_BEARING_MISMATCH` → `CUE_AND_IDENTIFY` |
| **S3** | Shipping Lane & Coastal Anomaly — SAR Difference vs AIS | Space-based SAR anomaly diff (unannounced dark cluster with length/beam/heading metrology) vs thin AIS; coastal radar joined via dead-reckoned reachability envelope (#57), not a shared MMSI | `APPROACH_PATROL` |

**S2** is the air hero (Slide 04): do not fuse into one hallucinated track — cue identify only.  

> **S2 Operational & Cognitive Value (Why OSINT in C2?):**  
> 1. **Human as a Distributed Sensor**: Low-flying attritable drones (e.g., Shahed-136) often slip beneath radar horizons or clutter filters in urban/coastal corridors. Eyewitness social media and recon text often provide the *first operational cue* before radar acquires track lock.
> 2. **Preventing Kinetic Over-Reaction**: Social chatter is prone to panic, exaggeration, and enemy deception (*"20 swarm drones incoming!"*). An un-governed C2 risks launching million-dollar surface-to-air interceptors prematurely. NexusGate surfaces the **Amber contradiction** (Social claims filtered 3 vs Radar detects 1) and routes tasking to non-kinetic **`CUE_AND_IDENTIFY`** (slew cameras/recon drones to verify) rather than lethal over-kill.
> 3. **Decoupled Ingress Architecture**: Just as AIS history is decoupled to Indago, raw social media scraping/crawling lives in external OSINT Threat Intelligence services. NexusGate ingests only structured semantic extracts (`claimed_count`, `bearing`, `objective`) via [`app/adapters/osint_text.py`](data-provenance.md) without maintaining an internal social database.

**S3** is the maritime hero: connects macro space-based SAR scene-difference alerts (GLINT) and micro OBB metrology (SIA) to tactical C2 tasking via dead-reckoning kinematics ([#57](https://github.com/edgesentry/sdth-nexus-c2/issues/57)) and lead-pursuit interception ([#58](https://github.com/edgesentry/sdth-nexus-c2/issues/58)) (see [SAR Pipeline Architecture](architecture/sar_pipeline.md)).

> **S3 Cognitive Load Compression (Dual-SAR × Dual-AIS):**  
> Resolves the core maritime dilemma (*"SAR detects returns, AIS indicates normal traffic: is it clutter, a dark vessel, or latency?"*) across three decoupled tiers:
> 1. **GLINT (Macro SAR)**: Cues anomalous corridor sectors without requiring AIS.
> 2. **SIA (Micro SAR × AIS)**: Correlates with pass-time AIS snapshot ($T - \Delta t$) to isolate dark vessels and extract OBB metrology ($L/B/\theta$).
> 3. **NexusGate $\leftarrow$ Indago (Tactical C2)**: Overlays live background traffic ($T \approx 0$) and computes dynamic lead-pursuit POI, allowing the Commander to authorize a mathematically verified Amber Warning Picture rather than manually cross-referencing raw sensor feeds.

Each CLI / TUI run prints a **WARNING PICTURE** (threat class, minutes of warning, sources, “if false collapses when…”) before the gate.

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
