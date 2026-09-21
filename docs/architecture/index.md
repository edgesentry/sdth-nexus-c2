# Closed loop

NexusGate splits **probabilistic interpretation** (app layer) from **deterministic gating** (core):

1. **Probabilistic** — noisy, conflicting feeds (social OSINT, radar, EO blur, AIS, RF) become a Warning Picture / candidate COA.
2. **Deterministic** — kinematic corroboration, geofence/speed interlocks, latency-bounded HITL, sealed `DecisionToken`, immutable OCSF audit.

## End-to-end path

```mermaid
flowchart TD
  A[Multi-source ingress] --> B[SpatialEntityGraph]
  B --> C[Discrepancy / Amber flag]
  C --> D[Warning Picture]
  D --> E[Latency-bounded gate]
  E -->|deny / timeout| F[Default deny / safe hold]
  E -->|approve| G[DecisionToken]
  G --> H[Recipient inbox]
  H --> I[Field Ack]
  I --> J[OCSF hash-chain audit]
  E --> J
```

## Decision path (code)

```text
build_events()  →  SpatialEntityGraph
        →  detect() → Finding | None
        →  build_coa() → CourseOfAction (Tier-1 HITL)
        →  LatencyBoundedGate.evaluate()
              fast-reject (<5ms) → Geofence / Speed / Duplicate
              approve (<50ms)   → DecisionToken → Recipient
              deny / timeout    → Default = Deny
        →  Recipient Ack → AuditLogger seals Token & Ack
```

## Warning Picture (`Finding`)

| Field | Meaning |
|-------|---------|
| `threat_class` | e.g. `attritable_air_incursion` |
| `warning_minutes_est` | Tactical minutes remaining |
| `mismatch_m` | Spatial disagreement between sources |
| `confidence` | Rule-composed score (0.0 to 1.0) |
| `picture_summary` | Single operational summary |
| `adversarial_hypothesis` | “If source X is false…” |
| `amber_alert` | e.g. `COUNT_AND_BEARING_MISMATCH` |
| `source_breakdown` | Claims by modality |

Core never invents a fused track when sensors disagree — it surfaces the contradiction, then gates action.

---

## Extensibility & Scaling: 8 Orthogonal Dimensions

A common failure mode in C2 engineering is **combinatorial complexity**: as sensor types, tactical actions, effectors, mission scenarios, and operational rules grow, naive architectures scale exponentially as $\mathcal{O}(N \times A \times E \times U \times \dots)$, requiring bespoke cross-conversion code for every permutation.

NexusGate prevents implementation explosion by decomposing the C2 problem into **eight orthogonal boundaries** across two tiers: **Functional Pipeline (I/O & Tasks)** and **Governance & Operational Environment**. This reduces architectural complexity to strictly linear scaling:

$$\mathcal{O}(N + A + E + U + H + G + S + C)$$

```mermaid
flowchart TD
    subgraph Governance ["Governance & Operational Environment Layer (Orthogonal Constraints)"]
        H["5. Hierarchy & ROE (H)<br/>(Tier-1 HITL / Dual-Key / Tier-0)"]
        G["6. Geographic Jurisdiction (G)<br/>(12nm Territorial / EEZ / Corridor)"]
        S["7. Security Enclave (S)<br/>(Unclassified AIS / Secret Radar)"]
        C["8. Contested State (C)<br/>(Live / Degraded DIL / Offline Fixture)"]
    end

    subgraph Pipeline ["Functional Task Pipeline (Linear Scaling)"]
        N_IN["1. Sensors (N)<br/>(Radar, AIS, SAR, EO, RF, OSINT)"] --> ADAPT["Canonical Ingress<br/>(Observation)"]
        ADAPT --> GRAPH["SpatialEntityGraph<br/>(Dynamic Ontology)"]
        GRAPH --> U_RULES["4. Use Cases (U)<br/>(Discrepancy Archetypes)"]
        U_RULES --> A_COA["2. Actions (A)<br/>(COA Primitives + Lead POI)"]
        A_COA --> GATE{"Deterministic Gate<br/>(<50ms Interlock)"}
        GATE -->|Sealed Token| E_OUT["3. Effectors (E)<br/>(Inbox / Ack Contract)"]
    end

    Governance -.->|Invariant Guardrails| GATE
    Governance -.->|Provenance Tagging| GRAPH
```

---

### A. Functional Task Pipeline Dimensions

| Dimension | What Changes | Why Complexity Does NOT Explode | Where Code Is Added |
|---|---|---|---|
| **1. Sensor Inputs ($N$)** | Acoustic sonar, satellite optical, cyber signal, OSINT text | **Ingress Normalization ($\mathcal{O}(N)$)**: An adapter maps the feed into the canonical [`Observation`](../api/rest.md) structure. The core graph handles spatial and temporal correlation automatically via physics (Haversine & Dead-Reckoning); zero cross-sensor mapping matrices ($N \times M$) are needed. Upstream crawling and CV inference remain strictly externalized. | `app/adapters/<sensor>.py` |
| **2. Actions ($A$)** | Warning flare, jamming, civilian evacuation cue | **COA Primitives ($\mathcal{O}(A)$)**: Actions are modeled as standard tactical intents (`target_coordinates`, `action_type`, `tier`, `vectoring`). Intercept geometry is resolved centrally by [`core/kinematics.py`](sar_pipeline.md#23-dual-sar-synergy-temporal-kinematic-bridge) rather than re-engineered per action. | [`core/coa.py`](../api/rest.md#post-apigateproposals) |
| **3. Field Effectors ($E$)** | USV, MPA aircraft, shore battery, municipal police | **Recipient Ack Contract ($\mathcal{O}(E)$)**: Core never communicates directly with hardware actuators. It delivers cryptographically sealed `DecisionTokens` via a pull-based inbox (`GET /api/recipient/inbox`) and awaits signed Ack (`POST /api/recipient/ack`). Physical actuation protocol conversion lives at the edge. | Edge effector client |
| **4. Use Cases ($U$)** | Counter-piracy, illegal fishing, contested airspace | **Discrepancy Archetypes ($\mathcal{O}(U)$)**: Operational contradictions naturally reduce to 4 mathematical primitives (*Presence vs Silence*, *Kinematic Velocity*, *Count*, and *Spatial Offset*). New scenarios simply map these primitives to COA intents via declarative policies or probabilistic proposers ([`app/llm_interpreter.py`](../litellm.md)). | `app/scenarios/` or declarative policy |

---

### B. Governance & Operational Environment Dimensions

| Dimension | What Changes | Why Complexity Does NOT Explode | Where Policy Is Configured |
|---|---|---|---|
| **5. Hierarchy & ROE ($H$)** | Tier-1 operator approval, Tier-2 dual-key commander sign-off, Tier-0 automated kinetic defense | **Multi-Tier Gate Engine**: Authority logic is decoupled from tactical action code. [`core/gate.py`](../api/rest.md#post-apigateapprove) enforces approval windows, required operator keys, and latency limits based strictly on the COA's `tier` field. | Gate policy / approval config |
| **6. Geographic Jurisdiction ($G$)** | Singapore Strait TSS, 12nm territorial waters, 200nm EEZ, flight corridors | **Spatial Interlock Policy**: Legal boundaries (UNCLOS, municipal zones) are maintained as polygon attributes in [`core/interlock.py`](../api/rest.md). Spatial rules fast-reject unauthorized actions without modifying scenario logic. | Geofence geojson / polygon registry |
| **7. Security & Multi-Tenancy ($S$)** | Unclassified open AIS, sovereign classified 3D radar, cross-domain coalition feeds | **Cryptographic Enclaves & Provenance**: Raw observations carry source clearance tags. The in-memory graph computes contradictions across enclaves, while the immutable OCSF hash chain seals decision tokens without leaking classified telemetry. | `Observation.attributes` + OCSF audit |
| **8. Contested & DIL States ($C$)** | Peacetime high-bandwidth, GPS jamming/spoofing, disconnected/intermittent/limited (DIL) | **Degraded Mode Ladder**: Each subsystem has an automatic fail-safe fallback (e.g., Live API $\to$ Indago DuckDB $\to$ Golden Fixtures; Cloudflare $\to$ Local laptop Core). The deterministic gate executes locally even under complete network severance. | Ingress adapters & runtime fallbacks |

---

### Ingress Boundaries: Why C2 Does Not Scrape Raw OSINT / Social Media

A fundamental tenet of NexusGate is the strict separation between **Intelligence Collection/Filtering** (upstream services) and **Tactical Action Gating** (C2 Core):

```mermaid
flowchart LR
    subgraph External ["External Intelligence Layer (Public Internet / Cloud)"]
        SM["Public Social Media<br/>(Telegram, X, Civil Apps)"] --> CRAWL["Crawler & NLP Pipeline<br/>(Deduplication / Geocoding / LLM)"]
        CRAWL --> LAKE[("Threat Intel Store<br/>(Elasticsearch / OpenSearch)")]
    end

    subgraph Boundary ["Cross-Domain Boundary"]
        DIODE["Data Diode / TLS API Gateway<br/>POST /api/ingress/candidate-event"]
    end

    subgraph C2 ["NexusGate C2 Enclave (Tactical / Air-Gapped)"]
        ADAPT["OSINT Adapter<br/>(app/adapters/osint_text.py)"]
        GRAPH[("SpatialEntityGraph<br/>(In-Memory Correlation)")]
        GATE{"Deterministic Gate<br/>(<50ms Interlock)"}

        ADAPT --> GRAPH
        GRAPH --> GATE
    end

    LAKE -->|Structured Event JSON| DIODE
    DIODE --> ADAPT
```

| Question | Architectural Decision | Operational Rationale |
|---|---|---|
| **Does C2 crawl social media directly?** | **No.** Social media crawling is strictly externalized to specialized threat intelligence platforms. | **Air-gap & Enclave Security**: Military C2 cores run inside restricted or air-gapped enclaves (e.g. SIPRNet, tactical edge servers) that prohibit direct outbound internet scraping. |
| **Why not run scrapers / full NLP in C2?** | Heavy multi-modal NLP, video OCR, and bot-mitigation pipelines run asynchronously upstream. | **Deterministic Latency Budget**: 99.9% of social chatter is noise, spam, or disinfo. Crawling firehoses would destroy C2's sub-50ms deterministic gate guarantee. |
| **How does OSINT enter C2?** | Via normalized ingress adapters ([`app/adapters/osint_text.py`](../data-provenance.md#inventory)). | **Canonical Contract**: Upstream services distill raw chatter into structured claims (`timestamp`, `lat/lon`, `count=3`, `confidence=0.72`) which map into canonical `Observation` objects. |
| **Current Mock vs. Production Reality** | Current repo uses synthetic text fixtures and regex/NLP parsers ([#59](https://github.com/edgesentry/sdth-nexus-c2/issues/59)). | In production, the adapter ingests structured event JSON from external feeds (e.g., Dataminr, Primer, or civil defense intake apps like Ukraine's *єВорог*). See [Data Provenance](../data-provenance.md) and [Scenarios (S2)](../scenarios.md). |

---

### Key Architectural Invariants Under Scale
1. **No Data Fusion Loss**: Because observations remain discrete in the graph, new use cases can leverage raw modality claims without being blinded by premature track blending.
2. **Immutable Gate Rules**: Adding 50 new sensors or 20 new effectors does not alter the deterministic fast-reject safety rules (<50ms geofence, velocity clamps, duplicate suppression). Safety constraints remain constant regardless of operational scale.
3. **Decoupled Data Storage & Ingestion**: Heavy historical persistence ([Indago / ClickHouse](sar_pipeline.md#24-decoupled-3-tier-architecture-cognitive-load-compression)) and raw intelligence gathering (social media web scraping, raster CV) are absorbed by external upstream systems. The C2 decision engine remains strictly in-memory, state-bounded, and deterministic.
