"""Schema validation, ``extends``, precedence and the built-in catalogue."""

import pytest

from inventag.templating.errors import TemplateError
from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.schema import SPECS

from .conftest import write

BUILTINS = sorted(p.stem for p in BUILTIN_DIR.glob("*.yaml"))


def test_catalogue_is_what_the_docs_promise():
    assert BUILTINS == [
        "ci-pipeline",
        "evidence-gdpr",
        "evidence-hipaa",
        "evidence-pci-dss",
        "evidence-pdpa",
        "evidence-soc2",
        "executive-summary",
        "finops-cost-allocation",
        "finops-cost-report",
        "org-multi-account",
        "security-baseline",
        "single-account",
        "standard-bom",
    ]


@pytest.mark.parametrize("name", BUILTINS)
def test_every_builtin_resolves(registry, name):
    template = registry.resolve(name)
    assert template.name == name
    assert template.file.path.stem == name


def test_unknown_field_suggests_and_gives_line(registry, user_dir):
    path = write(
        user_dir / "t.yaml",
        "kind: report\nname: t\nspec:\n  excel:\n    layuot: single-sheet\n",
    )
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    issue = info.value.issues[0]
    assert issue.line == 5
    assert issue.field == "spec.excel.layuot"
    assert "did you mean 'layout'" in issue.message


@pytest.mark.parametrize(
    "spec, field, fragment",
    [
        (
            "  excel:\n    layout: per_service\n",
            "spec.excel.layout",
            "did you mean 'per-service'",
        ),
        ("  colors:\n    header_fill: blue\n", "spec.colors.header_fill", "hex colour"),
        (
            "  word:\n    max_rows_per_service: 0\n",
            "spec.word.max_rows_per_service",
            "at least 1",
        ),
        (
            "  word:\n    sections: [cover, cover]\n",
            "spec.word.sections[1]",
            "duplicate",
        ),
        ("  tag_columns: some\n", "spec.tag_columns", "'all', 'none'"),
        ("  columns: []\n", "spec.columns", "at least 1"),
        ("  columns:\n    - header: X\n", "spec.columns[0].field", "is required"),
    ],
)
def test_report_type_errors(registry, user_dir, spec, field, fragment):
    path = write(user_dir / "r.yaml", "kind: report\nname: r\nspec:\n" + spec)
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    assert any(
        i.field == field and fragment in i.message for i in info.value.issues
    ), info.value


def test_required_top_level_fields(registry, user_dir):
    path = write(user_dir / "x.yaml", "description: no kind\n")
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    fields = {i.field for i in info.value.issues}
    assert {"kind", "name", "spec"} <= fields


def test_bad_name_and_format_version(registry, user_dir):
    path = write(
        user_dir / "x.yaml",
        "format_version: 2\nkind: report\nname: My_Report\nspec: {}\n",
    )
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    fields = {i.field for i in info.value.issues}
    assert {"format_version", "name"} <= fields


def test_tag_policy_checks(registry, user_dir):
    path = write(
        user_dir / "p.yaml",
        "kind: tag-policy\nname: p\nspec:\n  required_tags:\n"
        "    - key: A\n      pattern: '(['\n"
        "    - key: A\n"
        "    - key: B\n      allowed_values: [x]\n      pattern: 'x'\n",
    )
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    text = str(info.value)
    assert "not a valid regular expression" in text
    assert "listed twice" in text
    assert "either allowed_values or pattern" in text


def test_config_rejects_credentials_and_checks_accounts(registry, user_dir):
    path = write(
        user_dir / "c.yaml",
        "kind: config\nname: c\nspec:\n  accounts:\n"
        "    - account_id: 123\n"
        '    - account_id: "111111111111"\n      access_key_id: AKIAEXAMPLE\n'
        '    - account_id: "222222222222"\n'
        "      role_arn: arn:aws:iam::333333333333:role/R\n"
        "  fail_on_tag_violations: true\n  regions: [us-east-1, Mars]\n",
    )
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    text = str(info.value)
    assert "Put account IDs in quotes" in text
    assert "must not contain credentials" in text
    assert "role is in account 333333333333 but account_id is 222222222222" in text
    assert "needs spec.tag_policy" in text
    assert "region code" in text


# ----------------------------------------------------------------- extends


def test_extends_merges_mappings_and_replaces_lists(registry, user_dir):
    path = write(
        user_dir / "acme.yaml",
        "kind: report\nname: acme\nextends: standard-bom\nspec:\n"
        "  title: Acme inventory\n  excel:\n    layout: single-sheet\n"
        "  columns:\n    - field: resource_name\n",
    )
    template = registry.resolve(str(path))
    assert template.spec["title"] == "Acme inventory"
    assert template.spec["excel"]["layout"] == "single-sheet"
    assert template.spec["excel"]["freeze_header"] is True  # inherited
    assert [c["field"] for c in template.spec["columns"]] == ["resource_name"]
    assert template.spec["colors"]["header_fill"] == "1F3A5F"  # from standard-bom
    assert [t.name for t in template.chain] == ["acme", "standard-bom"]


def test_null_resets_to_default(registry, user_dir):
    path = write(
        user_dir / "a.yaml",
        "kind: report\nname: a\nextends: finops-cost-report\n"
        "spec:\n  tag_policy: null\n  subtitle: null\n",
    )
    template = registry.resolve(str(path))
    assert template.spec["tag_policy"] is None
    assert template.spec["subtitle"] == ""


def test_required_tags_merge_by_key(registry, user_dir):
    path = write(
        user_dir / "mine.yaml",
        "kind: tag-policy\nname: mine\nextends: finops-cost-allocation\nspec:\n"
        "  required_tags:\n"
        "    - key: Environment\n      allowed_values: [production, development]\n"
        "    - key: Project\n      remove: true\n"
        "    - key: DataClassification\n",
    )
    template = registry.resolve(str(path))
    keys = [t["key"] for t in template.spec["required_tags"]]
    assert keys == ["CostCenter", "Owner", "Environment", "DataClassification"]
    env = template.spec["required_tags"][2]
    assert env["allowed_values"] == ["production", "development"]
    assert all(
        "remove" not in t or t["remove"] is False
        for t in template.spec["required_tags"]
    )


def test_child_can_shadow_and_extend_builtin_of_same_name(registry, user_dir):
    write(
        user_dir / "standard-bom.yaml",
        "kind: report\nname: standard-bom\nextends: standard-bom\n"
        "spec:\n  title: Ours\n",
    )
    template = registry.resolve("standard-bom")
    assert template.spec["title"] == "Ours"
    assert template.chain[0].origin == "user"
    assert template.chain[1].origin == "builtin"


def test_extends_by_relative_path(registry, user_dir):
    write(user_dir / "base" / "b.yaml", "kind: report\nname: b\nspec:\n  title: Base\n")
    path = write(
        user_dir / "c.yaml", "kind: report\nname: c\nextends: ./base/b.yaml\nspec: {}\n"
    )
    assert registry.resolve(str(path)).spec["title"] == "Base"


def test_extends_cannot_escape_folder(registry, tmp_path, user_dir):
    write(tmp_path / "outside.yaml", "kind: report\nname: outside\nspec: {}\n")
    path = write(
        user_dir / "c.yaml",
        "kind: report\nname: c\nextends: ../outside.yaml\nspec: {}\n",
    )
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(path))
    assert "inside the template's folder" in str(info.value)
    assert info.value.issues[0].line == 3


def test_extends_url_is_refused(registry, user_dir):
    path = write(
        user_dir / "c.yaml",
        "kind: report\nname: c\nextends: https://example.com/x.yaml\nspec: {}\n",
    )
    with pytest.raises(TemplateError, match="URLs"):
        registry.resolve(str(path))


def test_extends_loop_detected(registry, user_dir):
    write(user_dir / "a.yaml", "kind: report\nname: a\nextends: b\nspec: {}\n")
    write(user_dir / "b.yaml", "kind: report\nname: b\nextends: a\nspec: {}\n")
    with pytest.raises(TemplateError, match="loop"):
        registry.resolve("a")


def test_extends_kind_mismatch(registry, user_dir):
    path = write(
        user_dir / "x.yaml",
        "kind: report\nname: x\nextends: security-baseline\nspec: {}\n",
    )
    with pytest.raises(TemplateError, match="tag-policy template"):
        registry.resolve(str(path))


def test_errors_in_parent_point_at_parent_file(registry, user_dir):
    write(
        user_dir / "p.yaml",
        "kind: report\nname: p\nspec:\n  excel:\n    layout: wrong\n",
    )
    child = write(user_dir / "c.yaml", "kind: report\nname: c\nextends: p\nspec: {}\n")
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(child))
    issue = info.value.issues[0]
    assert issue.source.endswith("p.yaml") and issue.line == 5


def test_missing_required_value_after_merge_points_at_child(registry, user_dir):
    child = write(
        user_dir / "c.yaml",
        "kind: tag-policy\nname: c\nextends: security-baseline\n"
        "spec:\n  required_tags:\n"
        "    - key: Owner\n      remove: true\n"
        "    - key: Environment\n      remove: true\n"
        "    - key: DataClassification\n      remove: true\n",
    )
    with pytest.raises(TemplateError) as info:
        registry.resolve(str(child))
    assert "at least 1" in str(info.value)


# --------------------------------------------------------------- precedence


def test_search_order_first_match_wins(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    write(first / "same.yaml", "kind: report\nname: same\nspec:\n  title: First\n")
    write(second / "same.yaml", "kind: report\nname: same\nspec:\n  title: Second\n")
    registry = TemplateRegistry([SearchDir("env", first), SearchDir("user", second)])
    assert registry.resolve("same").spec["title"] == "First"
    entries = registry.entries()
    assert entries[1].shadowed_by is entries[0]


def test_search_dirs_order(tmp_path, monkeypatch):
    from inventag.templating.registry import search_dirs

    env = {
        "INVENTAG_TEMPLATE_PATH": f"/a{__import__('os').pathsep}/b",
        "XDG_CONFIG_HOME": "/xdg",
    }
    dirs = search_dirs(cwd=tmp_path, env=env)
    assert [d.origin for d in dirs] == ["env", "env", "project", "user", "builtin"]
    assert str(dirs[2].path) == str(tmp_path / ".inventag" / "templates")
    assert str(dirs[3].path) == "/xdg/inventag/templates"


def test_yaml_beats_yml_in_same_folder(tmp_path):
    write(tmp_path / "t.yml", "kind: report\nname: t\nspec:\n  title: yml\n")
    write(tmp_path / "t.yaml", "kind: report\nname: t\nspec:\n  title: yaml\n")
    registry = TemplateRegistry([SearchDir("user", tmp_path)])
    assert registry.resolve("t").spec["title"] == "yaml"


def test_unknown_name_lists_where_it_looked(registry):
    with pytest.raises(TemplateError) as info:
        registry.resolve("does-not-exist")
    assert "inventag templates list" in str(info.value)


def test_every_schema_field_has_a_description():
    def walk(fields):
        for name, spec in fields.items():
            assert spec.description, name
            if spec.fields:
                walk(spec.fields)
            if spec.item is not None and spec.item.fields:
                walk(spec.item.fields)

    for fields in SPECS.values():
        walk(fields)


def test_docs_field_reference_is_up_to_date():
    from inventag.templating import reference

    text = reference.DOC.read_text()
    assert reference.update(text) == text, (
        "docs/templates/reference.md is out of date; run "
        "'python -m inventag.templating.reference --write'"
    )
