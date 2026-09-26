# Upstream Ingress Contract & Feeds

**Status:** Phase 2 freeze · Ingress specification for sensor adapters, external feeds, and candidate events into the Nexus Spatial Entity Graph.

Core downstream C2 decision, gating, and recipient handshake endpoints are documented in **[C2 REST API](rest.md)**. Shared data models are documented in **[Shared Schemas](schemas.md)**.

---

## 1. Overview & Operational Assumptions

For **upstream macro intelligence ingress** (such as space-based SAR scene-difference anomaly evidence), the C2 engine assumes an open, typed `CandidateEvent` payload structure (pending final schema file handover). This enables continuous, non-blocking development via local fixtures and mock adapters.

1. **Retrospective & Periodic Ingress:** The payload represents a discrete, verified evidence package derived from satellite passes, not a high-frequency live video feed.
2. **Non-Blocking Loose Coupling:** The C2 platform operates fully stand-alone using synthetic fixture equivalents (`tests/fixtures/candidate_event_assumed.json`) if live upstream services are offline during hackathon operations.
3. **Transport Interfaces:** Supported via HTTP REST (`GET` pull or `POST` push) and compatible with Model Context Protocol (MCP) tool querying.

---

## 2. Assumed Wire Payload (`CandidateEvent` v1.3.0)

```json
{
  "event_id": "evt_sar_20260918_001",
  "timestamp": "2026-09-18T14:30:00Z",
  "source_id": "SPACE_SAR_SCENE_DIFF",
  "area_id": "malacca_strait_sector_b",
  "event_type": "UNANNOUNCED_DARK_VESSEL_CLUSTER",
  "confidence": 0.88,
  "location": {
    "latitude": 1.254,
    "longitude": 103.812
  },
  "bounding_box": {
    "min_lat": 1.250,
    "max_lat": 1.258,
    "min_lon": 103.808,
    "max_lon": 103.816
  },
  "attributes": {
    "vessel_count_est": 2,
    "ais_correlation": "NONE",
    "diff_metric": "intensity_ratio_anomaly",
    "sar_pass_id": "S1_20260918_PASS_42"
  }
}
```

### Ingress to Observation Mapping

When ingested (either via upstream REST pull, `POST /api/ingress/candidate-event`, or local scenario fixture), the adapter maps the payload into an internal `Observation` entity:

| `CandidateEvent` Field | Internal `Observation` Target | Notes |
|------------------------|-------------------------------|-------|
| `event_id` | `observation_id` | Unique ingress identifier |
| `source_id` | `source_id` | e.g. `SPACE_SAR_SCENE_DIFF` |
| `event_type` | `entity_hint` | Used for track correlation |
| `location.latitude` | `latitude` | Spatial point |
| `location.longitude` | `longitude` | Spatial point |
| `confidence` | `confidence` | Normalized (0.0 to 1.0) |
| `timestamp` | `observed_at` | Ingress observation time |
| `"space_sar"` | `modality` | Explicit modality tag |
| `bounding_box` + `attributes` | `attributes` | Preserved for audit & operator display |

---

## 3. `POST /api/ingress/candidate-event`

Push an assumed CandidateEvent, load the Pitch-1 offline fixture, ingest
**Sentinel-Imagery-Analysis** dark vessels (issue #47), pull **GLINT** Assumed-mock
(issue #55), or **Dual-SAR** corroborate GLINT × SIA (issue #56). This is the
**Pillar 3** (`S3_sar_ais`) GLINT primary showcase (see [scenarios.md](../scenarios.md)):

```bash
# Pitch-1 assumed CandidateEvent fixture
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"use_fixture":true}'

# Singapore Strait Sentinel run_cv fixture (uncorrelated only)
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"use_sentinel_fixture":true}'

# Pattern B: pull sibling upstream (default http://127.0.0.1:5050); fixture if down
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"pull_upstream":true}'

# GLINT Assumed-mock fixture (no HTTP)
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"use_glint_fixture":true}'

# GLINT pull (default http://127.0.0.1:5051); assumed fixture if down
#   uv run sdth-mock-glint   # or: uv run python scripts/mock_glint_server.py
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"pull_glint":true}'

# Dual-SAR: GLINT macro × SIA micro fixtures → composite (issue #56)
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"dual_sar":true}'

# Dual-SAR pull both; GLINT down → SIA/fixture fail-safe
curl -s -X POST localhost:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' \
  -d '{"pull_dual_sar":true}'
```

| Field | Role |
|-------|------|
| `event` | Assumed CandidateEvent v1.3.0 object |
| `use_fixture` | Load `tests/fixtures/candidate_event_assumed.json` |
| `use_sentinel_fixture` | Map `tests/fixtures/sentinel_run_cv_sg_strait.json` → dark vessels |
| `pull_upstream` | `POST {SAR_UPSTREAM_URL}/api/run_cv/{SAR_UPSTREAM_SCAN}`; on failure use sentinel fixture |
| `run_cv` | Raw Sentinel `run_cv` JSON body (push) |
| `use_glint_fixture` | Load assumed CandidateEvent via GLINT client (tags `ingress=glint`) |
| `pull_glint` | `GET {GLINT_BASE_URL}/api/candidate-event`; on failure use assumed fixture |
| `dual_sar` | Corroborate GLINT × SIA fixtures via `app/adapters/dual_sar.py` |
| `pull_dual_sar` | Pull GLINT + SIA; corroborate when aligned; fail-safe to SIA/fixture |

**Response `200`**
```json
{
  "status": "INGESTED",
  "observation": {},
  "observations": [],
  "track_id": "...",
  "track_ids": [],
  "count": 1,
  "source": "fixture|upstream|run_cv|event|glint|glint_fixture|dual_sar|sia_only"
}
```
*Note: Ingress operations never seal a `DecisionToken`.*

On success, the raw request body is appended to `.audit/ingress.jsonl` (`received_at`, `source`, `endpoint`, `payload`) for demo replay. Write failures are logged as warnings and **do not** fail ingress. This file is **not** the OCSF gate chain (that remains `.audit/gate.jsonl`). Re-run with:

```bash
uv run python scripts/replay_ingress.py --reset
# Optional demo hygiene (truncate jsonl only; does not touch gate.jsonl):
# uv run python scripts/replay_ingress.py --clear
```

---

## 4. `POST /api/ingress/open-feed`

Optional open AIS (Indago DuckDB / live / fixture) or open air (ADS-B-style) ingress
(issues #16, #70). Synthetic S1–S3 remain primary; this path is additive. Never seals a `DecisionToken`.

```bash
# Golden fixture (deterministic CI / default demo)
curl -s -X POST localhost:8080/api/ingress/open-feed \
  -H 'content-type: application/json' \
  -d '{"feed":"all","use_fixture":true}'

# Indago DuckDB (Singapore/Malacca stream → ~/.indago/data/raw/ais/singapore.duckdb)
curl -s -X POST localhost:8080/api/ingress/open-feed \
  -H 'content-type: application/json' \
  -d '{"feed":"ais","source":"indago","limit":80}'
```

| Field | Role |
|-------|------|
| `feed` | `ais`, `air`, `all`, or comma list |
| `use_fixture` | Load `tests/fixtures/open_ais_datagovsg.json` / `open_air_traffic.json` |
| `source` | AIS ladder: `auto` → Indago DuckDB → live → fixture; or force `indago` / `live` / `fixture` |
| `limit` | Max vessels from Indago (default 80) |
| `payload` | Raw snapshot for a **single** feed (`ais` or `air`) |

Indago DuckDB path is configured via env `INDAGO_DUCKDB_PATH` only (not a request field — avoids path injection).

**Response `200`**
```json
{
  "status": "INGESTED",
  "feeds": ["ais"],
  "resolved_sources": {"ais": "indago"},
  "count": 40,
  "items": [{ "feed": "ais", "source": "indago", "observation": {}, "track_id": "..." }]
}
```

### Ingress Normalization

| Open AIS field | Observation Target | Notes |
|----------------|-------------------|-------|
| `vessels[].mmsi` | `source_id` / `observation_id` | MMSI identifier |
| `vessels[].latitude/longitude` | `latitude` / `longitude` | Coordinates |
| `vessels[].speed_kt` | `speed_mps` | Converted via southbound adapter |
| — | `modality` | `"ais"`, `attributes.ingress="open_feed"` |

| Open air field | Observation Target | Notes |
|----------------|-------------------|-------|
| `aircraft[].icao24` | `source_id` / `observation_id` | ICAO 24-bit transponder hex |
| `aircraft[].callsign` | `entity_hint` | Callsign |
| `aircraft[].velocity_kt` | `speed_mps` | Converted via southbound adapter |
| — | `modality` | `"adsb"`, `attributes.ingress="open_feed"` |
