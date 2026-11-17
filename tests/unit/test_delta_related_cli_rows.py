"""Related resources are found for rows as the CLI saves them (A-48).

The scanner keeps network and identity links in ``raw_data`` in AWS shapes
(EC2 ``SecurityGroups[].GroupId``, ``VpcId``, ``SubnetId``; Lambda
``VpcConfig`` and ``Role``; RDS ``VpcSecurityGroups``; ``KmsKeyId``). The
change report reads them there, the way the network and security analyzers
do, and keeps the existing rule: two rows are related when they share a value
of the same field. A container (VPC, subnet, security group) carries only its
own ID, so members are related to their containers, not to each other through
the container.

The dependency patterns are compared without regard to case, so the Lambda
patterns (and Lambda rows under VPC changes) are no longer dead.
"""

from inventag.state import ChangelogGenerator, DeltaDetector

ACC = "123456789012"
REG = "us-east-1"


def _ec2(kind, rid):
    return f"arn:aws:ec2:{REG}:{ACC}:{kind}/{rid}"


def _row(service, type_, arn, rid, raw, tags=None):
    return {
        "service": service,
        "type": type_,
        "resource_type": type_,
        "id": rid,
        "resource_id": rid,
        "arn": arn,
        "region": REG,
        "account_id": ACC,
        "source_account_id": ACC,
        "source": "service-api",
        "tags": tags if tags is not None else {"Name": rid},
        "raw_data": raw,
    }


SG1, SG2 = _ec2("security-group", "sg-1"), _ec2("security-group", "sg-2")
I1, I2 = _ec2("instance", "i-1"), _ec2("instance", "i-2")
VPC, SUBNET = _ec2("vpc", "vpc-1"), _ec2("subnet", "subnet-1")
FN = f"arn:aws:lambda:{REG}:{ACC}:function:fn-1"
DB = f"arn:aws:rds:{REG}:{ACC}:db:db-1"


def _estate(sg1_tags=None, vpc_tags=None):
    return [
        _row("VPC", "VPC", VPC, "vpc-1", {"VpcId": "vpc-1"}, vpc_tags),
        _row(
            "VPC",
            "Subnet",
            SUBNET,
            "subnet-1",
            {"SubnetId": "subnet-1", "VpcId": "vpc-1"},
        ),
        _row(
            "VPC",
            "SecurityGroup",
            SG1,
            "sg-1",
            {"GroupId": "sg-1", "VpcId": "vpc-1"},
            sg1_tags,
        ),
        _row(
            "VPC", "SecurityGroup", SG2, "sg-2", {"GroupId": "sg-2", "VpcId": "vpc-1"}
        ),
        _row(
            "EC2",
            "Instance",
            I1,
            "i-1",
            {
                "InstanceId": "i-1",
                "VpcId": "vpc-1",
                "SubnetId": "subnet-1",
                "SecurityGroups": [{"GroupId": "sg-1", "GroupName": "web"}],
            },
        ),
        _row(
            "EC2",
            "Instance",
            I2,
            "i-2",
            {
                "InstanceId": "i-2",
                "VpcId": "vpc-1",
                "SubnetId": "subnet-1",
                "SecurityGroups": [{"GroupId": "sg-2", "GroupName": "db"}],
            },
        ),
        _row(
            "LAMBDA",
            "Function",
            FN,
            "fn-1",
            {
                "FunctionName": "fn-1",
                "Role": f"arn:aws:iam::{ACC}:role/app",
                "VpcConfig": {
                    "VpcId": "vpc-1",
                    "SubnetIds": ["subnet-1"],
                    "SecurityGroupIds": ["sg-1"],
                },
            },
        ),
        _row(
            "RDS",
            "DBInstance",
            DB,
            "db-1",
            {
                "DBInstanceIdentifier": "db-1",
                "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-2"}],
                "DBSubnetGroup": {
                    "VpcId": "vpc-1",
                    "Subnets": [{"SubnetIdentifier": "subnet-1"}],
                },
            },
        ),
    ]


def _related(report, arn):
    (change,) = [c for c in report.modified_resources if c.resource_arn == arn]
    return change.related_resources


def test_a_changed_security_group_lists_the_resources_that_use_it():
    report = DeltaDetector().detect_changes(
        _estate(), _estate(sg1_tags={"Name": "sg-1", "Env": "x"}), "s1", "s2"
    )
    # The instance and the function in sg-1, not i-2 (same VPC, other group).
    assert _related(report, SG1) == [I1, FN]


def test_a_changed_vpc_lists_its_members_not_its_plumbing():
    report = DeltaDetector().detect_changes(
        _estate(), _estate(vpc_tags={"Name": "vpc-1", "Env": "x"}), "s1", "s2"
    )
    assert _related(report, VPC) == [I1, I2, FN, DB]


def test_a_related_resource_is_listed_once():
    """Found by both passes (it depends on the change and the change affects
    it), it is still one resource: the count in the change log is true."""
    report = DeltaDetector().detect_changes(
        _estate(), _estate(sg1_tags={"Name": "sg-1", "Env": "x"}), "s1", "s2"
    )
    assert _related(report, SG1) == [I1, FN]
    markdown = ChangelogGenerator().generate_changelog(report).to_markdown()
    assert "This change may affect 2 related resource(s)." in markdown
