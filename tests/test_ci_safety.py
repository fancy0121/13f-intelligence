"""The interim CI must not publish unvalidated production images."""
from pathlib import Path
import json
import ntpath
import re
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_readme_does_not_claim_full_delivery_before_human_gate():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "v0.1 已交付" not in readme
    assert "NOT_REVIEWED" in readme


def test_deployment_docs_do_not_claim_public_session_file_storage():
    for name in ("README_DEPLOY.md", "deploy/hostinger_vps.md"):
        document = (ROOT / name).read_text(encoding="utf-8")
        assert "服务端会话内存" in document
        assert "浏览器会话的临时目录" not in document
        assert "浏览器会话隔离的临时目录" not in document
        assert "只存放在容器临时目录" not in document
        assert "NOT_READY" in document


def test_historical_manifests_do_not_publish_local_machine_paths():
    manifest = json.loads((ROOT / "reports/research/research_manifest.json").read_text(encoding="utf-8"))
    assert not ntpath.isabs(manifest["db_snapshot"])
    document = (ROOT / "reports/research/FINAL_RESEARCH_MANIFEST.md").read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:[\\/]", document)


def test_ci_is_readonly_and_cannot_publish_before_real_gates():
    path = ROOT / ".github/workflows/build-image.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"contents": "read"}
    assert "pull_request" in workflow["on"]
    steps = [step for job in workflow["jobs"].values() for step in job["steps"]]
    assert any("pytest" in step.get("run", "") for step in steps)
    assert not any("build-push-action" in step.get("uses", "") for step in steps)
    assert not any("secrets." in str(step) for step in steps)


def test_docker_context_excludes_private_and_raw_data():
    entries = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    assert {".env", ".env.*", "data/raw", "data/private", "config/portfolio.csv"} <= entries


def test_public_ui_uses_explicit_theme_and_hides_internal_tracebacks():
    config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
    assert config["theme"]["base"] == "light"
    assert config["client"]["showErrorDetails"] == "none"
    assert config["browser"]["gatherUsageStats"] is False
