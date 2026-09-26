# Tests

Pytest suite for NexusGate Core (`pyproject.toml` → `testpaths = ["tests"]`).

```text
tests/
  unit/           # Fast, in-process checks (no live server)
  integration/    # Multi-hop / HTTP / UI closed loops
  fixtures/       # Deterministic ingress snapshots for CI
```

Run everything:

```text
uv run python -m pytest -q
```

## `unit/`

Focused checks on one module or thin FastAPI `TestClient` slices. Prefer these
for everyday development.

| Area | Examples |
| --- | --- |
| Core gate / audit | `test_core_gate.py`, `test_audit.py`, `test_audit_eds.py` |
| REST contract | `test_c2_rest_contract.py`, `test_c2_server.py` |
| Scenarios / kinematics | `test_scenarios.py`, `test_kinematics.py`, `test_lead_pursuit.py` |
| Ingress adapters | `test_dual_sar.py`, `test_glint_client.py`, `test_sentinel_imagery.py`, `test_open_feed.py`, `test_sar_candidate_event.py` |
| Verify UI / interlocks | `test_verify_ui.py`, `test_tri_service_interlocks.py` (#116) |
| Deploy / pitch helpers | `test_cloudflare_deploy.py`, `test_demo_pitch_run.py`, `test_litellm_*` |

## `integration/`

End-to-end paths that exercise propose → approve → inbox → ack, Verify UI HTML,
or live-optional adapters. Many still use in-process `TestClient` (no
`sdth-c2-server` required); a few expect optional upstreams and fall back to
fixtures.

| File | Covers |
| --- | --- |
| `test_picture_to_tasking.py` | Picture→Tasking script closed loop |
| `test_verify_ui_e2e.py` | `/verify` Screen 1/2 HTML handshake |
| `test_trojan_mothership_e2e.py` | `s1_trojan` amber, Navy silo, guardrail (#116) |
| `test_s2_c2_e2e.py` / `test_osint_s2_e2e.py` | S2 OSINT contradiction path |
| `test_lead_pursuit_e2e.py` | Lead-pursuit POI on proposals |
| `test_eds_audit_e2e.py` / `test_tamper_detection_e2e.py` | OCSF / EDS integrity |
| `test_archview_contract_e2e.py` | ARCHVIEW type / REST contract |
| `test_zero_internet_resilience.py` | Fixture fail-safe when upstream is down |

Issue #116 CUI subset:

```text
uv run python -m pytest \
  tests/unit/test_tri_service_interlocks.py \
  tests/integration/test_trojan_mothership_e2e.py \
  tests/unit/test_verify_ui.py \
  -q
```

Live curl / `picture_to_tasking` against a running Core: see
[`docs/verify-e2e.md`](../docs/verify-e2e.md).

## `fixtures/`

Vendored ingress snapshots so CI and Core-only checkouts stay deterministic
**without** sibling repos or live SIA/GLINT/Indago.

| File | Role |
| --- | --- |
| `s1_trojan_scenario.jsonl` | SensorSim canonical stream copy for `s1_trojan` |
| `s2_osint_swarm_scenario.jsonl` | SensorSim Pillar-1 stream copy for `S2_osint_swarm` |
| `s1_trojan_pois.json` | Jurong CNI + military POI buffers |
| `s1_trojan_site_origins.json` | Site origins for polar reverse-geocode |
| `sentinel_run_cv_sg_strait.json` / `sentinel_chip.jpg` | SIA Singapore Strait fixture |
| `candidate_event_assumed.json` | Assumed CandidateEvent / GLINT-style macro (Nexus S3 Dual-SAR; not SensorSim) |
| `open_ais_datagovsg.json` / `open_air_traffic.json` | Open-feed ladder fixtures |

### Why `s1_trojan_*` lives here

**Source of truth** for Trojan mothership data is **SensorSim**
([`SDTH-Sensor-Simulation`](https://github.com/marun6207/SDTH-Sensor-Simulation),
local sibling `SDTH-Sensor-Simulation/exports/` or `marun-sensor-simulation/exports/`). Loader preference
(`app/adapters/sensorsim_canonical.py`):

1. `SENSORSIM_EXPORT_DIR` (or `MARUN_EXPORT_DIR`)
2. Sibling `../SDTH-Sensor-Simulation/exports/` (or `../marun-sensor-simulation/exports/`)
3. These fixtures (CI / offline fail-safe)

After regenerating SensorSim exports, refresh the three `s1_trojan_*` files here so
CI stays in sync.

Aliases used in [docs/verify-e2e.md](../docs/verify-e2e.md): **Nexus** =
`sdth-nexus-c2`, **SensorSim** = `SDTH-Sensor-Simulation`, **SIA** =
`Sentinel-Imagery-Analysis`, **Indago** = `indago` (optional DuckDB AIS).
