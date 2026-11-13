"""Settings files such as --bom-config: loading and applying."""

import dataclasses
from decimal import Decimal

import pytest

from inventag.reporting.bom_processor import BOMProcessingConfig
from inventag.reporting.settings_loader import (
    MAX_SETTINGS_BYTES,
    SettingsFileError,
    apply_bom_settings,
    load_settings_file,
    read_bom_settings,
    valid_bom_setting_names,
)


def put(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


def test_valid_names_match_the_dataclass():
    assert valid_bom_setting_names() == sorted(
        f.name for f in dataclasses.fields(BOMProcessingConfig)
    )


@pytest.mark.parametrize(
    "name, data",
    [
        ("a.yaml", "enable_cost_analysis: true\n"),
        ("a.yml", "\ufeffenable_cost_analysis: true\n"),
        ("a.json", '{"enable_cost_analysis": true}'),
        ("a.JSON", b'\xef\xbb\xbf{"enable_cost_analysis": true}'),
        ("noext", '{"enable_cost_analysis": true}'),
        ("noext2", "enable_cost_analysis: true"),
        ("crlf.yaml", "enable_cost_analysis: true\r\n"),
        ("anchor.yaml", "x: &a true\nenable_cost_analysis: *a\n"),
    ],
)
def test_formats_and_encodings(tmp_path, name, data):
    got = load_settings_file(put(tmp_path, name, data))
    assert got["enable_cost_analysis"] is True


def test_unicode_values_survive(tmp_path):
    f = put(tmp_path, "u.yaml", "service_descriptions_config: 'café/ü.yaml'\n")
    assert load_settings_file(f)["service_descriptions_config"] == "café/ü.yaml"


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("e.yaml", "", "the file is empty"),
        ("c.yaml", "# only a comment\n", "the file is empty"),
        ("l.json", "[1, 2]", "holds a list"),
        ("s.yaml", "just text", "holds text"),
        ("d.yaml", "a: 1\na: 2\n", "duplicate key 'a'"),
        ("d.json", '{"a": 1, "a": 2}', "duplicate key 'a'"),
        ("t.yaml", "a:\n\tb: 1\n", "character '\\t'"),
        ("bad.json", "{", "invalid JSON"),
        ("x.txt", "a: 1", "unsupported file type"),
        ("n.yaml", b"\xff\xfe\x00bad", "not UTF-8"),
    ],
)
def test_problems_name_the_file(tmp_path, name, data, message):
    f = put(tmp_path, name, data)
    with pytest.raises(SettingsFileError) as error:
        load_settings_file(f, "--bom-config")
    assert message in str(error.value)
    assert name in str(error.value) and "--bom-config" in str(error.value)


def test_duplicate_yaml_key_reports_a_line(tmp_path):
    f = put(tmp_path, "d.yaml", "a: 1\nb: 2\na: 3\n")
    with pytest.raises(SettingsFileError, match=r"d\.yaml:3: duplicate key 'a'"):
        load_settings_file(f)


def test_missing_and_huge_files(tmp_path):
    with pytest.raises(SettingsFileError, match="file not found"):
        load_settings_file(tmp_path / "nope.yaml")
    with pytest.raises(SettingsFileError, match="is not valid"):
        load_settings_file("")
    f = put(tmp_path, "big.yaml", "a: " + "x" * (MAX_SETTINGS_BYTES + 1))
    with pytest.raises(SettingsFileError, match="maximum"):
        load_settings_file(f)
    with pytest.raises(SettingsFileError, match="maximum"):
        load_settings_file(put(tmp_path, "s.yaml", "a: 1\n"), max_bytes=2)


def test_windows_style_path_text_is_just_text(tmp_path):
    f = put(tmp_path, "w.yaml", "tag_mappings_config: 'C:\\data\\tags.yaml'\n")
    assert load_settings_file(f)["tag_mappings_config"] == "C:\\data\\tags.yaml"


def test_apply_sets_values_and_reports_ignored_keys():
    config = BOMProcessingConfig()
    ignored = apply_bom_settings(
        config,
        {
            "enable_cost_analysis": True,
            "max_worker_threads": 8,
            "tag_mappings_config": "t.yaml",
            "typo_key": 1,
            "cost_thresholds": {
                "expensive_resource_monthly_threshold": 250,
                "forgotten_resource_days_threshold": 10,
                "cost_trend_alert_percentage": 20.5,
            },
        },
    )
    assert ignored == ["typo_key"]
    assert config.enable_cost_analysis is True and config.max_worker_threads == 8
    assert config.tag_mappings_config == "t.yaml"
    assert config.cost_thresholds.expensive_resource_monthly_threshold == Decimal(250)
    assert config.cost_thresholds.forgotten_resource_days_threshold == 10


@pytest.mark.parametrize(
    "settings, message",
    [
        ({"max_worker_threads": "x"}, "max_worker_threads must be a whole number"),
        ({"max_worker_threads": 0}, "max_worker_threads must be a whole number"),
        ({"max_worker_threads": True}, "max_worker_threads"),
        ({"enable_cost_analysis": "yes"}, "enable_cost_analysis must be true or false"),
        ({"processing_timeout": 1.5}, "processing_timeout"),
        ({"tag_mappings_config": 5}, "tag_mappings_config must be a file path"),
        ({"cost_thresholds": [1]}, "cost_thresholds must be a mapping"),
        ({"cost_thresholds": {"nope": 1}}, "unknown key"),
        ({"cost_thresholds": {"cost_trend_alert_percentage": "x"}}, "number"),
        ({"cost_thresholds": {"forgotten_resource_days_threshold": 1.5}}, "whole"),
    ],
)
def test_wrong_types_name_the_key_and_change_nothing(settings, message):
    config = BOMProcessingConfig()
    before = dataclasses.asdict(config)
    with pytest.raises(SettingsFileError, match=message):
        apply_bom_settings(config, {"enable_cost_analysis": True, **settings})
    assert dataclasses.asdict(config) == before


def test_read_bom_settings_end_to_end(tmp_path):
    f = put(tmp_path, "b.yaml", "enable_network_analysis: false\nbogus: 1\n")
    config = BOMProcessingConfig()
    assert read_bom_settings(f, config) == ["bogus"]
    assert config.enable_network_analysis is False
