"""The packaging workflow (.github/workflows/package.yml) and the job of
release.yml that calls it (plan v14 sections 3.5, 5.2 B3 and 5.6; architect
reviews of wave 1, items B3 and F2).

Nothing here runs a runner: the tests read the workflow as data and check the
rules of the repository (pinned actions, named runner images, least
privilege) and the rules of this workflow (build image pinned, no release
trigger, the notices addresses fetched, nothing published in a dry run).
"""

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "package.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
DATA = yaml.safe_load(TEXT)
JOBS = DATA["jobs"]
PINNED = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")
NAMED_IMAGE = re.compile(r"^(ubuntu|macos)-\d+(\.\d+)?(-(arm|intel))?$")


def _pinned_python():
    # Read as data (no import): the assignment of PINNED_PYTHON in the licence check.
    path = ROOT / "scripts" / "packaging" / "third_party_licenses.py"
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        target = getattr(node, "target", None) or (getattr(node, "targets", [None])[0])
        if getattr(target, "id", "") == "PINNED_PYTHON":
            return ast.literal_eval(node.value)
    raise AssertionError("PINNED_PYTHON not found")


def _triggers():
    # PyYAML (YAML 1.1) reads a bare `on:` key as True.
    return DATA.get("on", DATA.get(True))


def _steps(job):
    return JOBS[job]["steps"]


def _run_text(job):
    return "\n".join(step.get("run", "") for step in _steps(job))


def _all_steps():
    for name, job in JOBS.items():
        for step in job.get("steps", []):
            yield name, step


# ---- stage 1: triggers, permissions, the plan job -------------------------


def test_it_is_a_reusable_workflow_started_by_hand_or_by_a_pull_request_that_touches_packaging():
    # No release, push or schedule trigger: a release created with the
    # workflow's own token starts no workflow, and a second trigger would
    # package a tag twice (plan 3.5). The pull request trigger (architect
    # review of B3, ruling 1) is the dry run of the branch's own file.
    assert set(_triggers()) == {"workflow_call", "workflow_dispatch", "pull_request"}
    assert "pull_request_target" not in TEXT


PACKAGING_PATHS = [
    "packaging/**",
    "scripts/packaging/**",
    "requirements-lock*.txt",
    ".github/workflows/package.yml",
    "inventag/cli/selftest.py",
    "inventag/cli/completion.py",
    # B6 fix 4: an application change can break the bundle (a missed import or
    # data file); the dry run must see it before the release does.
    "inventag/**",
    "pyproject.toml",
    "requirements.txt",
]


def test_the_pull_request_trigger_is_limited_to_the_paths_of_packaging():
    trigger = _triggers()["pull_request"]
    assert trigger["paths"] == PACKAGING_PATHS
    # No other filter: every base branch, every default activity type.
    assert set(trigger) == {"paths"}


def test_both_triggers_take_a_tag_a_ref_and_a_dry_run_flag_that_defaults_to_true():
    for name in ("workflow_call", "workflow_dispatch"):
        inputs = _triggers()[name]["inputs"]
        # A real run takes a tag; a dry run may take a branch or commit instead
        # (plan 5.2: a dry run on the integration branch before the tag exists).
        for key in ("tag", "ref"):
            assert inputs[key]["type"] == "string"
            assert inputs[key]["required"] is False
            assert inputs[key]["default"] == ""
        assert inputs["dry_run"]["type"] == "boolean"
        assert inputs["dry_run"]["default"] is True


def test_the_workflow_reads_no_secret_of_the_repository():
    assert "secrets." not in TEXT
    assert "secrets:" not in TEXT


def test_the_default_permission_is_read_only_contents():
    assert DATA["permissions"] == {"contents": "read"}


def test_every_job_states_its_permissions_and_only_two_jobs_hold_more_than_read():
    for name, job in JOBS.items():
        assert "permissions" in job, name
    holders = {
        name: job["permissions"]
        for name, job in JOBS.items()
        if set(job["permissions"].items()) - {("contents", "read")}
    }
    # B6 fix 5: the attestation has its own job; provenance holds read only.
    assert set(holders) == {"attest", "publish"}
    assert holders["attest"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }
    assert holders["publish"] == {"contents": "write"}
    assert JOBS["provenance"]["permissions"] == {"contents": "read"}


def test_every_action_is_pinned_by_commit_with_its_version_in_a_comment():
    uses = [
        line
        for line in TEXT.splitlines()
        if re.match(r"^\s*-?\s*uses:", line) and not line.lstrip().startswith("#")
    ]
    assert uses
    for line in uses:
        ref = line.split("uses:", 1)[1].split("#")[0].strip()
        assert PINNED.match(ref), line
        assert re.search(r"#\s*v\d", line), line


def test_every_runner_image_is_named_and_literal():
    for name, job in JOBS.items():
        assert NAMED_IMAGE.match(job["runs-on"]), (name, job["runs-on"])


def test_every_checkout_drops_the_token_after_use():
    for name, step in _all_steps():
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] is False, name


def test_no_expression_of_the_inputs_is_pasted_into_a_script():
    # Inputs reach shell code through env: only (script injection).
    for name, step in _all_steps():
        assert "${{ inputs." not in step.get("run", ""), name
        assert "${{ github.event" not in step.get("run", ""), name


def test_one_run_per_tag_or_pull_request_and_a_running_package_is_never_cancelled():
    group = DATA["concurrency"]
    assert "inputs.tag" in group["group"] and "inputs.ref" in group["group"]
    # Both inputs are empty on a pull request: without its number the group
    # would be the same empty string for every pull request.
    assert "github.event.pull_request.number" in group["group"]
    assert group["cancel-in-progress"] is False


def test_the_plan_job_checks_the_tag_against_the_version_file():
    plan = JOBS["plan"]
    assert plan["outputs"].keys() >= {"tag", "ref", "version", "dry_run"}
    text = _run_text("plan")
    assert "inventag/_version.py" in text
    assert "^v[0-9]+\\.[0-9]+\\.[0-9]+$" in text
    for needed in ("requirements-lock.txt", "requirements-lock-build.txt"):
        assert needed in text
    checkout = [s for s in _steps("plan") if "checkout" in s.get("uses", "")][0]
    # A pull request builds its own commit (not the merge commit); a manual
    # dry run its ref; a release its tag.
    assert checkout["with"]["ref"] == (
        "${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha"
        " || inputs.ref || format('refs/tags/{0}', inputs.tag) }}"
    )
    env = _step("plan", "version")["env"]
    assert env["EVENT_NAME"] == "${{ github.event_name }}"
    assert (
        env["DRY_RUN"] == "${{ github.event_name == 'pull_request' || inputs.dry_run }}"
    )
    assert env["REF"] == (
        "${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha"
        " || inputs.ref }}"
    )


def _plan(
    tmp_path,
    tag="",
    ref="",
    dry_run="true",
    version="1.4.0",
    event="workflow_dispatch",
    include_macos="true",
):
    """Run the plan step in a tiny tree; return (result, outputs as a dict)."""
    import subprocess

    (tmp_path / "inventag").mkdir(exist_ok=True)
    (tmp_path / "inventag" / "_version.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    for name in ("requirements-lock.txt", "requirements-lock-build.txt"):
        (tmp_path / name).write_text("", encoding="utf-8")
    out = tmp_path / "github-output"
    out.write_text("", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", _step("plan", "version")["run"]],
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "TAG": tag,
            "REF": ref,
            "DRY_RUN": dry_run,
            "EVENT_NAME": event,
            "INCLUDE_MACOS": include_macos,
            "GITHUB_OUTPUT": str(out),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    pairs = [line.split("=", 1) for line in out.read_text("utf-8").splitlines()]
    return result, dict(pairs)


def test_plan_accepts_the_tag_of_the_version_and_returns_its_ref(tmp_path):
    result, out = _plan(tmp_path, tag="v1.4.0", dry_run="false")
    assert result.returncode == 0, result.stderr
    assert out == {
        "tag": "v1.4.0",
        "ref": "refs/tags/v1.4.0",
        "version": "1.4.0",
        "dry_run": "false",
        "include_macos": "true",
    }


def test_plan_refuses_a_tag_that_is_not_the_version_in_the_commit(tmp_path):
    result, _ = _plan(tmp_path, tag="v1.4.1", version="1.4.0")
    assert result.returncode != 0


def test_plan_refuses_a_malformed_tag_and_a_missing_tag(tmp_path):
    for tag in ("1.4.0", "v1.4", "v1.4.0; echo x", ""):
        result, _ = _plan(tmp_path, tag=tag)
        assert result.returncode != 0, tag


def test_plan_takes_a_branch_only_for_a_dry_run(tmp_path):
    result, out = _plan(tmp_path, ref="next/v1.4", dry_run="true", version="1.3.0")
    assert result.returncode == 0, result.stderr
    assert out["ref"] == "next/v1.4" and out["version"] == "1.3.0"
    assert out["dry_run"] == "true"
    refused, _ = _plan(tmp_path, ref="next/v1.4", dry_run="false")
    assert refused.returncode != 0
    assert "dry run" in refused.stdout + refused.stderr


def test_plan_refuses_a_ref_with_characters_outside_the_allowed_set(tmp_path):
    # B6 fix 6: the ref is written to the step output; a newline would add an
    # output line, a space or a quote has no place in a ref.
    for ref in (
        "next/v1.4\ntag=v9.9.9",
        "next/v1.4\n",
        "a b",
        "x;echo y",
        'x"y',
        "x$(id)",
        "x`id`",
        "x\ty",
    ):
        result, out = _plan(tmp_path, ref=ref, dry_run="true")
        assert result.returncode != 0, repr(ref)
        assert out == {}, repr(ref)
        assert "ref" in result.stdout + result.stderr, repr(ref)


def test_plan_takes_the_refs_of_branches_and_commits(tmp_path):
    for ref in (
        "next/v1.4",
        "v14/b3i",
        "release-1.4_rc.1",
        "0123456789abcdef0123456789abcdef01234567",
    ):
        result, out = _plan(tmp_path, ref=ref, dry_run="true")
        assert result.returncode == 0, (ref, result.stdout + result.stderr)
        assert out["ref"] == ref


def test_plan_takes_the_commit_of_a_pull_request_as_a_dry_run(tmp_path):
    sha = "0123456789abcdef0123456789abcdef01234567"
    result, out = _plan(tmp_path, ref=sha, dry_run="true", event="pull_request")
    assert result.returncode == 0, result.stderr
    assert out["ref"] == sha and out["dry_run"] == "true" and out["tag"] == ""


def test_plan_refuses_a_pull_request_that_is_not_a_dry_run(tmp_path):
    sha = "0123456789abcdef0123456789abcdef01234567"
    for dry_run in ("false", ""):
        result, _ = _plan(tmp_path, ref=sha, dry_run=dry_run, event="pull_request")
        assert result.returncode != 0, dry_run
    # A pull request with no commit has nothing to build, and a tag is never
    # packaged from a pull request.
    result, _ = _plan(tmp_path, ref="", dry_run="true", event="pull_request")
    assert result.returncode != 0
    result, _ = _plan(tmp_path, tag="v1.4.0", dry_run="true", event="pull_request")
    assert result.returncode != 0
    assert "pull request" in result.stdout + result.stderr


def test_every_other_job_waits_for_the_plan():
    for name, job in JOBS.items():
        if name != "plan":
            assert "plan" in job["needs"], name


# ---- stage 2: the three builds, the build image, nfpm ----------------------

# name: (runner label, CPU as build_binary.sh names it, nfpm arch)
LINUX_BUILDS = {
    "build-linux-x86_64": ("ubuntu-24.04", "x86_64", "amd64"),
    "build-linux-arm64": ("ubuntu-24.04-arm", "arm64", "arm64"),
}
MACOS_BUILDS = {
    "build-macos-arm64": ("macos-15", "arm64"),
}
# Read from nfpm's own checksums.txt of the v2.49.0 release (GitHub, 20 Nov 2026).
NFPM_SHA256 = {
    "x86_64": "2afaa5ffb5e3493402e31e7c67a5a1fb42133e3f66fc315ca0051934125561c7",
    "arm64": "d4eee71839e92c68cbd3b101640bad32d2856fc551acae0635be9118e48c9d9c",
}
DIGEST_PLACEHOLDER = "TO-BE-FILLED-BY-THE-DRY-RUN"


def _non_plan_checkouts():
    for name, step in _all_steps():
        if name != "plan" and step.get("uses", "").startswith("actions/checkout@"):
            yield name, step


def test_the_three_builds_run_on_the_three_named_systems():
    for name, (label, *_rest) in {**LINUX_BUILDS, **MACOS_BUILDS}.items():
        assert JOBS[name]["runs-on"] == label


def test_every_job_after_the_plan_checks_out_the_ref_the_plan_checked():
    found = list(_non_plan_checkouts())
    assert len(found) >= 6
    for name, step in found:
        assert step["with"]["ref"] == "${{ needs.plan.outputs.ref }}", name


def test_every_build_packages_the_tag_the_plan_checked():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        checkout = [s for s in _steps(name) if "checkout" in s.get("uses", "")]
        assert len(checkout) == 1, name
        assert checkout[0]["with"]["ref"] == "${{ needs.plan.outputs.ref }}"


def test_the_build_image_is_pinned_by_digest_or_the_job_refuses_to_run():
    value = str(DATA["env"]["ALMALINUX_9_DIGEST"])
    assert value == DIGEST_PLACEHOLDER or re.fullmatch(r"[0-9a-f]{64}", value)
    for name in LINUX_BUILDS:
        text = _run_text(name)
        # The check comes first and refuses anything that is not 64 hex
        # digits; the refusal names the digest the tag has now.
        check = text.index("[0-9a-f]{64}")
        pinned_pull = text.index('docker pull "almalinux@sha256:${ALMALINUX_9_DIGEST}"')
        assert check < pinned_pull
        assert "almalinux:9" in text[check:pinned_pull]
        # After the pinned pull no line names the image by tag.
        assert "almalinux:" not in text[pinned_pull:]
        assert ":latest" not in text


def test_the_build_image_check_names_the_system_python_libc_and_packages():
    for name in LINUX_BUILDS:
        text = _run_text(name)
        assert 'test "$ID" = almalinux' in text
        assert "VERSION_ID" in text
        assert "python3.12 python3.12-pip" in text
        assert "Py_ENABLE_SHARED" in text
        assert "libpython3.12" in text
        assert "rpm -q" in text and "glibc" in text and "2.34" in text
        assert "2.28" not in text
        assert 'case "$VERSION_ID" in 9|9.*)' in text
        assert "build-image" in text


def test_the_build_image_is_almalinux_9_and_no_older_image_is_left():
    assert "ALMALINUX_8_DIGEST" not in TEXT
    for name in LINUX_BUILDS:
        assert "almalinux:8" not in _run_text(name)
        assert "ALMALINUX_9_DIGEST" in _run_text(name)


def test_the_glibc_floor_is_named_once_in_a_comment_and_never_as_2_28():
    # Architect ruling 2 of package-dryrun-1: the floor is glibc 2.34.
    comments = _comment_text()
    assert len(re.findall(r"glibc 2\.34", comments)) == 1
    assert "2_28" not in TEXT


def test_the_linux_builds_use_the_scripts_of_the_repository_and_the_lock():
    for name in LINUX_BUILDS:
        text = _run_text(name)
        assert "scripts/packaging/build_binary.sh venv" in text
        assert "python3.12" in text
        assert "scripts/packaging/build_binary.sh build" in text
        assert "scripts/packaging/build_linux_packages.sh" in text
        # No install of our own: the script installs from the hash-pinned lock.
        assert "pip install" not in text
        assert "--no-selftest" not in text
        # The source tree is mounted read-only into the build container.
        assert ":/src:ro" in text


def test_the_two_linux_builds_run_the_same_commands_and_differ_in_env_only():
    a, b = (JOBS[n] for n in LINUX_BUILDS)
    # The install smoke of the arm64 packages is the one difference (B3b):
    # the x86_64 packages are installed by smoke-linux.
    arm64 = "\n".join(
        step.get("run", "")
        for step in _steps("build-linux-arm64")
        if "smoke container" not in step.get("name", "")
        and not step.get("name", "").startswith("Install smoke")
    )
    assert _run_text("build-linux-x86_64") == arm64
    assert a["env"]["CPU"] == "x86_64" and b["env"]["CPU"] == "arm64"


def test_nfpm_is_pinned_by_version_and_sha256_and_checked_before_use():
    assert str(DATA["env"]["NFPM_VERSION"]) == "2.49.0"
    for name, (_label, cpu, _arch) in LINUX_BUILDS.items():
        assert JOBS[name]["env"]["NFPM_SHA256"] == NFPM_SHA256[cpu]
        run = [s["run"] for s in _steps(name) if "sha256sum -c" in s.get("run", "")]
        assert len(run) == 1
        assert run[0].index("sha256sum -c") < run[0].index("tar -x")
        assert "nfpm_${NFPM_VERSION}_Linux_${CPU}" in run[0]


def test_the_macos_builds_use_python_3_12_and_gnu_tar_and_the_same_scripts():
    for name in MACOS_BUILDS:
        steps = _steps(name)
        python = [s for s in steps if "setup-python" in s.get("uses", "")]
        assert python and python[0]["with"]["python-version"].startswith("3.12")
        text = _run_text(name)
        assert "gnu-tar" in text and "gnubin" in text
        assert "scripts/packaging/build_binary.sh venv" in text
        assert "scripts/packaging/build_binary.sh build" in text
        assert "--no-selftest" not in text
        assert "pip install" not in text


def test_the_macos_build_asks_for_the_python_patch_version_that_the_licence_check_pins():
    # B6 fix 1: a pin in the licence check alone is a tripwire that fails after
    # the PyPI publish. The workflow asks for the same patch version.
    pinned = _pinned_python()["darwin"]
    want = ".".join(str(part) for part in pinned)
    for name in MACOS_BUILDS:
        python = [s for s in _steps(name) if "setup-python" in s.get("uses", "")]
        assert python[0]["with"]["python-version"] == want


def test_every_build_uploads_its_files_and_fails_when_there_are_none():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        upload = [
            s for s in _steps(name) if s.get("uses", "").startswith("actions/upload-")
        ]
        # One upload of the files of the build; the macOS build has a second
        # one for its build record (evidence, B3d).
        files = [u for u in upload if u["with"]["name"] == name]
        assert len(files) == 1, name
        assert len(upload) == (2 if name in MACOS_BUILDS else 1), name
        assert files[0]["with"]["if-no-files-found"] == "error"
        text = _run_text(name)
        assert "THIRD-PARTY-LICENSES" in text and "components.json" in text


def test_the_scripts_a_build_calls_exist_in_the_repository():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        for path in set(re.findall(r"scripts/packaging/[\w.]+", _run_text(name))):
            assert (ROOT / path).is_file(), (name, path)


# ---- stage 3: smoke tests on fresh systems --------------------------------

SMOKE_SYSTEMS = {
    # system: (image, format) as in plan 3.5 and architect ruling 2 of
    # package-dryrun-1: almalinux:9 is the glibc floor system (2.34), and
    # amazonlinux:2023 is added (rpm)
    "ubuntu-22.04": ("ubuntu:22.04", "deb"),
    "ubuntu-24.04": ("ubuntu:24.04", "deb"),
    "debian-12": ("debian:12", "deb"),
    "debian-12-tar": ("debian:12", "tar"),
    "fedora": ("fedora:latest", "rpm"),
    "rockylinux-9": ("rockylinux:9", "rpm"),
    "rockylinux-9-tar": ("rockylinux:9", "tar"),
    "almalinux-9": ("almalinux:9", "rpm"),
    "amazonlinux-2023": ("amazonlinux:2023", "rpm"),
}


def _matrix(job):
    return JOBS[job]["strategy"]["matrix"]["include"]


def test_the_workflow_never_hides_a_failure():
    code = "\n".join(
        line for line in TEXT.splitlines() if not line.lstrip().startswith("#")
    )
    assert "continue-on-error" not in code
    assert "|| true" not in code
    assert "set +e" not in code


def test_the_linux_smoke_matrix_covers_the_systems_of_the_plan():
    seen = {m["system"]: (m["image"], m["format"]) for m in _matrix("smoke-linux")}
    assert seen == SMOKE_SYSTEMS
    assert JOBS["smoke-linux"]["strategy"]["fail-fast"] is False
    assert JOBS["smoke-linux"]["needs"] == ["plan", "build-linux-x86_64"]


def test_the_smoke_matrix_has_no_almalinux_8_and_floors_on_almalinux_9():
    images = {m["image"] for m in _matrix("smoke-linux")}
    assert "almalinux:8" not in images
    assert {"almalinux:9", "amazonlinux:2023"} <= images
    assert "2.28" not in TEXT


def test_the_smoke_installs_each_format_the_way_a_user_does():
    text = _run_text("smoke-linux")
    assert "dpkg -i" in text
    assert "dnf install" in text
    assert "tar -xzf" in text
    assert "dpkg -r inventag" in text
    assert "dnf remove" in text
    # The deb is not blocked by the image's own exclusion of man pages.
    assert "/etc/dpkg/dpkg.cfg.d/excludes" in text


def test_the_smoke_runs_version_selftest_man_and_three_completions():
    text = _run_text("smoke-linux")
    assert "inventag --version" in text and '"inventag $VERSION"' in text
    assert "inventag selftest" in text
    assert 'gzip -dc "$page"' in text and ".TH INVENTAG 1 " in text
    for check in ("bash -n", "zsh -n", "fish -n"):
        assert check in text
    for matrix in _matrix("smoke-linux"):
        assert set(matrix["shells"].split()) <= {"bash", "zsh", "fish"}
        assert "bash" in matrix["shells"].split()


def test_the_smoke_scan_runs_against_a_moto_server_outside_the_executable():
    text = _run_text("smoke-linux")
    assert "scripts/packaging/smoke_scan.py" in text
    assert "docker exec" in text and "AWS_ENDPOINT_URL" in text
    assert "--network host" in text
    pins = [
        s["run"]
        for s in _steps("smoke-linux")
        if "pip install" in s.get("run", "") and "moto" in s["run"]
    ]
    assert len(pins) == 1
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    pinned = re.search(r"^moto\[all\]==([\d.]+)", dev, re.M).group(1)
    assert f'"moto[server]=={pinned}"' in pins[0]


def test_the_smoke_checks_that_the_uninstall_left_nothing():
    text = _run_text("smoke-linux")
    assert "/opt/inventag" in text
    assert "left:" in text
    assert "command -v inventag" in text


def test_the_macos_smoke_jobs_unpack_run_scan_and_remove():
    for name, (label, cpu) in {
        "smoke-macos-arm64": MACOS_BUILDS["build-macos-arm64"],
    }.items():
        job = JOBS[name]
        assert job["runs-on"] == label
        assert job["needs"] == ["plan", f"build-macos-{cpu}"]
        text = _run_text(name)
        assert "tar -xzf" in text
        assert '"$BIN/inventag" selftest' in text
        assert '"inventag $VERSION"' in text
        assert "scripts/packaging/smoke_scan.py" in text
        assert "rm -rf" in text
        for check in ("bash -n", "zsh -n"):
            assert check in text


def test_the_macos_smoke_runs_version_and_selftest_before_any_python_is_set_up():
    # B6 fix 8: after setup-python the runner holds the Python that built the
    # bundle, so a stray absolute link would resolve there and not on a user's
    # Mac. The proof of --version and selftest comes first; the scan (which
    # needs Python for the moto server) comes after.
    steps = _steps("smoke-macos-arm64")
    python = [i for i, s in enumerate(steps) if "setup-python" in s.get("uses", "")]
    assert len(python) == 1
    before = "\n".join(s.get("run", "") for s in steps[: python[0]])
    after = "\n".join(s.get("run", "") for s in steps[python[0] :])
    assert "tar -xzf" in before
    assert '"$BIN/inventag" --version' in before
    assert '"$BIN/inventag" selftest' in before
    assert "env -i PATH=/usr/bin:/bin" in before
    assert "selftest" not in after.replace("smoke_scan", "")
    assert "scripts/packaging/smoke_scan.py" in after and "scripts/packaging/smoke_scan.py" not in before
    # Nothing before the Python step uses Python.
    assert "python" not in before.lower().replace("setup-python", "")


def test_the_pipx_install_of_the_wheel_is_smoked():
    job = JOBS["smoke-pipx"]
    assert job["runs-on"] == "ubuntu-24.04"
    text = _run_text("smoke-pipx")
    assert "pip wheel --no-deps" in text
    assert "pipx install" in text and "pipx uninstall inventag-aws" in text
    assert "inventag selftest" in text


UV_SHA256 = re.compile(r"--hash=sha256:[0-9a-f]{64}")


def test_uv_installs_the_wheel_runs_it_and_removes_it_with_uv_pinned_by_version_and_sha256():
    # B6 fix 3, way (a): the sentence "uv tool install gives the same result"
    # of the install page cites this step.
    step = _step("smoke-pipx", "uv")
    run = step["run"]
    assert re.search(r"uv==\d+\.\d+\.\d+", run)
    assert "--require-hashes" in run and UV_SHA256.search(run)
    assert "--only-binary" in run
    steps = [s.get("name", "") for s in _steps("smoke-pipx")]
    assert steps.index(step["name"]) > steps.index(
        "Build the wheel, install it with pipx, run it, remove it"
    )
    # The wheel of the commit, not the file of PyPI.
    assert re.search(r"uv tool install .*inventag_aws-", run)
    assert 'test "$(inventag --version)" = "inventag $VERSION"' in run
    assert "inventag selftest" in run
    assert "uv tool uninstall inventag-aws" in run
    # The program must be gone from the PATH after the uninstall.
    assert "hash -r" in run and "command -v inventag" in run
    assert run.index("uv tool uninstall") < run.index("command -v inventag")
    assert "left: inventag is still on the PATH" in run


def test_the_smoke_jobs_use_the_artifacts_of_their_build():
    for name in ("smoke-linux", "smoke-macos-arm64"):
        down = [
            s for s in _steps(name) if s.get("uses", "").startswith("actions/download-")
        ]
        assert len(down) == 1, name
        build = [n for n in JOBS[name]["needs"] if n.startswith("build-")][0]
        assert down[0]["with"]["name"] == build


# ---- stage 4: provenance (notices addresses, SBOMs, checksums, attestation) and publish

BUILDS_AND_SMOKES = {
    "build-linux-x86_64",
    "build-linux-arm64",
    "build-macos-arm64",
    "smoke-linux",
    "smoke-macos-arm64",
    "smoke-pipx",
}
GNU_PAGE = "https://www.gnu.org/software/libiconv/"
GNU_TARBALL = "https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz"


def _step(job, fragment):
    found = [s for s in _steps(job) if fragment in s.get("name", "")]
    assert len(found) == 1, (job, fragment, [s.get("name") for s in _steps(job)])
    return found[0]


def _heredoc(run, tag):
    return re.search(rf"<<'{tag}'\n(.*?)\n\s*{tag}\n", run, re.S).group(1)


def test_provenance_waits_for_every_build_and_every_smoke_test():
    assert set(JOBS["provenance"]["needs"]) == BUILDS_AND_SMOKES | {"plan"}
    assert JOBS["provenance"]["runs-on"] == "ubuntu-24.04"


def test_provenance_takes_the_files_of_the_builds_and_nothing_else():
    down = _step("provenance", "Download the files of the builds")
    assert down["with"]["pattern"] == "build-*"
    assert down["with"]["merge-multiple"] is True


def _libiconv_run(tmp_path, notices, stub_fails=""):
    """Run the notices-address step with a stub curl; return (exit code, requested URLs)."""
    import subprocess
    import tarfile

    release = tmp_path / "release"
    release.mkdir()
    for name, text in notices.items():
        (release / name).write_text(text, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"
    payload = tmp_path / "libiconv-1.18"
    payload.mkdir()
    (payload / "README").write_text("libiconv", encoding="utf-8")
    sample = tmp_path / "sample.tar.gz"
    with tarfile.open(sample, "w:gz") as archive:
        archive.add(payload, arcname="libiconv-1.18")
    stub = bin_dir / "curl"
    stub.write_text(
        "#!/bin/bash\n"
        'out=""; url=""\n'
        'while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2;;'
        ' --max-time|--retry) shift 2;; -*) shift;; *) url="$1"; shift;; esac; done\n'
        f'echo "$url" >> "{calls}"\n'
        f'case "$url" in *"{stub_fails}"*) [ -n "{stub_fails}" ] && exit 22;; esac\n'
        f'case "$url" in *.tar.gz) cp "{sample}" "$out";; *) echo page > "$out";; esac\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    summary = tmp_path / "summary.md"
    script = _step("provenance", "libiconv")["run"]
    result = subprocess.run(
        ["bash", "-c", script],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    urls = calls.read_text("utf-8").split() if calls.exists() else []
    return result, urls


GOOD_NOTICE = (
    "- GNU libiconv, linked into lxml's extension modules 1.18: LGPL-2.1\n"
    f"    source: {GNU_PAGE}\n"
    f"    source: {GNU_TARBALL}\n"
    "    source: https://github.com/lxml/lxml\n"
)


def test_the_provenance_job_requests_both_libiconv_addresses_of_each_notices_file(
    tmp_path,
):
    # Architect review F2: an address in a notices file is a claim that the
    # source is there; the job fetches both before a release carries them.
    result, urls = _libiconv_run(
        tmp_path, {"inventag-1.4.0-linux-x86_64.THIRD-PARTY-LICENSES.txt": GOOD_NOTICE}
    )
    assert result.returncode == 0, result.stderr
    assert GNU_PAGE in urls and GNU_TARBALL in urls
    assert "https://github.com/lxml/lxml" not in urls


def test_the_provenance_job_fails_when_the_versioned_tarball_cannot_be_fetched(
    tmp_path,
):
    result, urls = _libiconv_run(
        tmp_path,
        {"a.THIRD-PARTY-LICENSES.txt": GOOD_NOTICE},
        stub_fails="libiconv-1.18.tar.gz",
    )
    assert result.returncode != 0
    assert GNU_TARBALL in urls


def test_the_provenance_job_fails_when_the_gnu_page_cannot_be_fetched(tmp_path):
    result, _urls = _libiconv_run(
        tmp_path,
        {"a.THIRD-PARTY-LICENSES.txt": GOOD_NOTICE},
        stub_fails="software/libiconv/",
    )
    assert result.returncode != 0


def test_the_provenance_job_fails_when_a_notices_file_lost_an_address(tmp_path):
    only_page = f"    source: {GNU_PAGE}\n"
    result, _urls = _libiconv_run(tmp_path, {"a.THIRD-PARTY-LICENSES.txt": only_page})
    assert result.returncode != 0


def test_the_provenance_job_fails_when_there_is_no_notices_file(tmp_path):
    result, _urls = _libiconv_run(tmp_path, {})
    assert result.returncode != 0


def test_a_downloaded_tarball_that_is_not_libiconv_fails_the_job(tmp_path):
    notice = (
        f"    source: {GNU_PAGE}\n"
        "    source: https://ftp.gnu.org/pub/gnu/libiconv/libiconv-9.99.tar.gz\n"
    )
    # The stub serves a tarball holding libiconv-1.18/: not the 9.99 asked for.
    result, _urls = _libiconv_run(tmp_path, {"a.THIRD-PARTY-LICENSES.txt": notice})
    assert result.returncode != 0


def test_the_sbom_script_writes_stable_cyclonedx_for_every_artefact(tmp_path):
    import json
    import subprocess

    components = [
        {
            "name": "boto3",
            "version": "1.44.6",
            "licence": "Apache-2.0",
            "section": "package",
            "files": [],
        },
        {
            "name": "CPython",
            "version": "3.12.1",
            "licence": "PSF-2.0",
            "section": "runtime",
            "files": [],
        },
        {
            "name": "GNU libiconv, linked into lxml's extension modules",
            "version": "1.18",
            "licence": "LGPL-2.1",
            "section": "library",
            "files": ["_internal/lxml/etree.so"],
        },
    ]
    release = tmp_path / "release"
    release.mkdir()
    for cpu in ("x86_64", "arm64"):
        (release / f"inventag-1.4.0-linux-{cpu}.components.json").write_text(
            json.dumps(components), encoding="utf-8"
        )
    for name in (
        "inventag-1.4.0-linux-x86_64.tar.gz",
        "inventag-1.4.0-linux-arm64.tar.gz",
        "inventag_1.4.0_amd64.deb",
        "inventag_1.4.0_arm64.deb",
        "inventag-1.4.0-1.x86_64.rpm",
        "inventag-1.4.0-1.aarch64.rpm",
    ):
        (release / name).write_bytes(b"x")
    script = _heredoc(_step("provenance", "SBOM")["run"], "PY")

    def run():
        done = subprocess.run(
            ["python3", "-I", "-", str(release), "1.4.0"],
            input=script,
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert done.returncode == 0, done.stderr
        return {p.name: p.read_bytes() for p in release.glob("*.cdx.json")}

    first = run()
    assert sorted(first) == sorted(
        f"{name}.cdx.json"
        for name in (
            "inventag-1.4.0-linux-x86_64.tar.gz",
            "inventag-1.4.0-linux-arm64.tar.gz",
            "inventag_1.4.0_amd64.deb",
            "inventag_1.4.0_arm64.deb",
            "inventag-1.4.0-1.x86_64.rpm",
            "inventag-1.4.0-1.aarch64.rpm",
        )
    )
    assert run() == first
    bom = json.loads(first["inventag_1.4.0_arm64.deb.cdx.json"])
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.5"
    assert "timestamp" not in json.dumps(bom) and "serialNumber" not in bom
    assert bom["metadata"]["component"]["version"] == "1.4.0"
    names = [c["name"] for c in bom["components"]]
    assert names == sorted(names, key=str.lower) or names == sorted(names)
    boto = [c for c in bom["components"] if c["name"] == "boto3"][0]
    assert boto["purl"] == "pkg:pypi/boto3@1.44.6"
    assert boto["licenses"] == [{"expression": "Apache-2.0"}]


def test_the_checksums_cover_every_file_sorted_and_are_checked_at_once():
    run = _step("provenance", "checksums")["run"]
    assert "SHA256SUMS" in run
    assert "LC_ALL=C" in run and "sort" in run
    assert "sha256sum -c SHA256SUMS" in run
    assert "! -name SHA256SUMS" in run


def test_the_attestation_is_keyless_and_only_made_for_a_real_release():
    step = _step("attest", "attest")
    assert step["uses"].startswith("actions/attest@")
    assert step["with"]["subject-checksums"].endswith("/release/SHA256SUMS")
    assert "private-key" not in str(step) and "secret" not in str(step).lower()
    # No step of provenance attests anything any more.
    for provenance_step in _steps("provenance"):
        assert "actions/attest" not in provenance_step.get("uses", "")


def test_the_attest_job_never_runs_on_a_pull_request_and_is_the_only_one_with_a_token_for_it():
    # B6 fix 5: a same-repository pull request runs the workflow file of its
    # own branch; a job with id-token and attestations: write that a pull
    # request can start could sign files that pass `gh attestation verify`.
    job = JOBS["attest"]
    condition = " ".join(str(job["if"]).split())
    assert "github.event_name != 'pull_request'" in condition
    assert "needs.plan.outputs.dry_run == 'false'" in condition
    assert set(job["needs"]) == {"plan", "provenance"}
    assert job["runs-on"] == "ubuntu-24.04"
    # It signs the files provenance kept, after checking them once more.
    down = [s for s in _steps("attest") if s.get("uses", "").startswith("actions/download-")]
    assert len(down) == 1 and down[0]["with"]["name"] == "release-files"
    run = _run_text("attest")
    assert "sha256sum -c SHA256SUMS" in run
    names = [s.get("name", "") for s in _steps("attest")]
    assert names.index(_step("attest", "attest")["name"]) == len(names) - 1
    # Nothing else in the workflow names id-token or attestations.
    for name, other in JOBS.items():
        if name != "attest":
            assert "id-token" not in other["permissions"], name
            assert "attestations" not in other["permissions"], name


def test_provenance_keeps_the_release_files_for_the_publish_job():
    up = _step("provenance", "Keep the release files")
    assert up["with"]["name"] == "release-files"
    assert up["with"]["if-no-files-found"] == "error"


def test_publish_attaches_to_the_release_only_when_it_is_not_a_dry_run():
    job = JOBS["publish"]
    assert job["needs"] == ["plan", "provenance", "attest"]
    assert job["if"] == "needs.plan.outputs.dry_run == 'false'"
    assert job["permissions"] == {"contents": "write"}
    assert job["env"]["GH_TOKEN"] == "${{ github.token }}"
    run = _run_text("publish")
    assert "gh release upload" in run and "--clobber" in run
    assert "gh release view" in run
    assert not [s for s in _steps("publish") if "checkout" in s.get("uses", "")]


def test_nothing_but_publish_touches_the_release():
    for name, step in _all_steps():
        if name != "publish":
            assert "gh release" not in step.get("run", ""), name
            assert "gh api" not in step.get("run", ""), name


# ---- stage 5: the job of release.yml that calls this workflow --------------

RELEASE_DATA = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
RELEASE_JOBS = RELEASE_DATA["jobs"]


def test_release_yml_calls_this_workflow_in_one_last_job():
    called = {n: j for n, j in RELEASE_JOBS.items() if "uses" in j}
    assert list(called) == ["package"]
    job = called["package"]
    assert job["uses"] == "./.github/workflows/package.yml"
    assert job["with"]["tag"] == "v${{ needs.release.outputs.new_version }}"
    assert job["with"]["dry_run"] is False
    assert "steps" not in job and "runs-on" not in job


def test_the_package_job_runs_after_pypi_and_only_for_a_release_that_was_made():
    job = RELEASE_JOBS["package"]
    assert set(job["needs"]) == {"check-for-release", "release", "publish-pypi"}
    condition = " ".join(job["if"].split())
    assert "always()" in condition
    assert "needs.check-for-release.outputs.should_release == 'true'" in condition
    assert "needs.release.result == 'success'" in condition
    # PyPI published, or was switched off by the repository variable; a failed
    # or cancelled publish stops the packaging.
    assert "needs.publish-pypi.result == 'success'" in condition
    assert "needs.publish-pypi.result == 'skipped'" in condition


def test_no_other_job_of_the_release_waits_for_the_package_job():
    for name, job in RELEASE_JOBS.items():
        needs = job.get("needs", [])
        needs = [needs] if isinstance(needs, str) else needs
        assert "package" not in needs, name


def test_the_package_job_grants_what_the_called_jobs_use_and_no_more():
    permissions = RELEASE_JOBS["package"]["permissions"]
    assert permissions == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }
    # Every permission the called workflow's jobs use is inside that grant.
    for job in JOBS.values():
        for key, value in job["permissions"].items():
            assert value == "read" or permissions.get(key) == value


def test_the_package_job_passes_no_secret_and_leaves_the_other_jobs_alone():
    job = RELEASE_JOBS["package"]
    assert "secrets" not in job
    for name in ("check-for-release", "release", "publish-pypi"):
        assert "package" not in str(RELEASE_JOBS[name].get("outputs", {}))


# ---- B3b: the pull request trigger and the release.yml job -----------------


def _comment_text():
    lines = [
        ln.lstrip()[1:].strip()
        for ln in TEXT.splitlines()
        if ln.lstrip().startswith("#")
    ]
    return " ".join(" ".join(lines).split())


def test_the_workflow_says_why_the_release_job_waits_for_v1_4_0():
    comment = _comment_text()
    assert "job of release.yml must not reach main before v1.4.0" in comment
    assert "pull request" in comment and "dry run" in comment


# What the `package` job of release.yml packages. A tree that lacks one of
# these files must not call package.yml: a v1.3.2 patch made from main would
# start packaging a tag that has no packaging/ (architect review of B3, M2).
PACKAGED_FILES = (
    "packaging/nfpm/nfpm.yaml",
    "scripts/packaging/build_binary.sh",
    "scripts/packaging/build_linux_packages.sh",
    "inventag/cli/selftest.py",
    "inventag/cli/completion.py",
    "requirements-lock.txt",
    "requirements-lock-build.txt",
)


def _calls_package(release_text):
    jobs = yaml.safe_load(release_text)["jobs"]
    return any(j.get("uses", "").endswith("/package.yml") for j in jobs.values())


def _release_job_is_safe(release_text, tree):
    """True when release.yml has no package job, or the tree holds what it packages."""
    if not _calls_package(release_text):
        return True
    return all((Path(tree) / name).is_file() for name in PACKAGED_FILES)


def test_a_release_job_for_a_tree_without_packaging_is_not_safe(tmp_path):
    with_job = RELEASE.read_text(encoding="utf-8")
    assert _calls_package(with_job)
    assert not _release_job_is_safe(with_job, tmp_path)
    (tmp_path / "packaging" / "nfpm").mkdir(parents=True)
    for name in PACKAGED_FILES[:-1]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    assert not _release_job_is_safe(with_job, tmp_path)  # one file still missing
    (tmp_path / PACKAGED_FILES[-1]).write_text("", encoding="utf-8")
    assert _release_job_is_safe(with_job, tmp_path)


def test_a_release_without_the_package_job_is_safe_anywhere(tmp_path):
    text = "jobs:\n  release:\n    runs-on: ubuntu-24.04\n"
    assert _release_job_is_safe(text, tmp_path)


def test_the_release_job_is_only_in_a_tree_that_holds_what_it_packages():
    # On main before v1.4.0 this fails if the job was cherry-picked there
    # without the packaging files; on next/v1.4 it holds.
    assert _release_job_is_safe(RELEASE.read_text(encoding="utf-8"), ROOT)


# ---- B3b: the digest of every image a smoke test pulled --------------------


def _digest_step_run(job, fragment="digest"):
    return _step(job, fragment)["run"]


PULL_OUTPUT = (
    "Using default tag: latest\n"
    "12: Pulling from library/debian\n"
    "69245854ad58: Pull complete\n"
    "Digest: sha256:" + "ab" * 32 + "\n"
    "Status: Downloaded newer image for debian:12\n"
    "docker.io/library/debian:12\n"
)
SOME_DIGEST = "sha256:" + "ab" * 32


def _run_digest(tmp_path, run, pull_output=PULL_OUTPUT, image="debian:12"):
    """Run a digest-recording step with a stub docker; return (result, summary text, calls).

    The stub is the docker of the runner as the dry run 6 log shows it: `pull`
    prints the pull text with its "Digest:" line, `image inspect` prints an
    empty string (RepoDigests is empty there), everything else prints an id.
    """
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    calls = tmp_path / "docker.log"
    text = tmp_path / "pull.txt"
    text.write_text(pull_output, encoding="utf-8")
    stub = bin_dir / "docker"
    stub.write_text(
        "#!/bin/bash\n"
        f'echo "$@" >> "{calls}"\n'
        'case "$1" in\n'
        f'  pull) cat "{text}" ;;\n'
        "  image) ;;\n"
        "  *) echo 815aa372d99e ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", run],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "IMAGE": image,
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    called = calls.read_text("utf-8") if calls.exists() else ""
    return result, summary.read_text("utf-8"), called


def test_every_linux_smoke_job_writes_the_digest_of_its_image_to_the_job_summary(
    tmp_path,
):
    steps = _steps("smoke-linux")
    names = [s.get("name", "") for s in steps]
    # The image is pulled by an explicit `docker pull`, before the container
    # starts and before anything is installed.
    assert names.index("Record the digest of the image") < names.index(
        "Start a fresh system"
    )
    assert names.index("Start a fresh system") < names.index("Install the package")
    result, summary, calls = _run_digest(tmp_path, _digest_step_run("smoke-linux"))
    assert result.returncode == 0, result.stderr
    assert calls.splitlines()[0] == "pull debian:12"
    # dry run 6: RepoDigests is empty on the runner after the pull.
    assert (
        "RepoDigests" not in _digest_step_run("smoke-linux")
        and "image inspect" not in calls
    )
    assert f"debian:12: {SOME_DIGEST}" in summary


BAD_PULLS = {
    "no Digest line": "Status: Image is up to date for debian:12\n",
    "63 hex digits": "Digest: sha256:" + "ab" * 31 + "a\n",
    "65 hex digits": "Digest: sha256:" + "ab" * 32 + "c\n",
    "upper case": "Digest: sha256:" + "AB" * 32 + "\n",
    "not at the start of a line": "Pulled. Digest: sha256:" + "ab" * 32 + "\n",
    "another algorithm": "Digest: sha512:" + "ab" * 32 + "\n",
}


def test_a_smoke_image_with_no_recorded_digest_fails_the_job(tmp_path):
    for index, (why, pulled) in enumerate(BAD_PULLS.items()):
        work = tmp_path / str(index)
        work.mkdir()
        result, summary, _ = _run_digest(
            work, _digest_step_run("smoke-linux"), pull_output=pulled
        )
        assert result.returncode != 0, why
        assert "digest" in result.stdout + result.stderr, why
        assert "sha256" not in summary, why


def test_no_digest_is_typed_into_the_workflow_for_a_smoke_image():
    # The digests are written by each run (job summary); the only value typed
    # here is the build image's, which the dry run prints (placeholder). The
    # one other digest is uv's wheel in `--hash=sha256:` form (B3i-2).
    typed = re.findall(r"(?<!--hash=)sha256:[0-9a-f]{64}", TEXT)
    assert typed == []


# ---- B3b: install smoke of the arm64 packages (architect ruling 3) ---------

ARM64_SMOKES = {
    # step name fragment: (image, install, uninstall)
    ".deb on debian:12": (
        "debian:12",
        "dpkg -i /pkg/inventag_*_arm64.deb",
        "dpkg -r inventag",
    ),
    ".rpm on rockylinux:9": (
        "rockylinux:9",
        "dnf install -y -q /pkg/inventag-*.aarch64.rpm",
        "dnf remove -y -q inventag",
    ),
}


def _arm64_names():
    return [s.get("name", "") for s in _steps("build-linux-arm64")]


def test_the_arm64_build_installs_its_deb_and_rpm_in_fresh_containers_on_the_same_runner():
    names = _arm64_names()
    built = names.index("Build the .deb and the .rpm")
    uploaded = names.index("Upload the files of this build")
    for fragment, (image, install, uninstall) in ARM64_SMOKES.items():
        start = _step("build-linux-arm64", f"Start smoke container: {fragment}")
        check = _step("build-linux-arm64", f"Install smoke: {fragment}")
        remove = _step("build-linux-arm64", f"Remove smoke container: {fragment}")
        # Between the build of the packages and the upload: a package that
        # does not install is never uploaded.
        order = [names.index(s["name"]) for s in (start, check, remove)]
        assert built < order[0] < order[1] < order[2] < uploaded
        assert start["env"]["IMAGE"] == image
        # The packages the build made, read-only, in a fresh container.
        assert "$RUNNER_TEMP/work/out/pkg:/pkg:ro" in start["run"]
        run = check["run"]
        assert install in run and uninstall in run
        # It really ran on arm64 (not under emulation of another CPU).
        assert 'test "$(uname -m)" = aarch64' in run
        assert 'test "$(inventag --version)" = "inventag $VERSION"' in run
        assert "inventag selftest" in run
        # Nothing is left on the PATH after the uninstall.
        assert "command -v inventag" in run
        # The container goes whether the checks passed or not.
        assert remove["if"] == "always()"
        assert "docker rm -f" in remove["run"]


def test_the_arm64_smoke_images_are_pulled_explicitly_and_their_digest_is_recorded(
    tmp_path,
):
    for index, (fragment, (image, _, _)) in enumerate(ARM64_SMOKES.items()):
        start = _step("build-linux-arm64", f"Start smoke container: {fragment}")
        work = tmp_path / str(index)
        work.mkdir()
        result, summary, calls = _run_digest(work, start["run"], image=image)
        assert result.returncode == 0, result.stderr
        lines = calls.splitlines()
        # The pull comes first; the container starts only after the digest is known.
        assert lines[0] == f"pull {image}"
        assert lines[1].startswith("run -d --name smoke-")
        assert "image inspect" not in calls
        assert f"{image}: {SOME_DIGEST}" in summary
        for why, pulled in BAD_PULLS.items():
            empty = work / why.replace(" ", "-")
            empty.mkdir()
            refused, bad_summary, bad_calls = _run_digest(
                empty, start["run"], pull_output=pulled, image=image
            )
            assert refused.returncode != 0, why
            assert "sha256" not in bad_summary, why
            # No container is started without a recorded digest.
            assert "run -d" not in bad_calls, why


def test_the_arm64_smoke_is_in_the_arm64_job_only_with_no_new_runner_label():
    names = [n.get("name", "") for n in _steps("build-linux-x86_64")]
    assert not [n for n in names if "smoke" in n.lower()]
    assert JOBS["build-linux-arm64"]["runs-on"] == "ubuntu-24.04-arm"
    assert set(JOBS) == {
        "plan",
        "build-linux-x86_64",
        "build-linux-arm64",
        "build-macos-arm64",
        "smoke-linux",
        "smoke-macos-arm64",
        "smoke-pipx",
        "provenance",
        "attest",
        "publish",
    }


# ---- B3d: the uninstall check must not be fooled by bash's command cache ---


def _pipx_run_with_stubs(tmp_path, leave="nothing"):
    """Run the pipx smoke step with a stub python and a stub inventag.

    `leave`: "nothing" (uninstall removes the program), "file" (uninstall
    leaves it), "second" (uninstall removes it, but another inventag is
    installed in a later PATH directory).
    """
    import subprocess

    pipx_bin = tmp_path / "pipx_bin"
    other_bin = tmp_path / "other_bin"
    stubs = tmp_path / "stubs"
    for directory in (pipx_bin, other_bin, stubs, tmp_path / "home", tmp_path / "dist"):
        directory.mkdir(exist_ok=True)
    program = (
        "#!/bin/bash\n" 'if [ "$1" = --version ]; then echo "inventag $VERSION"; fi\n'
    )
    (other_bin / "inventag").write_text(program, encoding="utf-8")
    (other_bin / "inventag").chmod(0o755)
    if leave != "second":
        (other_bin / "inventag").unlink()
    (stubs / "python").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        f'  "-m pipx install"*) cp "{other_bin}/../prog" "{pipx_bin}/inventag" ;;\n'
        f'  "-m pipx uninstall"*) [ "{leave}" = file ] || rm -f "{pipx_bin}/inventag" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    (stubs / "python").chmod(0o755)
    (tmp_path / "prog").write_text(program, encoding="utf-8")
    (tmp_path / "prog").chmod(0o755)
    run = _step("smoke-pipx", "Build the wheel")["run"]
    return subprocess.run(
        ["bash", "-e", "-c", run],
        env={
            # the pipx bin directory is on the PATH before the step starts, as
            # /opt/pipx_bin is on the runner (dry run 6)
            "PATH": f"{stubs}:{pipx_bin}:{other_bin}:/usr/bin:/bin",
            "HOME": str(tmp_path / "home"),
            "RUNNER_TEMP": str(tmp_path),
            "VERSION": "1.3.1",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_pipx_uninstall_check_passes_when_the_program_is_gone_although_bash_hashed_it(
    tmp_path,
):
    # Dry run 6: `inventag --version` put /opt/pipx_bin/inventag into bash's
    # command cache; after the uninstall `command -v inventag` still printed
    # that path and the step failed with "left: inventag is still on the PATH".
    result = _pipx_run_with_stubs(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "left:" not in result.stdout


def test_the_pipx_uninstall_check_still_fails_when_the_program_is_left(tmp_path):
    result = _pipx_run_with_stubs(tmp_path, leave="file")
    assert result.returncode != 0
    assert "left: inventag is still on the PATH" in result.stdout


def test_the_pipx_uninstall_check_still_fails_when_a_second_inventag_is_on_the_path(
    tmp_path,
):
    result = _pipx_run_with_stubs(tmp_path, leave="second")
    assert result.returncode != 0
    assert "left: inventag is still on the PATH" in result.stdout


def test_every_path_check_after_an_uninstall_forgets_bashs_command_cache_first():
    # `command -v` answers from the cache of a command that ran before, even
    # when its file is gone. This applies to every uninstall check.
    checked = 0
    for job, step in _all_steps():
        run = step.get("run", "")
        lines = run.splitlines()
        for number, line in enumerate(lines):
            if "command -v inventag" in line:
                checked += 1
                assert any(
                    "hash -r" in earlier
                    for earlier in lines[max(0, number - 3) : number]
                ), (job, step.get("name"))
    # smoke-linux, the two arm64 smokes, pipx and uv
    assert checked == 5


# ---- B3d: the macOS evidence steps and the build record (b2f report) -------

UPLOAD_PIN = "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9"


def _macos_names():
    return [s.get("name", "") for s in _steps("build-macos-arm64")]


def test_the_macos_build_prints_its_evidence_between_the_build_and_the_collect_step():
    names = _macos_names()
    evidence = [n for n in names if "macOS evidence" in n]
    assert len(evidence) == 1
    built = names.index(
        "Build the executable, check the licences, run selftest, write the archive"
    )
    assert (
        built
        < names.index(evidence[0])
        < names.index("Collect the files of this build")
    )
    # Only the macOS build has it.
    for job, step in _all_steps():
        if job != "build-macos-arm64":
            assert "macOS evidence" not in step.get("name", "")


MACOS_EVIDENCE_COMMANDS = (
    'cat "$work/build-record-macos.txt"',
    "lipo -archs",
    "otool -L",
    "codesign -v",
    "codesign -dv",
    "shasum -a 256",
    "-iname '*licen*'",
    "-iname 'copying*'",
    "Stefan Krah",
    "decimal.__libmpdec_version__",
    "_lzma*.so",
    "'^5\\.[0-9]+\\.[0-9]+$'",
)


def test_the_macos_evidence_step_runs_the_commands_that_the_licence_rows_need():
    run = _step("build-macos-arm64", "macOS evidence")["run"]
    for command in MACOS_EVIDENCE_COMMANDS:
        assert command in run, command
    # Both the copy of lxml in the build environment and the one in the bundle.
    assert "$bundle/_internal/lxml/" in run and '"$site/$f"' in run


def test_the_macos_evidence_step_prints_every_section_with_the_tools_stubbed(tmp_path):
    import subprocess

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for tool in ("lipo", "otool", "codesign", "shasum", "strings"):
        (stubs / tool).write_text(
            '#!/bin/bash\necho "[$(basename "$0") $*]"\n'
            + ("echo 5.8.4\n" if tool == "strings" else ""),
            encoding="utf-8",
        )
        (stubs / tool).chmod(0o755)
    work = tmp_path / "work"
    site = tmp_path / "venv" / "site" / "lxml"
    bundle_lxml = work / "dist" / "inventag" / "_internal" / "lxml"
    lib_dynload = (
        work / "dist" / "inventag" / "_internal" / "python3.12" / "lib-dynload"
    )
    fw = tmp_path / "fw"
    for directory in (site, bundle_lxml, lib_dynload, fw / "lib" / "python3.12"):
        directory.mkdir(parents=True)
    (site / "etree.so").write_text("x", encoding="utf-8")
    (bundle_lxml / "etree.so").write_text("x", encoding="utf-8")
    (lib_dynload / "_lzma.cpython-312-darwin.so").write_text("x", encoding="utf-8")
    (fw / "lib" / "python3.12" / "LICENSE.txt").write_text(
        "libmpdec\nStefan Krah\n", encoding="utf-8"
    )
    (work / "build-record-macos.txt").write_text(
        "BUILD RECORD: a link\n", encoding="utf-8"
    )
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/bash\n"
        f'case "$2" in *lxml*) echo "{site}" ;; *) echo 2.5.1 ;; esac\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    # The step names the python.org framework by an absolute path: point it at the stub tree.
    run = _step("build-macos-arm64", "macOS evidence")["run"].replace(
        "/Library/Frameworks/Python.framework/Versions/3.12", str(fw)
    )
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", run],
        env={
            "PATH": f"{stubs}:/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = result.stdout
    assert result.returncode == 0, out + result.stderr
    assert "BUILD RECORD: a link" in out
    assert "== lxml/etree.so" in out
    assert out.count("[lipo -archs") == 2 and out.count("[otool -L") == 2
    assert out.count("[shasum -a 256") == 2 and out.count("[codesign -dv") == 2
    assert "LICENSE.txt" in out and "Stefan Krah" in out
    assert "2.5.1" in out and "5.8.4" in out


def test_the_macos_build_record_and_notices_are_uploaded_with_the_macos_build():
    names = _macos_names()
    step = _step("build-macos-arm64", "Attach the macOS build record")
    assert names.index(step["name"]) > names.index("Upload the files of this build")
    assert step["uses"] == UPLOAD_PIN or step["uses"].startswith(UPLOAD_PIN)
    assert step["with"]["name"] == "macos-build-record-arm64"
    paths = step["with"]["path"].splitlines()
    assert "${{ runner.temp }}/work/build-record-macos.txt" in paths
    assert "${{ runner.temp }}/work/dist/inventag/THIRD-PARTY-LICENSES.txt" in paths
    assert step["with"]["if-no-files-found"] == "error"
    # Not a "build-*" artifact: provenance and the release do not pick it up
    # as a release file (it is evidence, not a file of the release).
    assert not step["with"]["name"].startswith("build-")


# ---- B3e: no early-exiting reader after a multi-line writer (dry run 6) -----

EARLY_READER = re.compile(r"\|\s*(grep\s+-\w*q\w*|head\b)")
SINGLE_WRITER = re.compile(r"(^|[\s$(])(printf|echo)\s")


def test_no_step_pipes_a_command_that_can_write_many_lines_into_grep_q_or_head():
    # grep -q and head leave at the first match; the writer then gets SIGPIPE
    # and under `set -o pipefail` the pipeline fails, silently (dry run 6, the
    # fish completion check: exit 1 right after "completion loads in zsh").
    # A printf or echo of one value is no such writer. Capture the output in a
    # variable first, then test the variable.
    found = []
    for job, step in _all_steps():
        for line in step.get("run", "").splitlines():
            match = EARLY_READER.search(line)
            if match and not SINGLE_WRITER.search(line[: match.start()]):
                found.append((job, step.get("name"), line.strip()))
    assert found == []


def _completions_run(tmp_path, fish_mode):
    """Run the fish branch of the completions step with a stub fish.

    fish_mode: "many" (prints 5000 lines, the inventag one first), "none"
    (many lines, none names inventag), "fails" (prints inventag, exits 3).
    """
    import subprocess

    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "fish").write_text(
        "#!/bin/bash\n"
        '[ "$1" = -n ] && exit 0\n'
        'case "$MODE" in\n'
        "  many) echo 'complete -c inventag -l help'; yes 'complete -c other' | head -5000 ;;\n"
        "  none) yes 'complete -c other' | head -5000 ;;\n"
        "  fails) echo 'complete -c inventag -l help'; exit 3 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    (stubs / "fish").chmod(0o755)
    share = tmp_path / "share"
    share.mkdir(exist_ok=True)
    (share / "inventag.fish").write_text("", encoding="utf-8")
    script = _heredoc(_step("smoke-linux", "Completions load")["run"], "COMPLETIONS")
    script = script.replace("/opt/inventag/share/completions", str(share))
    return subprocess.run(
        ["bash", "-s"],
        input=script,
        env={
            "PATH": f"{stubs}:/usr/bin:/bin",
            "FORMAT": "tar",
            "SHELLS": "fish",
            "MODE": fish_mode,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_fish_completion_check_passes_when_fish_prints_many_lines_with_inventag(
    tmp_path,
):
    result = _completions_run(tmp_path, "many")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "completion loads in fish" in result.stdout


def test_the_fish_completion_check_keeps_its_meaning(tmp_path):
    for mode in ("none", "fails"):
        result = _completions_run(tmp_path, mode)
        assert result.returncode != 0, mode
        assert "completion loads in fish" not in result.stdout, mode


# ---- B3f: dry run 7 (macOS man, files written by root in the container) ----


def _macos_man_run(tmp_path, man_output="INVENTAG(1)\n", page=None, renderer="works"):
    """Run the macOS unpack step with a stub man that behaves as macOS man does.

    Dry run 7, log line 438: `/usr/bin/man: illegal option -- l`. The stub
    accepts a page name or a path with a slash and prints `man_output`.
    """
    import subprocess
    import tarfile

    root = tmp_path / "root"
    inside = root / "inventag"
    for sub in ("share/man/man1", "share/completions"):
        (inside / sub).mkdir(parents=True)
    program = inside / "inventag"
    program.write_text(
        '#!/bin/bash\nif [ "$1" = --version ]; then echo "inventag 1.3.1"; fi\n',
        encoding="utf-8",
    )
    program.chmod(0o755)
    (inside / "share/man/man1/inventag.1").write_text(
        GOOD_PAGE if page is None else page, "utf-8"
    )
    (inside / "share/completions/inventag.bash").write_text("true\n", "utf-8")
    (inside / "share/completions/_inventag").write_text("true\n", "utf-8")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    with tarfile.open(artifacts / "inventag-1.3.1-darwin-arm64.tar.gz", "w:gz") as tar:
        tar.add(inside, arcname="inventag")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    if renderer == "works":
        (stubs / "man").write_text(
            "#!/bin/bash\n"
            'case "$1" in\n'
            '  -l) echo "/usr/bin/man: illegal option -- l" >&2; exit 1 ;;\n'
            '  */*) [ -f "$1" ] || exit 1; printf "%s" "$MAN_OUT" ;;\n'
            "  *) exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        (stubs / "col").write_text("#!/bin/bash\ncat\n", encoding="utf-8")
        (stubs / "col").chmod(0o755)
    elif renderer == "fails":
        (stubs / "man").write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
    (stubs / "zsh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    for tool in ("man", "zsh"):
        if (stubs / tool).exists():
            (stubs / tool).chmod(0o755)
    # The two steps that were one before B3i-6: unpack and run, then the checks.
    run = (
        _step("smoke-macos-arm64", "Unpack")["run"]
        + "\n"
        + _step("smoke-macos-arm64", "Check the man page")["run"]
    )
    return subprocess.run(
        ["bash", "-e", "-c", run],
        env={
            "PATH": f"{stubs}:/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
            "VERSION": "1.3.1",
            "CPU": "arm64",
            "MAN_OUT": man_output,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


# The tarball is read from $RUNNER_TEMP/artifacts; the step unpacks to install/.


def test_the_macos_man_page_check_does_not_use_the_gnu_only_option_l(tmp_path):
    for job, step in _all_steps():
        if job == "smoke-macos-arm64":
            assert "man -l" not in step.get("run", "")
    result = _macos_man_run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_macos_man_page_check_keeps_its_meaning(tmp_path):
    result = _macos_man_run(tmp_path, man_output="a page about something else\n")
    assert result.returncode != 0


def _scan_args(tmp_path, uid_gid=True):
    """Run the scan step with a stub python that runs the command after `--`."""
    import subprocess

    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    calls = tmp_path / "docker.log"
    (stubs / "python").write_text(
        '#!/bin/bash\nwhile [ "$1" != -- ]; do shift; done; shift; exec "$@"\n',
        encoding="utf-8",
    )
    (stubs / "docker").write_text(
        f'#!/bin/bash\necho "$@" >> "{calls}"\n', encoding="utf-8"
    )
    for tool in ("python", "docker"):
        (stubs / tool).chmod(0o755)
    run = _step("smoke-linux", "Scan a simulated AWS")["run"]
    result = subprocess.run(
        ["bash", "-e", "-c", run],
        env={"PATH": f"{stubs}:/usr/bin:/bin", "RUNNER_TEMP": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return calls.read_text("utf-8").split()


def test_the_linux_smoke_scan_runs_as_the_runner_user_so_that_the_runner_can_read_and_remove_its_files(
    tmp_path,
):
    # Dry run 7: the scan ran as root in the container; the runner could not
    # read audit.json or remove the output directory (PermissionError).
    import os

    args = _scan_args(tmp_path)
    assert args[0] == "exec"
    assert "-u" in args
    assert args[args.index("-u") + 1] == f"{os.getuid()}:{os.getgid()}"
    # -u comes before the container name; the program runs after it.
    assert args.index("-u") < args.index("smoke") < args.index("inventag")
    # The home of that user is the scan's own writable directory (smoke_scan.py
    # sets HOME to it); the environment is passed on.
    assert "HOME" in args[args.index("-e") :]


# ---- B3g: the man page check does not depend on the tools of the image ------

GOOD_PAGE = (
    '.TH INVENTAG 1 "" "inventag 1.3.1" "User Commands"\n'
    ".SH NAME\n"
    "inventag \\- read\\-only AWS inventory\n"
    ".SH SYNOPSIS\n"
)
MAN_PAGES = {
    "good": GOOD_PAGE,
    "empty": "",
    "no TH line": ".SH NAME\ninventag \\- x\n",
    "wrong page": '.TH OTHER 1 "" "x"\n.SH NAME\ninventag \\- x\n',
    "wrong section": '.TH INVENTAG 8 "" "x"\n.SH NAME\ninventag \\- x\n',
    "NAME names another program": '.TH INVENTAG 1 "" "x"\n.SH NAME\nother \\- x\n',
}


def _linux_man_run(
    tmp_path,
    fmt,
    page,
    renderer="missing",
    present=True,
    in_deb=True,
    exclude=False,
):
    """Run the Linux "Version, selftest and the man page" step in a temporary tree.

    renderer: "missing" (man and col absent), "stub-fails" (man exits 1, col
    absent), "unminimize" (the stub of the minimized Ubuntu images: it prints
    the unminimize text and exits 0, col present), "good" (man and col work),
    "no-inventag" (they work but print another page).
    present: the installed page exists. in_deb: the page is in the .deb (deb
    only). exclude: dpkg is configured with path-exclude=/usr/share/man/*.
    """
    import gzip
    import io
    import subprocess
    import tarfile

    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "inventag").write_text(
        '#!/bin/bash\nif [ "$1" = --version ]; then echo "inventag $VERSION"; fi\n',
        encoding="utf-8",
    )
    (stubs / "inventag").chmod(0o755)
    man_scripts = {
        "stub-fails": "echo \"run 'unminimize'\"\nexit 1\n",
        "unminimize": "echo \"run 'unminimize', ensure man-db is installed\"\n",
        "good": "echo 'INVENTAG(1)'\n",
        "no-inventag": "echo 'something else'\n",
    }
    if renderer in man_scripts:
        (stubs / "man").write_text("#!/bin/bash\n" + man_scripts[renderer], "utf-8")
        (stubs / "man").chmod(0o755)
    if renderer in ("good", "no-inventag", "unminimize"):
        (stubs / "col").write_text("#!/bin/bash\ncat\n", encoding="utf-8")
        (stubs / "col").chmod(0o755)
    man1 = tmp_path / "man1"
    man1.mkdir(exist_ok=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(exist_ok=True)
    dpkg_etc = tmp_path / "dpkg"
    (dpkg_etc / "dpkg.cfg.d").mkdir(parents=True, exist_ok=True)
    if exclude:
        (dpkg_etc / "dpkg.cfg.d" / "excludes").write_text(
            "path-exclude=/usr/share/man/*\n", encoding="utf-8"
        )
    if present:
        if fmt == "tar":
            (man1 / "inventag.1").write_text(page, encoding="utf-8")
        else:
            with gzip.open(man1 / "inventag.1.gz", "wb") as handle:
                handle.write(page.encode("utf-8"))
    if fmt == "deb":
        # The .deb is a stub file; dpkg-deb --fsys-tarfile prints its files as a tar.
        (artifacts / "inventag_1.3.1_amd64.deb").write_text("x", encoding="utf-8")
        member = (
            "./usr/share/man/man1/inventag.1.gz" if in_deb else "./usr/bin/inventag"
        )
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            data = gzip.compress(page.encode("utf-8"))
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        (tmp_path / "fsys.tar").write_bytes(buffer.getvalue())
        (stubs / "dpkg-deb").write_text(
            f'#!/bin/bash\ncat "{tmp_path}/fsys.tar"\n', encoding="utf-8"
        )
        (stubs / "dpkg-deb").chmod(0o755)
    script = _heredoc(_step("smoke-linux", "man page")["run"], "RUN")
    script = (
        script.replace("/usr/share/man/man1", str(man1))
        .replace("/opt/inventag/share/man/man1", str(man1))
        .replace("/artifacts", str(artifacts))
        .replace("/etc/dpkg", str(dpkg_etc))
    )
    return subprocess.run(
        ["bash", "-s"],
        input=script,
        env={
            "PATH": f"{stubs}:/usr/bin:/bin",
            "FORMAT": fmt,
            "VERSION": "1.3.1",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_linux_man_check_needs_neither_man_nor_col_to_pass(tmp_path):
    for fmt in ("deb", "rpm", "tar"):
        for renderer in ("missing", "stub-fails", "good"):
            work = tmp_path / f"{fmt}-{renderer}"
            work.mkdir()
            result = _linux_man_run(work, fmt, GOOD_PAGE, renderer)
            assert result.returncode == 0, (fmt, renderer, result.stdout, result.stderr)


def test_the_linux_man_check_fails_for_a_missing_file_an_empty_file_and_a_bad_page(
    tmp_path,
):
    for fmt in ("deb", "tar"):
        work = tmp_path / f"{fmt}-missing"
        work.mkdir()
        assert _linux_man_run(work, fmt, GOOD_PAGE, present=False).returncode != 0, fmt
        for why, page in MAN_PAGES.items():
            if why == "good":
                continue
            work = tmp_path / f"{fmt}-{why.replace(' ', '-')}"
            work.mkdir()
            result = _linux_man_run(work, fmt, page)
            assert result.returncode != 0, (fmt, why)


def test_a_renderer_that_works_but_prints_another_page_fails_the_check(tmp_path):
    result = _linux_man_run(tmp_path, "deb", GOOD_PAGE, renderer="no-inventag")
    assert result.returncode != 0


def test_the_linux_man_check_looks_at_the_path_of_each_format():
    run = _step("smoke-linux", "man page")["run"]
    assert "/usr/share/man/man1/inventag.1.gz" in run
    assert "/opt/inventag/share/man/man1/inventag.1" in run


def _macos_man_text_run(tmp_path, page, renderer):
    return _macos_man_run(tmp_path, man_output="x", page=page, renderer=renderer)


def test_the_macos_man_check_reads_the_roff_source_and_needs_no_renderer(tmp_path):
    for renderer in ("missing", "fails"):
        work = tmp_path / renderer
        work.mkdir()
        result = _macos_man_text_run(work, GOOD_PAGE, renderer)
        assert result.returncode == 0, (renderer, result.stdout, result.stderr)
    for why, page in MAN_PAGES.items():
        if why == "good":
            continue
        work = tmp_path / why.replace(" ", "-")
        work.mkdir()
        assert _macos_man_text_run(work, page, "missing").returncode != 0, why


# ---- B3h: Ubuntu images (dry run 9): the .deb is the proof for deb ----------


def test_the_deb_page_is_proved_from_the_deb_when_the_image_excludes_man_pages(
    tmp_path,
):
    # dpkg path-exclude=/usr/share/man/*: the page is in the .deb, not installed.
    result = _linux_man_run(tmp_path, "deb", GOOD_PAGE, present=False, exclude=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_deb_without_the_page_fails_even_when_the_image_excludes_man_pages(
    tmp_path,
):
    for exclude in (True, False):
        work = tmp_path / str(exclude)
        work.mkdir()
        result = _linux_man_run(
            work, "deb", GOOD_PAGE, in_deb=False, present=False, exclude=exclude
        )
        assert result.returncode != 0, exclude


def test_a_page_missing_after_the_install_fails_unless_dpkg_excludes_man_pages(
    tmp_path,
):
    result = _linux_man_run(tmp_path, "deb", GOOD_PAGE, present=False, exclude=False)
    assert result.returncode != 0


def test_a_bad_page_in_the_deb_fails(tmp_path):
    for why, page in MAN_PAGES.items():
        if why == "good":
            continue
        work = tmp_path / why.replace(" ", "-")
        work.mkdir()
        result = _linux_man_run(work, "deb", page, present=False, exclude=True)
        assert result.returncode != 0, why


def test_the_stub_man_of_a_minimized_image_that_exits_0_does_not_fail_the_check(
    tmp_path,
):
    # Dry run 8/9: the minimized Ubuntu man prints the unminimize text and
    # exits 0; grepping that text for inventag failed the step silently.
    for fmt in ("deb", "rpm", "tar"):
        work = tmp_path / fmt
        work.mkdir()
        result = _linux_man_run(work, fmt, GOOD_PAGE, renderer="unminimize")
        assert result.returncode == 0, (fmt, result.stdout, result.stderr)


# ---- B3b: the INCLUDE_MACOS switch (architect ruling 4) --------------------

MACOS_JOBS = (
    "build-macos-arm64",
    "smoke-macos-arm64",
)


def test_there_is_no_macos_x86_64_job_and_nothing_refers_to_one():
    # Architect ruling 3 of package-dryrun-1: cryptography 50 publishes no
    # macOS x86_64 wheel, so there is no Intel Mac executable.
    assert not [name for name in JOBS if "x86_64" in name and "macos" in name]
    for name, job in JOBS.items():
        for need in job.get("needs", []):
            assert "macos-x86_64" not in need, (name, need)
    for fragment in ("macos-x86_64", "macos-15-intel", "darwin-x86_64"):
        assert fragment not in TEXT, fragment
    assert set(MACOS_JOBS) == {name for name in JOBS if "macos" in name}


def test_the_macos_switch_is_a_workflow_level_value_that_is_on():
    # Fallback decided by the architect (not the default): if macOS is not
    # green after three dry-run rounds, v1.4.0 ships the Linux files only and
    # this value is set to 'false'.
    assert DATA["env"]["INCLUDE_MACOS"] == "true"
    assert "INCLUDE_MACOS" in _comment_text()


def test_plan_reads_the_switch_and_passes_it_on_as_an_output(tmp_path):
    assert "include_macos" in JOBS["plan"]["outputs"]
    assert (
        _step("plan", "version")["env"]["INCLUDE_MACOS"] == "${{ env.INCLUDE_MACOS }}"
    )
    for value in ("true", "false"):
        result, out = _plan(tmp_path, tag="v1.4.0", include_macos=value)
        assert result.returncode == 0, result.stderr
        assert out["include_macos"] == value
    for bad in ("", "yes", "True", "1"):
        result, _ = _plan(tmp_path, tag="v1.4.0", include_macos=bad)
        assert result.returncode != 0, bad
        assert "INCLUDE_MACOS" in result.stdout + result.stderr


def test_the_two_macos_jobs_run_only_when_the_switch_is_on():
    for name in MACOS_JOBS:
        # The env context is not available in a job condition: the plan job passes the value on.
        assert JOBS[name]["if"] == "needs.plan.outputs.include_macos == 'true'", name


def test_provenance_runs_when_the_macos_jobs_were_switched_off_and_not_after_a_failure():
    job = JOBS["provenance"]
    condition = " ".join(str(job["if"]).split())
    assert "!cancelled()" in condition and "!failure()" in condition
    # Still listed in needs: a skipped job satisfies it only with the condition above.
    assert set(job["needs"]) == BUILDS_AND_SMOKES | {"plan"}


def _expected_files(tmp_path, include_macos, drop=(), stray_macos=False):
    import subprocess

    release = tmp_path / "release"
    release.mkdir(exist_ok=True)
    names = []
    for cpu in ("x86_64", "arm64"):
        base = f"inventag-1.4.0-linux-{cpu}"
        deb_cpu, rpm_cpu = (
            ("amd64", "x86_64") if cpu == "x86_64" else ("arm64", "aarch64")
        )
        names += [
            f"{base}.tar.gz",
            f"{base}.THIRD-PARTY-LICENSES.txt",
            f"inventag_1.4.0_{deb_cpu}.deb",
            f"inventag-1.4.0-1.{rpm_cpu}.rpm",
        ]
    if include_macos == "true" or stray_macos:
        names += [
            f"inventag-1.4.0-darwin-{cpu}{ext}"
            for cpu in ("arm64",)
            for ext in (".tar.gz", ".THIRD-PARTY-LICENSES.txt")
        ]
    for name in names:
        if name not in drop:
            (release / name).write_text("x", encoding="utf-8")
    return subprocess.run(
        ["bash", "-c", _step("provenance", "expected file")["run"]],
        env={
            "PATH": "/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
            "VERSION": "1.4.0",
            "INCLUDE_MACOS": include_macos,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_provenance_checks_the_files_it_expects_for_each_state_of_the_switch(tmp_path):
    step = _step("provenance", "expected file")
    assert step["env"]["INCLUDE_MACOS"] == "${{ needs.plan.outputs.include_macos }}"
    cases = (
        ("on", "true", False, 0),
        # Switched off: the Linux files alone are the whole set.
        ("off", "false", False, 0),
        # Switched off but a macOS file is there: something is wrong.
        ("stray", "false", True, 1),
    )
    for name, switch, stray, code in cases:
        work = tmp_path / name
        work.mkdir()
        result = _expected_files(work, switch, stray_macos=stray)
        assert (result.returncode != 0) == bool(code), (name, result.stdout)


def test_provenance_fails_when_an_expected_file_is_missing(tmp_path):
    # file dropped: what the error names (the packages are matched by pattern)
    for drop, named in (
        ("inventag-1.4.0-darwin-arm64.tar.gz", "inventag-1.4.0-darwin-arm64.tar.gz"),
        ("inventag_1.4.0_arm64.deb", "inventag_*_arm64.deb"),
        (
            "inventag-1.4.0-linux-x86_64.THIRD-PARTY-LICENSES.txt",
            "inventag-1.4.0-linux-x86_64.THIRD-PARTY-LICENSES.txt",
        ),
    ):
        work = tmp_path / drop
        work.mkdir()
        result = _expected_files(work, "true", drop=(drop,))
        assert result.returncode != 0, drop
        assert named in result.stdout + result.stderr


def test_the_workflow_checks_of_actions_run_this_test_file():
    checks = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "actions-checks.yml").read_text("utf-8")
    )
    text = str(checks)
    assert "tests/unit/test_packaging_workflow.py" in text


# ---- B2h: libiconv evidence (architect-run10-macos-iconv.md section 3) -----


def test_the_macos_evidence_step_records_the_libiconv_evidence(tmp_path):
    import subprocess

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    outputs = {
        "lipo": 'echo "x86_64 arm64"',
        "nm": 'echo "0000000000008008 s __libiconv_version"',
        "strings": "echo libiconv_open",
        # The x86_64 part fails, as run 10's "not signed at all" may mean.
        "codesign": 'echo "[codesign $*]"; [ "$1 $3" != "-v x86_64" ]',
    }
    for tool in ("lipo", "otool", "codesign", "shasum", "strings", "nm"):
        body = outputs.get(tool, 'echo "[$(basename "$0") $*]"')
        (stubs / tool).write_text(f"#!/bin/bash\n{body}\n", encoding="utf-8")
        (stubs / tool).chmod(0o755)
    work = tmp_path / "work"
    site = tmp_path / "venv" / "site" / "lxml"
    bundle = work / "dist" / "inventag"
    for directory in (site, bundle / "_internal" / "lxml", tmp_path / "fw"):
        directory.mkdir(parents=True)
    (site / "etree.so").write_bytes(b"\0libiconv_open\0")
    (site / "_elementpath.so").write_bytes(b"\0")
    (bundle / "THIRD-PARTY-LICENSES.txt").write_text(
        "- GNU libiconv, linked into lxml's extension modules 1.17: LGPL-2.1\n",
        encoding="utf-8",
    )
    record = work / "build-record-macos.txt"
    record.write_text("BUILD RECORD: a link\n", encoding="utf-8")
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/bash\n"
        f'case "$2" in *ICONV*) echo "(6, 1, 3, 0) (0, 0)" ;; '
        f'*lxml*) echo "{site}" ;; *) echo 2.5.1 ;; esac\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    run = _step("build-macos-arm64", "macOS evidence")["run"].replace(
        "/Library/Frameworks/Python.framework/Versions/3.12", str(tmp_path / "fw")
    )
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", run],
        env={"PATH": f"{stubs}:/usr/bin:/bin", "RUNNER_TEMP": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    kept = record.read_text("utf-8")
    assert kept.startswith("BUILD RECORD: a link\n")  # appended, not replaced
    assert "== libiconv: lxml/etree.so" in kept
    assert "_elementpath" not in kept.split("== libiconv evidence")[1]
    assert "lipo -archs: x86_64 arm64" in kept
    for arch in ("x86_64", "arm64"):
        assert f"nm -arch {arch}:\n0000000000008008 s __libiconv_version" in kept
        assert f"strings -arch {arch} | grep -c libiconv_open: 1" in kept
    assert "codesign -v --architecture arm64: exit 0" in kept
    assert "codesign -v --architecture x86_64: exit 1" in kept
    assert "(6, 1, 3, 0) (0, 0)" in kept
    assert "1.17: LGPL-2.1" in kept
