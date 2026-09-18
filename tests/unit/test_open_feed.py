"""Optional open-feed ingress adapters (issue #16)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app import c2_server
from app.adapters.open_feed import (
    load_open_ais_fixture,
    load_open_air_fixture,
    open_feed_to_observations,
    open_feeds_from_env,
    parse_open_feed_selection,
)
from app.c2_server import app
from app.scenarios.base import get_scenario
from core.ontology import SpatialEntityGraph
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


def test_parse_open_feed_selection() -> None:
    assert parse_open_feed_selection(None) == []
    assert parse_open_feed_selection("") == []
    assert parse_open_feed_selection("off") == []
    assert parse_open_feed_selection("ais") == ["ais"]
    assert parse_open_feed_selection("air,ais") == ["air", "ais"]
    assert parse_open_feed_selection("all") == ["ais", "air"]
    assert parse_open_feed_selection("data.gov.sg") == ["ais"]
    with pytest.raises(ValueError, match="Unknown open feed"):
        parse_open_feed_selection("satellite")


def test_open_feeds_from_env_default_off() -> None:
    assert open_feeds_from_env({}) == []
    assert open_feeds_from_env({"OPEN_FEED": "ais,air"}) == ["ais", "air"]


def test_ais_fixture_maps_via_southbound() -> None:
    payload = load_open_ais_fixture()
    obs = open_feed_to_observations("ais", payload)
    assert len(obs) == 2
    assert {o.modality for o in obs} == {"ais"}
    assert obs[0].source_id.startswith("OPEN_AIS_")
    assert obs[0].attributes.get("ingress") == "open_feed"
    assert obs[0].attributes.get("feed_source") == "data.gov.sg/demo"
    assert obs[0].latitude == pytest.approx(1.264)
    assert len(obs[0].raw_digest) == 64


def test_air_fixture_maps_via_southbound() -> None:
    payload = load_open_air_fixture()
    obs = open_feed_to_observations("air", payload)
    assert len(obs) == 2
    assert {o.modality for o in obs} == {"adsb"}
    assert obs[0].source_id.startswith("OPEN_AIR_")
    assert obs[0].attributes.get("callsign") == "SIA123"
    assert obs[0].attributes.get("altitude_m") == 3500.0


def test_invalid_ais_payload_raises() -> None:
    with pytest.raises(ValueError, match="vessels"):
        open_feed_to_observations("ais", {"vessels": []})


def test_synthetic_s1_unchanged_without_open_feed() -> None:
    scenario = get_scenario("S1")
    events = scenario.build_events()
    assert all(e.get("ingress") != "open_feed" for e in events)


def test_open_feed_additive_to_scenario_graph() -> None:
    scenario = get_scenario("S2")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    from app.adapters.southbound_sensor import normalize_sensor_event

    base = [normalize_sensor_event(e) for e in scenario.build_events()]
    graph.ingest_many(base)
    before = len(graph.observations)
    extra = open_feed_to_observations("ais", use_fixture=True)
    graph.ingest_many(extra)
    assert len(graph.observations) == before + len(extra)
    modalities = {o.modality for o in graph.observations}
    assert "ais" in modalities


def test_ingress_open_feed_fixture_ais(client: TestClient) -> None:
    resp = client.post(
        "/api/ingress/open-feed",
        json={"feed": "ais", "use_fixture": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["count"] == 2
    assert body["feeds"] == ["ais"]
    assert body["items"][0]["observation"]["modality"] == "ais"

    state = client.get("/api/ontology/state")
    modalities = {o["modality"] for o in state.json()["observations"]}
    assert "ais" in modalities


def test_ingress_open_feed_all_fixtures(client: TestClient) -> None:
    resp = client.post(
        "/api/ingress/open-feed",
        json={"feed": "all", "use_fixture": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 4
    assert body["feeds"] == ["ais", "air"]
    modalities = {item["observation"]["modality"] for item in body["items"]}
    assert modalities == {"ais", "adsb"}


def test_ingress_open_feed_payload(client: TestClient) -> None:
    payload = load_open_air_fixture()
    payload = {
        **payload,
        "aircraft": [
            {
                **payload["aircraft"][0],
                "icao24": "deadbe",
                "callsign": "TEST1",
            }
        ],
    }
    resp = client.post(
        "/api/ingress/open-feed",
        json={"feed": "air", "payload": payload},
    )
    assert resp.status_code == 200
    assert resp.json()["items"][0]["observation"]["observation_id"] == "open-air-deadbe"


def test_ingress_open_feed_requires_payload_or_fixture(client: TestClient) -> None:
    resp = client.post("/api/ingress/open-feed", json={"feed": "ais"})
    assert resp.status_code == 400


def test_ingress_open_feed_rejects_unknown_feed(client: TestClient) -> None:
    resp = client.post(
        "/api/ingress/open-feed",
        json={"feed": "satellite", "use_fixture": True},
    )
    assert resp.status_code == 400
