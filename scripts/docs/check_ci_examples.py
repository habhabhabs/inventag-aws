#!/usr/bin/env python3
"""Check the CI pipeline examples in docs/ (GitHub Actions and GitLab CI/CD).

Run it through `npm run check:ci-examples` in website/ (it calls this file).
Uses PyYAML, which is already in requirements.txt; the website package has
no YAML parser of its own.

For every fenced yaml block in docs/**/*.md that names a workflow file or has
the top-level keys of one, it runs named checks (see CHECKS; each rule carries
its source: a docs.gitlab.com page, InvenTag's own docs, or project policy):
  - the block parses as YAML;
  - GitHub: job structure, pinned `uses:`, `id-token: write` where OIDC is used;
  - GitLab: the keyword rules of the GitLab documentation (global keywords,
    reserved job names, job keywords, stages, needs, rules, allow_failure,
    artifacts, id_tokens, retry, timeout, when), and InvenTag's own policy
    (no literal AWS secrets, Python image pinned to a minor version, documented
    InvenTag exit codes in allow_failure);
  - every `inventag` command line is accepted by InvenTag's argument parser;
  - optional: the block validates against GitLab's JSON schema when a schema
    file is given (--schema, env GITLAB_CI_SCHEMA, or DEFAULT_SCHEMA exists).

`--report` prints, per block, every check that ran with PASS or FAIL and its
source: the evidence the docs team cites.

Translated pages are compared by `npm run check:i18n` (every code block must be
byte-identical to the English one), so this script reads only docs/.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_cli_examples  # noqa: E402

Problem = Tuple[int, str]

# Optional GitLab JSON schema. Not committed: its origin and licence must be
# shown first (see the v1.2.1 GitLab checker report).
DEFAULT_SCHEMA = Path(__file__).resolve().parent / "gitlab-ci-schema.json"

_GITHUB_NAME = re.compile(r"\.github/workflows/[\w.-]+\.ya?ml")
_GITLAB_NAME = re.compile(r"\.gitlab-ci(?:[\w.-]*)\.ya?ml")
_SHA = re.compile(r"[0-9a-f]{40}")
_TAG = re.compile(r"v?\d+(?:\.\d+){0,2}(?:[-+.][\w.]+)?")
_FENCE = re.compile(r"^(\s*)(`{3,})\s*(\w*)\s*(.*)$")


def find_blocks(text: str) -> List[Dict[str, Any]]:
    """Fenced blocks as dicts: lang, info, body, line (of the first body line)."""
    blocks: List[Dict[str, Any]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        indent, ticks, lang, info = m.groups()
        j = i + 1
        body: List[str] = []
        while j < len(lines) and not re.match(rf"^\s*{ticks}\s*$", lines[j]):
            body.append(lines[j][len(indent) :] if indent else lines[j])
            j += 1
        blocks.append(
            {"lang": lang, "info": info, "body": "\n".join(body) + "\n", "line": i + 2}
        )
        i = j + 1
    return blocks


def classify(block: Dict[str, Any]) -> Optional[str]:
    """Return 'github', 'gitlab' or None for a yaml block."""
    if block["lang"] not in ("yaml", "yml"):
        return None
    body = block["body"]
    first_comment = next(
        (ln for ln in body.split("\n") if ln.strip()), ""
    )  # first non-empty line
    head = (
        block["info"] + " " + (first_comment if first_comment.startswith("#") else "")
    )
    if _GITHUB_NAME.search(head):
        return "github"
    if _GITLAB_NAME.search(head):
        return "gitlab"
    if re.search(r"^on:", body, re.M) and re.search(r"^jobs:", body, re.M):
        return "github"
    if re.search(r"^stages:", body, re.M) or re.search(r"^\s+script:", body, re.M):
        return "gitlab"
    return None


def _line_of(block: Dict[str, Any], needle: str) -> int:
    for offset, ln in enumerate(block["body"].split("\n")):
        if needle in ln:
            return block["line"] + offset
    return block["line"]


def _commands(block: Dict[str, Any]) -> List[Tuple[int, str]]:
    problems: List[Tuple[int, str]] = []
    for lineno, text, tokens in check_cli_examples.extract_commands(block["body"]):
        found = (
            ["cannot split the command line (unbalanced quote)"]
            if tokens is None
            else check_cli_examples.check_command(tokens)
        )
        for problem in found:
            problems.append((block["line"] + lineno - 1, f"`{text}`: {problem}"))
    return problems


def _pin_problem(ref: str) -> Optional[str]:
    if ref.startswith("./"):
        return None
    if ref.startswith("docker://"):
        if "@sha256:" in ref:
            return None
        tag = ref.rsplit(":", 1)[-1] if ":" in ref.split("/")[-1] else ""
        return None if tag and tag != "latest" else "docker image is not pinned"
    if "@" not in ref:
        return f"`uses: {ref}` has no version after @"
    version = ref.rsplit("@", 1)[1]
    if _SHA.fullmatch(version) or _TAG.fullmatch(version):
        return None
    return f"`uses: {ref}` is not pinned to a tag or a full commit SHA"


def _has_id_token(perms: Any) -> bool:
    return isinstance(perms, dict) and perms.get("id-token") == "write"


class Check(NamedTuple):
    id: str
    source: str  # documentation link, or the project rule it enforces
    kinds: Tuple[str, ...]
    run: Callable[[Dict[Any, Any], Dict[str, Any]], List[Problem]]


CHECKS: Dict[str, Check] = {}


def rule(check_id: str, source: str, kinds: Tuple[str, ...] = ("gitlab",)):
    def register(fn: Callable[[Dict[Any, Any], Dict[str, Any]], List[Problem]]):
        CHECKS[check_id] = Check(check_id, source, kinds, fn)
        return fn

    return register


def _at(block: Dict[str, Any], needle: str) -> int:
    return _line_of(block, f"{needle}:")


# ---------------------------------------------------------------- GitHub ---

_GH = "project rule: pinned actions, least-privilege OIDC"


def _github_jobs(doc: Dict[Any, Any]) -> Dict[Any, Any]:
    jobs = doc.get("jobs")
    return jobs if isinstance(jobs, dict) else {}


@rule("github-job-structure", _GH, ("github",))
def check_github_structure(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    jobs = _github_jobs(doc)
    if not jobs:
        return [(block["line"], "workflow has no jobs")]
    # PyYAML reads the key `on` as True (YAML 1.1)
    if "on" not in doc and True not in doc:
        out.append((block["line"], "workflow has no `on:` trigger"))
    for name, job in jobs.items():
        at = _at(block, name)
        if not isinstance(job, dict):
            out.append((at, f"job `{name}` is not a mapping"))
        elif "uses" not in job:
            if "runs-on" not in job:
                out.append((at, f"job `{name}` has no `runs-on`"))
            if not isinstance(job.get("steps"), list) or not job.get("steps"):
                out.append((at, f"job `{name}` has no `steps`"))
    return out


@rule("github-action-pins", _GH, ("github",))
def check_github_pins(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for job in _github_jobs(doc).values():
        if not isinstance(job, dict):
            continue
        refs = [job["uses"]] if "uses" in job else []
        refs += [
            s["uses"]
            for s in job.get("steps") or []
            if isinstance(s, dict) and "uses" in s
        ]
        for ref in refs:
            problem = _pin_problem(str(ref))
            if problem:
                out.append((_line_of(block, str(ref)), problem))
    return out


@rule("github-oidc-permissions", _GH, ("github",))
def check_github_oidc(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    top_perms = doc.get("permissions")
    oidc_text = "id-token" in block["body"] or "role-to-assume" in block["body"]
    for name, job in _github_jobs(doc).items():
        if not isinstance(job, dict):
            continue
        uses_oidc = oidc_text or any(
            isinstance(s, dict) and "role-to-assume" in (s.get("with") or {})
            for s in job.get("steps") or []
        )
        if uses_oidc and not (
            _has_id_token(job.get("permissions")) or _has_id_token(top_perms)
        ):
            out.append(
                (
                    _at(block, name),
                    f"job `{name}` uses OIDC but has no `permissions: id-token: write`",
                )
            )
    return out


# ---------------------------------------------------------------- GitLab ---

GL_YAML = "https://docs.gitlab.com/ci/yaml/"
GL_DEPRECATED = "https://docs.gitlab.com/ci/yaml/deprecated_keywords/"
GL_JOBS = "https://docs.gitlab.com/ci/jobs/"

# Global keywords. Source: GL_YAML, "Global keywords".
GITLAB_GLOBAL_KEYWORDS = {"default", "include", "stages", "variables", "workflow"}
# Still accepted by GitLab but deprecated at the top level (define them under
# `default:`). Source: GL_DEPRECATED.
GITLAB_DEPRECATED_GLOBAL = {
    "image",
    "services",
    "cache",
    "before_script",
    "after_script",
}
# "You can't use these keywords as job names". Source: GL_JOBS.
GITLAB_RESERVED_JOB_NAMES = {
    "image",
    "services",
    "stages",
    "before_script",
    "after_script",
    "variables",
    "cache",
    "include",
}
# Job keywords. Source: GL_YAML, "Job keywords" (and the `id_tokens` section).
GITLAB_JOB_KEYWORDS = {
    "after_script",
    "allow_failure",
    "artifacts",
    "before_script",
    "cache",
    "coverage",
    "dast_configuration",
    "dependencies",
    "description",
    "environment",
    "extends",
    "id_tokens",
    "identity",
    "image",
    "inherit",
    "interruptible",
    "manual_confirmation",
    "needs",
    "pages",
    "parallel",
    "release",
    "resource_group",
    "retry",
    "rules",
    "run",
    "script",
    "secrets",
    "services",
    "stage",
    "start_in",
    "tags",
    "timeout",
    "trigger",
    "variables",
    "when",
}
# Source: GL_DEPRECATED ("only and except are deprecated", use rules).
GITLAB_LEGACY_JOB_KEYWORDS = {"only", "except"}
# Source: GL_YAML, `stages`: "the default pipeline stages are".
GITLAB_DEFAULT_STAGES = [".pre", "build", "test", "deploy", ".post"]
_JOB_BODY_KEYS = ("script", "run", "trigger", "extends")
# Source: GL_YAML, `rules`.
GITLAB_RULE_KEYS = {
    "if",
    "changes",
    "exists",
    "when",
    "allow_failure",
    "needs",
    "variables",
    "interruptible",
}
_RULE_CONDITIONS = ("if", "changes", "exists", "when")
GITLAB_WHEN = {"on_success", "manual", "always", "on_failure", "delayed", "never"}
GITLAB_ARTIFACTS_WHEN = {"on_success", "on_failure", "always"}
GITLAB_RETRY_WHEN = {
    "always",
    "unknown_failure",
    "script_failure",
    "api_failure",
    "stuck_or_timeout_failure",
    "stuck_pending_with_matching_runners",
    "stuck_pending_no_matching_runners",
    "no_updates_running",
    "no_updates_canceling",
    "runner_system_failure",
    "runner_configuration_error",
    "runner_external_dependency_failure",
    "runner_interrupted",
    "runner_unsupported",
    "stale_schedule",
    "job_execution_timeout",
    "server_timeout_running",
    "server_timeout_canceling",
    "archived_failure",
    "unmet_prerequisites",
    "scheduler_failure",
    "data_integrity_failure",
}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _gitlab_jobs(doc: Dict[Any, Any]) -> Dict[str, Dict[Any, Any]]:
    """Jobs: mappings that are not global keywords and not hidden (`.name`)."""
    known = GITLAB_GLOBAL_KEYWORDS | GITLAB_DEPRECATED_GLOBAL
    return {
        k: v
        for k, v in doc.items()
        if isinstance(k, str)
        and isinstance(v, dict)
        and k not in known
        and not k.startswith(".")
    }


def _job_pairs(doc: Dict[Any, Any]) -> List[Tuple[str, Dict[Any, Any]]]:
    return list(_gitlab_jobs(doc).items())


@rule("gitlab-top-level-keys", GL_YAML + " (Global keywords), " + GL_DEPRECATED)
def check_top_level(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for key, value in doc.items():
        at = _at(block, key)
        if not isinstance(key, str):
            out.append((at, f"top-level key `{key}` is not a string"))
        elif key in GITLAB_GLOBAL_KEYWORDS or key.startswith("."):
            continue  # hidden jobs and templates start with a dot
        elif key in GITLAB_DEPRECATED_GLOBAL:
            out.append(
                (at, f"top-level `{key}` is deprecated: define it under `default:`")
            )
        elif not isinstance(value, dict):
            out.append(
                (
                    at,
                    f"top-level key `{key}` is not a global keyword and not a job "
                    "(a job is a mapping)",
                )
            )
    return out


@rule("gitlab-reserved-job-names", GL_JOBS + " (Unavailable names for jobs)")
def check_reserved_names(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    return [
        (_at(block, key), f"`{key}` cannot be used as a job name")
        for key, value in doc.items()
        if key in GITLAB_RESERVED_JOB_NAMES
        and isinstance(value, dict)
        and any(k in value for k in _JOB_BODY_KEYS)
    ]


@rule("gitlab-job-has-script", GL_YAML + " (script, trigger, extends, run)")
def check_job_has_script(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    return [
        (_at(block, name), f"job `{name}` has no `script` (or trigger, run, extends)")
        for name, job in _job_pairs(doc)
        if not any(k in job for k in _JOB_BODY_KEYS)
    ]


@rule("gitlab-job-keywords", GL_YAML + " (Job keywords), " + GL_DEPRECATED)
def check_job_keywords(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        for key in job:
            at = _at(block, key)
            if key in GITLAB_LEGACY_JOB_KEYWORDS:
                out.append(
                    (at, f"job `{name}`: `{key}` is deprecated (legacy): use `rules`")
                )
            elif key not in GITLAB_JOB_KEYWORDS:
                out.append(
                    (at, f"job `{name}`: `{key}` is not in the documented job keywords")
                )
    return out


@rule("gitlab-stage-declared", GL_YAML + " (stages, stage)")
def check_stages(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    stages = doc.get("stages")
    if stages is None:
        if "include" in doc:
            return []  # stages may come from an included file
        declared = set(GITLAB_DEFAULT_STAGES)
    elif isinstance(stages, list) and all(isinstance(x, str) for x in stages):
        declared = set(stages) | {".pre", ".post"}
    else:
        return [(_at(block, "stages"), "`stages` must be a list of strings")]
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        if "stage" not in job and "extends" in job:
            continue  # the stage may come from the template
        stage = job.get("stage", "test")  # "the job uses the test stage by default"
        if stage not in declared:
            how = (
                "" if "stage" in job else " (the default stage when `stage` is absent)"
            )
            out.append(
                (
                    _at(block, name),
                    f"job `{name}`: stage `{stage}`{how} is not in `stages`",
                )
            )
    return out


@rule("gitlab-needs-exist", GL_YAML + " (needs, needs:optional, needs:project)")
def check_needs(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    names = set(_gitlab_jobs(doc)) | {
        k for k in doc if isinstance(k, str) and k.startswith(".")
    }
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        needs = job.get("needs")
        if needs is None:
            continue
        if not isinstance(needs, list):
            out.append((_at(block, name), f"job `{name}`: `needs` must be a list"))
            continue
        for item in needs:
            if isinstance(item, dict):
                if (
                    "project" in item
                    or "pipeline" in item
                    or item.get("optional") is True
                ):
                    continue  # another project's job, or allowed to be absent
                target = item.get("job")
            else:
                target = item
            if target not in names:
                out.append(
                    (
                        _at(block, name),
                        f"job `{name}`: needs `{target}`, which is not a job here",
                    )
                )
    return out


def _check_allow_failure(value: Any, where: str, at: int) -> List[Problem]:
    if isinstance(value, bool):
        return []
    if isinstance(value, dict) and set(value) == {"exit_codes"}:
        codes = value["exit_codes"]
        if _is_int(codes) or (
            isinstance(codes, list) and codes and all(_is_int(c) for c in codes)
        ):
            return []
        return [
            (
                at,
                f"{where}: `allow_failure:exit_codes` must be an integer or a list of integers",
            )
        ]
    return [
        (at, f"{where}: `allow_failure` must be true, false or a map with `exit_codes`")
    ]


@rule("gitlab-rules-keys", GL_YAML + " (rules)")
def check_rules(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        rules = job.get("rules")
        if rules is None:
            continue
        at = _at(block, "rules")
        if not isinstance(rules, list):
            out.append((at, f"job `{name}`: `rules` must be a list"))
            continue
        for entry in rules:
            if not isinstance(entry, dict):
                out.append((at, f"job `{name}`: a `rules` entry must be a mapping"))
                continue
            for key in entry:
                if key not in GITLAB_RULE_KEYS:
                    out.append(
                        (at, f"job `{name}`: `{key}` is not a documented `rules` key")
                    )
            if not any(k in entry for k in _RULE_CONDITIONS):
                out.append(
                    (
                        at,
                        f"job `{name}`: a `rules` entry needs at least one of "
                        "if, changes, exists, when",
                    )
                )
            if "when" in entry and entry["when"] not in GITLAB_WHEN:
                out.append(
                    (
                        at,
                        f"job `{name}`: `rules:when` `{entry['when']}` is not documented",
                    )
                )
            if "allow_failure" in entry:
                out += _check_allow_failure(
                    entry["allow_failure"], f"job `{name}` rules", at
                )
    return out


@rule("gitlab-allow-failure", GL_YAML + " (allow_failure, allow_failure:exit_codes)")
def check_allow_failure(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        if "allow_failure" in job:
            out += _check_allow_failure(
                job["allow_failure"], f"job `{name}`", _at(block, "allow_failure")
            )
    return out


@rule("gitlab-artifacts", GL_YAML + " (artifacts:when, artifacts:expire_in)")
def check_artifacts(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        art = job.get("artifacts")
        if art is None:
            continue
        if not isinstance(art, dict):
            out.append(
                (
                    _at(block, "artifacts"),
                    f"job `{name}`: `artifacts` must be a mapping",
                )
            )
            continue
        if "when" in art and art["when"] not in GITLAB_ARTIFACTS_WHEN:
            out.append(
                (
                    _at(block, "when"),
                    f"job `{name}`: `artifacts:when` must be one of "
                    + ", ".join(sorted(GITLAB_ARTIFACTS_WHEN)),
                )
            )
        # the page shows the number as the string '42'
        if "expire_in" in art and not isinstance(art["expire_in"], str):
            out.append(
                (
                    _at(block, "expire_in"),
                    f"job `{name}`: `artifacts:expire_in` must be a string "
                    "(quote a bare number, e.g. '42')",
                )
            )
    return out


def _token_problems(tokens: Any, where: str, block: Dict[str, Any]) -> List[Problem]:
    if not isinstance(tokens, dict):
        return [(_at(block, "id_tokens"), f"{where}: id_tokens must be a mapping")]
    out: List[Problem] = []
    for tname, tval in tokens.items():
        aud = tval.get("aud") if isinstance(tval, dict) else None
        ok = (isinstance(aud, str) and aud) or (
            isinstance(aud, list) and aud and all(isinstance(a, str) for a in aud)
        )
        if not ok:
            out.append(
                (
                    _at(block, tname),
                    f"{where}: id_tokens `{tname}` needs `aud` (a string or a list of strings)",
                )
            )
    return out


@rule("gitlab-id-tokens", GL_YAML + " (id_tokens, id_tokens:aud)")
def check_id_tokens(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    default = doc.get("default")
    if isinstance(default, dict) and "id_tokens" in default:
        out += _token_problems(default["id_tokens"], "default", block)
    for name, job in _job_pairs(doc):
        if "id_tokens" in job:
            out += _token_problems(job["id_tokens"], f"job `{name}`", block)
    return out


@rule("gitlab-retry", GL_YAML + " (retry, retry:max, retry:when)")
def check_retry(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        if "retry" not in job:
            continue
        retry, at, where = job["retry"], _at(block, "retry"), f"job `{name}`"
        if _is_int(retry):
            if retry not in (0, 1, 2):
                out.append((at, f"{where}: `retry` must be 0, 1 or 2"))
        elif (
            isinstance(retry, dict) and set(retry) <= {"max", "when"} and "max" in retry
        ):
            if retry["max"] not in (0, 1, 2) or not _is_int(retry["max"]):
                out.append((at, f"{where}: `retry:max` must be 0, 1 or 2"))
            when = retry.get("when", "always")
            whens = when if isinstance(when, list) else [when]
            for w in whens:
                if w not in GITLAB_RETRY_WHEN:
                    out.append((at, f"{where}: `retry:when` `{w}` is not documented"))
        else:
            out.append(
                (at, f"{where}: `retry` must be 0, 1, 2 or a map with `max` and `when`")
            )
    return out


@rule("gitlab-timeout", GL_YAML + " (timeout)")
def check_timeout(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    return [
        (
            _at(block, "timeout"),
            f"job `{name}`: `timeout` must be text such as `3 hours 30 minutes`",
        )
        for name, job in _job_pairs(doc)
        if "timeout" in job and not (isinstance(job["timeout"], str) and job["timeout"])
    ]


@rule("gitlab-when", GL_YAML + " (when)")
def check_when(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        if "when" not in job:
            continue
        value = job["when"]
        if value == "never":
            out.append(
                (
                    _at(block, "when"),
                    f"job `{name}`: `when: never` is only valid in `rules` "
                    "or `workflow:rules`",
                )
            )
        elif value not in GITLAB_WHEN:
            out.append(
                (
                    _at(block, "when"),
                    f"job `{name}`: `when` `{value}` is not documented",
                )
            )
    return out


# ------------------------------------------------- InvenTag project policy ---

_POLICY = "InvenTag policy for docs examples"
_AWS_SECRET_NAME = re.compile(r"^AWS_.*(SECRET|ACCESS_KEY|SESSION_TOKEN)", re.I)
_AWS_KEY_VALUE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
# docs/reference/cli.md, "Exit codes": 3 tag policy, 4 risk threshold,
# 5 account error, 6 empty. Codes 1 and 2 are errors; 0 is success.
INVENTAG_EXIT_CODES_TO_HANDLE = {3, 4, 5, 6}


def _variable_maps(doc: Dict[Any, Any]) -> List[Tuple[str, Any]]:
    maps: List[Tuple[str, Any]] = [("global", doc.get("variables"))]
    for name, job in _job_pairs(doc):
        maps.append((f"job `{name}`", job.get("variables")))
        for entry in job.get("rules") or []:
            if isinstance(entry, dict):
                maps.append((f"job `{name}` rules", entry.get("variables")))
    return maps


@rule(
    "inventag-no-literal-aws-secrets",
    _POLICY + ": no AWS keys as literal values",
    ("gitlab",),
)
def check_no_secrets(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for where, variables in _variable_maps(doc):
        if not isinstance(variables, dict):
            continue
        for name, raw in variables.items():
            value = raw.get("value") if isinstance(raw, dict) else raw
            text = "" if value is None else str(value)
            literal = bool(text) and "$" not in text
            if (literal and _AWS_SECRET_NAME.match(str(name))) or _AWS_KEY_VALUE.search(
                text
            ):
                out.append(
                    (
                        _at(block, name),
                        f"{where}: variable `{name}` holds a literal AWS credential; "
                        "use a masked CI/CD variable reference such as `$"
                        + str(name)
                        + "`",
                    )
                )
    return out


def _image_refs(doc: Dict[Any, Any]) -> List[Any]:
    holders = [doc]
    if isinstance(doc.get("default"), dict):
        holders.append(doc["default"])
    holders += [job for _, job in _job_pairs(doc)]
    refs = []
    for holder in holders:
        image = holder.get("image")
        refs.append(image.get("name") if isinstance(image, dict) else image)
    return [r for r in refs if isinstance(r, str)]


def _python_tag_problem(ref: str) -> Optional[str]:
    if "@sha256:" in ref:
        return None
    segment = ref.rsplit("/", 1)[-1]
    repo, _, tag = segment.partition(":")
    if repo != "python":
        return None
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?", tag):
        return None
    return f"image `{ref}` is not pinned to a Python minor version (use e.g. python:3.12-slim)"


@rule(
    "inventag-python-image-pinned", _POLICY + ": python image pinned to a minor version"
)
def check_python_image(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for ref in _image_refs(doc):
        problem = _python_tag_problem(ref)
        if problem:
            out.append((_line_of(block, ref), problem))
    return out


def _script_lines(job: Dict[Any, Any]) -> List[str]:
    lines: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            lines.extend(value.split("\n"))
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for key in ("before_script", "script", "after_script"):
        walk(job.get(key))
    return lines


_RUNS_INVENTAG = re.compile(r"(?:^|[\s;&|(])inventag(?:\s|$)")


@rule(
    "inventag-allow-failure-exit-codes",
    "docs/reference/cli.md#exit-codes (InvenTag): only codes 3, 4, 5, 6 are for a pipeline to tolerate",
)
def check_exit_codes(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    out: List[Problem] = []
    for name, job in _job_pairs(doc):
        allow = job.get("allow_failure")
        if not (isinstance(allow, dict) and "exit_codes" in allow):
            continue
        if not any(_RUNS_INVENTAG.search(ln) for ln in _script_lines(job)):
            continue
        codes = allow["exit_codes"]
        for code in codes if isinstance(codes, list) else [codes]:
            if _is_int(code) and code not in INVENTAG_EXIT_CODES_TO_HANDLE:
                out.append(
                    (
                        _at(block, "exit_codes"),
                        f"job `{name}`: `allow_failure:exit_codes` lists {code}, which "
                        "is not an InvenTag exit code to tolerate (3, 4, 5, 6); "
                        "1 and 2 are errors",
                    )
                )
    return out


@rule(
    "inventag-commands-parse",
    "InvenTag's own argument parser (inventag.cli.main.create_parser)",
    ("github", "gitlab"),
)
def check_commands(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    return _commands(block)


# -------------------------------------------------- optional JSON schema ---


def schema_check(path: Optional[Path]) -> Optional[Check]:
    """A check that validates a GitLab block against a JSON schema file.

    Returns None when there is no file: the layer then does not run.
    """
    if path is None or not Path(path).is_file():
        return None
    from jsonschema import validators

    schema = json.loads(Path(path).read_text("utf-8"))
    validator = validators.validator_for(schema)(schema)

    def run(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
        out: List[Problem] = []
        for err in sorted(
            validator.iter_errors(doc), key=lambda e: list(map(str, e.path))
        ):
            where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
            keys = [str(p) for p in err.absolute_path if isinstance(p, str)]
            at = _at(block, keys[-1]) if keys else block["line"]
            out.append((at, f"schema: {where}: {err.message[:200]}"))
        return out

    return Check(
        "gitlab-json-schema", f"JSON schema file {Path(path).name}", ("gitlab",), run
    )


def run_checks(
    kind: str,
    doc: Dict[Any, Any],
    block: Dict[str, Any],
    extra: Optional[Check] = None,
) -> List[Tuple[Check, List[Problem]]]:
    checks = [c for c in CHECKS.values() if kind in c.kinds]
    if extra is not None and kind in extra.kinds:
        checks.append(extra)
    return [(c, sorted(c.run(doc, block))) for c in checks]


def check_gitlab(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    return [p for _, found in run_checks("gitlab", doc, block) for p in found]


def check_github(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Problem]:
    return [p for _, found in run_checks("github", doc, block) for p in found]


YAML_SOURCE = "PyYAML safe_load"


def check_file(
    path: Path, docs_root: Path, schema: Optional[Check] = None
) -> Tuple[List[str], List[Dict[str, Any]]]:
    findings: List[str] = []
    seen: List[Dict[str, Any]] = []
    rel = (
        path.relative_to(docs_root.parent) if docs_root.parent in path.parents else path
    )
    for block in find_blocks(path.read_text("utf-8")):
        kind = classify(block)
        if kind is None:
            continue
        block["kind"] = kind
        block["path"] = str(rel)
        block["results"] = []
        seen.append(block)
        try:
            doc = yaml.safe_load(block["body"])
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            at = block["line"] + (mark.line if mark else 0)
            msg = f"does not parse as YAML: {getattr(exc, 'problem', exc)}"
            block["results"].append(("yaml-parses", YAML_SOURCE, [(at, msg)]))
            findings.append(f"{rel}:{at}: [{kind}] {msg}")
            continue
        block["results"].append(("yaml-parses", YAML_SOURCE, []))
        if not isinstance(doc, dict):
            msg = "is not a YAML mapping"
            block["results"].append(
                ("yaml-mapping", YAML_SOURCE, [(block["line"], msg)])
            )
            findings.append(f"{rel}:{block['line']}: [{kind}] {msg}")
            continue
        problems: List[Problem] = []
        for check, found in run_checks(kind, doc, block, schema):
            block["results"].append((check.id, check.source, found))
            problems += found
        findings += [f"{rel}:{n}: [{kind}] {msg}" for n, msg in sorted(problems)]
    return findings, seen


def print_report(blocks: List[Dict[str, Any]]) -> None:
    """Per block: block id (file:line), kind, and every check with PASS or FAIL."""
    print(
        "# PASS on a rule whose keyword the block does not use means there was "
        "nothing to check."
    )
    for b in blocks:
        print(
            f"block {b['path']}:{b['line']} [{b['kind']}] {b['info'] or '(no title)'}"
        )
        for check_id, source, found in b["results"]:
            print(f"  {'FAIL' if found else 'PASS'} {check_id}  <{source}>")
            for n, msg in found:
                print(f"       line {n}: {msg}")


def main(argv: Optional[List[str]] = None) -> int:
    default_docs = Path(__file__).resolve().parents[2] / "docs"
    ap = argparse.ArgumentParser(description="Check CI pipeline examples in docs.")
    ap.add_argument("--docs", type=Path, default=default_docs)
    ap.add_argument(
        "--list", action="store_true", help="also list every CI block found"
    )
    ap.add_argument(
        "--report",
        action="store_true",
        help="print every check that ran per block, with PASS or FAIL and its source",
    )
    ap.add_argument(
        "--schema",
        type=Path,
        help="GitLab CI JSON schema file for the optional schema layer "
        "(else env GITLAB_CI_SCHEMA, else scripts/docs/gitlab-ci-schema.json if present)",
    )
    ns = ap.parse_args(argv)
    schema_path = ns.schema or (
        Path(os.environ["GITLAB_CI_SCHEMA"])
        if os.environ.get("GITLAB_CI_SCHEMA")
        else DEFAULT_SCHEMA
    )
    if ns.schema and not ns.schema.is_file():
        print(f"schema file not found: {ns.schema}", file=sys.stderr)
        return 2
    schema = schema_check(schema_path)
    findings: List[str] = []
    blocks: List[Dict[str, Any]] = []
    for md in sorted(ns.docs.rglob("*.md")):
        f, b = check_file(md, ns.docs, schema)
        findings += f
        blocks += b
    if ns.report:
        print_report(blocks)
    elif ns.list or not findings:
        for b in blocks:
            print(
                f"checked {b['path']}:{b['line']} [{b['kind']}] "
                f"{b['info'] or '(no title)'}"
            )
    for line in findings:
        print(line)
    print(f"{len(blocks)} CI example block(s) checked, {len(findings)} problem(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
