---
title: Network and security analysis
description: What InvenTag's network and security-group analysis flags add to the Excel report, what they leave out, and how to review VPCs and security groups.
sidebar_position: 5
slug: /architecture/network-analysis
---

# Network and security analysis

**Who this is for:** you want to review VPCs, subnets and security groups with
InvenTag.

**What you will know after reading:** what the analysis flags add to a report.

## What the flags add

InvenTag has two flags for this:

- `--enable-network-analysis`: VPCs, subnets and how they are used.
- `--enable-security-analysis`: security groups.

Each flag adds one sheet to the Excel report:

- `--enable-network-analysis` adds the `Network Analysis` sheet. It lists each
  VPC with its CIDR block, total and available IP addresses, utilisation and
  subnet count, then a table of subnets.
- `--enable-security-analysis` adds the `Security Analysis` sheet. It lists
  each security group with its rule counts, a risk level and whether it has
  permissive rules, then a table of each rule.

Limits:

- A sheet is written only if the scan finds VPCs or security groups.
- The Word report has no network or security sections.
- Network ACLs are not part of the Security Analysis sheet. They appear on the
  `VPC` sheet.
- With `--template`, the flags add **no sheets**: the built-in report
  templates have no such sheets (we checked with `--template standard-bom`).
  Use the default layout, or a layout file (`--excel-template`), which keeps
  the `network_analysis` and `security_analysis` sections.
- The risk level is a simple rule in InvenTag, not a security assessment.

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

What a run prints, and the first rows of each sheet, from an offline run
against mocked AWS (sample data):

<!-- BEGIN EXAMPLE OUTPUT: analysis-console -->

```text title="Output"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

<!-- END EXAMPLE OUTPUT: analysis-console -->

<!-- BEGIN EXAMPLE OUTPUT: analysis-network -->

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

`Network Analysis` sheet, first rows:

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

<!-- END EXAMPLE OUTPUT: analysis-network -->

<!-- BEGIN EXAMPLE OUTPUT: analysis-security -->

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

`Security Analysis` sheet, first rows:

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

<!-- END EXAMPLE OUTPUT: analysis-security -->

### What the network analysis does

- A subnet counts as public when the route table it uses (its own, or the
  VPC's main table) has an active route for `0.0.0.0/0` or `::/0` to an
  internet gateway (`igw-`). A VPC that has an internet gateway but no such
  route does not make its subnets public. The sheets do not show this
  property.
- `Total IPs` comes from the VPC's CIDR blocks. `Available IPs` and
  `Utilization %` come from its subnets, so the three columns do not add up,
  and a VPC without subnets shows 0 available. IPv6 addresses are not counted.
- `Associated Resources` counts the resources whose API data names the VPC or
  subnet: EC2 instances, Lambda functions in a VPC, RDS and ElastiCache
  resources and load balancers. Security groups, network ACLs, route tables
  and gateways are the VPC's own plumbing and are not counted.
- It reads only the VPCs and subnets in the regions you scan. It does not
  check network ACLs, security groups, `MapPublicIpOnLaunch`, Direct Connect,
  VPN connections, Network Firewall or peering routes.

### What the security analysis does

- Each rule gets a risk level from the rule alone. A rule open to `0.0.0.0/0`
  or `::/0` is **critical** if it allows all protocols, all ports, or a range
  that contains 22, 23, 3389, 1433, 3306 or 5432. For example, ports 20 to 25
  are critical. It is **high** if the range has a port below 1024, and
  **medium** for any other port. An ICMP rule open to the internet is medium.
  A source range wider than `/16` is medium, so `10.0.0.0/8` is medium.
  Everything else is low.
- Outbound rules are always **low**. Open outbound traffic is the AWS default.
- A group's risk level is the highest level among its rules.
- A group counts as unused when no network interface uses it, no other group
  refers to it, and it is not the `default` group. A group that only a launch
  template or an Auto Scaling group refers to looks unused. If the network
  interfaces cannot be read, no group is called unused. The sheet does not
  show this property.
- The `Has Permissive Rules` column says `Yes` when an inbound rule is open to
  `0.0.0.0/0` or `::/0`. A rule that refers to another security group or to a
  prefix list is listed, but InvenTag does not look at what is behind the
  reference. Network ACLs are not analyzed.

### Fail a pipeline on risky rules

`--risk-threshold LOW|MEDIUM|HIGH|CRITICAL` needs `--enable-security-analysis`.
InvenTag looks at the security group rules that are open to `0.0.0.0/0` or
`::/0`, inbound and outbound. If one has a level at or above the threshold,
InvenTag writes the reports, logs each rule and exits with code 4:

```text
2 security group rule(s) at or above risk level LOW:
  - sg-57691d920ce0e0a5e: outbound All All 0.0.0.0/0 (low)
```

Because outbound rules are low, `--risk-threshold LOW` exits with code 4 for
the `default` group of almost every VPC. `MEDIUM` and higher ignore outbound
rules. Only security group rules count: network ACLs and other resources
never trigger exit code 4. Exit code 5 (`--fail-on-account-error`) and 6
(`--fail-if-empty`) take precedence over 4.

### Permissions

Both analyses make read-only EC2 calls in each scanned region. Besides the
usual `ec2:Describe*` calls for VPCs, subnets and security groups, they need
`ec2:DescribeRouteTables` (public subnets) and `ec2:DescribeNetworkInterfaces`
(unused groups). The policy file in the repository includes
them. See [IAM permissions](../reference/iam-permissions.md). Without them,
the analysis carries on and leaves that detail out.

## More detail on network resources

Network resources are part of every normal scan. With the `standard-bom`
template they appear on the **VPC** sheet: VPCs, subnets, route tables,
network ACLs and security groups, each with its tags.

To see their configuration as well, add every field the AWS API returned:

```yaml
# .inventag/templates/network-review.yaml
format_version: 1
kind: report
name: network-review
description: Every field, for a network review
extends: standard-bom
spec:
  title: Network review
  excel:
    include_all_fields: true
```

```bash
inventag --template network-review --create-excel --account-regions us-east-1
```

The VPC sheet then has a column for every field the AWS API returned. They
are detailed but not summarised. In an offline run (sample data):

<!-- BEGIN EXAMPLE OUTPUT: network-columns -->

The VPC sheet has 57 columns. The `raw_data.*` columns in this sample are:

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

<!-- END EXAMPLE OUTPUT: network-columns -->

## Next steps

- [Feature status](../getting-started/status.md)
- [Adapt a template](../templates/adapt-a-template.md)
