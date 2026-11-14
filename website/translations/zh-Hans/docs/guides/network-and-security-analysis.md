---
title: 网络与安全分析
description: InvenTag 的网络和安全组分析参数会向 Excel 报告增加什么、不包含什么，以及如何审查 VPC 和安全组。
sidebar_position: 5
slug: /architecture/network-analysis
---

# 网络与安全分析

**适合谁阅读：** 你想用 InvenTag 审查 VPC、子网和安全组。

**读完后你会了解：** 这些分析参数会向报告增加什么内容。

## 这些参数增加什么 {#what-the-flags-add}

InvenTag 为此提供两个参数：

- `--enable-network-analysis`：VPC、子网及其使用情况。
- `--enable-security-analysis`：安全组。

每个参数会向 Excel 报告增加一个工作表：

- `--enable-network-analysis` 增加 `Network Analysis` 工作表。它列出每个 VPC 及其 CIDR 块、
  IP 地址总数和可用数量、利用率和子网数量，然后是一张子网表。
- `--enable-security-analysis` 增加 `Security Analysis` 工作表。它列出每个安全组及其规则数量、
  风险级别以及是否有宽松规则，然后是一张列出每条规则的表。

限制：

- 只有当扫描发现了 VPC 或安全组时，才会写入相应的工作表。
- Word 报告没有网络或安全章节。
- 网络 ACL 不属于 Security Analysis 工作表，它们出现在 `VPC` 工作表中。
- 使用 `--template` 时，这些参数**不会增加任何工作表**：内置的报告模板没有这类工作表
  （我们用 `--template standard-bom` 检查过）。请使用默认版式，或使用保留了
  `network_analysis` 和 `security_analysis` 部分的版式文件（`--excel-template`）。
- 风险级别是 InvenTag 中的一条简单规则，不是安全评估。

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

下面是针对模拟 AWS 离线运行时打印的内容，以及每个工作表的前几行（示例数据）：

```text title="输出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Network Analysis` 工作表的前几行：

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Security Analysis` 工作表的前几行：

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

### 网络分析做什么 {#what-the-network-analysis-does}

- 当子网所用的路由表（它自己的，或 VPC 的主路由表）中有一条指向互联网网关（`igw-`）的、处于活动状态的 `0.0.0.0/0` 或 `::/0` 路由时，该子网算作公有子网。
  VPC 有互联网网关但没有这样的路由，并不会让它的子网变成公有。工作表不显示这一属性。
- `Total IPs` 来自 VPC 的 CIDR 块。`Available IPs` 和 `Utilization %` 来自它的子网，所以这三列加起来对不上，
  没有子网的 VPC 显示可用数为 0。IPv6 地址不计入。
- `Associated Resources` 统计 API 数据中指明了该 VPC 或子网的资源：EC2 实例、位于 VPC 中的 Lambda 函数、RDS 资源。负载均衡器按其所在的 VPC 统计，而不按子网统计。
  安全组、网络 ACL、路由表和网关属于 VPC 自身的网络组件，不计入。
- 它只读取你所扫描区域中的 VPC 和子网。它不检查网络 ACL、安全组、`MapPublicIpOnLaunch`、Direct Connect、VPN 连接、Network Firewall 或对等连接路由。

### 安全分析做什么 {#what-the-security-analysis-does}

- 每条规则只根据规则本身得到风险级别。对 `0.0.0.0/0` 或 `::/0` 开放的规则，如果允许所有协议、所有端口，或者范围包含 22、23、3389、1433、3306 或 5432，就是 **critical**（严重）。
  例如 20 到 25 号端口是 critical。范围内含 1024 以下的端口则是 **high**（高），其他端口是 **medium**（中）。对互联网开放的 ICMP 规则是 medium。
  来源范围比 `/16` 更宽也是 medium，所以 `10.0.0.0/8` 是 medium。其余都是 low（低）。
- 出站规则始终是 **low**。出站全开是 AWS 的默认设置。
- 安全组的风险级别是其规则中最高的级别。
- 当没有网络接口使用某个安全组、没有其他安全组引用它，并且它不是 `default` 组时，它算作未使用。只被启动模板或 Auto Scaling 组引用的组看起来会是未使用。
  如果无法读取网络接口，就不会把任何组判为未使用。工作表不显示这一属性。
- 当入站规则对 `0.0.0.0/0` 或 `::/0` 开放时，`Has Permissive Rules` 列显示 `Yes`。引用其他安全组或前缀列表的规则会被列出，但 InvenTag 不会查看引用背后的内容。不分析网络 ACL。

### 让流水线因高风险规则而失败 {#fail-a-pipeline-on-risky-rules}

`--risk-threshold LOW|MEDIUM|HIGH|CRITICAL` 需要 `--enable-security-analysis`。InvenTag 会检查对 `0.0.0.0/0` 或 `::/0` 开放的安全组规则，入站和出站都检查。
只要有一条的级别达到或超过阈值，InvenTag 就会写出报告，记录每条规则，并以退出码 4 结束：

```text
2 security group rule(s) at or above risk level LOW:
  - sg-57691d920ce0e0a5e: outbound All All 0.0.0.0/0 (low)
```

因为出站规则是 low，`--risk-threshold LOW` 几乎对每个 VPC 的 `default` 组都会以退出码 4 结束。`MEDIUM` 及更高的阈值会忽略出站规则。
只有安全组规则会计入：网络 ACL 和其他资源永远不会触发退出码 4。退出码 5（`--fail-on-account-error`）和 6（`--fail-if-empty`）优先于 4。

### 权限 {#permissions}

两种分析都会在每个被扫描的区域中发出只读的 EC2 调用。除了针对 VPC、子网和安全组的常规 `ec2:Describe*` 调用外，
还需要 `ec2:DescribeRouteTables`（公有子网）和 `ec2:DescribeNetworkInterfaces`（未使用的组）。仓库中的策略文件已包含它们。
见 [IAM 权限](../reference/iam-permissions.md)。缺少它们时，分析会继续，只是省略相应的细节。

## 网络资源的更多细节 {#more-detail-on-network-resources}

网络资源是每次普通扫描的一部分。使用 `standard-bom` 模板时，它们出现在 **VPC** 工作表中：
VPC、子网、路由表、网络 ACL 和安全组，每个都带有其标签。

如果还想看到它们的配置，请加入 AWS API 返回的所有字段：

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

这样 VPC 工作表中，AWS API 返回的每个字段都有一列。它们很详细，但没有经过汇总。
在一次离线运行中（示例数据）：

VPC 工作表有 57 列。此示例中的 `raw_data.*` 列是：

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

## 下一步 {#next-steps}

- [功能状态](../getting-started/status.md)
- [调整模板](../templates/adapt-a-template.md)
