"""Shared pytest fixtures."""

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def temp_workspace(tmp_path):
    """Per-test scratch directory (never the repository tree)."""
    return tmp_path


@pytest.fixture
def repo_root():
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _no_real_aws(monkeypatch):
    """Tests must never reach real AWS or the instance metadata service."""
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    for var in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-tests-only")
    monkeypatch.setenv(
        "AWS_DEFAULT_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
