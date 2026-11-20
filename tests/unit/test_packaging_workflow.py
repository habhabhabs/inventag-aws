"""The packaging workflow (.github/workflows/package.yml) and the job of
release.yml that calls it (plan v14 sections 3.5, 5.2 B3 and 5.6; architect
reviews of wave 1, items B3 and F2).

Nothing here runs a runner: the tests read the workflow as data and check the
rules of the repository (pinned actions, named runner images, least
privilege) and the rules of this workflow (build image pinned, no release
trigger, the notices addresses fetched, nothing published in a dry run).
"""

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


def test_it_is_a_reusable_workflow_and_can_be_started_by_hand_only():
    # No release, push or schedule trigger: a release created with the
    # workflow's own token starts no workflow, and a second trigger would
    # package a tag twice (plan 3.5).
    assert set(_triggers()) == {"workflow_call", "workflow_dispatch"}


def test_both_triggers_take_a_tag_and_a_dry_run_flag_that_defaults_to_true():
    for name in ("workflow_call", "workflow_dispatch"):
        inputs = _triggers()[name]["inputs"]
        assert inputs["tag"]["required"] is True
        assert inputs["tag"]["type"] == "string"
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
    assert set(holders) <= {"provenance", "publish"}
    if "provenance" in holders:
        assert holders["provenance"] == {
            "contents": "read",
            "id-token": "write",
            "attestations": "write",
        }
    if "publish" in holders:
        assert holders["publish"] == {"contents": "write"}


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


def test_one_run_per_tag_and_a_running_package_is_never_cancelled():
    group = DATA["concurrency"]
    assert "inputs.tag" in group["group"]
    assert group["cancel-in-progress"] is False


def test_the_plan_job_checks_the_tag_against_the_version_file():
    plan = JOBS["plan"]
    assert plan["outputs"].keys() >= {"tag", "version", "dry_run"}
    text = _run_text("plan")
    assert "inventag/_version.py" in text
    assert "^v[0-9]+\\.[0-9]+\\.[0-9]+$" in text
    for needed in ("requirements-lock.txt", "requirements-lock-build.txt"):
        assert needed in text
    checkout = [s for s in _steps("plan") if "checkout" in s.get("uses", "")][0]
    assert checkout["with"]["ref"] == "refs/tags/${{ inputs.tag }}"


def test_every_other_job_waits_for_the_plan():
    for name, job in JOBS.items():
        if name != "plan":
            assert "plan" in job["needs"], name


# ---- stage 2: the four builds, the build image, nfpm ----------------------

# name: (runner label, CPU as build_binary.sh names it, nfpm arch)
LINUX_BUILDS = {
    "build-linux-x86_64": ("ubuntu-24.04", "x86_64", "amd64"),
    "build-linux-arm64": ("ubuntu-24.04-arm", "arm64", "arm64"),
}
MACOS_BUILDS = {
    "build-macos-arm64": ("macos-15", "arm64"),
    "build-macos-x86_64": ("macos-15-intel", "x86_64"),
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


def test_the_four_builds_run_on_the_four_named_systems():
    for name, (label, *_rest) in {**LINUX_BUILDS, **MACOS_BUILDS}.items():
        assert JOBS[name]["runs-on"] == label


def test_every_build_packages_the_tag_the_plan_checked():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        checkout = [s for s in _steps(name) if "checkout" in s.get("uses", "")]
        assert len(checkout) == 1, name
        assert checkout[0]["with"]["ref"] == "refs/tags/${{ needs.plan.outputs.tag }}"


def test_the_build_image_is_pinned_by_digest_or_the_job_refuses_to_run():
    value = str(DATA["env"]["ALMALINUX_8_DIGEST"])
    assert value == DIGEST_PLACEHOLDER or re.fullmatch(r"[0-9a-f]{64}", value)
    for name in LINUX_BUILDS:
        text = _run_text(name)
        # The check comes first and refuses anything that is not 64 hex
        # digits; the refusal names the digest the tag has now.
        check = text.index("[0-9a-f]{64}")
        pinned_pull = text.index('docker pull "almalinux@sha256:${ALMALINUX_8_DIGEST}"')
        assert check < pinned_pull
        assert "almalinux:8" in text[check:pinned_pull]
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
        assert "rpm -q" in text and "glibc" in text and "2.28" in text
        assert "build-image" in text


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
    assert _run_text("build-linux-x86_64") == _run_text("build-linux-arm64")
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
        assert python and python[0]["with"]["python-version"] == "3.12"
        text = _run_text(name)
        assert "gnu-tar" in text and "gnubin" in text
        assert "scripts/packaging/build_binary.sh venv" in text
        assert "scripts/packaging/build_binary.sh build" in text
        assert "--no-selftest" not in text
        assert "pip install" not in text


def test_every_build_uploads_its_files_and_fails_when_there_are_none():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        upload = [
            s for s in _steps(name) if s.get("uses", "").startswith("actions/upload-")
        ]
        assert len(upload) == 1, name
        assert upload[0]["with"]["name"] == name
        assert upload[0]["with"]["if-no-files-found"] == "error"
        text = _run_text(name)
        assert "THIRD-PARTY-LICENSES" in text and "components.json" in text


def test_the_scripts_a_build_calls_exist_in_the_repository():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        for path in set(re.findall(r"scripts/packaging/[\w.]+", _run_text(name))):
            assert (ROOT / path).is_file(), (name, path)


# ---- stage 3: smoke tests on fresh systems --------------------------------

SMOKE_SYSTEMS = {
    # system: (image, format) as in plan 3.5, plus the glibc floor (AlmaLinux 8)
    "ubuntu-22.04": ("ubuntu:22.04", "deb"),
    "ubuntu-24.04": ("ubuntu:24.04", "deb"),
    "debian-12": ("debian:12", "deb"),
    "debian-12-tar": ("debian:12", "tar"),
    "fedora": ("fedora:latest", "rpm"),
    "rockylinux-9": ("rockylinux:9", "rpm"),
    "rockylinux-9-tar": ("rockylinux:9", "tar"),
    "almalinux-8": ("almalinux:8", "rpm"),
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
    assert "inventag --version" in text and '"$VERSION"' in text
    assert "inventag selftest" in text
    assert "man -w inventag" in text or "man -l" in text
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
        "smoke-macos-x86_64": MACOS_BUILDS["build-macos-x86_64"],
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


def test_the_pipx_install_of_the_wheel_is_smoked():
    job = JOBS["smoke-pipx"]
    assert job["runs-on"] == "ubuntu-24.04"
    text = _run_text("smoke-pipx")
    assert "pip wheel --no-deps" in text
    assert "pipx install" in text and "pipx uninstall inventag-aws" in text
    assert "inventag selftest" in text


def test_the_smoke_jobs_use_the_artifacts_of_their_build():
    for name in ("smoke-linux", "smoke-macos-arm64", "smoke-macos-x86_64"):
        down = [
            s for s in _steps(name) if s.get("uses", "").startswith("actions/download-")
        ]
        assert len(down) == 1, name
        build = [n for n in JOBS[name]["needs"] if n.startswith("build-")][0]
        assert down[0]["with"]["name"] == build
