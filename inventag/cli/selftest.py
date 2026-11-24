"""``inventag selftest``: check offline that this copy of InvenTag works.

It is the smoke test of every packaged format (wheel, executable, ``.deb``,
``.rpm``, Homebrew formula). It makes no AWS call, opens no network
connection, needs no credentials and writes nothing outside a temporary
directory that it removes.

The command is a word before the flags, like ``inventag templates``
(``inventag selftest``); :func:`main` takes the arguments after that word and
returns the exit code: 0 when every check passed, 1 when one failed.
"""

from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
import sys
import tempfile
from typing import Callable, List, Optional, Sequence, TextIO, Tuple

from ..exit_codes import EXIT_ERROR, EXIT_OK

# Import names of the packages in requirements.txt (a test keeps the two in step).
RUNTIME_PACKAGES = (
    "boto3",
    "botocore",
    "yaml",
    "openpyxl",
    "docx",
    "colorama",
    "psutil",
    "keyring",
    "cryptography.fernet",
    "requests",
    "jsonschema",
    "urllib3",
    "certifi",
    "idna",
    "lxml.etree",
    "jmespath",
)

# Operations the read-only guard must allow and must refuse.
_GUARD_ALLOWED = (("ec2", "DescribeInstances"), ("s3", "ListBuckets"))
_GUARD_REFUSED = (("ec2", "RunInstances"), ("s3", "DeleteObject"))

NAME_WIDTH = 17
FAILURE_ADVICE = (
    "Install inventag-aws again (or download the release again) and run "
    "'inventag selftest' again. If it fails again, report the output above at "
    "https://github.com/habhabhabs/inventag-aws/issues."
)


class CheckFailed(Exception):
    """A check found a problem. The message is shown as it is: keep it short,
    true, and free of paths, credentials and library error text."""


def _names(items: Sequence[str], limit: int = 3) -> str:
    shown = ", ".join(items[:limit])
    if len(items) > limit:
        shown += f" and {len(items) - limit} more"
    return shown


# ------------------------------------------------------------------- checks


def check_python() -> str:
    from .._python_version import MIN_PYTHON

    version = ".".join(str(part) for part in sys.version_info[:3])
    if tuple(sys.version_info[:2]) < MIN_PYTHON:
        raise CheckFailed(
            f"Python {version} is older than the {MIN_PYTHON[0]}.{MIN_PYTHON[1]} "
            "that InvenTag needs"
        )
    return f"Python {version}"


def check_packages() -> str:
    missing = []
    for name in RUNTIME_PACKAGES:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    if missing:
        raise CheckFailed(f"cannot import {_names(missing, 5)}")
    return f"{len(RUNTIME_PACKAGES)} packages import"


def check_ca_bundle() -> str:
    import certifi

    if not os.path.isfile(certifi.where()):
        raise CheckFailed("the CA certificate bundle of certifi is missing")
    return "the CA certificate bundle is present"


def check_modules() -> str:
    import inventag

    failed: List[str] = []
    found: List[str] = []

    def not_importable(name: str) -> None:
        failed.append(name)

    for info in pkgutil.walk_packages(
        inventag.__path__, "inventag.", onerror=not_importable
    ):
        if info.name == "inventag.__main__":
            continue
        found.append(info.name)
        try:
            importlib.import_module(info.name)
        except Exception:
            failed.append(info.name)
    if failed:
        raise CheckFailed(f"cannot import {_names(sorted(set(failed)))}")
    if not found:
        raise CheckFailed("no InvenTag modules were found")
    return f"{len(found)} InvenTag modules import"


def check_templates() -> str:
    from ..templating import registry

    reg = registry.TemplateRegistry(
        [registry.SearchDir("builtin", registry.BUILTIN_DIR)]
    )
    entries = reg.entries()
    if not entries:
        raise CheckFailed("no built-in templates were found")
    broken = []
    for entry in entries:
        try:
            reg.resolve(entry.name)
        except Exception:
            broken.append(entry.name)
    if broken:
        raise CheckFailed(f"built-in templates do not load: {_names(broken)}")
    return f"{len(entries)} built-in templates load"


def check_botocore() -> str:
    import botocore.session

    session = botocore.session.get_session()
    services = session.get_available_services()
    missing = [s for s in ("ec2", "s3", "sts") if s not in services]
    if len(services) < 100 or missing:
        raise CheckFailed("the AWS service list of botocore is incomplete")
    try:
        session.get_service_model("s3")
    except Exception:
        raise CheckFailed("the AWS service models of botocore cannot be read")
    return f"{len(services)} AWS services in the botocore data files"


def check_read_only_guard() -> str:
    import botocore.session

    from ..security import read_only_guard as guard_module

    guard = guard_module.ReadOnlyGuard()
    for service, operation in _GUARD_ALLOWED:
        if not guard.evaluate(service, operation)[0]:
            raise CheckFailed(f"the guard refuses {service}:{operation}")
    for service, operation in _GUARD_REFUSED:
        if guard.evaluate(service, operation)[0]:
            raise CheckFailed(f"the guard allows {service}:{operation}")

    # Install it like a scan does, look at a client made while it is on, and
    # put the process back as it was. No call is made on the client.
    if guard_module.get_installed_guard() is None:
        guard_module.install_global_guard(guard)
        try:
            client = botocore.session.get_session().create_client(
                "ec2",
                region_name="us-east-1",
                aws_access_key_id="selftest",
                aws_secret_access_key="selftest",
            )
            allowed, _ = guard_module.check_client_call(client, "run_instances")
            if allowed:
                raise CheckFailed("the guard is installed but allows ec2:RunInstances")
        finally:
            guard_module.uninstall_global_guard()
    return "installs, allows reads and refuses writes"


def check_reports() -> str:
    import openpyxl
    from docx import Document

    from ..reporting.bom_processor import BOMData
    from ..reporting.document_generator import DocumentConfig
    from ..reporting.excel_builder import ExcelWorkbookBuilder
    from ..reporting.word_builder import WordDocumentBuilder

    bom = BOMData(
        resources=[
            {
                "service": "EC2",
                "type": "Instance",
                "id": "i-selftest",
                "name": "selftest",
                "region": "us-east-1",
                "tags": {"Name": "selftest"},
            }
        ],
        generation_metadata={"generated_by": "inventag selftest"},
    )
    config = DocumentConfig()
    with tempfile.TemporaryDirectory(prefix="inventag-selftest-") as folder:
        excel_path = os.path.join(folder, "selftest.xlsx")
        word_path = os.path.join(folder, "selftest.docx")
        for label, builder, path in (
            ("Excel", ExcelWorkbookBuilder(config), excel_path),
            ("Word", WordDocumentBuilder(config), word_path),
        ):
            result = builder.generate_document(bom, path)
            if not result.success or not os.path.isfile(path):
                kind = (result.error_message or "error").split(":")[0]
                raise CheckFailed(f"the {label} file could not be written ({kind})")
        try:
            sheets = openpyxl.load_workbook(excel_path).sheetnames
            paragraphs = Document(word_path).paragraphs
        except Exception:
            raise CheckFailed("a file that was just written cannot be read back")
        if not sheets or not paragraphs:
            raise CheckFailed("a file that was just written is empty")
    return "Excel and Word files written, read back and removed"


CHECKS: List[Tuple[str, Callable[[], str]]] = [
    ("python", check_python),
    ("packages", check_packages),
    ("ca-bundle", check_ca_bundle),
    ("modules", check_modules),
    ("templates", check_templates),
    ("botocore", check_botocore),
    ("read-only-guard", check_read_only_guard),
    ("reports", check_reports),
]


# ------------------------------------------------------------------ running


def version_line() -> str:
    from .._version import __version__

    return (
        f"inventag selftest v{__version__.lstrip('v')} on Python "
        f"{sys.version_info[0]}.{sys.version_info[1]}"
    )


def run_checks(
    checks: Sequence[Tuple[str, Callable[[], str]]], out: TextIO, err: TextIO
) -> int:
    """Run every check (one failing does not stop the others); return the exit code."""
    print(version_line(), file=out)
    failures = 0
    for name, check in checks:
        try:
            status, text = "ok", check()
        except CheckFailed as problem:
            status, text = "FAIL", str(problem)
        except Exception as problem:
            status, text = "FAIL", f"unexpected error ({type(problem).__name__})"
        if status == "FAIL":
            failures += 1
        print(f"{status:<5}{name:<{NAME_WIDTH}}{text}", file=out)
    if failures:
        print(
            f"selftest failed: {failures} of {len(checks)} checks failed. "
            f"{FAILURE_ADVICE}",
            file=err,
        )
        return EXIT_ERROR
    print(
        f"selftest passed: {len(checks)} checks. "
        "No AWS call was made and no network connection was opened.",
        file=out,
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="inventag selftest",
        description=(
            "Check that this copy of InvenTag works: packages, built-in\n"
            "templates, AWS service data, the read-only guard, and an Excel\n"
            "and a Word file written to a temporary folder and removed.\n"
            "\n"
            "It makes no AWS call, opens no network connection and needs no\n"
            "credentials. Exit code 0: every check passed. 1: a check failed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main(
    argv: Optional[Sequence[str]] = None,
    out: Optional[TextIO] = None,
    err: Optional[TextIO] = None,
) -> int:
    build_parser().parse_args(argv)
    return run_checks(
        CHECKS,
        out if out is not None else sys.stdout,
        err if err is not None else sys.stderr,
    )
