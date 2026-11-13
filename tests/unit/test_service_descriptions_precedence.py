"""A description from --service-descriptions beats a built-in one."""

import pytest
import yaml

from inventag.discovery.service_descriptions import ServiceDescriptionManager

CASES = [
    ("S3", "Bucket", "b-1", "Team bucket"),
    ("EC2", "Instance", "i-0abc", "Team server"),
    ("RDS", "DBInstance", "db-1", "Team database"),
    ("LAMBDA", "Function", "fn-1", "Team function"),
    ("VPC", "VPC", "vpc-1", "Team network"),
    ("DYNAMODB", "Table", "tbl-1", "Team table"),  # no built-in description
]


def _manager(tmp_path, body):
    path = tmp_path / "descriptions.yaml"
    path.write_text(yaml.safe_dump(body))
    manager = ServiceDescriptionManager(str(path))
    assert manager.last_reload is not None  # the file was accepted
    return manager


def _resource(service, rtype, rid):
    return {
        "id": rid,
        "service": service,
        "type": rtype,
        "region": "us-east-1",
        "service_attributes": {
            "InstanceType": "t3.micro",
            "Engine": "postgres",
            "Runtime": "python3.12",
            "CidrBlock": "10.0.0.0/16",
        },
    }


@pytest.mark.parametrize("service,rtype,rid,text", CASES)
def test_plain_description_for_resource_type_wins(tmp_path, service, rtype, rid, text):
    manager = _manager(
        tmp_path, {"service_descriptions": {service: {rtype: {"description": text}}}}
    )
    assert manager.get_dynamic_description(_resource(service, rtype, rid)) == text


@pytest.mark.parametrize("service,rtype,rid,text", CASES)
def test_plain_service_default_wins(tmp_path, service, rtype, rid, text):
    manager = _manager(
        tmp_path,
        {"service_descriptions": {service: {"default": {"description": text}}}},
    )
    assert manager.get_dynamic_description(_resource(service, rtype, rid)) == text


@pytest.mark.parametrize("service,rtype,rid,text", CASES)
def test_service_key_in_file_is_not_case_sensitive(tmp_path, service, rtype, rid, text):
    manager = _manager(
        tmp_path,
        {"service_descriptions": {service.lower(): {rtype: {"description": text}}}},
    )
    assert manager.get_dynamic_description(_resource(service, rtype, rid)) == text


@pytest.mark.parametrize("service,rtype,rid,text", CASES)
def test_template_still_works(tmp_path, service, rtype, rid, text):
    manager = _manager(
        tmp_path,
        {
            "service_descriptions": {
                service: {rtype: {"description": text, "template": "mine"}}
            },
            "templates": {"mine": {"template": "Mine {resource_id} in {region}"}},
        },
    )
    got = manager.get_dynamic_description(_resource(service, rtype, rid))
    assert got == f"Mine {rid} in us-east-1"


def test_failed_template_falls_back_to_user_description_not_builtin(tmp_path):
    manager = _manager(
        tmp_path,
        {
            "service_descriptions": {
                "EC2": {"Instance": {"description": "Mine", "template": "needs_x"}}
            },
            "templates": {
                "needs_x": {
                    "template": "x={x}",
                    "required_attributes": ["service_attributes.Missing"],
                }
            },
        },
    )
    assert (
        manager.get_dynamic_description(_resource("EC2", "Instance", "i-1")) == "Mine"
    )


def test_user_default_beats_builtin_resource_type_entry(tmp_path):
    manager = _manager(
        tmp_path,
        {"service_descriptions": {"EC2": {"default": {"description": "Any EC2"}}}},
    )
    assert (
        manager.get_dynamic_description(_resource("EC2", "Volume", "vol-1"))
        == "Any EC2"
    )


def test_user_resource_type_entry_beats_user_default(tmp_path):
    manager = _manager(
        tmp_path,
        {
            "service_descriptions": {
                "S3": {
                    "default": {"description": "Any S3"},
                    "Bucket": {"description": "A bucket"},
                }
            }
        },
    )
    assert manager.get_dynamic_description(_resource("S3", "Bucket", "b")) == "A bucket"
    assert manager.get_dynamic_description(_resource("S3", "Other", "o")) == "Any S3"


def test_builtin_text_is_kept_for_services_without_user_entry(tmp_path):
    manager = _manager(
        tmp_path,
        {"service_descriptions": {"DYNAMODB": {"default": {"description": "T"}}}},
    )
    # Built-in text (here the fallback templates, as the richer ones need
    # attributes the resource does not have).
    assert (
        manager.get_dynamic_description(_resource("S3", "Bucket", "my-bucket"))
        == "Amazon S3 Bucket (my-bucket)"
    )
    assert (
        manager.get_dynamic_description(_resource("EC2", "Instance", "i-9"))
        == "Amazon EC2 Instance (i-9) in us-east-1"
    )


def test_service_without_any_entry_gets_generic_text():
    manager = ServiceDescriptionManager()
    assert (
        manager.get_dynamic_description(_resource("SQS", "Queue", "q"))
        == "AWS SQS Queue - Cloud resource managed by Amazon Web Services"
    )


def test_metadata_reports_custom_description_and_template(tmp_path):
    manager = _manager(
        tmp_path,
        {"service_descriptions": {"RDS": {"DBInstance": {"description": "Mine"}}}},
    )
    out = manager.apply_descriptions_to_resources(
        [_resource("RDS", "DBInstance", "d")]
    )[0]
    assert out["service_description"] == "Mine"
    assert out["description_metadata"]["has_custom_description"] is True
    assert out["description_metadata"]["template_used"] is None
