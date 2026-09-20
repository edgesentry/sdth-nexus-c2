# Defense scenarios

App-layer scenarios under `app/scenarios/`. Each run builds synthetic multi-vendor observations **without shared track IDs**, detects a Finding, and proposes a Tier-1 COA.

| ID | Title | Conflict | Tasking |
|----|-------|----------|---------|
| **S1** | Sea Approach — Adversarial AIS Spoof | Stationary AIS vs ~20 kt radar/EO (~850 m) | `ISR_IDENTIFY_CONTACT` |
| **S2** | Air Corridor — Shahed Swarm Contradiction | Social claims 3; radar 1 (~1.2 km N); EO blur 0.42; RF silent; no ADS-B | Amber `COUNT_AND_BEARING_MISMATCH` → `CUE_AND_IDENTIFY` |
| **S3** | Shipping Lane & Coastal Anomaly — SAR Difference vs AIS | Space-based SAR anomaly diff (unannounced dark cluster with length/beam/heading metrology) vs thin AIS; coastal radar joined via dead-reckoned reachability envelope (#57), not a shared MMSI | `APPROACH_PATROL` |

**S2** is the air hero (Slide 04): do not fuse into one hallucinated track — cue identify only.  
**S3** is the maritime hero: connects macro space-based SAR scene-difference alerts and OBB metrology to tactical C2 tasking via dead-reckoning (#57) (see [SAR Pipeline Architecture](architecture/sar_pipeline.md)).

Each CLI / TUI run prints a **WARNING PICTURE** (threat class, minutes of warning, sources, “if false collapses when…”) before the gate.

## Modalities

Provenance labels (**Synthetic** / **Real-processed** / **Assumed-mock**): [Data provenance](data-provenance.md).

| Modality | Scenarios | Provenance | Role in contradiction |
|----------|-----------|------------|------------------------|
| Space-based SAR (SIA micro) | S3 | Real-processed or fixture | Dark vessels, OBB + chip |
| Space-based SAR (GLINT macro) | S3 | Assumed-mock → live Phase 4 | Corridor-scale anomaly |
| Social / recon text | S2 | **Synthetic** | Exaggerated count claims |
| Gap-filler radar | S1–S3 | **Synthetic** | Count / bearing disagree |
| EO / optical | S1, S2 | **Synthetic** | Low-confidence blur |
| AIS | S1, S3 | S1 Synthetic; S3 via **SIA** Real-processed (`demo`) or MockAIS | Spoof / dark-vessel filter |
| RF | S1, S2 | **Synthetic** | Silent / emitter cue |
| ADS-B | S2 | **Synthetic** (+ optional open air fixture) | Empty sector |

## Optional open feeds (issue #16)

Synthetic S1–S3 remain the primary demo. Opt in to **demo-grade** open AIS (data.gov.sg-shaped) and/or open air (ADS-B-style) fixtures — no live coastal poll in Phase 2.

```bash
# CLI (additive on top of --scenario)
uv run python -m app.main --scenario S2 --stub --yes --open-feed ais,air
# or: OPEN_FEED=all uv run python -m app.main --scenario S2 --stub --yes

# REST (does not replace scenario ingest)
curl -s -X POST localhost:8080/api/ingress/open-feed \
  -H 'content-type: application/json' \
  -d '{"feed":"all","use_fixture":true}'
```

Fixtures: `tests/fixtures/open_ais_datagovsg.json`, `tests/fixtures/open_air_traffic.json`.  
Also: `OPEN_FEED=ais,air` / `--open-feed` / `POST /api/ingress/open-feed` — additive only. Live Singapore coastal harness is Phase 5.

## Temporal streamer

`scripts/stream_events.py` plays a 19-step timeline (T-60s → T-00s) for demo fidelity beyond static fixtures. Commands and step bands: [Demo Path B](demo.md#demo-path-b-19-event-temporal-streamer).
