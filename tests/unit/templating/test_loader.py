"""Safe loading: YAML tags, limits, duplicate keys, file references."""

import pytest

from inventag.templating.errors import TemplateError
from inventag.templating.loader import (
    MAX_NODES,
    load_template_file,
    parse_template_text,
    safe_relative_path,
)


def test_parses_mapping_and_records_lines():
    t = parse_template_text("kind: report\nname: x\nspec:\n  title: Hi\n", "t.yaml")
    assert t.data["spec"]["title"] == "Hi"
    assert t.line_of(("spec", "title")) == 4
    assert t.line_of(("spec", "title", "missing")) == 4  # falls back to parent


@pytest.mark.parametrize(
    "text",
    [
        "kind: !!python/object/apply:os.system ['echo hacked']\n",
        "kind: !!python/name:os.system\n",
        "kind: !custom value\n",
    ],
)
def test_unsafe_yaml_tags_are_rejected(text, tmp_path):
    marker = tmp_path / "hacked"
    with pytest.raises(TemplateError) as info:
        parse_template_text(text.replace("echo hacked", f"touch {marker}"), "evil.yaml")
    assert not marker.exists()
    message = str(info.value)
    assert "evil.yaml:1" in message
    assert "not allowed" in message or "could not determine" in message


def test_duplicate_keys_are_an_error_with_line():
    with pytest.raises(TemplateError) as info:
        parse_template_text("kind: report\nname: a\nname: b\n", "d.yaml")
    assert "d.yaml:3" in str(info.value)
    assert "duplicate key 'name'" in str(info.value)


def test_invalid_yaml_reports_line():
    with pytest.raises(TemplateError) as info:
        parse_template_text("kind: report\nspec:\n  title: [unclosed\n", "bad.yaml")
    assert "invalid YAML" in str(info.value)
    assert "bad.yaml:" in str(info.value)


def test_alias_bomb_is_stopped():
    lines = ["a: &a [x, x, x, x, x, x, x, x, x, x]"]
    for i in range(1, 8):
        lines.append(
            f"{chr(97 + i)}: &{chr(97 + i)} [{', '.join(['*' + chr(96 + i)] * 10)}]"
        )
    with pytest.raises(TemplateError) as info:
        parse_template_text("\n".join(lines) + "\n", "bomb.yaml")
    assert str(MAX_NODES) in str(info.value)


def test_recursive_alias_is_stopped():
    with pytest.raises(TemplateError):
        parse_template_text("a: &a [*a]\n", "loop.yaml")


def test_top_level_must_be_mapping_and_not_empty():
    with pytest.raises(TemplateError, match="mapping"):
        parse_template_text("- a\n- b\n", "list.yaml")
    with pytest.raises(TemplateError, match="empty"):
        parse_template_text("# nothing\n", "empty.yaml")


def test_size_limit(tmp_path):
    path = tmp_path / "big.yaml"
    path.write_text("a: " + "x" * (300 * 1024))
    with pytest.raises(TemplateError, match="larger than"):
        load_template_file(path)


def test_non_utf8_file(tmp_path):
    path = tmp_path / "latin.yaml"
    path.write_bytes(b"name: caf\xe9\n")
    with pytest.raises(TemplateError, match="UTF-8"):
        load_template_file(path)


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.yaml",
        "sub/../../outside.yaml",
        "/etc/passwd",
        "~/secret.yaml",
        "https://example.com/t.yaml",
        "file:///etc/passwd",
        "",
    ],
)
def test_safe_relative_path_rejects_escapes(tmp_path, reference):
    with pytest.raises(ValueError):
        safe_relative_path(tmp_path, reference)


def test_safe_relative_path_rejects_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.png").write_bytes(b"x")
    base = tmp_path / "base"
    base.mkdir()
    (base / "link").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_relative_path(base, "link/x.png")


def test_safe_relative_path_allows_subfolders(tmp_path):
    (tmp_path / "img").mkdir()
    assert (
        safe_relative_path(tmp_path, "img/logo.png")
        == (tmp_path / "img" / "logo.png").resolve()
    )
    assert (
        safe_relative_path(tmp_path, "./img/../logo.png")
        == (tmp_path / "logo.png").resolve()
    )
