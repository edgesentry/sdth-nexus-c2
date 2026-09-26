# End-to-End Verification (NexusGate)

Comprehensive runbook for executing and validating the full **Picture → Gate → Ack** closed loop starting from a **clean zero-state reset** (all processes stopped, state cleared) to end-to-end execution and cryptographic data verification.

- **Primary scenarios** (see [scenarios.md](scenarios.md)):
  - **S3** — Singapore Strait dark vessel (Dual-SAR × AIS) — hero maritime loop
  - **s1_trojan** — Happy Tug AIS vs coastal radar disagreement + CNI debris VETO (#116)
- **CUI (no browser)**: pytest (in-process) · `scripts/picture_to_tasking.py` · curl against `:8080`
- **Console UIs**: Core `/verify` (Jinja2/HTMX Screen 1/2) or external **ARCHVIEW** (`:3001`)
- **Key Specifications**: [C2 REST API](api/rest.md) · [Demo Guide](demo.md) · [Data Provenance](data-provenance.md) · [SAR Pipeline](architecture/sar_pipeline.md) · [Architecture Map](architecture/index.md)

---

## 0. System Topology & Port Allocations

| Component | Port | Startup Command | Status | Role |
|---|---|---|---|---|
| **NexusGate Core** | `:8080` | `uv run sdth-c2-server` | **Required** | C2 server, in-memory ontology graph, deterministic gate, OCSF audit seal, `/verify` UI |
| **GLINT Mock** | `:5051` | `uv run sdth-mock-glint` | Optional (Live pull) | Team 02 GLINT macro SAR corridor anomaly cluster mock |
| **SIA Upstream** | `:5050` | `uv run sia-server` | Optional (Live pull) | In-house Sentinel-1 micro SAR CV metrology (automatic fail-safe fallback when offline) |
| **USV Effector Mock** | `:8000` | `uv run uvicorn mocks.usv:app --port 8000` | Optional (Demo script) | CLEARBOT / autonomous USV telemetry & tasking mock |
| **ARCHVIEW Vite** | `:3001` | `npm run dev` | Optional (ARCHVIEW) | External React/Vite tactical command cockpit (Screen 1) |
| **ARCHVIEW BFF** | `:3102` | `npm run dev:api` | Optional (ARCHVIEW) | Evidence image/video BFF server |

```mermaid
flowchart TD
    subgraph IngressFeeds ["1. Ingress Feeds"]
        AIS["Indago DuckDB / Live AIS<br/>(Singapore Strait T-0)"]
        GLINT["GLINT Mock :5051<br/>(Macro SAR Cluster)"]
        SIA["SIA :5050 / Fixtures<br/>(Micro SAR Metrology)"]
    end

    subgraph C2Core ["2. NexusGate C2 Core (:8080)"]
        GRAPH["SpatialEntityGraph<br/>(Modality Separation)"]
        KINEMATICS["Kinematic Engine<br/>(Lead Intercept POI)"]
        GATE["Deterministic Gate<br/>(Amber Alert Interlock)"]
        SEAL["DecisionToken Issuer<br/>(SHA-256 + Private Key)"]
        AUDIT["OCSF Audit Logger<br/>(.audit/gate.jsonl Hash Chain)"]
    end

    subgraph Consoles ["3. Tactical Consoles (Screen 1)"]
        VERIFY["Core /verify (Screen 1/2)<br/>(Jinja2 + HTMX)"]
        ARCHVIEW["ARCHVIEW Vite :3001<br/>(External Frontend)"]
    end

    subgraph Effectors ["4. Field Effectors (Screen 2)"]
        INBOX["Unit Tasking Inbox<br/>(CUE-NODE-01 / USV-02)"]
        ACK["Signed Recipient Ack<br/>(Closed Loop Completed)"]
    end

    AIS -->|POST /api/ingress/open-feed| GRAPH
    GLINT -->|POST /api/ingress/candidate-event| GRAPH
    SIA -->|POST /api/ingress/candidate-event| GRAPH
    GRAPH --> KINEMATICS
    KINEMATICS --> GATE
    GATE -->|POST /api/gate/approve| SEAL
    SEAL --> AUDIT
    SEAL --> INBOX
    INBOX --> ACK
    ACK -->|POST /api/recipient/ack| AUDIT

    C2Core <--> VERIFY
    C2Core <--> ARCHVIEW
```

---

## 1. Zero-State Clean Reset

Follow these steps to kill any lingering processes, clear local storage and audit trails, and ensure a completely clean environment before running the E2E verification.

### 1.1 Terminate Running Processes

Stop any existing C2, mock, or frontend processes and free ports `:8080`, `:5051`, `:5050`, `:8000`, `:3001`, and `:3102`:

```bash
# Terminate processes occupying target ports
kill $(lsof -ti :8080 :5051 :5050 :8000 :3001 :3102) 2>/dev/null || true

# Verify that all ports are freed (should return empty output)
lsof -i :8080 -i :5051 -i :5050 -i :8000 -i :3001 -i :3102
```

### 1.2 Clear Audit Trails, Scratch Directories & Cache

Wipe previous audit records (`.audit/`), temporary test files (`.tmp-e2e/`), and compiled Python cache:

```bash
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2

# Remove existing audit trails and temporary artifacts
rm -rf .audit/gate.jsonl .audit/ingress.jsonl .tmp-e2e/
mkdir -p .audit

# Clean Python bytecode caches
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

### 1.3 Sync Environment & Dependencies

```bash
uv sync
```

---

## 2. Server Startup Options

Select the deployment profile appropriate for your verification target:

### Profile A: Core Only (Minimal & Recommended)

No external processes (Node.js, SIA, or GLINT server) are required. C2 uses built-in fail-safe fixtures that emulate identical Dual-SAR fusion and closed-loop gating behavior.

```bash
# Terminal 1: Start C2 Core
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2
export C2_DEMO_TAMPER=1
uv run sdth-c2-server
# => Running on http://127.0.0.1:8080
```

### Profile B: Full-Spectrum (With Live GLINT Mock)

To verify live macro SAR HTTP polling alongside SIA micro SAR fail-safe:

```bash
# Terminal 1: C2 Core
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2
export C2_DEMO_TAMPER=1
uv run sdth-c2-server

# Terminal 2: GLINT Mock (:5051)
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2
uv run sdth-mock-glint
```

### Profile C: ARCHVIEW Tactical Console Integration

```bash
# Terminal 1: C2 Core (:8080)
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2
uv run sdth-c2-server

# Terminal 2: ARCHVIEW Tactical Console (:3001) & BFF (:3102)
cd /path/to/SDTH-2026
npm run dev:api &   # Starts BFF on :3102
npm run dev         # Starts Vite on :3001
```

### Startup Health Verification

Verify responsiveness in a separate terminal:

```bash
curl -sf http://127.0.0.1:8080/health | jq .
# Expected: {"status": "ok"}

curl -sf http://127.0.0.1:8080/api/audit/health | jq .
# Expected: {"verified": true, "broken": 0, "count": 0, "label": "0 of 0"}
```

---

## 3. End-to-End Execution Workflows

CUI first. Browser `/verify` is optional rehearsal (Workflow 4).

| Mode | Server needed? | Scenarios | What it proves |
|---|---|---|---|
| **pytest** | No (in-process `TestClient`) | `s1_trojan` (+ S2 claim-tags via verify UI tests) | Gate CNI VETO, Navy silo, claim-tags, guardrail queue |
| **`picture_to_tasking.py`** | Yes (`uv run sdth-c2-server`) | `S1` / `S2` / `S3` | Propose → Approve → Inbox → Ack → audit seal |
| **curl** | Yes | `S3` and `s1_trojan` | Same loops; `s1_trojan` must use the guardrail endpoint |

> **`s1_trojan` note:** `POST /api/gate/proposals` with `scenario_id=s1_trojan` returns
> `REJECTED_FAST` / `SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD` by design (terminal SAM over
> Jurong CNI). Use `POST /api/gate/demo-evaluate-with-guardrail` to VETO Option A and
> queue enforced Option B.

---

### Workflow 1: pytest (CUI, no server)

Fastest check for issue #116 acceptance without starting uvicorn:

```bash
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2
uv sync

uv run python -m pytest \
  tests/unit/test_tri_service_interlocks.py \
  tests/integration/test_trojan_mothership_e2e.py \
  tests/unit/test_verify_ui.py \
  -q
```

**Expected**: all tests `PASSED` (≈22+ depending on suite growth). Covers CNI VETO,
offshore Option B, Verify propose claim-tags, Navy silo, and guardrail panel.

One-shot Trojan mothership only:

```bash
uv run python -m pytest tests/integration/test_trojan_mothership_e2e.py -q
```

---

### Workflow 2: One-shot Picture→Tasking script (CUI, S1/S2/S3)

Starts (or reuses) Core and runs Propose → Approve → Inbox → Ack → audit.

```bash
# Terminal A — Core
cd /Users/yoheionishi/work/SDTH2026/sdth-nexus-c2
export C2_DEMO_TAMPER=1
uv run sdth-c2-server
# => http://127.0.0.1:8080

# Terminal B — closed loop (default scenario S2)
SCENARIO=S3 uv run python scripts/picture_to_tasking.py --require-roundtrip

# Or one process (script starts Core if C2_BASE_URL is local):
SCENARIO=S3 ./scripts/picture_to_tasking.sh
```

**Expected** (stdout ends with PASS / Ack sealed):

```text
NexusGate — Picture→Tasking demo (no UI)
  Scenario   : S3
...
PASS: Ack sealed in OCSF audit chain within target
```

Other scenarios:

```bash
SCENARIO=S1 uv run python scripts/picture_to_tasking.py
SCENARIO=S2 uv run python scripts/picture_to_tasking.py --require-roundtrip
```

Do **not** pass `SCENARIO=s1_trojan` here — plain propose is hard-rejected by the CNI
interlock. Use Workflow 3b instead.

---

### Workflow 3a: curl closed loop — Hero S3

```bash
export C2=http://127.0.0.1:8080

# 0. Health
curl -sf "$C2/health" | jq .
curl -sf "$C2/api/audit/health" | jq .

# 1. Reset in-memory + SQLite runtime picture
curl -sf -X POST "$C2/api/admin/reset" | jq .

# 2. Optional background AIS (Indago ladder / fixture)
curl -sf -X POST "$C2/api/ingress/open-feed" \
  -H 'content-type: application/json' \
  -d '{"feed":"ais","use_fixture":true,"limit":40}' | jq '{status, count}'

# 3. Dual-SAR anomaly (GLINT macro + SIA micro fixtures)
curl -sf -X POST "$C2/api/ingress/candidate-event" \
  -H 'content-type: application/json' \
  -d '{"dual_sar":true}' | jq '{source, count}'

# 4. Propose S3 COA
PROP=$(curl -sf -X POST "$C2/api/gate/proposals" \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"S3","unit_id":"CUE-NODE-01"}')
echo "$PROP" | jq '{status, amber: .finding.amber_alert, threat: .finding.threat_class}'
COA_ID=$(echo "$PROP" | jq -r '.coa.coa_id')
test "$COA_ID" != null && test -n "$COA_ID"

# 5. Commander Approve -> Seals DecisionToken
APPROVE=$(curl -sf -X POST "$C2/api/gate/approve" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"decision\":\"y\",\"operator_id\":\"commander-01\"}")
echo "$APPROVE" | jq '{status, coa_id: .coa.coa_id, token_digest: .decision_token.token_digest}'

# 6. Recipient Effector Inbox Inspection
curl -sf "$C2/api/recipient/inbox?unit_id=CUE-NODE-01" | jq '{count, tasking_coa: .taskings[0].coa.coa_id}'

# 7. Recipient Effector Execution Acknowledgment (Ack)
curl -sf -X POST "$C2/api/recipient/ack" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"unit_id\":\"CUE-NODE-01\",\"status\":\"ACKED\"}" | jq .

# 8. Cryptographic Audit Health Check
curl -sf "$C2/api/audit/health" | jq .
```

---

### Workflow 3b: curl closed loop — `s1_trojan` (CNI guardrail, #116)

Requires Core running (`uv run sdth-c2-server`). Plain propose is expected to
hard-reject; the demo path evaluates Option A through the live CNI interlock and
queues enforced Option B for dual-unit authorize.

```bash
export C2=http://127.0.0.1:8080

curl -sf -X POST "$C2/api/admin/reset" | jq .

# Optional: show that plain propose is hard-rejected (CNI debris)
curl -sf -X POST "$C2/api/gate/proposals" \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"s1_trojan","unit_id":"GBAD-RSAF-01"}' \
  | jq '{status, reason}'
# Expected: status == "REJECTED_FAST", reason contains SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD

# Guardrail path: VETO Option A, queue Option B
GR=$(curl -sf -X POST "$C2/api/gate/demo-evaluate-with-guardrail" \
  -H 'content-type: application/json' \
  -d '{
    "scenario_id":"s1_trojan",
    "unit_id":"GBAD-RSAF-01",
    "navy_unit_id":"PCG-PT-44"
  }')
echo "$GR" | jq '{
  status,
  veto_code,
  veto_reason,
  option_b_intent: .fallback_coa.intent,
  finding_amber: .finding.amber_alert,
  queued_for
}'
# Expected:
#   status == "GUARDRAIL_VETO_OPTION_B_QUEUED"
#   veto_code == "SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD"
#   fallback_coa.intent == "OFFSHORE_INTERCEPT_RF_SOFTKILL"
#   finding.amber_alert contains VELOCITY_MISMATCH_AIS_VS_RADAR
#   queued_for == ["GBAD-RSAF-01","PCG-PT-44"]

COA_ID=$(echo "$GR" | jq -r '.fallback_coa.coa_id')

# Authorize Option B (dual dispatch: GBAD + Navy)
curl -sf -X POST "$C2/api/gate/approve" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"decision\":\"y\",\"operator_id\":\"commander-01\"}" \
  | jq '{status}'

# Both inboxes should receive tasking
curl -sf "$C2/api/recipient/inbox?unit_id=GBAD-RSAF-01" | jq '{unit_id, count}'
curl -sf "$C2/api/recipient/inbox?unit_id=PCG-PT-44" | jq '{unit_id, count}'

# Ack from GBAD line (repeat for Navy sister coa_id if dual-issued)
GBAD_COA=$(curl -sf "$C2/api/recipient/inbox?unit_id=GBAD-RSAF-01" | jq -r '.taskings[0].coa.coa_id')
curl -sf -X POST "$C2/api/recipient/ack" \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$GBAD_COA\",\"unit_id\":\"GBAD-RSAF-01\",\"status\":\"ACKED\"}" \
  | jq '{status}'

curl -sf "$C2/api/audit/health" | jq .
curl -sf "$C2/api/ontology/state" | jq '{
  scenario_id,
  amber: .amber_alert.alert,
  obs: (.observations|length),
  pending: (.pending_proposals|length)
}'
```

Ontology after guardrail should still carry the disagreement finding (AIS ~6 kt vs
radar ~120 kt) and POI ETA flags under `amber_alert.source_breakdown.poi_eta_sec`.

---

### Workflow 4: Core WebUI (`/verify`) rehearsal

Interactive HITL using dual browser tabs (optional after CUI pass):

1. Open:
   - Screen 1: [http://127.0.0.1:8080/verify/command](http://127.0.0.1:8080/verify/command)
   - Screen 2: [http://127.0.0.1:8080/verify/recipient](http://127.0.0.1:8080/verify/recipient)
2. **S3 path**: Ingress Dual-SAR → Propose `S3` → Approve → Ack on Screen 2.
3. **`s1_trojan` path (#116)**:
   - Select scenario `s1_trojan` → Propose (Warning Picture shows claim-tags AIS vs radar).
   - Service silo → **Navy** (Happy Tug AIS / coastal radar visible).
   - Guardrail panel → **Evaluate Option A (live VETO)** → AUTHORIZE Option B.
   - Screen 2: Ack for `GBAD-RSAF-01` (and Navy unit if dual-queued).

Deep-link:

```text
http://127.0.0.1:8080/verify/command?scenario_id=s1_trojan&service_view=navy
```

---

### Workflow 5: Path ARCHVIEW (Hero S3) {#path-archview-hero-s3--issue-99}

Closed-loop execution combining external **ARCHVIEW** (Vite `:3001`) with Core (`:8080`):

```bash
# 1. Reset Core & Ingest Dual-SAR
curl -sf -X POST http://127.0.0.1:8080/api/admin/reset >/dev/null
curl -sf -X POST http://127.0.0.1:8080/api/ingress/candidate-event \
  -H 'content-type: application/json' -d '{"dual_sar":true}' | jq '{source,count}'
# Expected: dual_sar observations ingested (count >= 1)

# 2. ARCHVIEW UI Actions (http://127.0.0.1:3001)
# - Scenario: Select S3 Maritime Hero -> Click [Propose]
# - Inspect Amber Warning ("SAR_DARK_CLUSTER_VS_AIS_SILENCE") & Lead Intercept POI
# - Click [Approve] on the HITL card within timeout (Core seals DecisionToken)

# 3. Screen 2 Recipient Ack (Abort path default)
# - Browser: http://127.0.0.1:8080/verify/recipient -> Click [Ack]
# - Or CLI:
COA_ID=$(curl -sf "http://127.0.0.1:8080/api/recipient/inbox?unit_id=CUE-NODE-01" | jq -r '.taskings[0].coa.coa_id')
curl -sf -X POST http://127.0.0.1:8080/api/recipient/ack \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"unit_id\":\"CUE-NODE-01\",\"status\":\"ACKED\"}" | jq .status

# 4. Verify ARCHVIEW Audit Pill
# ARCHVIEW console audit pill displays green ("0 of n", verified: true)
curl -sf http://127.0.0.1:8080/api/audit/health | jq .
```

---

### Workflow 6: Tamper Detection Rehearsal {#tamper-detection-rehearsal-88}

Validates that a 1-character insider tampering of `gate.jsonl` is detected immediately by SHA-256 hash chaining and out-of-process EDS verification, halting execution until restored:

1. **CLI Rehearsal**:
   ```bash
   uv run python scripts/demo_tamper_detection.py
   # Expected: Exit 0 (Chain built -> 1-char tamper injected -> mismatch detected -> restored -> valid)
   ```

2. **WebUI Interactive Rehearsal**:
   - Launch with `C2_DEMO_TAMPER=1 uv run sdth-c2-server`.
   - Complete a cycle (Propose → Approve → Ack) on `/verify/command`.
   - In the **Audit integrity** panel:
     1. Click **Inject 1-char tamper** → Status badge changes to warning (`broken links 1 of n` / `hash mismatch`).
     2. Click **Re-verify** → Confirms SHA-256 and EDS out-of-process verification failure.
     3. Click **Restore** → Restores pre-tamper snapshot (`broken links 0 of n`).

---

## 4. Data Verification Procedures

Checklist for verifying data correctness, mathematical integrity, and non-repudiation at each pipeline stage.

### 4.1 Ingress & Ontology State Verification (`GET /api/ontology/state`)

Execute inspection query:
```bash
curl -sf http://127.0.0.1:8080/api/ontology/state | jq '{
  scenario: .scenario_id,
  track_count: (.tracks | length),
  obs_count: (.observations | length),
  amber: .amber_alert.alert,
  pending: .pending_proposals,
  inbox: .inbox_depth
}'
```

#### ✅ Verification Point 1: Modality Separation
- **Check**: AIS commercial tracks and SAR radar observations must **never** be prematurely blended into a single hallucinated composite track.
- **Pass Criteria**:
  - `tracks[].modalities` preserves distinct values (`["ais"]` for AIS vessels, `["space_sar"]` for SAR detections).
  - Unannounced dark vessels remain isolated as independent radar tracks rather than overwriting legitimate AIS tracks.

#### ✅ Verification Point 2: Dual-SAR Corroboration
- **Check**: Macro SAR (GLINT cluster cue) and micro SAR (Sentinel-1 metrology) spatially align within the sector corridor ($\le 3\text{ km}$ or macro bbox), yielding elevated confidence.
- **Pass Criteria**:
  - `source_id`: `"DUAL_SAR"`
  - `attributes.dual_sar_status`: `"corroborated"`
  - `confidence`: `0.98` (boosted from individual 0.91 / 0.84 scores)
  - `attributes.metrology`: Length $L=78.2\text{ m}, 52.0\text{ m}$ preserved from SIA
  - Evidence chip URL: Valid link to `/static/fixtures/sentinel_chip.jpg`

#### ✅ Verification Point 3: SAR Ingress Mode Discrepancy {#compare-sar-ingress-modes-results-must-differ}
When executing each mode after an `/api/admin/reset`, verify that outputs are observably distinct:

| Mode | Trigger Payload | Expected `source_id` | Detections | Length ($L$) | Confidence | Radar Chip |
|---|---|---|---|---|---|---|
| **SIA only** | `{"use_sentinel_fixture":true}` | `SENTINEL_IMAGERY_ANALYSIS` | **2** | $78.2\text{m}, 52.0\text{m}$ | ~0.91 / 0.84 | **Yes** (`sentinel_chip.jpg`) |
| **GLINT only** | `{"use_glint_fixture":true}` | `SPACE_SAR_SCENE_DIFF` | **1** | None (Macro cluster) | ~0.88 | **No** (Macro scene difference) |
| **Dual-SAR** | `{"dual_sar":true}` | `DUAL_SAR` | **2** | Inherited from SIA | **~0.98** (Boosted) | **Yes** (Inherited from SIA) |

---

### 4.2 Gate / Amber Warning & Lead Intercept POI Verification (`POST /api/gate/proposals`)

Inspect proposal payload:
```bash
curl -sf -X POST http://127.0.0.1:8080/api/gate/proposals \
  -H 'content-type: application/json' \
  -d '{"scenario_id":"S3","unit_id":"CUE-NODE-01"}' | jq '.finding, .coa'
```

#### ✅ Verification Point 1: Amber Alert Formulation
- `finding.amber_alert`: `"SAR_DARK_CLUSTER_VS_AIS_SILENCE"`
- `finding.threat_class`: `"lane_sar_ais_dark_cluster"`
- `finding.mismatch_m`: $\approx 4,973\text{ m}$ (spatial disparity between AIS shipping lane and anomalous radar contact)

#### ✅ Verification Point 2: Dynamic Lead Intercept Kinematics
- **Check**: Action target coordinates must not point to stale historical detection positions. Instead, the system must calculate a dynamic **Point of Interception (POI)** using quadratic collision-course kinematics ([#58](https://github.com/edgesentry/sdth-nexus-c2/issues/58)).
- **Pass Criteria**:
  - `coa.intent`: `"APPROACH_PATROL"`
  - `coa.target_coordinates`: Four-decimal latitude/longitude pair
  - `coa.metadata.poi`: Contains calculated `bearing_deg`, `speed_mps`, and `eta_s`

---

### 4.3 Commander Authorization & DecisionToken Seal (`POST /api/gate/approve`)

Inspect approval response:
```bash
curl -sf -X POST http://127.0.0.1:8080/api/gate/approve \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"decision\":\"y\",\"operator_id\":\"commander-01\"}" | jq .
```

#### ✅ Verification Point 1: Cryptographic Seal Integrity
- `status`: `"APPROVED"`
- `decision_token`:
  - `token_id`: Valid UUID
  - `coa_id`: Exactly matches proposed COA ID
  - `token_digest`: 64-character hexadecimal SHA-256 digest
  - `sealed_at`: UTC ISO 8601 timestamp

#### ✅ Verification Point 2: Core Authority Invariant
- **The client UI or edge effector never issues or seals tokens independently.** Only Core `POST /api/gate/approve` has authority to issue a valid `DecisionToken`.

---

### 4.4 Recipient Tasking Delivery & Ack Verification

```bash
# 1. Inspect unit inbox
curl -sf "http://127.0.0.1:8080/api/recipient/inbox?unit_id=CUE-NODE-01" | jq .
# Pass: count == 1, taskings[0].coa.coa_id == $COA_ID

# 2. Submit execution Ack
curl -sf -X POST http://127.0.0.1:8080/api/recipient/ack \
  -H 'content-type: application/json' \
  -d "{\"coa_id\":\"$COA_ID\",\"unit_id\":\"CUE-NODE-01\",\"status\":\"ACKED\"}" | jq .
# Pass: status == "ACKED"
```

---

### 4.5 OCSF Audit Hash-Chain Integrity (`GET /api/audit/health`)

Verify audit trail health:
```bash
curl -sf http://127.0.0.1:8080/api/audit/health | jq .
```

#### ✅ Expected Health Output
```json
{
  "verified": true,
  "broken": 0,
  "count": 3,
  "label": "0 of 3"
}
```
- `verified`: Must be `true`.
- `broken`: Must be `0`.
- `count`: Minimum $\ge 3$ sequentially chained records (`coa_proposed`, `gate_decision`, `tasking_acked`).

#### Physical Log Verification
Inspect `.audit/gate.jsonl` to confirm cryptographic link chaining:
```bash
tail -n 3 .audit/gate.jsonl | jq '{class_name: .class_name, record_hash: .record_hash, prev_hash: .prev_record_hash}'
```

---

## 5. Troubleshooting & Operational Notes

| Issue | Likely Cause | Resolution |
|---|---|---|
| `Address already in use` error on startup | Stale C2 or mock server running in background | Run `kill $(lsof -ti :8080 :5051 :5050) 2>/dev/null \|\| true` |
| `Duplicate COA` / `active_coa_ids` 400 error | Previous scenario state remains in memory | Execute `curl -sf -X POST http://127.0.0.1:8080/api/admin/reset` |
| `Window expired` error during Approve | Operator exceeded HITL decision window (typically 30s) | Re-trigger proposal via `POST /api/gate/proposals` and approve promptly |
| SIA upstream 500 / unreachable | Sibling SIA service `:5050` is not running | SIA is optional; C2 automatically falls back to deterministic Singapore Strait fixtures |
| Audit health reports `broken > 0` | Audit file was tampered with or corrupted | Run `POST /api/admin/audit/restore` or remove `.audit/gate.jsonl` and reset |

---

## 6. Pass Criteria Checklist

### S3 (maritime hero)
- [ ] **Reset**: Ports 8080 (+ optional mocks) cleared; zero-state starts cleanly.
- [ ] **Ingress**: AIS and SAR observations populate the graph with modality separation.
- [ ] **Dual-SAR**: GLINT macro + SIA micro corroborate (`dual_sar`).
- [ ] **Gate**: Amber (`SAR_DARK_CLUSTER_VS_AIS_SILENCE` / equivalent) + Lead Intercept POI.
- [ ] **Approve / Ack / Audit**: sealed token → inbox → `ACKED` → `verified: true`, `broken: 0`.

### s1_trojan (#116)
- [ ] **pytest** Workflow 1 green (or curl Workflow 3b).
- [ ] Plain `POST /api/gate/proposals` → `REJECTED_FAST` + `SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD`.
- [ ] `POST /api/gate/demo-evaluate-with-guardrail` → Option B queued; amber includes velocity mismatch.
- [ ] Navy silo / ontology shows Happy Tug AIS; claim-tags show AIS vs radar.
- [ ] Approve Option B → GBAD (+ Navy) inbox → Ack → audit healthy.
