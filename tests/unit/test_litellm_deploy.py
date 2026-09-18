"""LiteLLM deploy artifacts for Pitch-2 live interpret (issue #32)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LITELLM_DIR = ROOT / "deploy" / "litellm"


def test_litellm_config_has_openai_anthropic_gemini_fireworks() -> None:
    cfg = yaml.safe_load((LITELLM_DIR / "config.yaml").read_text())
    assert isinstance(cfg, dict)
    names = {item["model_name"] for item in cfg["model_list"]}
    assert "gemini-3.8-flash" in names
    assert "gpt-4o-mini" in names
    assert "claude-haiku" in names
    assert "fireworks-glm" in names
    assert "nexus-interpreter" in names
    assert "ollama-llama3" in names
    assert "vllm-local" in names

    by_name = {item["model_name"]: item["litellm_params"]["model"] for item in cfg["model_list"]}
    assert by_name["gemini-3.8-flash"] == "gemini/gemini-3.8-flash"
    assert by_name["gpt-4o-mini"].startswith("openai/")
    assert by_name["claude-haiku"].startswith("anthropic/")
    assert by_name["fireworks-glm"] == "fireworks_ai/glm-5p2"
    assert by_name["nexus-interpreter"] == "gemini/gemini-3.8-flash"

    fallbacks = cfg["router_settings"]["fallbacks"]
    nexus_fb = next(fb["nexus-interpreter"] for fb in fallbacks if "nexus-interpreter" in fb)
    assert "gpt-4o-mini" in nexus_fb
    assert "claude-haiku" in nexus_fb
    assert "fireworks-glm" in nexus_fb
    assert "ollama-llama3" in nexus_fb
    # Live tests pin gemini-3.8-flash — do not silently swap vendors on that alias.
    assert "gemini-3.8-flash" not in nexus_fb
    assert cfg["litellm_settings"]["drop_params"] is True
    assert cfg["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"


def test_litellm_env_example_documents_vendor_keys() -> None:
    assert not (LITELLM_DIR / "docker-compose.yml").exists()
    env_example = (LITELLM_DIR / ".env.example").read_text()
    assert "GEMINI_API_KEY" in env_example
    assert "OPENAI_API_KEY" in env_example
    assert "ANTHROPIC_API_KEY" in env_example
    assert "FIREWORKS_AI_API_KEY" in env_example
    assert "host.docker.internal" not in env_example
    root_env = (ROOT / ".env.example").read_text()
    assert "LLM_BASE_URL=http://127.0.0.1:4000/v1" in root_env
    assert "LLM_MODEL=gemini-3.8-flash" in root_env


def test_pyproject_has_optional_litellm_group() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "[dependency-groups]" in pyproject
    assert "litellm = [" in pyproject or "litellm = [" in pyproject
    assert "litellm[proxy]" in pyproject
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    assert "litellm.md" in mkdocs
    assert "LiteLLM:" in mkdocs or "- LiteLLM:" in mkdocs
