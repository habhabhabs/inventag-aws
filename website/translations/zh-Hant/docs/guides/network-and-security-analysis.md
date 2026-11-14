---
title: 網路與安全分析
description: InvenTag 的網路和安全組分析引數會向 Excel 報告增加什麼、不包含什麼，以及如何審查 VPC 和安全組。
sidebar_position: 5
slug: /architecture/network-analysis
---

# 網路與安全分析

**適合誰閱讀：** 你想用 InvenTag 審查 VPC、子網和安全組。

**讀完後你會了解：** 這些分析引數會向報告增加什麼內容。

## 這些引數增加什麼 {#what-the-flags-add}

InvenTag 為此提供兩個引數：

- `--enable-network-analysis`：VPC、子網及其使用情況。
- `--enable-security-analysis`：安全組。

每個引數會向 Excel 報告增加一個工作表：

- `--enable-network-analysis` 增加 `Network Analysis` 工作表。它列出每個 VPC 及其 CIDR 塊、
  IP 地址總數和可用數量、利用率和子網數量，然後是一張子網表。
- `--enable-security-analysis` 增加 `Security Analysis` 工作表。它列出每個安全組及其規則數量、
  風險級別以及是否有寬鬆規則，然後是一張列出每條規則的表。

限制：

- 只有當掃描發現了 VPC 或安全組時，才會寫入相應的工作表。
- Word 報告沒有網路或安全章節。
- 網路 ACL 不屬於 Security Analysis 工作表，它們出現在 `VPC` 工作表中。
- 使用 `--template` 時，這些引數**不會增加任何工作表**：內建的報告範本沒有這類工作表
  （我們用 `--template standard-bom` 檢查過）。請使用預設版面配置，或使用保留了
  `network_analysis` 和 `security_analysis` 部分的版面配置檔案（`--excel-template`）。
- 風險級別是 InvenTag 中的一條簡單規則，不是安全評估。

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

下面是針對模擬 AWS 離線執行時列印的內容，以及每個工作表的前幾列（範例資料）：

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Network Analysis` 工作表的前幾列：

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Network Analysis`、`Security Analysis`

`Security Analysis` 工作表的前幾列：

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

### 網路分析做什麼 {#what-the-network-analysis-does}

- 當子網所用的路由表（它自己的，或 VPC 的主路由表）中有一條指向網際網路閘道器（`igw-`）的、處於活動狀態的 `0.0.0.0/0` 或 `::/0` 路由時，該子網算作公有子網。
  VPC 有網際網路閘道器但沒有這樣的路由，並不會讓它的子網變成公有。工作表不顯示這一屬性。
- `Total IPs` 來自 VPC 的 CIDR 塊。`Available IPs` 和 `Utilization %` 來自它的子網，所以這三欄加起來對不上，
  沒有子網的 VPC 顯示可用數為 0。IPv6 地址不計入。
- `Associated Resources` 統計 API 資料中指明瞭該 VPC 或子網的資源：EC2 例項、位於 VPC 中的 Lambda 函式、RDS 和 ElastiCache 資源。負載均衡器按其所在的 VPC 統計，而不按子網統計。
  安全組、網路 ACL、路由表和閘道器屬於 VPC 自身的網路元件，不計入。

  未針對 離線測試 驗證：`Associated Resources` 會統計 ElastiCache。
- 它唯讀取你所掃描區域中的 VPC 和子網。它不檢查網路 ACL、安全組、`MapPublicIpOnLaunch`、Direct Connect、VPN 連線、Network Firewall 或對等連線路由。

### 安全分析做什麼 {#what-the-security-analysis-does}

- 每條規則只根據規則本身得到風險級別。對 `0.0.0.0/0` 或 `::/0` 開放的規則，如果允許所有協議、所有埠，或者範圍包含 22、23、3389、1433、3306 或 5432，就是 **critical**（嚴重）。
  例如 20 到 25 號埠是 critical。範圍內含 1024 以下的埠則是 **high**（高），其他埠是 **medium**（中）。對網際網路開放的 ICMP 規則是 medium。
  來源範圍比 `/16` 更寬也是 medium，所以 `10.0.0.0/8` 是 medium。其餘都是 low（低）。
- 出站規則始終是 **low**。出站全開是 AWS 的預設設定。
- 安全組的風險級別是其規則中最高的級別。
- 當沒有網路介面使用某個安全組、沒有其他安全組引用它，並且它不是 `default` 組時，它算作未使用。只被啟動範本或 Auto Scaling 組引用的組看起來會是未使用。
  如果無法讀取網路介面，就不會把任何組判為未使用。工作表不顯示這一屬性。
- 當入站規則對 `0.0.0.0/0` 或 `::/0` 開放時，`Has Permissive Rules` 欄顯示 `Yes`。引用其他安全組或字首列表的規則會被列出，但 InvenTag 不會檢視引用背後的內容。不分析網路 ACL。

### 讓流水線因高風險規則而失敗 {#fail-a-pipeline-on-risky-rules}

`--risk-threshold LOW|MEDIUM|HIGH|CRITICAL` 需要 `--enable-security-analysis`。InvenTag 會檢查對 `0.0.0.0/0` 或 `::/0` 開放的安全組規則，入站和出站都檢查。
只要有一條的級別達到或超過閾值，InvenTag 就會寫出報告，記錄每條規則，並以結束代碼 4 結束：

```text
2 security group rule(s) at or above risk level LOW:
  - sg-57691d920ce0e0a5e: outbound All All 0.0.0.0/0 (low)
```

因為出站規則是 low，`--risk-threshold LOW` 幾乎對每個 VPC 的 `default` 組都會以結束代碼 4 結束。`MEDIUM` 及更高的閾值會忽略出站規則。
只有安全組規則會計入：網路 ACL 和其他資源永遠不會觸發結束代碼 4。結束代碼 5（`--fail-on-account-error`）和 6（`--fail-if-empty`）優先於 4。

### 權限 {#permissions}

兩種分析都會在每個被掃描的區域中發出唯讀的 EC2 呼叫。除了針對 VPC、子網和安全組的常規 `ec2:Describe*` 呼叫外，
還需要 `ec2:DescribeRouteTables`（公有子網）和 `ec2:DescribeNetworkInterfaces`（未使用的組）。儲存庫中的策略檔案已包含它們。
見 [IAM 權限](../reference/iam-permissions.md)。缺少它們時，分析會繼續，只是省略相應的細節。

## 網路資源的更多細節 {#more-detail-on-network-resources}

網路資源是每次普通掃描的一部分。使用 `standard-bom` 範本時，它們出現在 **VPC** 工作表中：
VPC、子網、路由表、網路 ACL 和安全組，每個都帶有其標籤。

如果還想看到它們的設定，請加入 AWS API 返回的所有欄位：

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

這樣 VPC 工作表中，AWS API 返回的每個欄位都有一欄。它們很詳細，但沒有經過彙總。
在一次離線執行中（範例資料）：

VPC 工作表有 57 欄。此範例中的 `raw_data.*` 欄是：

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

## 下一步 {#next-steps}

- [功能狀態](../getting-started/status.md)
- [調整範本](../templates/adapt-a-template.md)
