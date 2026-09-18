"""LiteLLM deploy artifacts for Pitch-2 live interpret (issue #32)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LITELLM_DIR = ROOT / "deploy" / "litellm"


def test_litellm_config_has_cloud_and_local_backends() -> None:
    cfg = yaml.safe_load((LITELLM_DIR / "config.yaml").read_text())
    assert isinstance(cfg, dict)
    names = {item["model_name"] for item in cfg["model_list"]}
    assert "nexus-interpreter" in names
    assert "gpt-4o-mini" in names
    assert "ollama-llama3" in names
    assert "vllm-local" in names
    backends = {item["litellm_params"]["model"] for item in cfg["model_list"]}
    assert any(m.startswith("openai/") for m in backends)
    assert any(m.startswith("ollama/") for m in backends)
    fallbacks = cfg["router_settings"]["fallbacks"]
    assert any("nexus-interpreter" in fb for fb in fallbacks)
    assert cfg["litellm_settings"]["drop_params"] is True
    assert cfg["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"


def test_litellm_compose_is_stateless_proxy() -> None:
    compose = yaml.safe_load((LITELLM_DIR / "docker-compose.yml").read_text())
    services = compose["services"]
    assert "litellm" in services
    assert "db" not in services
    assert "postgres" not in services
    litellm = services["litellm"]
    assert "4000:4000" in str(litellm["ports"]) or "4000" in str(litellm["ports"])
    assert "--config" in litellm["command"]
    env_example = (LITELLM_DIR / ".env.example").read_text()
    assert "LITELLM_MASTER_KEY" in env_example
    assert "OPENAI_API_KEY" in env_example
    root_env = (ROOT / ".env.example").read_text()
    assert "LLM_BASE_URL=http://127.0.0.1:4000/v1" in root_env
    assert "LLM_MODEL=nexus-interpreter" in root_env
