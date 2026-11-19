#!/usr/bin/env python3
"""Run on this host what the CI workflows run (L-04, L-05, P-03, P-13).

    ci-local.sh env --venv DIR --create      build a clean venv from the two
                                             requirement files (needs the network)
    ci-local.sh env --venv DIR               compare a venv and the host tools
                                             with the pins
    ci-local.sh plan AREA                    print the commands, run nothing
    ci-local.sh run AREA --venv DIR          run them
    ci-local.sh run site --venv DIR --allow-build --locale fr
                                             the assembled two-locale site build

Areas: application (ci.yml: lint, format, tests, bandit), docs (docs-deploy.yml:
type-check, translation structure, CI examples; plus the example generator's
`--check --no-images`, which no workflow runs), actions (actions-checks.yml),
site (docs-deploy.yml: the build, link check and accessibility check, on an
assembled English plus one locale build with the real /<locale>/ paths).

Every command comes from a `run:` step of a workflow; STEPS names the workflow
and step each one was copied from, and tests/unit/test_ci_local.py fails when a
workflow no longer contains the command, or when a workflow step is neither
listed here nor in NOT_RUN with a reason.

A clean environment is a venv built with `pip install -r requirements.txt -r
requirements-dev.txt`, as the workflows do. Any other interpreter (`--python`)
is accepted but the run says it is not CI-equal and lists the packages that
differ from the pins. Tool versions the runner uses are in ci-tools.json.
This script never installs anything except with `env --create`.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
TOOLS_FILE = Path(__file__).resolve().parent / "ci-tools.json"
LOCALES = ("zh-Hans", "zh-Hant", "es", "fr")
SITE_BASE = "/inventag-aws"


class Step(NamedTuple):
    area: str
    label: str
    command: str  # as written in the workflow (one shell line, no continuation)
    workflow: Optional[str]  # file in .github/workflows; None = no workflow runs it
    step: Optional[str]  # `name:` of the workflow step
    cwd: str = "."  # relative to the repository root
    tolerated: bool = False  # the workflow ignores a failure of this command
    env: Tuple[Tuple[str, str], ...] = ()


STEPS: List[Step] = [
    Step(
        "application",
        "flake8, errors only",
        "flake8 scripts/ inventag/ --count --select=E9,F63,F7,F82 --show-source --statistics",
        "ci.yml",
        "Run linting",
    ),
    Step(
        "application",
        "flake8, complexity (never fails)",
        "flake8 scripts/ inventag/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics",
        "ci.yml",
        "Run linting",
    ),
    Step(
        "application",
        "black",
        "black --check scripts/ inventag/",
        "ci.yml",
        "Check code formatting",
    ),
    Step(
        "application",
        "package imports",
        "python -c \"import inventag; print('✅ InvenTag package imports successfully')\"",
        "ci.yml",
        "Run tests",
    ),
    Step(
        "application",
        "test suite",
        "python -m pytest tests/ -v --cov=inventag --cov-report=xml --timeout=300",
        "ci.yml",
        "Run tests",
    ),
    Step(
        "application",
        "help: bom_converter",
        "python scripts/legacy/bom_converter.py --help",
        "ci.yml",
        "Run tests",
    ),
    Step(
        "application",
        "help: tag_compliance_checker",
        "python scripts/legacy/tag_compliance_checker.py --help",
        "ci.yml",
        "Run tests",
    ),
    Step(
        "application",
        "help: cicd_bom_generation",
        "python scripts/development/cicd_bom_generation.py --help",
        "ci.yml",
        "Run tests",
    ),
    Step(
        "application",
        "bandit (the workflow tolerates findings)",
        "bandit -r scripts/ inventag/ -ll",
        "ci.yml",
        "Python security checks",
        tolerated=True,
    ),
    Step(
        "docs",
        "type-check the site",
        "npm run typecheck",
        "docs-deploy.yml",
        "Type-check the site",
        cwd="website",
    ),
    Step(
        "docs",
        "translation structure",
        "npm run check:i18n -- --strict",
        "docs-deploy.yml",
        "Check translation structure",
        cwd="website",
    ),
    Step(
        "docs",
        "CI examples, shell blocks and json blocks in the docs",
        "npm run check:ci-examples",
        "docs-deploy.yml",
        "Check CI examples in the docs",
        cwd="website",
        env=(("PYTHON", "{python}"),),
    ),
    Step(
        "docs",
        "example outputs and pictures are current (no workflow runs this)",
        "python scripts/docs/generate_example_outputs.py --check --no-images",
        None,
        None,
    ),
    Step(
        "actions",
        "every workflow file parses",
        'yaml.safe_load(path.read_text(encoding="utf-8"))',
        "actions-checks.yml",
        "Every workflow file parses",
    ),
    Step(
        "actions",
        "actionlint (without shellcheck and pyflakes, as the workflow)",
        "actionlint -color -shellcheck= -pyflakes=",
        "actions-checks.yml",
        "actionlint",
    ),
    Step(
        "actions",
        "bash -n on .github/scripts",
        'bash -n "$script"',
        "actions-checks.yml",
        "shellcheck and bash -n on .github/scripts",
    ),
    Step(
        "actions",
        "shellcheck on .github/scripts",
        "shellcheck .github/scripts/*.sh",
        "actions-checks.yml",
        "shellcheck and bash -n on .github/scripts",
    ),
    Step(
        "actions",
        "tests of the workflow code",
        "python -m pytest -q tests/unit/test_release_needed.py "
        "tests/unit/test_sync_doc_versions.py "
        '"tests/backward_compatibility/test_github_actions_compatibility.py'
        '::TestGitHubActionsCompatibility"',
        "actions-checks.yml",
        "Tests of the workflow code",
    ),
]

# Workflow steps that this script does not run, each with the reason. The test
# lists every `run:` step of the three workflows and fails on one that is in
# neither STEPS nor here.
NOT_RUN: Dict[Tuple[str, str], str] = {
    ("ci.yml", "Install pinned tools"): "pip install: use `env --create`",
    ("ci.yml", "Install dependencies"): "pip install: use `env --create`",
    ("ci.yml", "Pin boto3 and botocore to the floor in requirements.txt"): (
        "needs a second environment at the oldest boto3; not built here"
    ),
    ("ci.yml", "Install dependencies at the floor"): "second environment",
    ("ci.yml", "Run guard and S3 upload tests"): "second environment (boto3 floor)",
    ("ci.yml", "Node.js security checks"): "npm audit needs the network",
    ("ci.yml", "Simple secrets check"): "a grep that always passes",
    ("ci.yml", "Create sample test data"): "writes test-data/ into the checkout",
    ("ci.yml", "Test BOM converter"): "writes test-output.xlsx into the checkout",
    ("ci.yml", "Test tag compliance checker"): "writes report files into the checkout",
    ("ci.yml", "Generate workflow summary"): "writes the GitHub step summary",
    ("docs-deploy.yml", "Verify version.json dependency"): "reads a CI-only layout",
    ("docs-deploy.yml", "Install SBOM generation tools"): "SBOM: installs packages",
    ("docs-deploy.yml", "Generate repository SBOM files"): "SBOM: writes into docs",
    ("docs-deploy.yml", "Generate Python SBOM with versions"): "SBOM",
    ("docs-deploy.yml", "Generate Node.js SBOM"): "SBOM",
    ("docs-deploy.yml", "Create SBOM summary documentation"): "SBOM",
    ("docs-deploy.yml", "Copy SBOM files to static directory"): "SBOM",
    ("docs-deploy.yml", "Generate component tables"): "SBOM",
    ("docs-deploy.yml", "Run vulnerability analysis"): "needs the network",
    ("docs-deploy.yml", "Generate download tables and documentation"): "SBOM",
    ("docs-deploy.yml", "Install dependencies"): "npm ci: run it in website/ yourself",
    ("docs-deploy.yml", "Validate documentation structure"): "rewrites docs/ in CI",
    ("docs-deploy.yml", "Run GitHub → Docusaurus transformation pipeline"): (
        "rewrites docs/ and makes backups in the checkout"
    ),
    ("docs-deploy.yml", "Install testing dependencies"): "installs packages",
    ("docs-deploy.yml", "Run markdown linting"): "runs after the transformation",
    ("docs-deploy.yml", "Validate frontmatter"): "runs after the transformation",
    ("docs-deploy.yml", "Run link validation"): "runs after the transformation",
    ("docs-deploy.yml", "Test dual-platform compatibility"): "after the transformation",
    (
        "docs-deploy.yml",
        "Validate transformed documentation",
    ): "after the transformation",
    ("docs-deploy.yml", "Build documentation site with fallback"): (
        "area `site`: one build per locale, assembled (never `npm run build` here)"
    ),
    (
        "docs-deploy.yml",
        "Validate build output",
    ): "area `site`: link check on the assembly",
    ("docs-deploy.yml", "Install Chromium for the accessibility checks"): (
        "installs Playwright and Chromium"
    ),
    ("docs-deploy.yml", "Check accessibility (axe-core, 4 widths, 2 themes)"): (
        "area `site` with --a11y (Playwright must be installed already)"
    ),
    (
        "docs-deploy.yml",
        "Test mobile responsiveness and performance",
    ): "needs a browser",
    ("docs-deploy.yml", "Generate accessibility and performance report"): "report only",
    ("docs-deploy.yml", "Run documentation health monitoring"): "monitoring",
    ("docs-deploy.yml", "Performance monitoring post-deployment"): "after a deploy",
    ("actions-checks.yml", "Install test tools"): "pip install: use `env --create`",
    (
        "actions-checks.yml",
        "Install actionlint (pinned version and checksum)",
    ): "downloads a binary: install the version in ci-tools.json yourself",
}


# ---------------------------------------------------------------- the plan


def _normalise(text: str) -> str:
    """One line, one space between words, line continuations removed."""
    return " ".join(text.replace("\\\n", " ").split())


def workflow_runs(workflow: str) -> Dict[str, str]:
    """{step name: its `run:` text} for every step of a workflow file."""
    import yaml

    data = yaml.safe_load((WORKFLOWS / workflow).read_text("utf-8"))
    out: Dict[str, str] = {}
    for job in data["jobs"].values():
        for step in job.get("steps", []):
            if "run" in step and "name" in step:
                out[step["name"]] = out.get(step["name"], "") + "\n" + step["run"]
    return out


def argv_for(step: Step, python: str, bin_dir: Optional[Path]) -> List[List[str]]:
    """The argv lists for a step, with the environment's python and tools."""
    if step.step == "Every workflow file parses":
        code = (
            "import pathlib, sys, yaml\n"
            "files = sorted(pathlib.Path('.github/workflows').glob('*.y*ml'))\n"
            "bad = 0\n"
            "for p in files:\n"
            "    try:\n"
            "        d = yaml.safe_load(p.read_text(encoding='utf-8'))\n"
            "        assert isinstance(d, dict) and 'jobs' in d, 'no jobs mapping'\n"
            "        print('ok:', p)\n"
            "    except Exception as e:\n"
            "        bad += 1\n"
            "        print('error:', p, e)\n"
            "print(len(files), 'workflow file(s),', bad, 'problem(s)')\n"
            "sys.exit(1 if bad or not files else 0)\n"
        )
        return [[python, "-c", code]]
    if step.step == "shellcheck and bash -n on .github/scripts":
        scripts = sorted((REPO / ".github" / "scripts").glob("*.sh"))
        rel = [str(s.relative_to(REPO)) for s in scripts]
        if step.label.startswith("bash -n"):
            return [["bash", "-n", s] for s in rel]
        return [["shellcheck", *rel]]
    argv = shlex.split(step.command)
    if argv[0] == "python":
        argv[0] = python
    elif bin_dir is not None and (bin_dir / argv[0]).exists():
        argv[0] = str(bin_dir / argv[0])
    return [argv]


def steps_for(area: str) -> List[Step]:
    return [s for s in STEPS if s.area == area]


# ------------------------------------------------------------ environments


def _version_key(text: str) -> Tuple[int, ...]:
    nums = re.findall(r"\d+", text.split("+")[0])
    return tuple(int(n) for n in nums[:4])


def parse_requirements(path: Path) -> List[Tuple[str, str, str]]:
    """(distribution, operator, version) for each pinned line of a file."""
    out = []
    for raw in path.read_text("utf-8").splitlines():
        line = raw.split("#")[0].strip()
        match = re.match(
            r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*(==|>=)\s*([\w.]+)", line
        )
        if match:
            out.append((match.group(1), match.group(2), match.group(3)))
    return out


def installed_packages(python: str) -> Dict[str, str]:
    code = (
        "import json, importlib.metadata as m\n"
        "print(json.dumps({d.metadata['Name'].lower().replace('_', '-'): d.version "
        "for d in m.distributions()}))"
    )
    done = subprocess.run([python, "-c", code], capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(done.stderr.strip() or "cannot list packages")
    return json.loads(done.stdout)


def package_problems(installed: Dict[str, str], files: Sequence[Path]) -> List[str]:
    """Differences between an environment and the pins of the requirement files."""
    problems = []
    for path in files:
        for name, op, wanted in parse_requirements(path):
            have = installed.get(name.lower().replace("_", "-"))
            where = f"{path.name}: {name}{op}{wanted}"
            if have is None:
                problems.append(f"{where}: not installed")
            elif op == "==" and have != wanted:
                problems.append(f"{where}: installed {have}")
            elif op == ">=" and _version_key(have) < _version_key(wanted):
                problems.append(f"{where}: installed {have}")
    return problems


def load_tools() -> Dict[str, Dict[str, object]]:
    return json.loads(TOOLS_FILE.read_text("utf-8"))


def _tool_version(name: str) -> Optional[str]:
    commands = {
        "node": ["node", "--version"],
        "shellcheck": ["shellcheck", "--version"],
        "actionlint": ["actionlint", "-version"],
    }
    if name not in commands or not shutil.which(commands[name][0]):
        return None
    out = subprocess.run(commands[name], capture_output=True, text=True).stdout
    match = re.search(r"(?:version:\s*|v)?(\d+(?:\.\d+)+)", out)
    return match.group(1) if match else None


def tool_problems(python: str) -> List[str]:
    """Host tools whose version differs from ci-tools.json."""
    out = []
    for name, entry in load_tools().items():
        if name.startswith("_"):
            continue
        want = str(entry["version"])
        if name == "python":
            done = subprocess.run(
                [python, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                capture_output=True,
                text=True,
            )
            have = done.stdout.strip() or None
        else:
            have = _tool_version(name)
        note = "" if entry.get("verified") else " (value not verified on the runner)"
        if have is None:
            out.append(f"{name}: not found; the runner uses {want}{note}")
        elif not (have == want or have.startswith(want + ".")):
            out.append(f"{name}: {have} here, the runner uses {want}{note}")
    return out


def create_venv(venv: Path, base_python: str = sys.executable) -> List[List[str]]:
    """Commands that build a clean venv from the two requirement files."""
    py = str(venv / "bin" / "python")
    return [
        [base_python, "-m", "venv", str(venv)],
        [py, "-m", "pip", "install", "--upgrade", "pip"],
        [
            py,
            "-m",
            "pip",
            "install",
            "-r",
            str(REPO / "requirements.txt"),
            "-r",
            str(REPO / "requirements-dev.txt"),
        ],
    ]


REQUIREMENT_FILES = (REPO / "requirements.txt", REPO / "requirements-dev.txt")


def environment_report(python: str, clean: bool) -> Tuple[List[str], bool]:
    """(lines to print, equal to CI)."""
    lines = []
    equal = clean
    if not clean:
        lines.append(
            "WARNING: this interpreter was not built from the two requirement "
            "files by `env --create`; the run is not CI-equal."
        )
    try:
        problems = package_problems(installed_packages(python), REQUIREMENT_FILES)
    except RuntimeError as exc:
        problems = [f"cannot read the installed packages: {exc}"]
    lines += [f"package: {p}" for p in problems]
    lines += [f"tool: {p}" for p in tool_problems(python)]
    return lines, equal and not problems


# ----------------------------------------------------------- the site area


def site_plan(
    locale: str, work: Path, port: int, a11y: bool
) -> List[Dict[str, object]]:
    """The assembled two-locale build as a list of {label, argv, cwd, env}."""
    if locale not in LOCALES:
        raise ValueError(f"locale must be one of {', '.join(LOCALES)}")
    prod = {"NODE_ENV": "production", "DOCUSAURUS_SSR_CONCURRENCY": "2"}
    steps: List[Dict[str, object]] = [
        {
            "label": "sync the translated pages (prebuild)",
            "argv": ["node", "scripts/sync-i18n.mjs"],
            "cwd": "website",
            "env": {},
        }
    ]
    for loc in ("en", locale):
        steps.append(
            {
                "label": f"build {loc} (flock: one build at a time on a shared host)",
                "argv": [
                    "flock",
                    "/tmp/docusaurus-build.lock",
                    "env",
                    "NODE_OPTIONS=--max-old-space-size=2500",
                    "npx",
                    "docusaurus",
                    "build",
                    "--locale",
                    loc,
                    "--out-dir",
                    str(work / loc),
                ],
                "cwd": "website",
                "env": prod,
            }
        )
    steps.append(
        {
            "label": f"assemble en and /{locale}/",
            "argv": [
                "node",
                "scripts/assemble-locales.mjs",
                "--en",
                str(work / "en"),
                "--locale",
                f"{locale}={work / locale}",
                "--out",
                str(work / "assembled"),
            ],
            "cwd": "website",
            "env": {},
        }
    )
    steps.append(
        {
            "label": "check:links on the assembled build",
            "argv": ["node", "scripts/check-links.mjs", str(work / "assembled")],
            "cwd": "website",
            "env": {},
        }
    )
    if a11y:
        steps.append(
            {
                "label": "check:a11y on the assembled build (fails when a locale is missing)",
                "argv": [
                    "node",
                    "scripts/check-a11y.mjs",
                    "--base",
                    f"http://localhost:{port}{SITE_BASE}",
                    "--strict-locales",
                ],
                "cwd": "website",
                "env": {},
                "serve": [
                    "node",
                    "scripts/serve-pages.mjs",
                    "--dir",
                    str(work / "assembled"),
                    "--port",
                    str(port),
                ],
            }
        )
    return steps


# ----------------------------------------------------------------- running


def _run(argv: List[str], cwd: Path, env: Dict[str, str]) -> int:
    return subprocess.run(argv, cwd=cwd, env=env).returncode


def run_area(
    area: str,
    python: str,
    bin_dir: Optional[Path],
    only: Optional[str] = None,
) -> Tuple[List[Tuple[str, str, int]], bool]:
    results = []
    ok = True
    env = dict(os.environ)
    if bin_dir is not None:
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    for step in steps_for(area):
        if only and only not in step.label:
            continue
        step_env = dict(env)
        for key, value in step.env:
            step_env[key] = value.replace("{python}", python)
        code = 0
        for argv in argv_for(step, python, bin_dir):
            print(f"\n$ ({step.cwd}) {' '.join(shlex.quote(a) for a in argv)[:200]}")
            code = _run(argv, REPO / step.cwd, step_env) or code
        label = "PASS" if code == 0 else ("WARN" if step.tolerated else "FAIL")
        ok = ok and label != "FAIL"
        results.append((label, step.label, code))
    return results, ok


def run_site(locale: str, python: str, bin_dir, work: Path, a11y: bool, port: int):
    env = dict(os.environ)
    results = []
    ok = True
    for item in site_plan(locale, work, port, a11y):
        step_env = dict(env, **item["env"])  # type: ignore[arg-type]
        server = None
        if "serve" in item:
            server = subprocess.Popen(
                item["serve"], cwd=REPO / "website", env=step_env  # type: ignore
            )
            _wait_for(f"http://localhost:{port}{SITE_BASE}/")
        try:
            print(f"\n$ {item['label']}")
            code = _run(item["argv"], REPO / str(item["cwd"]), step_env)  # type: ignore
        finally:
            if server:
                server.terminate()
        label = "PASS" if code == 0 else "FAIL"
        ok = ok and code == 0
        results.append((label, str(item["label"]), code))
        if code:
            break
    return results, ok


def _wait_for(url: str, seconds: int = 30) -> None:
    for _ in range(seconds):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(1)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    env_p = sub.add_parser("env", help="create or check an environment")
    env_p.add_argument("--venv", type=Path, required=True)
    env_p.add_argument("--create", action="store_true")
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("area", choices=["application", "docs", "actions", "site"])
        p.add_argument("--venv", type=Path, help="a venv made by `env --create`")
        p.add_argument("--python", help="any interpreter (not CI-equal)")
        p.add_argument("--only", help="run only steps whose label contains this")
        p.add_argument("--locale", default="fr", choices=LOCALES)
        p.add_argument("--allow-build", action="store_true", help="site: really build")
        p.add_argument("--a11y", action="store_true", help="site: run check:a11y")
        p.add_argument("--work", type=Path, help="site: folder for the builds")
        p.add_argument("--port", type=int, default=4173)
    ns = ap.parse_args(argv)

    if ns.cmd == "env":
        if ns.create:
            for cmd in create_venv(ns.venv):
                print("$", " ".join(shlex.quote(c) for c in cmd))
                if subprocess.run(cmd).returncode:
                    return 1
        py = str(ns.venv / "bin" / "python")
        lines, equal = environment_report(py, clean=ns.create)
        print("\n".join(lines) or "no differences from the pins")
        return 0 if equal or not ns.create else 1

    if ns.venv:
        python, bin_dir = str(ns.venv / "bin" / "python"), ns.venv / "bin"
    else:
        python, bin_dir = ns.python or sys.executable, None
    if ns.cmd == "plan":
        if ns.area == "site":
            work = ns.work or Path("<work>")
            for item in site_plan(ns.locale, work, ns.port, ns.a11y):
                print(f"{item['label']}: {' '.join(item['argv'])}")  # type: ignore
        for step in steps_for(ns.area):
            for a in argv_for(step, python, bin_dir):
                print(f"{step.label}: {' '.join(shlex.quote(x) for x in a)[:160]}")
        return 0

    lines, _ = environment_report(python, clean=bool(ns.venv))
    print("\n".join(lines))
    if ns.area == "site":
        if not ns.allow_build:
            print("site: a build is heavy; pass --allow-build to run it")
            return 2
        work = ns.work or Path(tempfile.mkdtemp(prefix="inventag-site-"))
        results, ok = run_site(ns.locale, python, bin_dir, work, ns.a11y, ns.port)
    else:
        results, ok = run_area(ns.area, python, bin_dir, ns.only)
    print("\nSummary")
    for label, text, code in results:
        print(f"  {label} (exit {code}): {text}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
