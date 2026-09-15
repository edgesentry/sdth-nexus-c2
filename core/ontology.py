"""Spatio-temporal entity graph for multi-source tracks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Iterable

from core.schema import Observation, sha256_hex


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * r * asin(sqrt(a))


@dataclass
class Track:
    track_id: str
    latitude: float
    longitude: float
    speed_mps: float
    confidence: float
    source_ids: list[str] = field(default_factory=list)
    modalities: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    digests: list[str] = field(default_factory=list)
    updated_at: datetime | None = None
    attributes: dict = field(default_factory=dict)

    def fused_digest(self) -> str:
        joined = "|".join(sorted(self.digests))
        return sha256_hex(joined)


class SpatialEntityGraph:
    """In-memory dynamic ontology: observations correlated into tracks."""

    def __init__(self, associate_radius_m: float = 2_000.0) -> None:
        self.associate_radius_m = associate_radius_m
        self.observations: list[Observation] = []
        self.tracks: dict[str, Track] = {}

    def ingest(self, observation: Observation) -> Track:
        observation.ensure_digest()
        self.observations.append(observation)

        track_id = observation.entity_hint or observation.source_id
        existing = self._find_nearby(observation.latitude, observation.longitude, track_id)
        if existing is None:
            track = Track(
                track_id=track_id,
                latitude=observation.latitude,
                longitude=observation.longitude,
                speed_mps=observation.speed_mps,
                confidence=observation.confidence,
                source_ids=[observation.source_id],
                modalities=[observation.modality],
                observation_ids=[observation.observation_id],
                digests=[observation.raw_digest],
                updated_at=observation.observed_at,
                attributes=dict(observation.attributes),
            )
            self.tracks[track.track_id] = track
            return track

        if observation.source_id not in existing.source_ids:
            existing.source_ids.append(observation.source_id)
        if observation.modality not in existing.modalities:
            existing.modalities.append(observation.modality)
        existing.observation_ids.append(observation.observation_id)
        existing.digests.append(observation.raw_digest)
        # Prefer higher-confidence kinematics for the fused track state
        if observation.confidence >= existing.confidence:
            existing.latitude = observation.latitude
            existing.longitude = observation.longitude
            existing.speed_mps = observation.speed_mps
            existing.confidence = observation.confidence
        existing.updated_at = observation.observed_at
        existing.attributes.update(observation.attributes)
        return existing

    def ingest_many(self, observations: Iterable[Observation]) -> list[Track]:
        return [self.ingest(o) for o in observations]

    def get_track(self, track_id: str) -> Track | None:
        return self.tracks.get(track_id)

    def all_tracks(self) -> list[Track]:
        return list(self.tracks.values())

    def observations_for(self, track_id: str) -> list[Observation]:
        return [o for o in self.observations if (o.entity_hint or o.source_id) == track_id
                or o.observation_id in (self.tracks.get(track_id).observation_ids if track_id in self.tracks else [])]

    def _find_nearby(self, lat: float, lon: float, preferred_id: str) -> Track | None:
        if preferred_id in self.tracks:
            return self.tracks[preferred_id]
        best: Track | None = None
        best_d = float("inf")
        for track in self.tracks.values():
            d = haversine_m(lat, lon, track.latitude, track.longitude)
            if d <= self.associate_radius_m and d < best_d:
                best = track
                best_d = d
        return best
