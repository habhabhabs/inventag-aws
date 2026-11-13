"""The five evidence-* tag-policy templates: wording, loading and evaluation."""

import io
import re

import pytest

from inventag.templating import cli as templates_cli
from inventag.templating.loader import load_template_file
from inventag.templating.registry import BUILTIN_DIR, SearchDir, TemplateRegistry
from inventag.templating.tag_policy import evaluate

NAMES = [
    "evidence-soc2",
    "evidence-hipaa",
    "evidence-pci-dss",
    "evidence-gdpr",
    "evidence-pdpa",
]
DISCLAIMER = "Checks tag evidence only; certifies nothing."
BANNED = ["compliant", "certified", "audit-ready", "ensures", "requires"]


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry([SearchDir("builtin", BUILTIN_DIR)])


def _raw(name):
    return (BUILTIN_DIR / f"{name}.yaml").read_text(encoding="utf-8")


def _file(name):
    return load_template_file(BUILTIN_DIR / f"{name}.yaml", "builtin")


@pytest.mark.parametrize("name", NAMES)
def test_loads_as_tag_policy_extending_baseline(registry, name):
    resolved = registry.resolve(name)
    assert resolved.kind == "tag-policy" and resolved.name == name
    assert _file(name).data["extends"] == "security-baseline"
    assert [t.name for t in resolved.chain] == [name, "security-baseline"]
    keys = [r["key"] for r in resolved.spec["required_tags"]]
    assert {"Owner", "Environment", "DataClassification"} <= set(keys)


@pytest.mark.parametrize("name", NAMES)
def test_disclaimer_is_last_sentence_and_in_header(name):
    description = " ".join(str(_file(name).data["description"]).split())
    assert description.endswith(DISCLAIMER)
    header = " ".join(
        line.lstrip("# ") for line in _raw(name).splitlines() if line.startswith("#")
    )
    assert "checks tag evidence only" in header.lower()
    assert "certifies nothing" in header.lower()


@pytest.mark.parametrize("name", NAMES)
def test_no_overclaiming_words(name):
    text = _raw(name).lower()
    for word in BANNED:
        assert not re.search(rf"\b{re.escape(word)}\b", text), (name, word)


@pytest.mark.parametrize("name", NAMES)
def test_yes_no_values_are_quoted_strings(registry, name):
    raw = _raw(name)
    assert not re.search(
        r"allowed_values:\s*\[(?:[^\]]*[\[,]\s*)?(yes|no|on|off|y|n)\s*[,\]]", raw
    )
    for rule in registry.resolve(name).spec["required_tags"]:
        for value in rule.get("allowed_values") or []:
            assert isinstance(value, str)
    if name == "evidence-hipaa":
        assert 'allowed_values: ["yes", "no"]' in raw


def test_o6_vocabularies(registry):
    def rule(name, key):
        rules = registry.resolve(name).spec["required_tags"]
        return next(r for r in rules if r["key"] == key)

    assert rule("evidence-pdpa", "PersonalData")["allowed_values"] == [
        "none",
        "personal",
        "special-category",
    ]
    assert rule("evidence-gdpr", "PersonalData")["allowed_values"] == [
        "none",
        "personal",
        "special-category",
    ]
    assert "other" in rule("evidence-soc2", "ManagedBy")["allowed_values"]
    card = rule("evidence-pci-dss", "CardholderData")
    assert "pick the main one" in card["description"]
    assert card["allowed_values"] == ["stores", "processes", "transmits", "none"]
    assert "phi" in rule("evidence-hipaa", "DataClassification")["allowed_values"]


def _res(service, rtype, tags):
    return {
        "service": service,
        "resource_type": rtype,
        "arn": f"arn:{rtype}",
        "tags": tags,
    }


BASE = {"Owner": "a", "Environment": "prod", "DataClassification": "internal"}

# name -> (resources, expected compliant flags for in-scope resources, out of scope)
SAMPLES = {
    "evidence-soc2": (
        [
            _res(
                "EC2",
                "Instance",
                {
                    **BASE,
                    "Soc2Scope": "in-scope",
                    "SystemName": "pay",
                    "ManagedBy": "Terraform",
                    "Criticality": "high",
                },
            ),
            _res(
                "EC2",
                "Instance",
                {
                    **BASE,
                    "Soc2Scope": "IN",
                    "SystemName": " ",
                    "ManagedBy": "manual",
                    "Criticality": "high",
                },
            ),
            _res(
                "EC2",
                "Instance",
                {
                    **BASE,
                    "Soc2Scope": "out-of-scope",
                    "SystemName": "x",
                    "ManagedBy": "other",
                    "Criticality": "low",
                },
            ),
        ],
        [True, False, True],
        0,
    ),
    "evidence-hipaa": (
        [
            _res(
                "S3",
                "Bucket",
                {
                    **BASE,
                    "DataClassification": "phi",
                    "PHI": "Yes",
                    "RetentionPeriod": "7y",
                },
            ),
            _res("S3", "Bucket", {**BASE, "PHI": "yes", "RetentionPeriod": "7Y"}),
            _res("VPC", "Subnet", {}),
        ],
        [True, False],
        1,
    ),
    "evidence-pci-dss": (
        [
            _res(
                "EC2",
                "Instance",
                {**BASE, "PciScope": "cde", "CardholderData": "stores"},
            ),
            _res(
                "EC2",
                "Instance",
                {**BASE, "PciScope": "cde", "CardholderData": "stores,transmits"},
            ),
            _res("VPC", "RouteTable", {}),
        ],
        [True, False],
        1,
    ),
    "evidence-gdpr": (
        [
            _res(
                "RDS",
                "DBInstance",
                {
                    **BASE,
                    "PersonalData": "special-category",
                    "ProcessingRecord": "ROPA-12",
                    "DataResidency": "eu",
                    "RetentionPeriod": "indefinite",
                },
            ),
            _res(
                "RDS",
                "DBInstance",
                {
                    **BASE,
                    "PersonalData": "yes",
                    "ProcessingRecord": "",
                    "DataResidency": "EU",
                    "RetentionPeriod": "7 years",
                },
            ),
        ],
        [True, False],
        0,
    ),
    "evidence-pdpa": (
        [
            _res(
                "DYNAMODB",
                "Table",
                {
                    **BASE,
                    "PersonalData": "personal",
                    "Purpose": "billing",
                    "RetentionPeriod": "30d",
                    "DataLocation": "sg",
                },
            ),
            _res(
                "DYNAMODB",
                "Table",
                {
                    **BASE,
                    "PersonalData": "special-category",
                    "Purpose": "billing",
                    "RetentionPeriod": "30d",
                    "DataLocation": "overseas",
                },
            ),
            _res(
                "DYNAMODB",
                "Table",
                {
                    **BASE,
                    "PersonalData": "yes",
                    "Purpose": "",
                    "RetentionPeriod": "30d",
                    "DataLocation": "SG",
                },
            ),
        ],
        [True, True, False],
        0,
    ),
}


def test_samples_cover_every_template():
    assert set(SAMPLES) == set(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_sample_resources_pass_and_fail_as_expected(registry, name):
    resources, expected, out_of_scope = SAMPLES[name]
    report = evaluate(resources, registry.resolve(name))
    assert [f.compliant for f in report.findings] == expected
    assert report.out_of_scope == out_of_scope


def test_missing_data_tags_fail(registry):
    report = evaluate(
        [_res("S3", "Bucket", dict(BASE))], registry.resolve("evidence-hipaa")
    )
    assert report.findings[0].missing == ["PHI", "RetentionPeriod"]


def test_listing_for_tag_policy_includes_the_five():
    out = io.StringIO()
    assert templates_cli.main(["list", "--kind", "tag-policy"], out=out) == 0
    names = {line.split()[0] for line in out.getvalue().splitlines() if line}
    assert set(NAMES) <= names
    assert {"security-baseline", "finops-cost-allocation"} <= names
