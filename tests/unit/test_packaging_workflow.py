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
    tmp_path, tag="", ref="", dry_run="true", version="1.4.0", event="workflow_dispatch"
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


def test_every_job_after_the_plan_checks_out_the_ref_the_plan_checked():
    found = list(_non_plan_checkouts())
    assert len(found) >= 8
    for name, step in found:
        assert step["with"]["ref"] == "${{ needs.plan.outputs.ref }}", name


def test_every_build_packages_the_tag_the_plan_checked():
    for name in (*LINUX_BUILDS, *MACOS_BUILDS):
        checkout = [s for s in _steps(name) if "checkout" in s.get("uses", "")]
        assert len(checkout) == 1, name
        assert checkout[0]["with"]["ref"] == "${{ needs.plan.outputs.ref }}"


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
    assert "inventag --version" in text and '"inventag $VERSION"' in text
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


# ---- stage 4: provenance (notices addresses, SBOMs, checksums, attestation) and publish

BUILDS_AND_SMOKES = {
    "build-linux-x86_64",
    "build-linux-arm64",
    "build-macos-arm64",
    "build-macos-x86_64",
    "smoke-linux",
    "smoke-macos-arm64",
    "smoke-macos-x86_64",
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
    step = _step("provenance", "attest")
    assert step["uses"].startswith("actions/attest@")
    assert step["if"] == "needs.plan.outputs.dry_run == 'false'"
    assert step["with"]["subject-checksums"].endswith("/release/SHA256SUMS")
    assert "private-key" not in str(step) and "secret" not in str(step).lower()


def test_provenance_keeps_the_release_files_for_the_publish_job():
    up = _step("provenance", "Keep the release files")
    assert up["with"]["name"] == "release-files"
    assert up["with"]["if-no-files-found"] == "error"


def test_publish_attaches_to_the_release_only_when_it_is_not_a_dry_run():
    job = JOBS["publish"]
    assert job["needs"] == ["plan", "provenance"]
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


def _run_digest(tmp_path, run, inspect_output, image="debian:12"):
    """Run a digest-recording step with a stub docker; return (code, summary text, calls)."""
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    calls = tmp_path / "docker.log"
    stub = bin_dir / "docker"
    stub.write_text(
        "#!/bin/bash\n" f'echo "$@" >> "{calls}"\n' f"printf '%s' '{inspect_output}'\n",
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
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result, summary.read_text("utf-8"), calls.read_text("utf-8")


SOME_DIGEST = "debian@sha256:" + "ab" * 32


def test_every_linux_smoke_job_writes_the_digest_of_its_image_to_the_job_summary(
    tmp_path,
):
    steps = _steps("smoke-linux")
    names = [s.get("name", "") for s in steps]
    # After the image was pulled (docker run pulls it) and before anything is installed.
    assert names.index("Record the digest of the image") > names.index(
        "Start a fresh system"
    )
    assert names.index("Record the digest of the image") < names.index(
        "Install the package"
    )
    result, summary, calls = _run_digest(
        tmp_path, _digest_step_run("smoke-linux"), SOME_DIGEST
    )
    assert result.returncode == 0, result.stderr
    assert "image inspect" in calls and "RepoDigests" in calls and "debian:12" in calls
    assert f"debian:12: {SOME_DIGEST}" in summary


def test_a_smoke_image_with_no_recorded_digest_fails_the_job(tmp_path):
    result, summary, _ = _run_digest(tmp_path, _digest_step_run("smoke-linux"), "")
    assert result.returncode != 0
    assert "digest" in result.stdout + result.stderr
    assert "sha256" not in summary


def test_no_digest_is_typed_into_the_workflow_for_a_smoke_image():
    # The digests are written by each run (job summary); the only value typed
    # here is the build image's, which the dry run prints (placeholder).
    typed = re.findall(r"sha256:[0-9a-f]{64}", TEXT)
    assert typed == []
