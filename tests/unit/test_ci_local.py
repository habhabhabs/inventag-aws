"""scripts/dev/ci_local.py: its command list against the workflow files (P-03),
the pinned tool file (L-05), the environment comparison, the site plan (L-04) and
the rule that tests import only what the requirement files install (P-13)."""

import ast
import importlib.util
import json
import sys
from importlib import metadata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
_PATH = ROOT / "scripts" / "dev" / "ci_local.py"
_spec = importlib.util.spec_from_file_location("ci_local", _PATH)
ci = importlib.util.module_from_spec(_spec)
sys.modules["ci_local"] = ci
_spec.loader.exec_module(ci)

WORKFLOW_FILES = ("ci.yml", "docs-deploy.yml", "actions-checks.yml")


# --- the command list against the workflow files ----------------------------


def test_every_listed_command_is_in_its_workflow_step():
    cache = {}
    for step in ci.STEPS:
        if step.workflow is None:
            continue
        runs = cache.setdefault(step.workflow, ci.workflow_runs(step.workflow))
        assert step.step in runs, f"{step.workflow} has no step {step.step!r}"
        text = ci._normalise(runs[step.step]).replace(
            '"$RUNNER_TEMP/actionlint"', "actionlint"
        )
        assert (
            ci._normalise(step.command) in text
        ), f"{step.workflow} step {step.step!r} no longer contains: {step.command}"


def test_every_workflow_run_step_is_listed_or_excluded_with_a_reason():
    listed = {(s.workflow, s.step) for s in ci.STEPS if s.workflow}
    for workflow in WORKFLOW_FILES:
        for name in ci.workflow_runs(workflow):
            key = (workflow, name)
            assert key in listed or key in ci.NOT_RUN, f"{workflow}: step {name!r}"
    for key, reason in ci.NOT_RUN.items():
        assert reason.strip(), key
        assert key not in listed, f"{key} is both run and excluded"
        assert key[1] in ci.workflow_runs(key[0]), f"{key} is not in the workflow"


def test_a_step_that_is_not_in_a_workflow_says_so():
    assert [s.label for s in ci.STEPS if s.workflow is None] == [
        "example outputs and pictures are current (no workflow runs this)"
    ]


def test_commands_use_the_environments_python_and_tools(tmp_path):
    (tmp_path / "black").write_text("")
    black = next(s for s in ci.STEPS if s.label == "black")
    assert ci.argv_for(black, "/venv/bin/python", tmp_path) == [
        [str(tmp_path / "black"), "--check", "scripts/", "inventag/"]
    ]
    tests = next(s for s in ci.STEPS if s.label == "test suite")
    assert ci.argv_for(tests, "/venv/bin/python", tmp_path)[0][:3] == [
        "/venv/bin/python",
        "-m",
        "pytest",
    ]


def test_shell_checks_cover_every_script_in_the_scripts_folder():
    bash_n = next(s for s in ci.STEPS if s.label.startswith("bash -n"))
    shellcheck = next(s for s in ci.STEPS if s.label.startswith("shellcheck"))
    names = sorted(
        str(p.relative_to(ROOT)) for p in (ROOT / ".github/scripts").glob("*.sh")
    )
    assert names
    assert [a[-1] for a in ci.argv_for(bash_n, "python", None)] == names
    assert ci.argv_for(shellcheck, "python", None) == [["shellcheck", *names]]


def test_workflow_parse_snippet_runs():
    parse = next(s for s in ci.STEPS if s.label == "every workflow file parses")
    import subprocess

    (argv,) = ci.argv_for(parse, sys.executable, None)
    done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_plan_prints_without_running(capsys):
    assert ci.main(["plan", "application"]) == 0
    out = capsys.readouterr().out
    assert "flake8" in out and "pytest tests/" in out


# --- the pinned tool file -----------------------------------------------------


def test_tool_pins_match_the_workflow_files():
    tools = ci.load_tools()
    actions = yaml.safe_load((ci.WORKFLOWS / "actions-checks.yml").read_text())
    env = next(
        step["env"]
        for step in actions["jobs"]["check"]["steps"]
        if step.get("env", {}).get("ACTIONLINT_VERSION")
    )
    assert tools["actionlint"]["version"] == env["ACTIONLINT_VERSION"]
    docs = yaml.safe_load((ci.WORKFLOWS / "docs-deploy.yml").read_text())
    node = {
        str(s["with"]["node-version"])
        for job in docs["jobs"].values()
        for s in job.get("steps", [])
        if s.get("uses", "").startswith("actions/setup-node")
    }
    assert node == {tools["node"]["version"]}
    lint = yaml.safe_load((ci.WORKFLOWS / "ci.yml").read_text())["jobs"]
    versions = {
        str(s["with"]["python-version"])
        for s in next(j for j in lint.values() if j["name"] == "Lint and format")[
            "steps"
        ]
        if s.get("uses", "").startswith("actions/setup-python")
    }
    assert versions == {tools["python"]["version"]}
    for name, entry in tools.items():
        if not name.startswith("_"):
            assert entry["source"] and isinstance(entry["verified"], bool)


# --- environments --------------------------------------------------------------


def test_requirement_lines_are_parsed(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("# c\nblack==1.2.3   # x\nmoto[all]==5.2.5\nboto3>=1.35.0\n\nfoo\n")
    assert ci.parse_requirements(path) == [
        ("black", "==", "1.2.3"),
        ("moto", "==", "5.2.5"),
        ("boto3", ">=", "1.35.0"),
    ]


def test_package_problems_name_each_difference(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("black==1.2.3\nmoto==5.2.5\nboto3>=1.35.0\nPyYAML>=6.0\nx_y==1\n")
    installed = {"black": "1.2.4", "moto": "5.2.5", "boto3": "1.9.0", "x-y": "1"}
    problems = ci.package_problems(installed, [path])
    assert problems == [
        "r.txt: black==1.2.3: installed 1.2.4",
        "r.txt: boto3>=1.35.0: installed 1.9.0",
        "r.txt: PyYAML>=6.0: not installed",
    ]


def test_version_comparison_is_numeric():
    assert ci._version_key("1.10.0") > ci._version_key("1.9.9")
    assert ci._version_key("2026.10.18") >= ci._version_key("2026.10.18")


def test_create_venv_builds_from_both_requirement_files(tmp_path):
    commands = ci.create_venv(tmp_path / "v", "/usr/bin/python3.13")
    assert commands[0] == ["/usr/bin/python3.13", "-m", "venv", str(tmp_path / "v")]
    install = commands[-1]
    assert install[-4:] == [
        "-r",
        str(ROOT / "requirements.txt"),
        "-r",
        str(ROOT / "requirements-dev.txt"),
    ]


def test_environment_report_says_when_it_is_not_ci_equal(monkeypatch):
    monkeypatch.setattr(ci, "installed_packages", lambda python: {})
    monkeypatch.setattr(ci, "tool_problems", lambda python: [])
    lines, equal = ci.environment_report("python", clean=False)
    assert equal is False and "not CI-equal" in lines[0]
    assert any("not installed" in line for line in lines)


def test_tool_problems_reports_a_different_version(monkeypatch):
    monkeypatch.setattr(ci, "_tool_version", lambda name: "0.11.0")
    problems = ci.tool_problems(sys.executable)
    assert any(
        p.startswith("shellcheck: 0.11.0 here") and "not verified" in p
        for p in problems
    )


# --- the assembled two-locale build -------------------------------------------


def test_site_plan_builds_en_and_one_locale_then_assembles_and_checks(tmp_path):
    plan = ci.site_plan("fr", tmp_path, 4173, a11y=True)
    labels = [item["label"] for item in plan]
    assert labels[0].startswith("sync")
    builds = [item["argv"] for item in plan if "docusaurus" in item["argv"]]
    assert [b[b.index("--locale") + 1] for b in builds] == ["en", "fr"]
    assert all(b[0] == "flock" and b[1] == "/tmp/docusaurus-build.lock" for b in builds)
    assert all("npm run build" not in " ".join(b) for b in builds)
    assemble = next(i["argv"] for i in plan if "assemble-locales.mjs" in i["argv"][1])
    assert f"fr={tmp_path / 'fr'}" in assemble
    assert plan[-1]["argv"][-1] == "--strict-locales"
    assert plan[-1]["serve"][-2:] == ["--port", "4173"]
    assert any(i["argv"][1] == "scripts/check-links.mjs" for i in plan)


def test_site_plan_without_a11y_and_with_a_bad_locale(tmp_path):
    assert all("serve" not in i for i in ci.site_plan("es", tmp_path, 1, a11y=False))
    try:
        ci.site_plan("de", tmp_path, 1, a11y=False)
    except ValueError as exc:
        assert "locale" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_site_run_needs_allow_build(capsys, monkeypatch):
    monkeypatch.setattr(ci, "environment_report", lambda python, clean: ([], True))
    assert ci.main(["run", "site", "--python", sys.executable]) == 2
    assert "--allow-build" in capsys.readouterr().out


def test_workflow_scripts_exist_for_the_site_plan():
    for name in (
        "assemble-locales.mjs",
        "check-links.mjs",
        "check-a11y.mjs",
        "serve-pages.mjs",
        "sync-i18n.mjs",
    ):
        assert (ROOT / "website" / "scripts" / name).is_file()
    assert "--strict-locales" in (ROOT / "website/scripts/check-a11y.mjs").read_text()
    assert "--dir" in (ROOT / "website/scripts/serve-pages.mjs").read_text()


# --- tests import only what the requirement files install (P-13) -------------


def _roots():
    names = set()
    for path in ci.REQUIREMENT_FILES:
        names |= {
            n.lower().replace("_", "-") for n, _, _ in ci.parse_requirements(path)
        }
    return names


def _closure(roots):
    seen, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            requires = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue
        for req in requires:
            if "extra ==" in req.replace("'", '"').replace('extra=="', 'extra == "'):
                continue
            base = req.split(";")[0]
            for sep in " [<>=!~(":
                base = base.split(sep)[0]
            todo.append(base.strip().lower().replace("_", "-"))
    return seen


def test_roots_come_from_both_requirement_files():
    roots = _roots()
    assert {"boto3", "pyyaml", "pytest", "moto", "black"} <= roots


def _imports(path):
    """Top-level module names imported by a file, not counting imports that are
    guarded by try/except ImportError."""
    tree = ast.parse(path.read_text("utf-8"))
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            isinstance(h.type, ast.Name)
            and h.type.id in ("ImportError", "ModuleNotFoundError")
            for h in node.handlers
        ):
            for child in ast.walk(node):
                guarded.add(id(child))
    names = set()
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_tests_import_only_what_the_requirement_files_install():
    local = {"inventag", "tests", "scripts", "conftest"}
    local |= {p.stem for p in (ROOT / "tests").rglob("*.py")}
    local |= {p.name for p in (ROOT / "tests").rglob("*") if p.is_dir()}
    allowed = _closure(_roots())
    owner = metadata.packages_distributions()
    problems = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        for module in sorted(_imports(path)):
            if module in sys.stdlib_module_names or module in local:
                continue
            dists = {d.lower().replace("_", "-") for d in owner.get(module, [])}
            if not dists & allowed:
                problems.append(f"{path.relative_to(ROOT)}: imports {module}")
    assert problems == []


def test_the_scan_finds_a_module_that_no_requirement_file_installs(tmp_path):
    sample = tmp_path / "t.py"
    sample.write_text(
        "import PIL\ntry:\n    import fancy\nexcept ImportError:\n    pass\n"
    )
    assert _imports(sample) == {"PIL"}
    assert "pillow" not in _closure(_roots())
