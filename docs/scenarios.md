# Defense scenarios

App-layer scenarios under `app/scenarios/`. Each run builds synthetic multi-vendor observations **without shared track IDs**, detects a Finding, and proposes a Tier-1 COA.

| ID | Title | Conflict | Tasking |
|----|-------|----------|---------|
| **S1** | Sea Approach — Adversarial AIS Spoof | Stationary AIS vs ~20 kt radar/EO (~850 m) | `ISR_IDENTIFY_CONTACT` |
| **S2** | Air Corridor — Shahed Swarm Contradiction | Social claims 3; radar 1 (~1.2 km N); EO blur 0.42; RF silent; no ADS-B | Amber `COUNT_AND_BEARING_MISMATCH` → `CUE_AND_IDENTIFY` |
| **S3** | Shipping Lane SPOF — Pattern Break | Thin open AIS vs uncorrelated coastal radar | `APPROACH_PATROL` |

**S2** is the pitch hero (Slide 04): do not fuse into one hallucinated track — cue identify only.

## Modalities

| Modality | Scenarios | Role in contradiction |
|----------|-----------|------------------------|
| Social / recon text | S2 | Exaggerated count claims |
| Gap-filler radar | S1–S3 | Count / bearing disagree |
| EO / optical | S1, S2 | Low-confidence blur |
| AIS / open AIS | S1, S3 | Spoof or density break |
| RF | S1, S2 | Silent / emitter cue |
| ADS-B | S2 | Empty sector |

## Temporal streamer

`scripts/stream_events.py` plays a 19-step timeline (T-60s → T-00s) for demo fidelity beyond static fixtures.
