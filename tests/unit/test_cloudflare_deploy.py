"""Cloudflare Containers deploy artifacts for C2 Core (issue #18)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CF_DIR = ROOT / "deploy" / "cloudflare"


def test_dockerfile_binds_all_interfaces_and_health_port() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "python:3.13-slim" in dockerfile
    assert "C2_HOST=0.0.0.0" in dockerfile
    assert "C2_PORT=8080" in dockerfile
    assert "sdth-c2-server" in dockerfile
    assert "tests/fixtures" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert 'CMD ["sdth-c2-server"]' in dockerfile


def test_wrangler_singleton_container_config() -> None:
    cfg = json.loads(_strip_jsonc((CF_DIR / "wrangler.jsonc").read_text()))
    assert cfg["name"] == "sdth-c2-core"
    assert cfg["main"] == "src/index.ts"
    container = cfg["containers"][0]
    assert container["class_name"] == "C2Container"
    assert container["image"] == "../../Dockerfile"
    assert container["image_build_context"] == "../.."
    assert container["instance_type"] == "basic"
    assert container["max_instances"] == 1
    binding = cfg["durable_objects"]["bindings"][0]
    assert binding["name"] == "C2_CONTAINER"
    assert binding["class_name"] == "C2Container"
    assert cfg["migrations"][0]["new_sqlite_classes"] == ["C2Container"]
    assert "nodejs_compat" in cfg["compatibility_flags"]
    assert cfg["observability"]["enabled"] is True


def test_worker_routes_demo_singleton() -> None:
    src = (CF_DIR / "src" / "index.ts").read_text()
    assert 'getByName("demo")' in src
    assert "C2_CONTAINER" in src
    assert 'sleepAfter = "30m"' in src
    assert "audit_records" in src
    assert "/api/admin/audit/snapshot" in src
    assert "/health" in src
    assert "satisfies ExportedHandler<Env>" in src


def test_docs_and_mkdocs_cover_cloudflare_deploy() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    assert "deploy.md" in mkdocs
    readme = (ROOT / "README.md").read_text()
    assert "uv run sdth-c2-server" in readme
    assert "C2_BASE_URL" in readme
    assert "sdth-c2-core" in readme
    deploy = (ROOT / "docs" / "deploy.md").read_text()
    assert "wrangler dev" in deploy
    assert "npx wrangler deploy" in deploy
    assert 'getByName("demo")' in deploy or "getByName('demo')" in deploy
    assert "uv run sdth-c2-server" in deploy


def _strip_jsonc(raw: str) -> str:
    """Drop // line comments so stdlib json can parse wrangler.jsonc."""
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        cut = line.split(" //", 1)[0]
        lines.append(cut)
    return "\n".join(lines)
