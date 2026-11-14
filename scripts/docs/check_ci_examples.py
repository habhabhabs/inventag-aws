#!/usr/bin/env python3
"""Check the CI pipeline examples in docs/ (GitHub Actions and GitLab CI/CD).

Run it through `npm run check:ci-examples` in website/ (it calls this file).
Uses PyYAML, which is already in requirements.txt; the website package has
no YAML parser of its own.

For every fenced yaml block in docs/**/*.md that names a workflow file or has
the top-level keys of one, it checks:
  - the block parses as YAML;
  - GitHub: every job has runs-on and steps, every `uses:` is pinned to a tag
    or a full commit SHA, `id-token: write` permissions exist where OIDC is used;
  - GitLab: every job has script, id_tokens entries have aud, and no top-level
    key is outside GITLAB_TOP_LEVEL_KEYS;
  - every `inventag` command line is accepted by InvenTag's argument parser.

Translated pages are compared by `npm run check:i18n` (every code block must be
byte-identical to the English one), so this script reads only docs/.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_cli_examples  # noqa: E402

# Top-level keys allowed in a GitLab CI example, besides jobs (a mapping with
# script, trigger or extends) and hidden jobs (names that start with a dot).
# The design memo /home/claude/audit/reports/v121-gitlab-ci-examples.md may
# extend this set: add its keys here, in one place.
GITLAB_TOP_LEVEL_KEYS = {
    "default",
    "include",
    "stages",
    "variables",
    "workflow",
    "image",
    "services",
    "cache",
    "before_script",
    "after_script",
}

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


def check_github(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return [(block["line"], "workflow has no jobs")]
    # PyYAML reads the key `on` as True (YAML 1.1)
    if "on" not in doc and True not in doc:
        out.append((block["line"], "workflow has no `on:` trigger"))
    top_perms = doc.get("permissions")
    oidc_text = "id-token" in block["body"] or "role-to-assume" in block["body"]
    for name, job in jobs.items():
        at = _line_of(block, f"{name}:")
        if not isinstance(job, dict):
            out.append((at, f"job `{name}` is not a mapping"))
            continue
        reusable = "uses" in job
        if reusable:
            problem = _pin_problem(str(job["uses"]))
            if problem:
                out.append((_line_of(block, str(job["uses"])), problem))
        else:
            if "runs-on" not in job:
                out.append((at, f"job `{name}` has no `runs-on`"))
            if not isinstance(job.get("steps"), list) or not job.get("steps"):
                out.append((at, f"job `{name}` has no `steps`"))
        for step in job.get("steps") or []:
            if isinstance(step, dict) and "uses" in step:
                problem = _pin_problem(str(step["uses"]))
                if problem:
                    out.append((_line_of(block, str(step["uses"])), problem))
        uses_oidc = oidc_text or any(
            isinstance(s, dict) and "role-to-assume" in (s.get("with") or {})
            for s in job.get("steps") or []
        )
        if uses_oidc and not (
            _has_id_token(job.get("permissions")) or _has_id_token(top_perms)
        ):
            out.append(
                (
                    at,
                    f"job `{name}` uses OIDC but has no `permissions: id-token: write`",
                )
            )
    return out


def check_gitlab(doc: Dict[Any, Any], block: Dict[str, Any]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []

    def check_tokens(tokens: Any, where: str, at: int) -> None:
        if not isinstance(tokens, dict):
            out.append((at, f"{where}: id_tokens must be a mapping"))
            return
        for tname, tval in tokens.items():
            if not isinstance(tval, dict) or "aud" not in tval:
                out.append(
                    (
                        _line_of(block, f"{tname}:"),
                        f"{where}: id_tokens `{tname}` has no `aud`",
                    )
                )

    for key, value in doc.items():
        at = _line_of(block, f"{key}:")
        if key == "default" and isinstance(value, dict) and "id_tokens" in value:
            check_tokens(value["id_tokens"], "default", at)
        if key in GITLAB_TOP_LEVEL_KEYS:
            continue
        if isinstance(key, str) and key.startswith("."):
            continue  # hidden job or template
        if isinstance(value, dict) and (
            "script" in value or "trigger" in value or "extends" in value
        ):
            if (
                "script" not in value
                and "trigger" not in value
                and "extends" not in value
            ):
                out.append((at, f"job `{key}` has no `script`"))
            if "id_tokens" in value:
                check_tokens(value["id_tokens"], f"job `{key}`", at)
            continue
        if isinstance(value, dict) and "script" not in value:
            out.append(
                (
                    at,
                    f"top-level key `{key}` is not a documented key and not a job "
                    "(no `script`)",
                )
            )
        else:
            out.append((at, f"top-level key `{key}` is not in the documented set"))
    return out


def check_file(path: Path, docs_root: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
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
        seen.append(block)
        problems: List[Tuple[int, str]] = []
        try:
            doc = yaml.safe_load(block["body"])
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            at = block["line"] + (mark.line if mark else 0)
            findings.append(
                f"{rel}:{at}: [{kind}] does not parse as YAML: "
                f"{getattr(exc, 'problem', exc)}"
            )
            continue
        if not isinstance(doc, dict):
            findings.append(f"{rel}:{block['line']}: [{kind}] is not a YAML mapping")
            continue
        problems += (
            check_github(doc, block) if kind == "github" else check_gitlab(doc, block)
        )
        problems += _commands(block)
        findings += [f"{rel}:{n}: [{kind}] {msg}" for n, msg in sorted(problems)]
    return findings, seen


def main(argv: Optional[List[str]] = None) -> int:
    default_docs = Path(__file__).resolve().parents[2] / "docs"
    ap = argparse.ArgumentParser(description="Check CI pipeline examples in docs.")
    ap.add_argument("--docs", type=Path, default=default_docs)
    ap.add_argument(
        "--list", action="store_true", help="also list every CI block found"
    )
    ns = ap.parse_args(argv)
    findings: List[str] = []
    blocks: List[Dict[str, Any]] = []
    for md in sorted(ns.docs.rglob("*.md")):
        f, b = check_file(md, ns.docs)
        findings += f
        blocks += b
    if ns.list or not findings:
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
