from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install-offline.sh"
BUILDER = ROOT / "scripts" / "build-bundle.sh"
REQUIRED_IMAGES = ("open-webui.tar", "ollama.tar", "elastic-mcp.tar", "investigator.tar")


def run_installer(bundle: Path, tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    docker_log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\nexit 0\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_DOCKER_LOG"] = str(docker_log)
    env["DLI_INSTALL_DIR"] = str(tmp_path / "install")
    result = subprocess.run(
        ["bash", str(INSTALLER), str(bundle)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=False,
    )
    return result, docker_log.read_text(encoding="utf-8") if docker_log.exists() else ""


def make_bundle(tmp_path: Path, *, valid_checksums: bool = True) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "images").mkdir(parents=True)
    (bundle / "models" / "ollama").mkdir(parents=True)
    (bundle / "runtime" / "deploy").mkdir(parents=True)
    (bundle / "runtime" / "config").mkdir(parents=True)
    (bundle / "runtime" / "scripts").mkdir(parents=True)
    (bundle / "scripts").mkdir(parents=True)
    for script in ("start.sh", "stop.sh", "health.sh", "install-offline.sh"):
        path = bundle / "scripts" / script
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    for name in REQUIRED_IMAGES:
        (bundle / "images" / name).write_bytes(f"fake-{name}".encode())
    (bundle / "models" / "ollama" / "manifest-marker").write_text("qwen3:8b-q4_K_M", encoding="utf-8")
    (bundle / "runtime" / "deploy" / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (bundle / "runtime" / ".env").write_text(
        "WEBUI_SECRET_KEY=x\nINVESTIGATOR_INTERNAL_TOKEN=y\nINVESTIGATOR_IMAGE_TAG=test\nES_URL=https://es.internal\nES_API_KEY=reader\n",
        encoding="utf-8",
    )
    files = sorted(path for path in bundle.rglob("*") if path.is_file())
    lines = []
    for path in files:
        rel = path.relative_to(bundle)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {rel.as_posix()}")
    if not valid_checksums:
        lines[0] = "0" * 64 + lines[0][64:]
    (bundle / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return bundle


def test_installer_aborts_when_required_image_is_missing(tmp_path):
    bundle = make_bundle(tmp_path)
    (bundle / "images" / "elastic-mcp.tar").unlink()
    result, docker_log = run_installer(bundle, tmp_path)
    assert result.returncode != 0
    assert "missing" in result.stdout.lower()
    assert docker_log == ""


def test_installer_aborts_on_checksum_mismatch_before_docker(tmp_path):
    bundle = make_bundle(tmp_path, valid_checksums=False)
    result, docker_log = run_installer(bundle, tmp_path)
    assert result.returncode != 0
    assert "checksum" in result.stdout.lower() or "failed" in result.stdout.lower()
    assert docker_log == ""


def test_installer_uses_loaded_images_and_never_pulls(tmp_path):
    bundle = make_bundle(tmp_path)
    result, docker_log = run_installer(bundle, tmp_path)
    assert result.returncode == 0, result.stdout
    assert docker_log.count("load -i") == 4
    assert " pull " not in f" {docker_log} "
    assert "compose" in docker_log
    assert "up -d --pull never" in docker_log


def test_builder_is_staging_only_and_exports_exact_four_images_plus_model():
    assert BUILDER.is_file(), "build-bundle.sh is missing"
    text = BUILDER.read_text(encoding="utf-8")
    for image in (
        "ghcr.io/open-webui/open-webui:0.11.4-slim",
        "ollama/ollama:0.34.4",
        "docker.elastic.co/mcp/elasticsearch:0.4.6",
        "devops-log-investigator/investigator:",
    ):
        assert image in text
    assert "docker save" in text
    assert "ollama pull" in text
    assert "SHA256SUMS" in text
    assert "chmod 0755" in text
