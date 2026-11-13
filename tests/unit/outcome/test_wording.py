"""Wording: every category has "Instead:" and a "More:" URL to a page that
exists in docs/ (invariants I7, I13); flags named in the text exist."""

import re
from pathlib import Path

import pytest

from inventag.outcome import wording
from inventag.outcome.model import PHASES, Category, Issue, Scope

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs"


def _slugify(heading: str) -> str:
    """Docusaurus (github-slugger) heading id."""
    text = re.sub(r"`", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.index("---", 3)
    out = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _pages():
    """URL path (without /docs/) -> file."""
    pages = {}
    for path in DOCS.rglob("*.md*"):
        if path.suffix not in (".md", ".mdx") or "assets" in path.parts:
            continue
        meta = _front_matter(path.read_text(encoding="utf-8"))
        if "slug" in meta:
            pages[meta["slug"].strip("/")] = path
        else:
            rel = path.relative_to(DOCS).with_suffix("").as_posix()
            if rel.endswith("/index"):
                rel = rel[: -len("/index")]
            pages[rel] = path
    return pages


def _anchors(path: Path):
    anchors = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if not m:
            continue
        title = m.group(1)
        pinned = re.search(r"\{#([\w-]+)\}", title)
        if pinned:
            anchors.add(pinned.group(1))
        anchors.add(_slugify(re.sub(r"\{#[\w-]+\}", "", title)))
    return anchors


def assert_url_exists(url: str):
    assert url.startswith(wording.DOCS), url
    path, _, anchor = url[len(wording.DOCS) :].partition("#")
    pages = _pages()
    assert path in pages, f"{url}: no page served at {path}"
    if anchor:
        assert anchor in _anchors(pages[path]), f"{url}: no heading #{anchor}"


def _all_more_urls():
    tables = [
        wording.CATEGORY_WORDING.values(),
        wording.SCOPE_WORDING.values(),
        wording.PHASE_WORDING.values(),
        wording.CODE_WORDING.values(),
    ]
    return sorted({w.more for t in tables for w in t if w.more})


def test_every_category_has_a_complete_entry():
    assert set(wording.CATEGORY_WORDING) == set(Category)
    for category, entry in wording.CATEGORY_WORDING.items():
        assert entry.what and entry.instead and entry.more, category


@pytest.mark.parametrize("url", _all_more_urls())
def test_more_urls_exist(url):
    assert_url_exists(url)


def test_the_url_check_catches_a_slugged_path():
    # docs/guides/read-only-access.md is served at user-guides/production-safety
    with pytest.raises(AssertionError):
        assert_url_exists(wording.DOCS + "guides/read-only-access")
    with pytest.raises(AssertionError):
        assert_url_exists(wording.DOCS + "guides/troubleshooting#no-such-heading")


def _every_issue():
    codes = [""] + sorted(wording.CODE_WORDING)
    for category in Category:
        for scope in Scope:
            for phase in ("",) + PHASES:
                for code in codes:
                    yield Issue(
                        scope=scope,
                        category=category,
                        account="111111111111",
                        region="eu-west-1",
                        service="sqs",
                        operation="ListQueues",
                        phase=phase,
                        code=code,
                    )


def test_every_combination_renders_without_a_dead_end():
    """I7 for every (category, scope, phase, code): message, Instead, More."""
    seen_more = set()
    for issue in _every_issue():
        message, instead, more = wording.render_texts(issue)
        assert message and instead and more, issue
        for text in (message, instead):
            assert "{" not in text and "}" not in text, (issue, text)
            assert "None" not in text, (issue, text)
        seen_more.add(more)
    for url in seen_more:
        assert_url_exists(url)


def test_minimal_issue_renders():
    message, instead, more = wording.render_texts(
        Issue(scope=Scope.RUN, category=Category.INTERNAL_ERROR)
    )
    assert message.startswith("An unexpected error occurred in InvenTag")
    assert "Instead" not in instead and instead


def _cli_flags():
    sources = [
        (REPO / "inventag/cli/main.py").read_text(encoding="utf-8"),
        (REPO / "inventag/templating/runner.py").read_text(encoding="utf-8"),
    ]
    flags = set()
    for src in sources:
        flags |= set(re.findall(r'"(--[a-z0-9-]+)"', src))
        # argparse.BooleanOptionalAction adds --no-<name>
        for name in re.findall(
            r'"--([a-z0-9-]+)",\s*\n?\s*action=argparse\.BooleanOptionalAction', src
        ):
            flags.add(f"--no-{name}")
    return flags | {"--help"}  # added by argparse


def test_flags_named_in_the_wording_exist():
    flags = _cli_flags()
    tables = [
        wording.CATEGORY_WORDING.values(),
        wording.SCOPE_WORDING.values(),
        wording.PHASE_WORDING.values(),
        wording.CODE_WORDING.values(),
    ]
    named = set()
    for table in tables:
        for entry in table:
            for text in (entry.what or "", entry.instead or ""):
                named |= set(re.findall(r"(--[a-z0-9-]+)", text))
    named.discard("--role-session-name")  # an aws CLI option
    named.discard("--role-arn")
    named.discard("--profile")
    named.discard("--bucket")
    assert named <= flags, named - flags


def test_permission_message_keeps_the_grep_prefix_and_the_action():
    issue = Issue(
        scope=Scope.SERVICE,
        category=Category.PERMISSION_DENIED,
        account="222222222222",
        service="sqs",
        operation="ListQueues",
        code="AccessDenied",
        regions=("eu-west-1", "us-east-1", "ap-southeast-1"),
        count=3,
    )
    message, instead, _ = wording.render_texts(issue)
    assert message.startswith("No permission for sqs in 3 regions")
    assert message.endswith("(ListQueues: AccessDenied)")
    assert "sqs:ListQueues" in instead


def test_iam_action_comes_from_the_policy_table_not_from_glued_strings():
    assert wording.iam_action("s3", "ListBuckets") == "s3:ListAllMyBuckets"
    assert wording.iam_action("resourcegroupstaggingapi", "GetResources") == (
        "tag:GetResources"
    )
    issue = Issue(
        scope=Scope.SERVICE,
        category=Category.PERMISSION_DENIED,
        service="madeup",
        operation="ListThings",
    )
    _, instead, _ = wording.render_texts(issue)
    assert "the read permission for madeup ListThings" in instead
    assert "madeup:ListThings" not in instead


@pytest.mark.parametrize(
    "aws_message,hint",
    [
        ("... with an explicit deny in a service control policy", "service control"),
        ("... with an explicit deny in an identity-based policy", "denies this"),
        ("... because no identity-based policy allows it", None),
    ],
)
def test_hints_from_aws_message_only_add_a_sentence(aws_message, hint):
    base = Issue(
        scope=Scope.SERVICE,
        category=Category.PERMISSION_DENIED,
        service="sqs",
        operation="ListQueues",
    )
    _, plain, _ = wording.render_texts(base)
    from dataclasses import replace

    _, instead, _ = wording.render_texts(replace(base, aws_message=aws_message))
    assert instead.endswith(plain)
    if hint:
        assert hint in instead and instead != plain
    else:
        assert instead == plain


def test_region_not_enabled_and_where():
    issue = Issue(
        scope=Scope.REGION,
        category=Category.NOT_ENABLED,
        account="222222222222",
        region="ap-east-1",
        code="AuthFailure",
        phase="region_check",
    )
    message, instead, more = wording.render_texts(issue)
    assert message == (
        "Region ap-east-1 is not enabled for account 222222222222; it was not "
        "scanned (AuthFailure)"
    )
    assert "--account-regions" in instead
    assert more.endswith("#a-region-is-not-enabled-for-the-account")


def test_global_region_is_not_named():
    issue = Issue(
        scope=Scope.SERVICE,
        category=Category.THROTTLED,
        service="iam",
        region="global",
    )
    assert wording.render_texts(issue)[0].startswith("AWS throttled iam and")


def test_apply_keeps_text_already_set():
    issue = Issue(
        scope=Scope.SERVICE,
        category=Category.THROTTLED,
        service="sqs",
        message="custom",
    )
    applied = wording.apply(issue)
    assert applied.message == "custom"
    assert applied.next_step and applied.more
