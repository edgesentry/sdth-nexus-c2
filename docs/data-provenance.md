# Data provenance — Synthetic vs Real-processed

Labels used across this repo. Prefer these over vague “real” / “fake”.

| Label | Meaning |
|-------|---------|
| **Synthetic** | Scenario or fixture invents the Observation (no live sensor attached) |
| **Real-processed** | Upstream processes a real-world source; C2 receives the result indirectly |
| **Assumed-mock** | Stand-in until the partner schema / endpoint is handed over (then becomes Real-processed) |

> **Primary hero is airborne `S2_osint_swarm`. Maritime secondary track is `S1_trojan` (tri-service + GLINT hull anchor) then `S3_sar_ais` (GLINT macro × SIA × AIS dark vessel). SensorSim (`SDTH-Sensor-Simulation`) `scenario_02_conflicting` is a legacy fusion bench, not Nexus S2.**

## Three-Pillar Operational Mapping

| Rank | Nexus ID | Role | GLINT Usage |
|------|----------|------|-------------|
| **1 (Primary Hero)** | `S2_osint_swarm` | In-flight OSINT ~50 × radar 4 / RF silence → GNSS denial + GBAD (Cognitive / Autonomous Saturation / Anti-Exhaustion) | **Not used** (Air domain & social sensor) |
| **2** | `S1_trojan` | Maritime + Land/Air: AIS vs coastal radar, CNI VETO, Option B (Tri-service contradiction + spatial SAR mothership lock) | **Used** — Mothership aft-deck / hull spatial anchor (already in narrative & export) |
| **3** | `S3_sar_ais` | Dark vessel: Dual-SAR × thin AIS → Approach Patrol (Orbital latency → reachable ellipse → USV intercept) | **Primary showcase** — macro cluster (`:5051` / live) + SIA micro |

*Auxiliary baseline*: `S1_ais_spoof` serves as a lightweight baseline outside the three pillars (no GLINT).

### Data Alignment with SensorSim (`SDTH-Sensor-Simulation`)

| Data Feed | Storage Location | Provenance / Role |
|-----------|------------------|-------------------|
| **S2 Synthetic** (OSINT / radar 4 / acoustic / RF silent) | SensorSim `exports/s2_osint_swarm_scenario.jsonl` | **Synthetic** (*`scenario_02_conflicting` is a legacy fusion bench, not Nexus S2*) |
| **Trojan Maritime + Land/Air + GLINT row** | Existing `synthetic_maritime_data/` → `exports/s1_trojan_*` | **Synthetic** / GLINT stub |
| **S3 Coastal AIS / Radar** | SensorSim optional; **GLINT macro / SIA chip owned by Nexus / Team 02 / SIA** | **Assumed-mock** (`:5051`) + **Real-processed** (SIA Sentinel-1) |

## Operational sensor classes (4-tier)

Singapore WOG multi-domain context — how feeds map to MOSAIC C2 ingress (not every class is live in-repo today):

| Class | Examples | Role in MOSAIC |
|-------|----------|----------------|
| **1. Live / Current Observations** | AIS (MPA OCEANS-X, AISStream), VTIS / STRAITREP | Cooperative traffic and port context at $T \approx 0$ |
| **2. Historical / Retrospective Evidence** | Satellite SAR `CandidateEvent` anomalies, Sentinel-1 CV detection (SIA) | Dark-vessel / corridor cues at $T - \Delta t$ |
| **3. Recorded Sensor Data** | Singapore Maritime Dataset (SMD) visible & NIR camera surveillance | Pitch realism / replay; not required for deterministic gate |
| **4. Synthetic Exercise Inputs** | Controlled multi-domain disagreement fixtures | Deterministic demo contradictions (`S2_osint_swarm`, `S1_trojan`, `S3_sar_ais`, `S1_ais_spoof`) |

Labels in the inventory below remain **Synthetic / Real-processed / Assumed-mock** for audit clarity.

## Inventory

| Data | Provenance | Path | Pitch role |
|------|------------|------|------------|
| Social / OSINT text | **Synthetic** (Phase 2 `osint_text` #59) or **External Service** (production target) | `S2_osint_swarm` scenario (`app/adapters/osint_text.py`) | Airborne passenger swarm cue (~50); discrepancy vs radar clutter |
| Gap-filler radar | **Synthetic** | All scenarios (`S1_trojan`, `S3_sar_ais`, `S1_ais_spoof`, `S2_osint_swarm`) | Velocity / count / bearing mismatch |
| EO / blur | **Synthetic** | `S1_trojan`, `S1_ais_spoof`, `S2_osint_swarm` scenarios | Low-confidence visual / delta-wing thermal |
| Acoustic array | **Synthetic** | `S2_osint_swarm` | 2-stroke Shahed-class harmonic corroboration |
| RF / ADS-B | **Synthetic** | `S1_trojan`, `S2_osint_swarm` scenarios | Silent / empty sector; S2 RF_SILENT_AUTONOMOUS |
| Coastal radar (S3 counterpart) | **Synthetic** | `S3_sar_ais` scenario (kinematics peer) | Match projected SAR |
| **open-feed AIS / air** | **Real-processed** (Indago DuckDB / live poll opt-in, #70) or **Synthetic** (fixture fallback) | `POST /api/ingress/open-feed` / Indago adapter | Background traffic & pitch realism |
| **AIS history** | **Real-processed** (`demo` SIA scrape) or **Synthetic** (`offline` MockAIS) | **SIA** `ingest_ais` → local SQLite `data.db` (not C2) | Cooperative side of dark-vessel filter |
| **SIA SAR detections + chip** | **Real-processed** (Sentinel-1 CV) or recorded **fixture** | SIA → `POST /api/ingress/candidate-event` **or** repo fixture (no SIA server) | `S3_sar_ais` micro |
| **GLINT macro** | **Assumed-mock** now → **Real-processed** after Team 02 | Mock `:5051` / live API → ingress | `S3_sar_ais`, `S1_trojan` macro |
| LLM interpret | Optional | `POST /api/interpret` | Not pitch-critical |

## Persistence (who stores what)

| What | Where |
|------|--------|
| C2 runtime (tracks, proposals, inbox) | In-memory `C2Runtime` **+** SQLite picture (`.audit/runtime.sqlite`; survives process restart; cleared by `/api/admin/reset`) |
| Decision / Ack evidence | `.audit/gate.jsonl` |
| Ingress replay | `.audit/ingress.jsonl` (not gate authority; `scripts/replay_ingress.py`) |
| **AIS history & persistence** | **Indago (DuckDB/Parquet)** or **SIA local SQLite** — C2 does not store raw AIS |
| **OSINT raw text & feeds** | **External Threat Intel / Social Lake** — C2 does not crawl or store raw social text |
| SAR imagery / chips | SIA `static/output` |

No C2 application RDB for sensor history. The SQLite runtime picture only reconstitutes the current tactical graph / proposals / inbox after a laptop restart; cryptographic gate seals remain in OCSF/EDS. Persistent AIS is decoupled to Indago/SIA, and raw OSINT ingestion/crawling is decoupled to external Threat Intel pipelines. C2 consumes only normalized Observation tracks and structured event claims via adapters.

## UI boundary (dual-tier)

| Name | Role | Location |
|------|------|----------|
| **BattlePlan (Tactical Map Cockpit)** | External MapLibre/React pitch UI | **Outside this repo** — consumes frozen REST (`/api/gate/proposals`, `/api/gate/approve`, `/api/recipient/inbox`, `/api/recipient/ack`) |
| **Verification WebUI (`/verify`)** | Inspect NexusGate Screen 1/2 (not for pitch); Phase 2 [#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65) | Core `/verify` (Jinja2/HTMX) |
| TUI / curl / scripts | Automation and cold-start | This repo |

Pitch screens can be fed by: Synthetic (tactical sensors + OSINT stretch) + Real-processed (AIS / SIA SAR + optional live open-feed [#70](https://github.com/edgesentry/sdth-nexus-c2/issues/70)) + Assumed-mock GLINT (swap to live on Day 1). Live coastal radar / tactical EO remain Phase 5 — not required for the pitch narrative.
