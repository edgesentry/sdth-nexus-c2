"""Scenario registry."""

from __future__ import annotations

from app.scenarios.base import Scenario
from app.scenarios.s1_sea_approach_spoof import SPEC as S1
from app.scenarios.s1_trojan_mothership import SPEC as S1_TROJAN
from app.scenarios.s2_air_corridor_attritable import SPEC as S2
from app.scenarios.s3_lane_spof_break import SPEC as S3

SCENARIOS: dict[str, Scenario] = {
    # Standardized S{N}_{subcategory} primary keys
    "S1_trojan": S1_TROJAN,
    "S1_ais_spoof": S1,
    "S2_osint_swarm": S2,
    "S3_sar_ais": S3,
    # Backward-compatible aliases
    "s1_trojan": S1_TROJAN,
    "S1": S1,
    "S2": S2,
    "S3": S3,
}

PRIMARY_SCENARIOS: dict[str, Scenario] = {
    "S1_trojan": S1_TROJAN,
    "S3_sar_ais": S3,
    "S1_ais_spoof": S1,
    "S2_osint_swarm": S2,
}
