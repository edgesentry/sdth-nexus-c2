"""Scenario registry."""

from __future__ import annotations

from app.scenarios.base import Scenario
from app.scenarios.s1_sea_approach_spoof import SPEC as S1_AIS_SPOOF
from app.scenarios.s1_trojan_mothership import SPEC as S1_TROJAN
from app.scenarios.s2_air_corridor_attritable import SPEC as S2_OSINT_SWARM
from app.scenarios.s3_lane_spof_break import SPEC as S3_SAR_AIS
from app.scenarios.s4_fusion_disagreement import SPEC as S4_FUSION_DISAGREEMENT

SCENARIOS: dict[str, Scenario] = {
    "S1_trojan": S1_TROJAN,
    "S3_sar_ais": S3_SAR_AIS,
    "S1_ais_spoof": S1_AIS_SPOOF,
    "S2_osint_swarm": S2_OSINT_SWARM,
    "S4_fusion_disagreement": S4_FUSION_DISAGREEMENT,
}
