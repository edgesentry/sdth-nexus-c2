# Defense scenarios

App-layer scenarios under `app/scenarios/`. Each run builds synthetic multi-vendor observations **without shared track IDs**, detects a Finding, and proposes a Tier-1 COA.

| ID | Title | Conflict | Tasking |
|----|-------|----------|---------|
| **S1** | Sea Approach — Adversarial AIS Spoof | Stationary AIS vs ~20 kt radar/EO (~850 m) | `ISR_IDENTIFY_CONTACT` |
| **S2** | Air Corridor — Shahed Swarm Contradiction | Social claims 3; radar 1 (~1.2 km N); EO blur 0.42; RF silent; no ADS-B | Amber `COUNT_AND_BEARING_MISMATCH` → `CUE_AND_IDENTIFY` |
| **S3** | Shipping Lane & Coastal Anomaly — SAR Difference vs AIS | Space-based SAR anomaly diff (unannounced dark cluster) vs thin AIS & coastal radar | `APPROACH_PATROL` |

**S2** is the air hero (Slide 04): do not fuse into one hallucinated track — cue identify only.  
**S3** is the maritime hero: connects macro space-based SAR scene-difference alerts to tactical C2 tasking.

Each CLI / TUI run prints a **WARNING PICTURE** (threat class, minutes of warning, sources, “if false collapses when…”) before the gate.

## Modalities

| Modality | Scenarios | Role in contradiction |
|----------|-----------|------------------------|
| Space-based SAR | S3 | Macro scene-difference anomaly (dark vessels, unannounced clusters) |
| Social / recon text | S2 | Exaggerated count claims |
| Gap-filler radar | S1–S3 | Count / bearing disagree |
| EO / optical | S1, S2 | Low-confidence blur |
| AIS / open AIS | S1, S3 (+ optional open feed) | Spoof, density break, or demo-grade data.gov.sg-shaped fixture |
| RF | S1, S2 | Silent / emitter cue |
| ADS-B | S2 (+ optional open air) | Empty sector, or opt-in open air fixture |

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
