"""``policy.lock`` (package P2): the sha256 of every policy and set file."""

import hashlib
import json

import pytest

from inventag.policy import lock
from inventag.policy.schema import PolicyError

POLICY = (
    "format_version: 1\nkind: policy\nname: a-1\n"
    "spec: {id: A-1, severity: low, resource: {services: [S3]},\n"
    "       check: [{type: value, key: region, value: us-east-1}]}\n"
)
SET = "format_version: 1\nkind: policy-set\nname: s\nspec: {policies: [a-1]}\n"


@pytest.fixture
def root(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.yaml").write_text(POLICY)
    (tmp_path / "sub" / "s.yaml").write_text(SET)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "fixture.yaml").write_text("not: a policy\n")
    return tmp_path


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_render_lists_each_file_with_its_sha256_and_leaves_tests_out(root):
    data = json.loads(lock.render(root))
    assert data == {
        "files": {"a.yaml": sha(POLICY), "sub/s.yaml": sha(SET)},
        "format_version": 1,
        "kind": "lock",
    }


def test_render_is_byte_stable_sorted_with_a_final_newline(root):
    text = lock.render(root)
    assert text == lock.render(root)
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert text == json.dumps(json.loads(text), sort_keys=True, indent=2) + "\n"


def test_write_creates_policy_lock_and_the_lock_does_not_list_itself(root):
    path = lock.write(root)
    assert path == root / "policy.lock"
    assert lock.LOCK_NAME == "policy.lock"
    assert lock.verify(root) == []
    assert "policy.lock" not in json.loads(path.read_text())["files"]


def test_a_changed_file_is_reported(root):
    lock.write(root)
    (root / "a.yaml").write_text(POLICY.replace("low", "high"))
    assert lock.verify(root) == ["a.yaml: changed since policy.lock was written"]


def test_an_added_file_and_a_removed_file_are_reported(root):
    lock.write(root)
    (root / "b.yaml").write_text(POLICY.replace("A-1", "B-1").replace("a-1", "b-1"))
    (root / "sub" / "s.yaml").unlink()
    assert lock.verify(root) == [
        "b.yaml: not listed in policy.lock",
        "sub/s.yaml: listed in policy.lock but missing",
    ]


def test_require_unchanged_raises_one_issue_per_problem_in_the_file_line_form(root):
    lock.write(root)
    (root / "a.yaml").write_text(POLICY + "\n")
    with pytest.raises(PolicyError) as caught:
        lock.require_unchanged(root)
    (issue,) = caught.value.issues
    assert issue.source == "a.yaml"
    assert "changed since policy.lock was written" in str(issue)
    assert "inventag policy lock" in str(issue)  # the next step


def test_require_unchanged_passes_when_nothing_changed(root):
    lock.write(root)
    lock.require_unchanged(root)


def test_missing_lock_file_is_an_error_with_a_next_step(root):
    with pytest.raises(PolicyError) as caught:
        lock.require_unchanged(root)
    assert "policy.lock" in str(caught.value)
    assert "inventag policy lock" in str(caught.value)


@pytest.mark.parametrize(
    "text, phrase",
    [
        ("not json", "not valid JSON"),
        ("[]", "must be an object"),
        ('{"kind": "lock", "format_version": 2, "files": {}}', "format_version"),
        ('{"kind": "lock", "format_version": 1}', "files"),
        (
            '{"kind": "lock", "format_version": 1, "files": {"a.yaml": "xyz"}}',
            "64 hex",
        ),
        (
            '{"kind": "lock", "format_version": 1, "files": {"../a.yaml": "'
            + "0" * 64
            + '"}}',
            "stay inside",
        ),
        ('{"kind": "x", "format_version": 1, "files": {}}', "kind"),
    ],
)
def test_an_invalid_lock_file_is_refused(root, text, phrase):
    (root / "policy.lock").write_text(text)
    with pytest.raises(PolicyError) as caught:
        lock.verify(root)
    assert phrase in str(caught.value)
    assert str(caught.value).startswith("policy.lock")


def test_the_hash_is_of_the_bytes_so_a_line_ending_change_is_a_change(root):
    lock.write(root)
    (root / "a.yaml").write_bytes(POLICY.replace("\n", "\r\n").encode())
    assert lock.verify(root) == ["a.yaml: changed since policy.lock was written"]


def test_verify_writes_nothing(root):
    lock.write(root)
    before = sorted(p.name for p in root.rglob("*"))
    lock.verify(root)
    assert before == sorted(p.name for p in root.rglob("*"))


WAIVERS = (
    "format_version: 1\nkind: waivers\nname: w\n"
    "spec: {waivers: [{policy: A-1, resource: arn:x, reason: 'a reason long enough',\n"
    "                  approved_by: lead, expires: 2027-01-01}]}\n"
)


def test_waiver_files_are_in_the_lock_and_a_change_to_one_is_reported(root):
    (root / "w.yaml").write_text(WAIVERS)
    assert json.loads(lock.render(root))["files"]["w.yaml"] == sha(WAIVERS)
    lock.write(root)
    (root / "w.yaml").write_text(WAIVERS.replace("2027-01-01", "2027-02-01"))
    assert lock.verify(root) == ["w.yaml: changed since policy.lock was written"]


def test_a_waivers_file_outside_the_directory_or_not_in_the_lock_is_refused(
    root, tmp_path_factory
):
    (root / "w.yaml").write_text(WAIVERS)
    lock.write(root)
    outside = tmp_path_factory.mktemp("out") / "w.yaml"
    outside.write_text(WAIVERS)
    (root / "late.yaml").write_text(WAIVERS.replace("name: w", "name: late"))
    lock.require_listed(root, [root / "w.yaml"])
    with pytest.raises(PolicyError) as caught:
        lock.require_listed(root, [outside, root / "late.yaml"])
    issues = caught.value.issues
    assert len(issues) == 2
    assert "outside the policy directory" in str(issues[0])
    assert "not listed in policy.lock" in str(issues[1])
    assert all("inventag policy lock" in str(i) for i in issues)
