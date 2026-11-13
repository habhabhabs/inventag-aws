"""A small, fixed AWS estate for end-to-end CLI tests (moto only).

``seed_estate()`` must be called inside ``mock_aws()``. It is also used by
``_moto_runner.py`` so a subprocess sees the same estate as an in-process test.
"""

import boto3

REGION = "us-east-1"
OWNER_TAG = {"Key": "Owner", "Value": "platform"}
ENV_TAG = {"Key": "Environment", "Value": "prod"}


def seed_estate(region: str = REGION) -> dict:
    """Create a VPC, subnet, open security group, bucket, queue, topic and table."""
    ec2 = boto3.client("ec2", region_name=region)
    vpc_id = ec2.create_vpc(
        CidrBlock="10.20.0.0/16",
        TagSpecifications=[
            {
                "ResourceType": "vpc",
                "Tags": [{"Key": "Name", "Value": "e2e-vpc"}, OWNER_TAG, ENV_TAG],
            }
        ],
    )["Vpc"]["VpcId"]
    subnet_id = ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.20.1.0/24", AvailabilityZone=f"{region}a"
    )["Subnet"]["SubnetId"]
    sg_id = ec2.create_security_group(
        GroupName="e2e-open-ssh", Description="open ssh", VpcId=vpc_id
    )["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }
        ],
    )
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(Bucket="e2e-bucket-one")
    s3.put_bucket_tagging(
        Bucket="e2e-bucket-one",
        Tagging={"TagSet": [OWNER_TAG, ENV_TAG]},
    )
    queue_url = boto3.client("sqs", region_name=region).create_queue(
        QueueName="e2e-queue", tags={"Owner": "platform"}
    )["QueueUrl"]
    topic_arn = boto3.client("sns", region_name=region).create_topic(
        Name="e2e-topic", Tags=[OWNER_TAG]
    )["TopicArn"]
    boto3.client("dynamodb", region_name=region).create_table(
        TableName="e2e-table",
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
        Tags=[OWNER_TAG],
    )
    return {
        "vpc_id": vpc_id,
        "subnet_id": subnet_id,
        "sg_id": sg_id,
        "bucket": "e2e-bucket-one",
        "queue_url": queue_url,
        "topic_arn": topic_arn,
        "table": "e2e-table",
    }


def seed_compute(region: str = REGION) -> dict:
    """Add one tagged EC2 instance and one tagged Lambda function."""
    import io
    import zipfile

    ec2 = boto3.client("ec2", region_name=region)
    instance_id = ec2.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [OWNER_TAG, {"Key": "Name", "Value": "e2e-box"}],
            }
        ],
    )["Instances"][0]["InstanceId"]
    role_arn = boto3.client("iam", region_name=region).create_role(
        RoleName="e2e-lambda-role", AssumeRolePolicyDocument="{}"
    )["Role"]["Arn"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("app.py", "def handler(event, context):\n    return 1\n")
    boto3.client("lambda", region_name=region).create_function(
        FunctionName="e2e-fn",
        Runtime="python3.12",
        Role=role_arn,
        Handler="app.handler",
        Code={"ZipFile": buffer.getvalue()},
        Tags={"Owner": "platform"},
    )
    return {"instance_id": instance_id, "function": "e2e-fn"}
