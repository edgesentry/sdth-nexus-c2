# Data provenance — Synthetic vs Real-processed

Labels used across this repo. Prefer these over vague “real” / “fake”.

| Label | Meaning |
|-------|---------|
| **Synthetic** | Scenario or fixture invents the Observation (no live sensor attached) |
| **Real-processed** | Upstream processes a real-world source; C2 receives the result indirectly |
| **Assumed-mock** | Stand-in until the partner schema / endpoint is handed over (then becomes Real-processed) |

## Inventory

| Data | Provenance | Path | Pitch role |
|------|------------|------|------------|
| Social / OSINT text | **Synthetic** | S2 scenario (± `osint_text` count/bearing extract) | S2 “3 vs 1” side |
| Gap-filler radar | **Synthetic** | S1–S3 scenarios | Count / bearing mismatch |
| EO / blur | **Synthetic** | S1, S2 scenarios | Low-confidence visual |
| RF / ADS-B | **Synthetic** | S1, S2 scenarios | Silent / empty sector |
| Coastal radar (S3 counterpart) | **Synthetic** | Scenario (kinematics peer) | Match projected SAR |
| open-feed AIS / air | **Synthetic** (fixture) | `POST /api/ingress/open-feed` | Optional demo only |
| **AIS history** | **Real-processed** (`demo` SIA scrape) or **Synthetic** (`offline` MockAIS) | **SIA** `ingest_ais` → local SQLite `data.db` (not C2) | Cooperative side of dark-vessel filter |
| **SIA SAR detections + chip** | **Real-processed** (Sentinel-1 CV) or recorded **fixture** | SIA → `POST /api/ingress/candidate-event` **or** repo fixture (no SIA server) | S3 micro |
| **GLINT macro** | **Assumed-mock** now → **Real-processed** after Team 02 | Mock `:5051` / live API → ingress | S3 macro |
| LLM interpret | Optional | `POST /api/interpret` | Not pitch-critical |

## Persistence (who stores what)

| What | Where |
|------|--------|
| C2 runtime (tracks, proposals, inbox) | In-memory `C2Runtime` |
| Decision / Ack evidence | `.audit/gate.jsonl` |
| Ingress replay | `.audit/ingress.jsonl` (not gate authority; `scripts/replay_ingress.py`) |
| **AIS history** | **SIA local SQLite** — C2 does not store raw AIS |
| SAR imagery / chips | SIA `static/output` |

No C2 application RDB. AIS enters only via SIA’s own ingest plugins (`demo` / `offline`) into SIA local SQLite.

## UI boundary

| Name | Role | Location |
|------|------|----------|
| **BattlePlan** | External pitch UI | **Outside this repo** |
| **Verification WebUI** | Inspect NexusGate Screen 1/2 (not for pitch); Phase 2 [#65](https://github.com/edgesentry/sdth-nexus-c2/issues/65) | Core `/verify` (Jinja2/HTMX) |
| TUI / curl / scripts | Automation and cold-start | This repo |

Pitch screens can be fed by: Synthetic (OSINT + tactical sensors) + Real-processed (AIS / SIA SAR) + Assumed-mock GLINT (swap to live on Day 1). Live coastal radar / EO are Phase 5 — not required for the pitch narrative.
