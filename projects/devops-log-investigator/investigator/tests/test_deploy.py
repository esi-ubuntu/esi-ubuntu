from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy" / "compose.yaml"


def load_compose():
    assert COMPOSE.is_file(), "deploy/compose.yaml is missing"
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_has_exactly_four_runtime_services():
    services = load_compose()["services"]
    assert set(services) == {"open-webui", "ollama", "elastic-mcp", "investigator"}


def test_only_open_webui_publishes_a_host_port():
    services = load_compose()["services"]
    assert services["open-webui"].get("ports")
    for name in ("ollama", "elastic-mcp", "investigator"):
        assert not services[name].get("ports"), f"{name} must not publish host ports"


def test_runtime_never_pulls_builds_or_uses_latest():
    for name, service in load_compose()["services"].items():
        assert service.get("pull_policy") == "never", name
        assert "build" not in service, name
        image = service["image"]
        assert ":latest" not in image and not image.endswith(":main"), image


def test_no_service_mounts_docker_socket():
    for name, service in load_compose()["services"].items():
        volumes = service.get("volumes") or []
        assert all("docker.sock" not in str(volume) for volume in volumes), name


def test_open_webui_is_offline_and_can_only_see_investigator_as_model_backend():
    service = load_compose()["services"]["open-webui"]
    env = service["environment"]
    assert str(env["OFFLINE_MODE"]).lower() == "true"
    assert str(env["ENABLE_OLLAMA_API"]).lower() == "false"
    assert env["OPENAI_API_BASE_URL"] == "http://investigator:8080/v1"
    assert env["OPENAI_API_KEY"] == "${INVESTIGATOR_INTERNAL_TOKEN}"


def test_investigator_and_mcp_have_hardening_controls():
    services = load_compose()["services"]
    for name in ("investigator", "elastic-mcp"):
        service = services[name]
        assert "ALL" in (service.get("cap_drop") or [])
        assert "no-new-privileges:true" in (service.get("security_opt") or [])
        assert service.get("read_only") is True
