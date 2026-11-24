"""A moto estate with one resource that passes and one that fails for each
shipped encryption and exposure rule, and the resources of the rules that are
not shipped (call ``seed()`` inside ``mock_aws()``)."""

import boto3

from tests.unit.finops import estate as finops_estate

SERVICES = "ec2,vpc,elb,elbv2,s3,rds,efs,sqs,sns,dynamodb"
REGION = "us-east-1"


def seed():
    finops_estate.seed()
    ec2 = boto3.client("ec2", region_name=REGION)
    for encrypted in (True, False):
        volume = ec2.create_volume(
            AvailabilityZone=REGION + "a", Size=1, Encrypted=encrypted
        )["VolumeId"]
        ec2.create_snapshot(VolumeId=volume)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    open_group = ec2.create_security_group(
        GroupName="open", Description="open", VpcId=vpc
    )["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=open_group,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }
        ],
    )
    ec2.create_security_group(GroupName="closed", Description="closed", VpcId=vpc)
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="probe-encrypted")
    s3.put_bucket_encryption(
        Bucket="probe-encrypted",
        ServerSideEncryptionConfiguration={
            "Rules": [
                {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
            ]
        },
    )
    rds = boto3.client("rds", region_name=REGION)
    for name, encrypted, public in (
        ("db-open", True, True),
        ("db-closed", False, False),
    ):
        rds.create_db_instance(
            DBInstanceIdentifier=name,
            DBInstanceClass="db.t3.micro",
            Engine="postgres",
            MasterUsername="admin",
            MasterUserPassword="not-a-real-password-1",
            AllocatedStorage=20,
            StorageEncrypted=encrypted,
            PubliclyAccessible=public,
        )
    efs = boto3.client("efs", region_name=REGION)
    efs.create_file_system(Encrypted=True, CreationToken="enc")
    efs.create_file_system(Encrypted=False, CreationToken="plain")
    boto3.client("sqs", region_name=REGION).create_queue(
        QueueName="q1", Attributes={"SqsManagedSseEnabled": "true"}
    )
    boto3.client("sns", region_name=REGION).create_topic(Name="t1")
    boto3.client("dynamodb", region_name=REGION).create_table(
        TableName="d1",
        KeySchema=[{"AttributeName": "k", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "k", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
