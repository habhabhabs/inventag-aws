"""A moto estate for the FinOps checks: one failing and one passing resource
per check (call ``seed()`` inside ``mock_aws()``)."""

import boto3

REGION = "us-east-1"
ALLOCATION_TAGS = [
    {"Key": "CostCenter", "Value": "CC-1234"},
    {"Key": "Owner", "Value": "platform"},
    {"Key": "Project", "Value": "inventory"},
    {"Key": "Environment", "Value": "prod"},
]


def _spec(resource_type, name, tags=()):
    return [
        {
            "ResourceType": resource_type,
            "Tags": [{"Key": "Name", "Value": name}, *tags],
        }
    ]


def seed(region: str = REGION) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    vpc_id = ec2.create_vpc(CidrBlock="10.30.0.0/16")["Vpc"]["VpcId"]
    subnet_a = ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.30.1.0/24", AvailabilityZone=f"{region}a"
    )["Subnet"]["SubnetId"]
    subnet_b = ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.30.2.0/24", AvailabilityZone=f"{region}b"
    )["Subnet"]["SubnetId"]

    running, stopped = [
        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            SubnetId=subnet_a,
            TagSpecifications=_spec("instance", name, ALLOCATION_TAGS),
        )["Instances"][0]["InstanceId"]
        for name in ("finops-running", "finops-stopped")
    ]
    ec2.stop_instances(InstanceIds=[stopped])

    attached = ec2.create_volume(
        AvailabilityZone=f"{region}a",
        Size=1,
        TagSpecifications=_spec("volume", "finops-attached", ALLOCATION_TAGS),
    )["VolumeId"]
    ec2.attach_volume(VolumeId=attached, InstanceId=running, Device="/dev/sdf")
    loose = ec2.create_volume(
        AvailabilityZone=f"{region}a",
        Size=1,
        TagSpecifications=_spec("volume", "finops-loose"),
    )["VolumeId"]
    snapshot = ec2.create_snapshot(
        VolumeId=attached,
        TagSpecifications=_spec("snapshot", "finops-snap", ALLOCATION_TAGS),
    )["SnapshotId"]

    associated = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.associate_address(AllocationId=associated, InstanceId=running)
    free = ec2.allocate_address(Domain="vpc")["AllocationId"]

    elbv2 = boto3.client("elbv2", region_name=region)
    used_lb = elbv2.create_load_balancer(
        Name="finops-used", Subnets=[subnet_a, subnet_b]
    )["LoadBalancers"][0]["LoadBalancerArn"]
    bare_lb = elbv2.create_load_balancer(
        Name="finops-bare", Subnets=[subnet_a, subnet_b]
    )["LoadBalancers"][0]["LoadBalancerArn"]
    group = elbv2.create_target_group(
        Name="finops-tg", Protocol="HTTP", Port=80, VpcId=vpc_id
    )["TargetGroups"][0]["TargetGroupArn"]
    elbv2.create_listener(
        LoadBalancerArn=used_lb,
        Protocol="HTTP",
        Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": group}],
    )

    elb = boto3.client("elb", region_name=region)
    listener = [{"Protocol": "HTTP", "LoadBalancerPort": 80, "InstancePort": 80}]
    for name in ("finops-classic-used", "finops-classic-bare"):
        elb.create_load_balancer(
            LoadBalancerName=name,
            Listeners=listener,
            AvailabilityZones=[f"{region}a"],
        )
    elb.register_instances_with_load_balancer(
        LoadBalancerName="finops-classic-used", Instances=[{"InstanceId": running}]
    )
    return {
        "running": running,
        "stopped": stopped,
        "attached": attached,
        "loose": loose,
        "snapshot": snapshot,
        "associated": associated,
        "free": free,
        "used_lb": used_lb,
        "bare_lb": bare_lb,
        "group": group,
    }
