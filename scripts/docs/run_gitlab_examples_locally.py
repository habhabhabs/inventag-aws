#!/usr/bin/env python3
"""Run the GitLab CI/CD examples in docs/ locally with gitlab-ci-local and moto.

For every GitLab block that scripts/docs/check_ci_examples.py finds, this:
  - writes the block as .gitlab-ci.yml in a new git repository in a temp dir;
  - builds this checkout into a wheel once, installs the wheel into a private
    --target dir per block (your environment is untouched), and replaces each
    `pip install "inventag-aws..."` of the jobs with an echo: jobs of one stage
    run at the same time and must not build the package in one folder;
  - creates each `--template NAME` that is not built in with
    `inventag templates init ci-pipeline` (step 2 of the CI guides);
  - starts a moto server on 127.0.0.1, seeds an EC2 instance and an S3 bucket,
    and points the job at it with AWS_ENDPOINT_URL;
  - gives every id_tokens variable an unsigned dummy JWT (gitlab-ci-local
    leaves id_tokens variables unset), so the AWS SDK's web identity path
    (AWS_ROLE_ARN + AWS_WEB_IDENTITY_TOKEN_FILE) calls moto's
    sts:AssumeRoleWithWebIdentity;
  - runs the pipeline with `gitlab-ci-local --force-shell-executor` with the
    pipeline source the block's own rules ask for (merge_request_event, schedule,
    ...; push when none; override: --pipeline-source) and prints which one
    (image: is ignored; jobs run on this host).

It prints, in the per-block form of `check_ci_examples.py --report`, one line
per job: result, exit code, collected artifacts and the role moto issued.

What this does NOT prove (gitlab-ci-local ignores or emulates it): GitLab
signing the token, AWS checking its claims, retry, timeout, cache, expire_in,
the image, and artifact passing between jobs. gitlab-ci-local 4.77.1 also
treats any `allow_failure: {exit_codes: [...]}` job as allowed at pipeline
level, so this script reads each job's own PASS/WARN/FAIL line, not
gitlab-ci-local's exit status.

Project CI/CD variables (the examples keep AWS_ROLE_ARN, INVENTAG_REPORTS_BUCKET
and INVENTAG_KMS_KEY_ID out of the YAML) are passed through gitlab-ci-local's
project variables file; dummy defaults for those three names exist, and
`--variable NAME=VALUE` (repeatable) adds or overrides.

Needs: gitlab-ci-local (on PATH or --gitlab-ci-local), rsync, and moto with
its server extra (`pip install "moto[server]"`) in the Python running this.
Without them it prints SKIP and exits 0. Not wired into any workflow.

Exit status: 0 when every job ended as its YAML says it should (PASS for exit
0, WARN for an exit code listed in allow_failure, FAIL otherwise), the exit
code is one InvenTag documents for a pipeline (0, 3, 4, 5, 6) and declared
artifacts were collected; 1 otherwise.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_ci_examples  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
BUILTIN_TEMPLATES = REPO / "inventag" / "templating" / "builtin"
PIPELINE_EXIT_CODES = {0, 3, 4, 5, 6}
JOB_TIMEOUT_S = 900
# Project CI/CD variables that the docs examples keep out of the YAML. The values
# are DUMMIES for the mocked AWS (moto accepts any role and any key id); they are
# not real accounts or keys. Override or add with `--variable NAME=VALUE`.
DUMMY_PROJECT_VARIABLES = {
    "AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/InvenTagGitLabReadOnly",
    "INVENTAG_REPORTS_BUCKET": "inventag-docs-reports",
    "INVENTAG_KMS_KEY_ID": "alias/inventag-docs-example",
}
# header.payload.signature with alg "none": moto does not check the signature.
DUMMY_JWT = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJwcm9qZWN0X3BhdGg6ZG9jcy9leGFtcGxlIn0."

_PIP_INSTALL = re.compile(
    r"""(?:python3?\s+-m\s+)?pip3?\s+install\s+(?:-\S+\s+)*"""
    r"""["']?inventag-aws(?:\[[^\]]*\])?(?:[=<>~!]=?[^"'\s]*)?["']?"""
)
_TEMPLATE_ARG = re.compile(r"--template[ =](\S+)")
_SOURCE_RULE = re.compile(r"""\$CI_PIPELINE_SOURCE\s*==\s*["']([a-z_]+)["']""")
_JOB_FINISHED = re.compile(
    r"^(?P<job>\S+)\s+finished in .*?(?:\s(?P<label>FAIL|WARN)\s+(?P<code>\d+))?\s*$"
)
_JOB_SUMMARY = re.compile(r"^\s(?P<label>PASS|WARN|FAIL)\s+(?P<job>\S+)")


class JobResult(NamedTuple):
    job: str
    label: str  # PASS, WARN or FAIL, as gitlab-ci-local printed it
    exit_code: int


def parse_variable_args(items: List[str]) -> Dict[str, str]:
    """`NAME=VALUE` arguments as a dict; the value may hold more `=` signs."""
    out: Dict[str, str] = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise ValueError(f"--variable needs NAME=VALUE, got {item!r}")
        out[name] = value
    return out


def project_variables(given: Dict[str, str]) -> Dict[str, str]:
    """The project CI/CD variables to pass: every dummy default (the AWS SDK
    reads AWS_ROLE_ARN itself, so no block names it), then those given with
    --variable, which win."""
    return {**DUMMY_PROJECT_VARIABLES, **given}


def write_variables_file(path: Path, variables: Dict[str, str]) -> None:
    """gitlab-ci-local's project file variables (README: `--variables-file`)."""
    path.write_text(yaml.safe_dump(dict(variables), default_style='"'))


PREINSTALLED_NOTE = (
    'echo "inventag-aws: installed before the pipeline, from a wheel built once"'
)


def install_argv(python: str, site: Path, wheel: Path) -> List[str]:
    """pip command that installs the wheel (and no dependencies) into `site`."""
    return [python, "-m", "pip", "install", "--quiet", "--no-deps"] + [
        "--target",
        str(site),
        str(wheel),
    ]


def find_wheel(wheel_dir: Path) -> Path:
    wheels = sorted(wheel_dir.glob("inventag_aws-*.whl"))
    if not wheels:
        raise RuntimeError(f"no inventag_aws wheel was built in {wheel_dir}")
    return wheels[-1]


def build_wheel(wheel_dir: Path) -> Path:
    """Build this checkout once. Jobs of one stage run at the same time, so
    none of them may build the package: they would share one build folder."""
    cmd = [sys.executable, "-m", "pip", "wheel", "--quiet", "--no-deps"]
    subprocess.run(
        cmd + ["--wheel-dir", str(wheel_dir), str(REPO)],
        check=True,
        capture_output=True,
    )
    return find_wheel(wheel_dir)


# Fixtures: what a real project holds outside the YAML, which moto starts without.
# Table: (what the example needs, a pattern in the block's text that shows it).
FIXTURE_NEEDS = [
    ("reports bucket", re.compile(r"--s3-bucket")),
    ("KMS key", re.compile(r"--s3-kms-key-id")),
    ("accounts file", re.compile(r"--accounts-file")),
]
ACCOUNTS_FILE = """\
accounts:
  - account_id: "111111111111"
    account_name: Production
    regions: [us-east-1]
  - account_id: "222222222222"
    account_name: Development
    regions: [us-east-1]
"""
_BUCKET_ARG = re.compile(r"""--s3-bucket[ =]["']?(?:\$\{?(\w+)\}?|([^\s"']+))""")
_ACCOUNTS_ARG = re.compile(r"""--accounts-file[ =]["']?([^\s"']+)""")


def fixtures_needed(body: str) -> List[str]:
    return [name for name, pattern in FIXTURE_NEEDS if pattern.search(body)]


def bucket_name(body: str, variables: Dict[str, str]) -> str:
    """The bucket `--s3-bucket` names: a literal, or the value of its variable."""
    m = _BUCKET_ARG.search(body)
    if not m:
        raise ValueError("no --s3-bucket in the block")
    return variables[m[1]] if m[1] else m[2]


def apply_fixtures(
    needs: List[str],
    body: str,
    project: Path,
    endpoint: str,
    variables: Dict[str, str],
) -> None:
    """Create each fixture the table asked for: project files in `project`
    (before the git commit), AWS objects in the moto server (after its reset)."""
    kw = dict(
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    if "accounts file" in needs:
        target = project / _ACCOUNTS_ARG.search(body)[1]  # type: ignore[index]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ACCOUNTS_FILE)
    if "reports bucket" in needs:
        import boto3

        boto3.client("s3", **kw).create_bucket(Bucket=bucket_name(body, variables))
    if "KMS key" in needs:
        import boto3

        kms = boto3.client("kms", **kw)
        key_id = kms.create_key()["KeyMetadata"]["KeyId"]
        alias = variables.get("INVENTAG_KMS_KEY_ID", "")
        if alias.startswith("alias/"):
            kms.create_alias(AliasName=alias, TargetKeyId=key_id)


def work_name(block: Dict[str, Any]) -> str:
    """A folder-name part that is unique per page path and line: the readable
    slug of the path, the line, and a short hash of the exact path (two paths
    can have the same slug)."""
    path = str(block["path"])
    slug = re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")[-60:]
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}-{block['line']}"


def rewrite_install(doc: Dict[Any, Any], install_cmd: str) -> Dict[Any, Any]:
    """Copy of doc with each `pip install inventag-aws...` in a script list
    (script, before_script, after_script of jobs and default) replaced."""

    def fix(lines: Any) -> Any:
        if isinstance(lines, str):
            return _PIP_INSTALL.sub(lambda _m: install_cmd, lines)
        if isinstance(lines, list):
            return [fix(line) for line in lines]
        return lines

    out: Dict[Any, Any] = {}
    for key, value in doc.items():
        if isinstance(value, dict):
            value = {
                k: fix(v) if k in ("script", "before_script", "after_script") else v
                for k, v in value.items()
            }
        out[key] = value
    return out


def template_names(body: str) -> List[str]:
    """Names given to --template in the block, in order, without duplicates."""
    names: List[str] = []
    for name in _TEMPLATE_ARG.findall(body):
        name = name.strip("\"'")
        if name not in names:
            names.append(name)
    return names


def id_token_names(doc: Dict[Any, Any]) -> List[str]:
    """Variable names declared under id_tokens in any job or in default."""
    names: List[str] = []
    for key, job in doc.items():
        if isinstance(job, dict) and isinstance(job.get("id_tokens"), dict):
            names += [n for n in job["id_tokens"] if n not in names]
    return names


def choose_pipeline_source(
    doc: Dict[Any, Any], override: Optional[str]
) -> Tuple[str, str]:
    """The pipeline source to simulate and why: the override, else the source
    named in `rules:if` that lets most jobs run (the first named wins a tie),
    else gitlab-ci-local's default, push."""
    if override:
        return override, "override"
    per_job: List[List[str]] = []
    for name, job in doc.items():
        rules = job.get("rules") if isinstance(job, dict) else None
        if str(name).startswith(".") or not isinstance(rules, list):
            continue
        found: List[str] = []
        for rule in rules:
            if isinstance(rule, dict) and rule.get("when") != "never":
                found += _SOURCE_RULE.findall(str(rule.get("if", "")))
        if found:
            per_job.append(found)
    order = list(dict.fromkeys(src for found in per_job for src in found))
    if not order:
        return "push", "default: no rule names a source"
    best = max(order, key=lambda src: sum(src in found for found in per_job))
    return best, "from the block's rules"


def parse_results(output: str) -> List[JobResult]:
    """Per job: gitlab-ci-local's PASS/WARN/FAIL label and the job's exit code."""
    codes: Dict[str, int] = {}
    labels: Dict[str, str] = {}
    for line in output.splitlines():
        m = _JOB_FINISHED.match(line)
        if m:
            codes[m["job"]] = int(m["code"]) if m["code"] else 0
            continue
        m = _JOB_SUMMARY.match(line)
        if m:
            labels[m["job"]] = m["label"]
    return [JobResult(job, labels[job], codes.get(job, -1)) for job in labels]


def expected_label(job: Dict[Any, Any], exit_code: int) -> str:
    """The job status GitLab documents for this exit code and allow_failure."""
    if exit_code == 0:
        return "PASS"
    allow = job.get("allow_failure", False)
    if allow is True:
        return "WARN"
    if isinstance(allow, dict):
        codes = allow.get("exit_codes", [])
        codes = codes if isinstance(codes, list) else [codes]
        if exit_code in codes:
            return "WARN"
    return "FAIL"


def missing_prerequisites(gcl: Optional[str]) -> List[str]:
    missing = []
    if not gcl:
        missing.append(
            "gitlab-ci-local not found (npm install gitlab-ci-local in a scratch "
            "directory, then pass --gitlab-ci-local or put it on PATH)"
        )
    if not shutil.which("rsync"):
        missing.append("rsync not found (gitlab-ci-local needs it for every job run)")
    try:
        import flask  # noqa: F401
        import moto.server  # noqa: F401
    except ImportError:
        missing.append('moto server mode not installed (pip install "moto[server]")')
    return missing


def _seed(endpoint: str) -> None:
    import boto3

    kw = dict(
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    urllib.request.urlopen(urllib.request.Request(f"{endpoint}/moto-api/reset", b""))
    ec2 = boto3.client("ec2", **kw)
    image = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    ec2.run_instances(
        ImageId=image,
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "web-1"}]}
        ],
    )
    boto3.client("s3", **kw).create_bucket(Bucket="inventag-docs-example")


def _assumed_roles(endpoint: str) -> List[str]:
    with urllib.request.urlopen(f"{endpoint}/moto-api/data.json") as resp:
        data = json.load(resp)
    return sorted(
        {r.get("role_arn", "?") for r in data.get("sts", {}).get("AssumedRole", [])}
    )


def _artifacts(project: Path, job: str) -> List[str]:
    safe = re.sub(r"[^\w-]+", "-", job)
    root = project / ".gitlab-ci-local" / "artifacts" / safe
    if not root.is_dir():
        return []
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and ".gitlab-ci-reports" not in p.parts
    )


def _prepare_project(
    block: Dict[str, Any],
    doc: Dict[Any, Any],
    work: Path,
    wheel: Path,
    endpoint: str,
    variables: Dict[str, str],
) -> Path:
    """A git repository holding the rewritten block and its config templates."""
    project = work / f"block-{work_name(block)}"
    site = work / f"site-{work_name(block)}"
    project.mkdir()
    subprocess.run(
        install_argv(sys.executable, site, wheel), check=True, capture_output=True
    )
    (project / ".gitlab-ci.yml").write_text(
        yaml.safe_dump(rewrite_install(doc, PREINSTALLED_NOTE), sort_keys=False)
    )
    needs = fixtures_needed(block["body"])
    apply_fixtures(needs, block["body"], project, endpoint, variables)
    builtin = {p.stem for p in BUILTIN_TEMPLATES.glob("*.yaml")}
    for name in template_names(block["body"]):
        if name not in builtin:
            subprocess.run(
                [sys.executable, "-m", "inventag.cli.main", "templates", "init"]
                + ["ci-pipeline", "--output", f".inventag/templates/{name}.yaml"],
                cwd=project,
                check=True,
                capture_output=True,
            )
    git = ["git", "-c", "user.name=docs", "-c", "user.email=docs@example.invalid"]
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "example"]):
        subprocess.run(git + cmd, cwd=project, check=True)
    return project


def gcl_args(gcl: str, variables_file: Path, variables: Dict[str, str]) -> List[str]:
    """The gitlab-ci-local command line (options as in its `--help`)."""
    args = [gcl, "--force-shell-executor", "--no-color"]
    args += ["--variables-file", str(variables_file)]
    args += ["--ignore-predefined-vars", "CI_PIPELINE_SOURCE"]
    for k, v in variables.items():
        args += ["--variable", f"{k}={v}"]
    return args


def _run_gitlab_ci_local(
    project: Path,
    site: Path,
    gcl: str,
    endpoint: str,
    tokens: List[str],
    source: str,
    variables_file: Path,
) -> str:
    """Run the pipeline with the given pipeline source and a controlled environment.

    gitlab-ci-local passes the host environment into shell jobs, so only the
    variables below reach a job: no local AWS credentials or config.
    """
    env = {
        "PATH": os.pathsep.join(
            [
                str(site / "bin"),
                str(Path(sys.executable).parent),
                str(Path(gcl).resolve().parent),
                os.environ.get("PATH", "/usr/bin:/bin"),
            ]
        ),
        "HOME": str(project.parent),
        "PYTHONPATH": str(site),
        "AWS_CONFIG_FILE": os.devnull,
        "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "LANG": "C.UTF-8",
    }
    variables = {"CI_PIPELINE_SOURCE": source, "AWS_ENDPOINT_URL": endpoint}
    variables.update({n: DUMMY_JWT for n in tokens})
    if not tokens:
        variables.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing")
    args = gcl_args(gcl, variables_file, variables)
    proc = subprocess.run(
        args,
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=JOB_TIMEOUT_S,
    )
    return proc.stdout + proc.stderr


def _job_line(
    r: JobResult, job: Dict[str, Any], files: List[str], roles: List[str], tokens
) -> Tuple[bool, str]:
    """One evidence line for a job, and whether it ended as its YAML says."""
    problems = []
    want = expected_label(job, r.exit_code)
    if r.label != want:
        problems.append(f"expected {want} for exit {r.exit_code}")
    if r.exit_code not in PIPELINE_EXIT_CODES:
        problems.append("exit code is not a documented pipeline outcome")
    if job.get("artifacts", {}).get("paths") and not files:
        problems.append("no artifacts collected")
    if tokens and not roles:
        problems.append("no role assumed through web identity")
    if tokens:
        creds = "web identity, moto role " + (", ".join(roles) or "none")
    else:
        creds = "dummy static keys"
    shown = ", ".join(files[:4]) + (", ..." if len(files) > 4 else "")
    evidence = (
        f"result {r.label}, exit {r.exit_code}; artifacts {len(files)} file(s)"
        f"{': ' + shown if files else ''}; credentials: {creds}"
    )
    if problems:
        evidence += "; PROBLEM: " + "; ".join(problems)
    return (
        not problems,
        f"  {'FAIL' if problems else 'PASS'} local-run:{r.job}  {evidence}",
    )


def run_block(
    block: Dict[str, Any],
    gcl: str,
    endpoint: str,
    work: Path,
    wheel: Path,
    source_override: Optional[str] = None,
    given_variables: Optional[Dict[str, str]] = None,
) -> bool:
    doc = yaml.safe_load(block["body"])
    tokens = id_token_names(doc)
    variables = project_variables(given_variables or {})
    _seed(endpoint)
    project = _prepare_project(block, doc, work, wheel, endpoint, variables)
    site = work / f"site-{work_name(block)}"
    source, why = choose_pipeline_source(doc, source_override)
    variables_file = work / f"variables-{work_name(block)}.yml"
    write_variables_file(variables_file, variables)
    output = _run_gitlab_ci_local(
        project, site, gcl, endpoint, tokens, source, variables_file
    )
    log = work / f"block-{work_name(block)}.log"
    log.write_text(output)
    roles = _assumed_roles(endpoint)
    title = block["info"] or "(no title)"
    print(f"block {block['path']}:{block['line']} [gitlab] {title}")
    results = parse_results(output)
    if not results:
        print(f"  FAIL local-run  no job ran; log {log}")
        return False
    ok = True
    tool = (
        f"<{_gcl_version(gcl)}, shell executor, moto server, "
        f"pipeline source {source} ({why}); "
        f"project variables {', '.join(variables) or 'none'}>"
    )
    for r in results:
        job_ok, line = _job_line(
            r, doc.get(r.job, {}), _artifacts(project, r.job), roles, tokens
        )
        ok = ok and job_ok
        print(f"{line}  {tool}")
    return ok


_VERSIONS: Dict[str, str] = {}


def _gcl_version(gcl: str) -> str:
    if gcl not in _VERSIONS:
        out = subprocess.run([gcl, "--version"], capture_output=True, text=True)
        _VERSIONS[gcl] = f"gitlab-ci-local {out.stdout.strip()}"
    return _VERSIONS[gcl]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--docs", type=Path, default=REPO / "docs")
    ap.add_argument(
        "--gitlab-ci-local",
        default=os.environ.get("GITLAB_CI_LOCAL") or shutil.which("gitlab-ci-local"),
        help="path to the gitlab-ci-local executable (default: env "
        "GITLAB_CI_LOCAL, else PATH)",
    )
    ap.add_argument(
        "--pipeline-source",
        help="simulate this CI_PIPELINE_SOURCE for every block (default: chosen "
        "per block from its rules:if, push when none names a source)",
    )
    ap.add_argument(
        "--variable",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="project CI/CD variable for every block, repeatable. Built-in dummy "
        "defaults exist for " + ", ".join(DUMMY_PROJECT_VARIABLES),
    )
    ap.add_argument("--keep", action="store_true", help="keep the work directory")
    ns = ap.parse_args(argv)
    try:
        given = parse_variable_args(ns.variable)
    except ValueError as exc:
        ap.error(str(exc))
    missing = missing_prerequisites(ns.gitlab_ci_local)
    if missing:
        for m in missing:
            print(f"SKIP: {m}")
        return 0
    blocks = []
    for md in sorted(ns.docs.rglob("*.md")):
        for block in check_ci_examples.find_blocks(md.read_text("utf-8")):
            if check_ci_examples.classify(block) == "gitlab":
                block["path"] = str(md.relative_to(ns.docs.parent))
                blocks.append(block)
    if not blocks:
        print(f"SKIP: no GitLab example blocks under {ns.docs}")
        return 0
    from moto.server import ThreadedMotoServer

    # moto answers unknown requests with a 500 and a traceback: keep it quiet.
    logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    work = Path(tempfile.mkdtemp(prefix="gl-examples-"))
    try:
        wheel = build_wheel(work / "wheel")
        ok = all(
            [
                run_block(
                    b,
                    ns.gitlab_ci_local,
                    f"http://{host}:{port}",
                    work,
                    wheel,
                    ns.pipeline_source,
                    given,
                )
                for b in blocks
            ]
        )
    finally:
        server.stop()
        if ns.keep:
            print(f"work directory kept: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    verdict = "all as expected" if ok else "PROBLEMS above"
    print(f"{len(blocks)} GitLab example block(s) run locally, {verdict}.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
