"""The error contract: every stop says what is wrong, what to do, where to read.

Plan section (b) of the CLI clean-up. Every path that ends the process with a
non-zero code prints, on stderr and before any AWS call:

    inventag: error: <subject>: <what happened>.
      Why: <reason>.                 (optional)
      Instead: <a command or value that works>
      More: <URL of a docs page that exists>

The five rule tests are at the top; one case per row of the plan's table a2
follows. Moto only, no network. A row marked ``xfail(strict=True)`` names what
is missing: ``M-n`` is a change in ``inventag/cli/main.py`` (the lead's file).
"""

import ast
import importlib
import json
import logging
import os
import re
import sys
from pathlib import Path

import boto3
import pytest
import yaml
from moto import mock_aws

from inventag.security import redaction
from inventag.security.read_only_guard import uninstall_global_guard

cli_main = importlib.import_module("inventag.cli.main")

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BASE_URL = "https://habhabhabs.github.io/inventag-aws/docs/"

# row id -> why it does not pass yet. Rows that need a change in main.py name
# the M-number of the plan (cli-cleanup-plan.md, work package WP-E).
PENDING = {
    "d3-unknown-option": "D3 unknown option: M-3 (parser class)",
    "d3-dev-script-option": "D3 dev-script option: M-3 (parser class)",
    "d3-stray-word": "D3 stray word: M-3 (parser class)",
    "argparse-invalid-choice": "other argparse errors: M-3 (parser class)",
    "argparse-bad-int": "other argparse errors: M-3 (parser class)",
    "d4-audit-output": "D4 --audit-output: M-6 (early path checks)",
    "d5-log-file": "D5 --log-file: M-6 (warn and continue)",
    "d6-output-directory": "D6 --output-directory: M-6 (early path checks)",
    "d7-region": "D7 unknown region: M-8 (region check)",
    "d7-region-typo": "D7 unknown region: M-8 (region check)",
    "d8-unexpected": "D8 catch-all: M-4 (errors.fail)",
    "d9-role-name": "D9 role name: M-5 (usage collection)",
    "b10-word-template": "B10 implied --create-word: M-7",
    "b12-excel-template": "B12 implied --create-excel: M-7",
    "b14-risk-threshold": "B14 implied analysis: M-7",
    "b05-kms-implied": "B05 implied aws:kms: M-7",
    "b05-kms-conflict": "B05 explicit AES256 conflict: M-7",
    "c01-prefix": "C01 prefix without bucket: M-4",
    "c02-bucket": "C02 bucket name: M-4",
    "c03-max-concurrent": "C03 range, exit 2 (O2): M-4",
    "c04-timeout": "C04 range, exit 2 (O2): M-4",
    "c05-credential-timeout": "C05 range, exit 2 (O2): M-4",
    "c06-resume-age": "C06 range, exit 2 (O2): M-4",
    "c07-tags-json": "C07 account tags, exit 2 (O2): M-4",
    "c08-tags-object": "C08 account tags, exit 2 (O2): M-4",
    "b03-accounts-both": "B03 conflict: M-4",
    "b04-arn-with-file": "B04 conflict: M-4",
    "b06-resume-no-state": "B06 conflict: M-4",
    "b07-bad-role-name": "B07 role: M-4",
    "b08-bad-role-arn": "B08 role: M-4",
    "b16-google-both": "B16 Google: M-4",
    "b17-google-title": "B17 Google: M-4",
    "b13-validate-templates": "B13 validate-templates alone: M-4",
    "f13-validate-operations": "F13 invalid operation: M-4",
    "c09-accounts-key": "C09-C14 accounts file key error: M-4",
    "c15-accounts-unknown-key": "C15 unknown key warning in a run: M-4",
    "c13-duplicate-accounts": "C13 duplicate account scanned once: M-4",
    "c16-tag-mappings": "C16-C18 tag mappings: M-4",
    "c19-service-descriptions": "C19 service descriptions: M-4",
    "d01-bom-config": "D01 bom-config exit 1 with contract: M-4",
    "f01-all-accounts-failed": "F01 cause per account: M-4",
    "f09-empty": "F09 hint --fail-if-empty: M-4",
    "ctrl-c": "Ctrl-C exit 130 and message: WP-F2 (cancellation), M-14",
    "no-bare-sys-exit-main": "main.py sys.exit calls: M-4",
}
# @@WPE-PENDING@@


def row(row_id):
    """The strict xfail mark for a row that is not there yet (none if done)."""
    if row_id in PENDING:
        return pytest.mark.xfail(strict=True, reason=PENDING[row_id])
    return pytest.mark.skipif(False, reason="")


def case(row_id, *args):
    marks = [] if row_id not in PENDING else [row(row_id)]
    return pytest.param(row_id, *args, id=row_id, marks=marks)


# ----------------------------------------------------------------- harness
@pytest.fixture
def aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-for-moto-only")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-creds"))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="a-bucket")
        yield tmp_path
    uninstall_global_guard()
    redaction.uninstall_log_record_redaction()
    redaction.clear_registered_secrets()
    for name in ("inventag", "botocore", "boto3", "urllib3", "s3transfer"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def run_cli(*args):
    old_argv = sys.argv
    sys.argv = ["inventag", *args]
    try:
        cli_main.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv


@pytest.fixture
def aws_calls(monkeypatch):
    """Count every AWS API call made through botocore."""
    import botocore.client

    calls = []
    original = botocore.client.BaseClient._make_api_call

    def counting(self, operation_name, api_params):
        calls.append(operation_name)
        return original(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", counting)
    return calls


MORE_RE = re.compile(r"^  More: (\S+)$", re.MULTILINE)


def assert_contract(stderr, first_line_has=None):
    """The four-line form: first line, Instead, More with a docs URL."""
    lines = stderr.splitlines()
    firsts = [i for i, line in enumerate(lines) if line.startswith("inventag: error:")]
    assert firsts, f"no 'inventag: error:' line in:\n{stderr}"
    if first_line_has:
        assert first_line_has in lines[firsts[0]], stderr
    for start, end in zip(firsts, firsts[1:] + [len(lines)]):
        block = lines[start:end]
        assert any(line.startswith("  Instead: ") for line in block), stderr
        assert any(MORE_RE.match(line) for line in block), stderr
        assert "Traceback" not in "\n".join(block)
    for url in MORE_RE.findall(stderr):
        assert url.startswith(BASE_URL) or url.startswith(
            "https://docs.aws.amazon.com/"
        ), url


def write(path, text):
    Path(path).write_text(text)
    return str(path)


def accounts_json(tmp_path, accounts, name="accounts.json"):
    return write(tmp_path / name, json.dumps({"accounts": accounts}))


GOOD = {"account_id": "123456789012", "regions": ["us-east-1"]}
REGION = ["--account-regions", "us-east-1"]


# The table. Each row: id, argv (a function of tmp_path), exit code, text that
# must be in the first error line (or in stderr), and an optional setup.
def _file(tmp_path):
    return write(tmp_path / "plain.txt", "x")


def _a_file_parent(tmp_path, tail):
    return f"{_file(tmp_path)}/{tail}"


CASES = [
    case(
        "a1-compliance-standard",
        lambda t: ["--compliance-standard", "soc2"],
        2,
        "--compliance-standard soc2: InvenTag does not assess or certify SOC 2",
    ),
    case(
        "a1-disable-production-safety",
        lambda t: ["--disable-production-safety"],
        2,
        "--disable-production-safety: InvenTag has no mode without the read-only",
    ),
    case(
        "d3-unknown-option",
        lambda t: ["--create-exel"],
        2,
        "unrecognized argument '--create-exel'",
    ),
    case(
        "d3-dev-script-option",
        lambda t: ["--formats", "excel"],
        2,
        "'--formats' is an option of scripts/development/cicd_bom_generation.py",
    ),
    case(
        "d3-stray-word",
        lambda t: ["bogusword"],
        2,
        "unrecognized argument 'bogusword'",
    ),
    case(
        "argparse-invalid-choice",
        lambda t: ["--s3-encryption", "weird"],
        2,
        "--s3-encryption: invalid choice: 'weird'",
    ),
    case(
        "argparse-bad-int",
        lambda t: ["--state-retention-days", "abc"],
        2,
        "--state-retention-days",
    ),
    case(
        "d4-audit-output",
        lambda t: ["--audit-output", _a_file_parent(t, "a.json"), *REGION],
        2,
        "--audit-output: cannot write",
    ),
    case(
        "d6-output-directory",
        lambda t: ["--output-directory", _a_file_parent(t, "x"), *REGION],
        2,
        "--output-directory: cannot create",
    ),
    case(
        "d7-region",
        lambda t: ["--create-excel", "--account-regions", "mars-north-1"],
        2,
        "--account-regions: unknown region 'mars-north-1'",
    ),
    case(
        "d9-role-name",
        lambda t: [*REGION, "--cross-account-role", "MyRole"],
        2,
        "--cross-account-role: 'MyRole' is a role name; it needs --accounts-file",
    ),
    case(
        "b05-kms-conflict",
        lambda t: [
            "--s3-bucket",
            "a-bucket",
            "--s3-kms-key-id",
            "alias/k",
            "--s3-encryption",
            "AES256",
        ],
        2,
        "--s3-kms-key-id: needs --s3-encryption aws:kms, but you gave "
        "--s3-encryption AES256",
    ),
    case(
        "c01-prefix",
        lambda t: ["--s3-key-prefix", "p/", *REGION],
        2,
        "--s3-key-prefix: has no effect without --s3-bucket",
    ),
    case(
        "c02-bucket",
        lambda t: ["--s3-bucket", "Bad_Bucket", *REGION],
        2,
        "--s3-bucket: 'Bad_Bucket' is not a valid bucket name",
    ),
    case(
        "c03-max-concurrent",
        lambda t: [*REGION, "--max-concurrent-accounts", "0"],
        2,
        "--max-concurrent-accounts: must be 1 or more (got 0)",
    ),
    case(
        "c04-timeout",
        lambda t: [*REGION, "--account-processing-timeout", "59"],
        2,
        "--account-processing-timeout: must be 60 or more seconds (got 59)",
    ),
    case(
        "c05-credential-timeout",
        lambda t: [*REGION, "--credential-timeout", "0"],
        2,
        "--credential-timeout: must be 1 or more seconds (got 0)",
    ),
    case(
        "c06-resume-age",
        lambda t: [*REGION, "--resume-max-age-hours", "200"],
        2,
        "--resume-max-age-hours: must be above 0 and at most 168 hours (got 200)",
    ),
    case(
        "c07-tags-json",
        lambda t: [*REGION, "--account-tags", "{not json"],
        2,
        "--account-tags: is not valid JSON",
    ),
    case(
        "c08-tags-object",
        lambda t: [*REGION, "--account-tags", "[1, 2]"],
        2,
        "--account-tags: must be a JSON object",
    ),
    case(
        "b03-accounts-both",
        lambda t: [
            "--accounts-file",
            accounts_json(t, [GOOD]),
            "--accounts-prompt",
        ],
        2,
        "--accounts-file and --accounts-prompt: give one of them, not both",
    ),
    case(
        "b04-arn-with-file",
        lambda t: [
            "--accounts-file",
            accounts_json(t, [GOOD]),
            "--cross-account-role",
            "arn:aws:iam::123456789012:role/R",
        ],
        2,
        "--cross-account-role: a full role ARN names one account",
    ),
    case(
        "b06-resume-no-state",
        lambda t: ["--resume", "--disable-state-management", *REGION],
        2,
        "--resume: needs state management",
    ),
    case(
        "b07-bad-role-name",
        lambda t: [*REGION, "--cross-account-role", "bad role name!"],
        2,
        "--cross-account-role:",
    ),
    case(
        "b08-bad-role-arn",
        lambda t: [*REGION, "--cross-account-role", "arn:aws:iam::cross:role/X"],
        2,
        "--cross-account-role:",
    ),
    case(
        "b16-google-both",
        lambda t: [
            "--create-google-sheets",
            "--google-credentials",
            _file(t),
            "--google-oauth-client",
            _file(t),
            *REGION,
        ],
        2,
        "give --google-credentials or --google-oauth-client, not both",
    ),
    case(
        "b17-google-title",
        lambda t: ["--google-title", "x", *REGION],
        2,
        "--google-title: needs --create-google-sheets or --create-google-docs",
    ),
    case(
        "b13-validate-templates",
        lambda t: ["--validate-templates"],
        2,
        "--validate-templates:",
    ),
    case(
        "g16-old-layout",
        lambda t: [
            "--template",
            write(t / "bad.yaml", "format: word\nsections:\n  - title: x\n"),
            *REGION,
        ],
        1,
        "bad.yaml: looks like a report layout file",
    ),
    case(
        "e01-unknown-template",
        lambda t: ["--template", "nonexist", *REGION],
        1,
        "no template named 'nonexist'",
    ),
    case(
        "c09-accounts-key",
        lambda t: [
            "--validate-config-only",
            "--accounts-file",
            accounts_json(t, [{"account_name": "x"}]),
        ],
        1,
        "accounts.json:",
    ),
    case(
        "c16-tag-mappings",
        lambda t: [
            "--validate-config-only",
            "--tag-mappings",
            write(t / "tags.yaml", "tag_mappings:\n  - tag: Owner\n"),
        ],
        1,
        "tags.yaml:2: tag_mappings[0].name: is required",
    ),
    case(
        "c19-service-descriptions",
        lambda t: [
            "--validate-config-only",
            "--service-descriptions",
            write(t / "desc.yaml", "ec2: 5\n"),
        ],
        1,
        "desc.yaml:1: ec2: must be a mapping",
    ),
    case(
        "d01-bom-config",
        lambda t: [
            "--bom-config",
            write(t / "bom.yaml", "enable_cost_analysis: 'yes'\n"),
            "--create-excel",
            *REGION,
        ],
        1,
        "enable_cost_analysis must be true or false",
    ),
]


@pytest.mark.parametrize("row_id, make_argv, code, first_line_has", CASES)
def test_every_exit_path_has_a_next_step(
    row_id, make_argv, code, first_line_has, aws, capsys
):
    """Each stop: exit code, `inventag: error:` first, Instead, More."""
    argv = make_argv(aws)
    assert run_cli(*argv) == code
    err = capsys.readouterr().err
    assert_contract(err)
    assert first_line_has in err, err
    if code == 2:
        assert not (aws / "bom_output").exists()


def _scan_files():
    cli = sorted((ROOT / "inventag" / "cli").glob("*.py"))
    return cli + [
        ROOT / "inventag" / "templating" / "cli.py",
        ROOT / "inventag" / "templating" / "runner.py",
    ]


def _usage_error_calls():
    for path in _scan_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "UsageError"
            ):
                yield path, node


@row("unit-ast-usage-errors")
def test_every_usage_error_in_the_code_has_an_instead_and_a_more():
    """UsageError(subject, what, instead, more): both of the last two are given."""
    found = list(_usage_error_calls())
    assert len(found) >= 30, "the scan finds the UsageErrors of the CLI"
    for path, node in found:
        keywords = {k.arg for k in node.keywords}
        given = len(node.args) + len(keywords & {"instead", "more"})
        assert (
            len(node.args) >= 4 or {"instead", "more"} <= keywords or given >= 4
        ), f"{path.name}:{node.lineno}: UsageError without 'instead' and 'more'"


ALLOWED_EXIT_FUNCTIONS = {"fail", "fail_all", "finish"}


def _bare_exits(path):
    """(line, text) of a sys.exit with a non-zero or unknown code, or .error()."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []

    def visit(node, function):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if isinstance(node, ast.Call):
            func = node.func
            is_exit = (
                isinstance(func, ast.Attribute)
                and func.attr == "exit"
                and isinstance(func.value, ast.Name)
                and func.value.id == "sys"
            )
            if is_exit and function not in ALLOWED_EXIT_FUNCTIONS:
                arg = node.args[0] if node.args else None
                zero = isinstance(arg, ast.Constant) and arg.value in (0, None)
                if not (arg is None or zero):
                    out.append((node.lineno, ast.unparse(node)))
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "error"
                and isinstance(func.value, ast.Name)
                and func.value.id in ("parser", "self")
                and path.name != "errors.py"
            ):
                out.append((node.lineno, ast.unparse(node)))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, None)
    return out


@row("no-bare-sys-exit")
def test_no_bare_sys_exit_outside_main():
    """Only errors.fail/fail_all/finish end the process with a non-zero code."""
    bad = {
        f"{p.name}:{line}": text
        for p in _scan_files()
        if p.name != "main.py"
        for line, text in _bare_exits(p)
    }
    assert not bad, bad


@row("no-bare-sys-exit-main")
def test_no_bare_sys_exit_in_main():
    """The same rule for inventag/cli/main.py (the lead's file)."""
    assert _bare_exits(ROOT / "inventag" / "cli" / "main.py") == []


def _slugs(path):
    """Heading anchors of a docs page: github-slugger style and {#pinned}."""
    slugs = set()
    in_code = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        match = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if not match:
            continue
        title = match.group(1)
        pinned = re.search(r"\{#([A-Za-z0-9_-]+)\}\s*$", title) or re.search(
            r"\{/\*\s*#([A-Za-z0-9_-]+)\s*\*/\}\s*$", title
        )
        if pinned:
            slugs.add(pinned.group(1))
            continue
        title = title.replace("`", "")
        slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        slugs.add(re.sub(r"\s", "-", slug))
    return slugs


def check_docs_url(url):
    assert url.startswith(BASE_URL), url
    target, _, anchor = url[len(BASE_URL) :].partition("#")
    page = next(
        (
            DOCS / f"{target}{suffix}"
            for suffix in (".md", ".mdx", "/index.md", "/index.mdx")
            if (DOCS / f"{target}{suffix}").is_file()
        ),
        None,
    )
    assert page is not None, f"{url}: no page under docs/"
    if anchor:
        assert anchor in _slugs(page), f"{url}: no heading '{anchor}' in {page.name}"


DOC_PATH = re.compile(
    r"^(reference|guides|templates|getting-started|examples|security|development)"
    r"/[a-z0-9-]+(#[a-z0-9-]+)?$"
)


def _doc_paths_in_code():
    for path in _scan_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if DOC_PATH.match(node.value):
                    yield path.name, node.lineno, node.value
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for url in re.findall(re.escape(BASE_URL) + r"\S+", node.value):
                    yield path.name, node.lineno, url[len(BASE_URL) :].rstrip(".,)")


@row("unit-more-urls-exist")
def test_more_urls_exist():
    """Every docs page (and heading) a message points at exists under docs/."""
    paths = list(_doc_paths_in_code())
    assert len(paths) >= 20
    for name, line, more in paths:
        try:
            check_docs_url(BASE_URL + more)
        except AssertionError as error:
            raise AssertionError(f"{name}:{line}: {error}") from None


@row("unit-more-urls-exist")
def test_more_urls_built_from_page_constants_exist():
    """``f"{RUN_A_SCAN}#heading"``: the constant's page has that heading."""
    from inventag.cli import usage_checks

    found = 0
    for path in _scan_files():
        for name, anchor in re.findall(
            r'f"\{([A-Z_]+)\}(#[a-z0-9-]+)', path.read_text(encoding="utf-8")
        ):
            page = getattr(usage_checks, name)
            check_docs_url(BASE_URL + page + anchor)
            found += 1
    assert found >= 4


PLAIN = [pytest.param(*p.values, id=p.id) for p in CASES]
LOOSE = [
    pytest.param(
        *p.values,
        id=p.id,
        marks=[pytest.mark.xfail(strict=False, reason=PENDING[p.values[0]])]
        if p.values[0] in PENDING
        else [],
    )
    for p in CASES
]


@pytest.mark.parametrize("row_id, make_argv, code, first_line_has", PLAIN)
def test_more_urls_of_every_case_exist(
    row_id, make_argv, code, first_line_has, aws, capsys
):
    run_cli(*make_argv(aws))
    err = capsys.readouterr().err
    for url in MORE_RE.findall(err):
        if url.startswith(BASE_URL):
            check_docs_url(url)


@pytest.mark.parametrize("row_id, make_argv, code, first_line_has", LOOSE)
def test_usage_errors_make_no_aws_call(
    row_id, make_argv, code, first_line_has, aws, aws_calls, capsys
):
    """A stop caused by the options happens before any AWS call."""
    if code != 2 and not row_id.startswith(("g16", "e01", "c09", "c16", "c19")):
        pytest.skip("only usage errors and file checks")
    run_cli(*make_argv(aws))
    assert aws_calls == []


SECRET = "SECRETVALUE-Zq81xTn"


def test_messages_have_no_secret(aws, capsys):
    """A secret in an accounts file, an option or the environment is not echoed."""
    redaction.register_secret(SECRET)
    path = write(
        aws / "secret-accounts.yaml",
        "accounts:\n"
        f"  - account_name: x\n    secret_access_key: {SECRET}\n    access_key_id: AKIAAAAAAAAAAAAAAAAA\n"
        f"  - account_id: '1'\n    secret_acces_key: {SECRET}\n",
    )
    os.chmod(path, 0o600)
    cases = [
        ["--validate-config-only", "--accounts-file", path],
        [f"--secret-access-key={SECRET}"],
        ["--account-tags", f'{{"k": {SECRET}']
        + REGION,
        ["--s3-bucket", f"Bad_{SECRET}", *REGION],
        ["--google-share-with", SECRET],
    ]
    for argv in cases:
        run_cli(*argv)
    out = capsys.readouterr()
    assert SECRET not in out.err and SECRET not in out.out
    assert SECRET not in out.err.replace("Bad_", "")


# ------------------------------------------------- rows that are not errors
def _write_template(tmp_path, fmt):
    from inventag.reporting.report_template import default_template_text

    suffix = ".yaml" if fmt == "word" else ".json"
    return write(tmp_path / f"{fmt}{suffix}", default_template_text(fmt))


IMPLIED = [
    case(
        "b10-word-template",
        lambda t: ["--word-template", _write_template(t, "word"), *REGION],
        "inventag: note: --word-template implies --create-word.",
        "*.docx",
    ),
    case(
        "b12-excel-template",
        lambda t: ["--excel-template", _write_template(t, "excel"), *REGION],
        "inventag: note: --excel-template implies --create-excel.",
        "*.xlsx",
    ),
    case(
        "b14-risk-threshold",
        lambda t: [
            "--risk-threshold",
            "CRITICAL",
            "--create-excel",
            "--no-billing-validation",
            *REGION,
        ],
        "inventag: note: --risk-threshold implies --enable-security-analysis.",
        "*.xlsx",
    ),
    case(
        "b05-kms-implied",
        lambda t: [
            "--s3-bucket",
            "a-bucket",
            "--s3-kms-key-id",
            "alias/aws/s3",
            "--create-excel",
            "--no-billing-validation",
            *REGION,
        ],
        "inventag: note: --s3-kms-key-id implies --s3-encryption aws:kms.",
        "*.xlsx",
    ),
]


@pytest.mark.parametrize("row_id, make_argv, note_text, produced", IMPLIED)
def test_implied_options_work_and_say_so(
    row_id, make_argv, note_text, produced, aws, capsys
):
    assert run_cli(*make_argv(aws)) == 0
    err = capsys.readouterr().err
    assert note_text in err
    assert list((aws / "bom_output").glob(produced))


@row("d5-log-file")
def test_unwritable_log_file_warns_and_the_run_goes_on(aws, capsys):
    code = run_cli(
        "--log-file",
        _a_file_parent(aws, "x.log"),
        "--create-excel",
        "--no-billing-validation",
        *REGION,
    )
    err = capsys.readouterr().err
    assert code == 0
    assert "inventag: warning: --log-file: cannot open" in err
    assert "Instead:" in err and "More:" in err
    assert "Traceback" not in err


@row("d8-unexpected")
def test_unexpected_error_names_the_type_and_hides_the_traceback(
    aws, capsys, monkeypatch
):
    def boom(args, logger):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "_run", boom)
    assert run_cli(*REGION) == 1
    err = capsys.readouterr().err
    assert_contract(err, "unexpected RuntimeError: boom")
    assert "--debug" in err and "Traceback" not in err


@row("f13-validate-operations")
def test_validate_operations_invalid_form_exits_1_with_a_next_step(aws, capsys):
    assert run_cli("--validate-operations", "notvalid") == 1
    captured = capsys.readouterr()
    assert "INVALID  notvalid: expected service:Operation" in captured.out
    assert_contract(captured.err)


@row("f01-all-accounts-failed")
def test_all_accounts_failed_prints_the_cause_of_each(aws, capsys):
    broken = {
        "account_id": "999999999999",
        "profile_name": "no-such-profile",
        "regions": ["us-east-1"],
    }
    path = accounts_json(aws, [broken])
    assert run_cli("--accounts-file", path, "--create-excel") == 1
    err = capsys.readouterr().err
    assert_contract(err, "999999999999:")
    assert "profile" in err and "aws configure list-profiles" in err


@row("f09-empty")
def test_empty_result_names_fail_if_empty(aws, capsys, monkeypatch):
    from inventag.core import cloud_bom_generator as cbg

    monkeypatch.setattr(
        cbg.CloudBOMGenerator,
        "_discover_account_resources_inner",
        lambda self, account_id, context: [],
    )
    path = accounts_json(aws, [GOOD])
    assert run_cli("--accounts-file", path, "--create-excel") == 0
    assert "Use --fail-if-empty to make this an error." in capsys.readouterr().err


@row("ctrl-c")
def test_ctrl_c_exits_130_with_a_message(aws, capsys, monkeypatch):
    from inventag.core import cloud_bom_generator as cbg

    def interrupt(self, *args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cbg.CloudBOMGenerator, "generate_comprehensive_bom", interrupt)
    assert run_cli("--create-excel", *REGION) == 130
    assert "inventag: interrupted" in capsys.readouterr().err


@row("c13-duplicate-accounts")
def test_duplicate_account_ids_are_scanned_once(aws):
    path = accounts_json(aws, [GOOD, {**GOOD, "account_name": "again"}])
    args = cli_main.create_parser().parse_args(["--accounts-file", path])
    config = cli_main.create_multi_account_config(args)
    assert [a.account_id for a in config.accounts] == ["123456789012"]


@row("c15-accounts-unknown-key")
def test_unknown_account_key_warns_with_a_suggestion_in_a_run(aws, caplog):
    path = accounts_json(aws, [{"acount_id": "123456789012"}, GOOD])
    caplog.set_level(logging.WARNING)
    assert run_cli("--validate-config-only", "--accounts-file", path) == 1
    assert "did you mean 'account_id'" in caplog.text


# ----------------------------------------------------- templates subcommand
@row("g09-bad-name")
def test_templates_init_rejects_a_bad_template_name(aws, capsys):
    from inventag.templating.cli import main as templates_main

    assert templates_main(["init", "standard-bom", "-o", "Bad_Name.yaml"]) == 2
    err = capsys.readouterr().err
    assert_contract(err, "'Bad_Name' is not a valid template name")
    assert not (aws / "Bad_Name.yaml").exists()


@row("g06-default-output")
def test_templates_init_without_output_writes_a_default_file(aws, capsys):
    """G06: no --output means ./my-<name>.yaml in the current folder."""
    from inventag.templating.cli import main as templates_main

    assert templates_main(["init", "standard-bom"]) == 0
    assert (aws / "my-standard-bom.yaml").is_file()
    assert templates_main(["validate", "my-standard-bom.yaml"]) == 0


@row("g-templates-errors")
def test_templates_subcommand_errors_follow_the_contract(aws, capsys):
    from inventag.templating.cli import main as templates_main

    out = write(aws / "x.txt", "")
    for argv in (
        ["init", "standard-bom", "-o", out],
        ["show", "nonexist"],
        ["validate", "nonexist.yaml"],
    ):
        assert templates_main(argv) in (1, 2)
        assert_contract(capsys.readouterr().err)
    with pytest.raises(SystemExit) as stop:
        templates_main(["bogus"])
    assert stop.value.code == 2
    assert_contract(capsys.readouterr().err, "COMMAND: invalid choice")


# ------------------------------------------------------ the pieces, by unit
@row("unit-usage-error")
def test_usage_error_needs_instead_and_more_and_renders_the_four_lines():
    from inventag.cli.errors import DOCS_BASE, UsageError

    with pytest.raises(ValueError):
        UsageError("--x", "is wrong", "", "reference/cli")
    with pytest.raises(ValueError):
        UsageError("--x", "is wrong", "do this", "")
    error = UsageError(
        "--x", "is wrong", "do this", "reference/cli#output", why="because"
    )
    assert error.render().splitlines() == [
        "inventag: error: --x: is wrong.",
        "  Why: because.".replace("because.", "because"),
        "  Instead: do this",
        f"  More: {DOCS_BASE}reference/cli#output",
    ]
    assert error.code == 2
    # str() has no prefix, so f"inventag: error: {error}" renders the same
    assert f"inventag: error: {error}" == error.render()


@row("unit-fail")
def test_fail_prints_to_stderr_and_exits_with_the_code(capsys):
    from inventag.cli.errors import UsageError, fail, fail_all

    with pytest.raises(SystemExit) as stop:
        fail(UsageError("a", "b", "c", "reference/cli"))
    assert stop.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("inventag: error: a: b.")
    with pytest.raises(SystemExit) as stop:
        fail_all(
            [
                UsageError("a", "b", "c", "reference/cli", code=1),
                UsageError("d", "e", "f", "reference/cli"),
            ]
        )
    assert stop.value.code == 2  # 2 beats 1


def _demo_parser():
    from inventag.cli.errors import InventagArgumentParser

    parser = InventagArgumentParser(prog="inventag")
    parser.add_argument("--create-excel", action="store_true")
    parser.add_argument("--create-word", action="store_true")
    parser.add_argument("--hidden", help="==SUPPRESS==")
    parser.add_argument("--count", type=int)
    parser.add_argument("--mode", choices=["a", "b"])
    return parser


@row("unit-parser")
def test_parser_hints_for_typos_dev_script_options_and_stray_words(capsys):
    parser = _demo_parser()
    cases = {
        "--create-exel": "did you mean --create-excel?",
        "--formats": "scripts/development/cicd_bom_generation.py",
        "--slack-webhook=https://hooks.example/SECRET": "guides/run-in-ci",
    }
    for token, expected in cases.items():
        with pytest.raises(SystemExit) as stop:
            parser.parse_args([token])
        assert stop.value.code == 2
        err = capsys.readouterr().err
        assert_contract(err)
        assert expected in err
        assert "SECRET" not in err and "hooks.example" not in err
    with pytest.raises(SystemExit):
        parser.parse_args(["--count", "abc"])
    assert_contract(capsys.readouterr().err, "--count: invalid int value: 'abc'")
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "z"])
    err = capsys.readouterr().err
    assert_contract(err, "--mode: invalid choice: 'z'")
    assert "use one of:" in err


@row("unit-parser-tombstones")
def test_parser_answers_removed_options_from_the_tombstone_table(
    capsys, monkeypatch
):
    from inventag.cli import errors

    monkeypatch.setattr(
        errors,
        "_removed_flags",
        lambda: {"--enforce-read-only": ("2.0.0", "delete it from your command.")},
    )
    with pytest.raises(SystemExit) as stop:
        _demo_parser().parse_args(["--enforce-read-only"])
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert_contract(err, "--enforce-read-only was removed in 2.0.0")


@row("unit-safety-table")
@pytest.mark.parametrize(
    "value, label",
    [
        ("soc2", "SOC 2"),
        ("pci", "PCI DSS"),
        ("hipaa", "HIPAA"),
        ("gdpr", "GDPR"),
        ("pdpa", "PDPA"),
        ("general", None),
    ],
)
def test_compliance_standard_message_gives_a_command_that_works(value, label, aws):
    from types import SimpleNamespace

    from inventag.cli import safety
    from inventag.templating.cli import main as templates_main

    (error,) = safety.unimplemented_flag_errors(
        SimpleNamespace(compliance_standard=value, disable_production_safety=False)
    )
    text = error.render()
    assert_contract(text)
    assert error.code == 2
    if label:
        assert f"does not assess or certify {label} compliance" in text
    else:
        assert "does not assess compliance" in text
    lowered = text.lower()
    for word in ("compliant with", "certified", "audit-ready", "ensures"):
        assert word not in lowered
    template = re.search(r"--template (\S+) --create-excel", text).group(1)
    assert templates_main(["show", template]) == 0


@row("unit-implied")
def test_apply_implied_sets_the_options_a_given_option_needs(capsys):
    from inventag.cli import usage_checks

    parser = cli_main.create_parser()
    args = parser.parse_args(
        ["--word-template", "w.yaml", "--risk-threshold", "HIGH"]
    )
    notes = usage_checks.apply_implied(args)
    assert args.create_word and args.enable_security_analysis
    assert args.s3_encryption == "AES256"
    assert notes == [
        "--word-template implies --create-word.",
        "--risk-threshold implies --enable-security-analysis.",
    ]
    assert capsys.readouterr().err.count("inventag: note:") == 2
    args = parser.parse_args(["--s3-kms-key-id", "alias/k"])
    usage_checks.apply_implied(args)
    assert args.s3_encryption == "aws:kms"


@row("unit-regions")
def test_region_check_names_the_typo_and_the_fix():
    from types import SimpleNamespace

    from inventag.cli import usage_checks

    ok = SimpleNamespace(account_regions="us-east-1, eu-west-1,")
    assert usage_checks.region_errors(ok) == []
    (error,) = usage_checks.region_errors(SimpleNamespace(account_regions="us-esat-1"))
    assert "unknown region 'us-esat-1'" in error.render()
    assert "did you mean 'us-east-1'?" in error.render()
    assert "aws ec2 describe-regions" in error.render()
    assert error.code == 2


@row("unit-paths")
def test_path_problem_finds_a_folder_that_cannot_be_made(tmp_path):
    from inventag.cli import usage_checks

    plain = tmp_path / "plain.txt"
    plain.write_text("x")
    assert usage_checks.path_problem(str(tmp_path / "new" / "deep")) is None
    assert "is not a folder" in usage_checks.path_problem(str(plain / "x"))
    assert usage_checks.log_file_problem(str(plain / "x.log")) is not None
    assert usage_checks.log_file_problem(str(tmp_path / "ok.log")) is None
    assert not (tmp_path / "new").exists(), "checking creates nothing"


@row("unit-locator")
def test_locator_names_file_line_and_key(tmp_path):
    from inventag.reporting.settings_loader import Locator, did_you_mean

    path = write(tmp_path / "a.yaml", "accounts:\n  - account_id: '1'\n  - acount_id: '2'\n")
    loc = Locator(path)
    assert loc.message(("accounts", 1, "acount_id"), "unknown key") == (
        f"{path}:3: accounts[1].acount_id: unknown key"
    )
    assert loc.line(("accounts", 1, "account_id")) == 3  # missing key: its item
    assert did_you_mean("acount_id", ["account_id", "regions"]) == (
        "; did you mean 'account_id'?"
    )
    assert did_you_mean("zzzz", ["account_id"]) == ""
    json_path = write(tmp_path / "a.json", '{\n  "accounts": [\n    {"x": 1}\n  ]\n}')
    assert Locator(json_path).line(("accounts", 0, "x")) == 3


@row("unit-config-validator")
def test_accounts_file_problems_have_file_line_key_and_suggestions(tmp_path):
    from inventag.cli.config_validator import ConfigValidator

    path = write(
        tmp_path / "accounts.yaml",
        "accounts:\n"
        "  - account_name: no id\n"
        "  - account_id: '2'\n"
        "    acount_name: typo\n"
        "    regions: [mars-north-1]\n"
        "  - account_id: '2'\n"
        "settings:\n"
        "  max_concurrent_account: 3\n",
    )
    result = ConfigValidator().validate_accounts_file(path)
    assert not result.is_valid
    assert result.errors == [f"{path}:2: accounts[0].account_id: is required"]
    warnings = "\n".join(result.warnings)
    assert f"{path}:4: accounts[1].acount_name: unknown key; did you mean 'account_name'?" in warnings
    assert f"{path}:5: accounts[1].regions[0]: unknown region 'mars-north-1'" in warnings
    assert f"{path}:6: accounts[2].account_id: '2' is already listed at accounts[1]" in warnings
    assert "settings.max_concurrent_account: unknown key; did you mean 'max_concurrent_accounts'?" in warnings


@row("unit-config-validator-flags")
def test_cli_value_problems_are_usage_errors_with_the_range():
    from types import SimpleNamespace

    from inventag.cli.config_validator import ConfigValidator

    args = cli_main.create_parser().parse_args(
        ["--max-concurrent-accounts", "0", "--s3-key-prefix", "p/"]
    )
    result = ConfigValidator().validate_cli_arguments(args)
    assert not result.is_valid
    assert [e.code for e in result.usage_errors] == [2, 2]
    assert result.errors[0].startswith("--s3-key-prefix: has no effect")
    for error in result.usage_errors:
        assert_contract(error.render())
    assert isinstance(SimpleNamespace(), object)


@row("unit-old-layout")
def test_old_layout_file_is_named_once(tmp_path):
    from inventag.templating.errors import TemplateError
    from inventag.templating.runner import detect_old_layout, load_templates

    path = write(tmp_path / "old.yaml", "format: word\nsections:\n  - title: x\n")
    with pytest.raises(TemplateError) as stop:
        load_templates([path])
    assert len(stop.value.issues) == 1
    assert "looks like a report layout file" in str(stop.value)
    other = TemplateError("something else")
    assert detect_old_layout(other) is other
