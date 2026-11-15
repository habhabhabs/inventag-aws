"""Other files written by inventag/core/ are written whole or not at all (A-14).

The credential file (``CredentialManager.create_secure_credential_file``),
the CI/CD artifacts and the Prometheus metrics file (``CICDIntegration``)
were opened in place in v1.2.1: a failing write left a partial file and
replaced the older one. Now each goes through ``reporting.safe_save``.
"""

import json
import os
import stat

import pytest

from inventag.core import cicd_integration as cicd
from inventag.core import credential_manager as cm
from inventag.core.cloud_bom_generator import AccountCredentials


def leftovers(folder):
    return [p.name for p in folder.iterdir() if p.name.endswith(".tmp")]


@pytest.mark.parametrize("name", ["accounts.json", "accounts.yaml"])
def test_a_failing_credential_file_write_keeps_the_old_file(
    tmp_path, monkeypatch, name
):
    target = tmp_path / name
    target.write_text("OLD")

    def broken(data, f, **kwargs):
        f.write("accounts: [")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cm.json, "dump", broken)
    monkeypatch.setattr(cm.yaml, "safe_dump", broken)
    manager = cm.CredentialManager()
    with pytest.raises(OSError):
        manager.create_secure_credential_file(
            [AccountCredentials(account_id="111111111111")],
            str(target),
            encrypt=False,
        )
    assert target.read_text() == "OLD"
    assert leftovers(tmp_path) == []


def test_a_credential_file_keeps_its_name_and_mode(tmp_path):
    target = tmp_path / "accounts.json"
    cm.CredentialManager().create_secure_credential_file(
        [AccountCredentials(account_id="111111111111")], str(target), encrypt=False
    )
    assert json.loads(target.read_text())["accounts"]
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert leftovers(tmp_path) == []


def test_a_failing_cicd_artifact_write_keeps_the_old_file(tmp_path, monkeypatch):
    integration = cicd.CICDIntegration(artifacts_dir=str(tmp_path))
    target = tmp_path / "pipeline_summary.json"
    target.write_text("OLD")

    def broken(data, f, **kwargs):
        f.write('{"run": ')
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cicd.json, "dump", broken)
    integration._generate_cicd_artifacts({}, cicd.CICDResult(success=True))
    assert target.read_text() == "OLD"
    assert leftovers(tmp_path) == []


def test_a_failing_metrics_file_move_keeps_the_old_file(tmp_path, monkeypatch):
    integration = cicd.CICDIntegration(artifacts_dir=str(tmp_path))
    target = tmp_path / "inventag_metrics.prom"
    target.write_text("OLD")

    def broken_replace(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", broken_replace)
    integration._export_prometheus_metrics(cicd.PrometheusMetrics(total_resources=3))
    assert target.read_text() == "OLD"
    assert leftovers(tmp_path) == []


def test_a_metrics_file_keeps_its_name_and_mode(tmp_path):
    integration = cicd.CICDIntegration(artifacts_dir=str(tmp_path))
    integration._export_prometheus_metrics(cicd.PrometheusMetrics(total_resources=3))
    target = tmp_path / "inventag_metrics.prom"
    assert "inventag_total_resources 3" in target.read_text()
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
