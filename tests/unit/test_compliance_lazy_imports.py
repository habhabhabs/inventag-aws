"""Start-up does not load the unused compliance modules; every public name
still imports; ComplianceManager.close() stops its monitor thread.

Child processes: each probe needs a clean interpreter (about 1 s each).
"""

import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]


def child(code_or_args, *, importtime=False):
    argv = [sys.executable]
    if importtime:
        argv += ["-X", "importtime"]
    argv += code_or_args
    return subprocess.run(
        argv, cwd=REPO, capture_output=True, text=True, timeout=120, check=False
    )


def test_version_command_loads_neither_psutil_nor_the_production_monitor():
    done = child(["-m", "inventag", "--version"], importtime=True)
    assert done.returncode == 0, done.stderr[-300:]
    imported = [line.split("|")[-1].strip() for line in done.stderr.splitlines()]
    assert "psutil" not in imported
    assert not [m for m in imported if "production_monitor" in m]
    assert not [m for m in imported if "compliance_manager" in m]
    assert not [m for m in imported if "security_validator" in m]


def test_importing_the_package_keeps_the_checker():
    done = child(
        [
            "-c",
            "import sys, inventag\n"
            "from inventag.compliance import ComprehensiveTagComplianceChecker\n"
            "assert 'inventag.compliance.checker' in sys.modules\n"
            "assert 'psutil' not in sys.modules\n"
            "print('ok')",
        ]
    )
    assert done.returncode == 0 and "ok" in done.stdout, done.stderr[-300:]


def test_every_public_name_still_imports_from_the_package():
    import inventag.compliance as compliance

    assert len(compliance.__all__) == 17
    for name in compliance.__all__:
        namespace = {}
        exec(f"from inventag.compliance import {name} as value", namespace)
        assert namespace["value"] is getattr(compliance, name)
    assert set(compliance.__all__) <= set(dir(compliance))


def test_an_unknown_name_is_still_an_attribute_error():
    import inventag.compliance as compliance

    with pytest.raises(AttributeError):
        compliance.NoSuchThing  # noqa: B018
    with pytest.raises(ImportError):
        exec("from inventag.compliance import NoSuchThing")


def test_names_the_repo_and_examples_import_resolve():
    done = child(
        [
            "-c",
            "from inventag.compliance import (ComplianceManager, "
            "ComplianceConfiguration, ComplianceStandard, "
            "ComprehensiveTagComplianceChecker)\nprint('ok')",
        ]
    )
    assert "ok" in done.stdout, done.stderr[-300:]


def monitor_threads():
    return [
        t
        for t in threading.enumerate()
        if getattr(getattr(t, "_target", None), "__name__", "")
        == "_performance_monitoring_loop"
    ]


def make_manager():
    from inventag.compliance import (
        ComplianceConfiguration,
        ComplianceManager,
        ComplianceStandard,
    )

    config = ComplianceConfiguration(
        compliance_standard=ComplianceStandard.GENERAL,
        enable_production_monitoring=True,
        enable_cloudtrail_integration=False,
    )
    with patch("boto3.Session"), patch("psutil.cpu_percent"):
        return ComplianceManager(config)


def test_close_stops_the_monitor_thread_and_can_be_called_twice():
    manager = make_manager()
    thread = manager.production_monitor.monitoring_thread
    assert thread.is_alive()
    manager.close()
    assert not thread.is_alive()
    assert manager.production_monitor.monitoring_active is False
    assert monitor_threads() == []
    manager.close()  # idempotent


def test_close_without_a_monitor_does_nothing():
    from inventag.compliance import (
        ComplianceConfiguration,
        ComplianceManager,
        ComplianceStandard,
    )

    config = ComplianceConfiguration(
        compliance_standard=ComplianceStandard.GENERAL,
        enable_production_monitoring=False,
    )
    with patch("boto3.Session"):
        ComplianceManager(config).close()


def test_no_monitor_thread_is_left_after_the_manager_tests():
    """Runs the manager's own tests without the suite's stray-thread fixture."""
    code = (
        "import sys, threading, unittest\n"
        "from tests.unit.test_compliance_manager import TestComplianceManager\n"
        "suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestComplianceManager)\n"
        "result = unittest.TextTestRunner(stream=open('/dev/null', 'w')).run(suite)\n"
        "left = [t.name for t in threading.enumerate() if "
        "'_performance_monitoring_loop' in t.name]\n"
        "print('RAN', result.testsRun, 'FAILED', len(result.failures + result.errors),"
        " 'LEFT', len(left))\n"
    )
    done = child(["-c", code])
    assert "FAILED 0 LEFT 0" in done.stdout, done.stdout + done.stderr[-300:]
