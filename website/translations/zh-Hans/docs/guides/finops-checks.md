---
title: FinOps 检查
description: 对扫描找到的资源运行六项固定的 FinOps 检查，不再发出任何 AWS 调用；并可选择从 Cost Explorer 读取上个月按服务、关联账户和成本分配标签划分的支出。
sidebar_position: 10
---

# FinOps 检查

**适合谁读：** 你负责云支出，想根据已有的清单得到一份值得查看的资源列表。

**读完后你能做到：** 运行六项 FinOps 检查，读懂 `FinOps` 工作表，并知道这些检查看不到什么。

## 运行检查 {#run-the-checks}

```bash
inventag --create-excel --finops-checks
```

该参数默认关闭。使用它时，InvenTag 对扫描找到的资源运行六项固定检查，并在 Excel 报告末尾添加一个名为 `FinOps` 的工作表。

- 这些检查只读取扫描已有的行。它们不再发出任何 AWS 调用，也不需要额外的权限。无论是否使用该参数，只读防护看到的调用都相同。
- 这些检查不会更改任何账户中的任何内容。
- 检查结果不改变退出码：有 `fail` 结果的运行与没有这些结果时以相同方式结束。
- 不使用该参数时，这些检查不运行：报告中没有 `FinOps` 工作表，其他工作表和控制台文字与使用该参数时相同。

## 六项检查 {#the-six-checks}

| 检查 ID | 资源 | 结果为 `fail` 的条件 |
|---|---|---|
| `FIN-001` | EBS 卷 | 卷的 `State` 为 `available`（未挂载） |
| `FIN-002` | 弹性 IP 地址 | 地址没有 `AssociationId` |
| `FIN-003` | 被扫描账户拥有的 EBS 快照 | 快照的 `StartTime` 早于运行开始时间 90 天以上 |
| `FIN-004` | EC2 实例 | 实例状态为 `stopped` |
| `FIN-005` | 负载均衡器 | 同一账户和区域中没有任何目标组指向它（`ELBV2` 工作表），或它没有列出任何实例（经典负载均衡器，`ELB` 工作表） |
| `FIN-006` | 内置标签策略 `finops-cost-allocation` 范围内的每个资源 | 缺少该策略的某个键：`CostCenter`、`Owner`、`Project` 或 `Environment` |

`FIN-003` 的 90 天是固定的，没有参数可以修改。

`FIN-006` 使用与 `finops-cost-allocation` 标签策略相同的检查（见[用策略检查标签](check-tag-compliance.md)），但只查找缺少的键。值不被策略允许的键不算 `FIN-006` 的结果。标签键区分大小写：`owner` 不算作 `Owner`。只来自 Cost Explorer 的行（来源为 `billing`）不检查。

## 结果 {#results}

每项检查对每个资源给出三种结果之一：

- `fail`：检查观察到了表中所说的情况。该资源会列出。
- `not_evaluated`：缺少检查需要的数据。该资源会列出，并附上原因。
- `pass`：该资源只计数，不列出。

数据中的空缺从不算作 pass。原因有：

| 原因 | 含义 |
|---|---|
| `identity_only` | 该资源只通过 Resource Groups Tagging API 得知，所以检查读取的字段不在它的行上。 |
| `field_missing` | 检查读取的字段不在该行上。对于 `FIN-003`，运行没有开始时间时也是如此。 |
| `tags_not_read` | 仅 `FIN-006`：缺少某个键，并且该区域的 Tagging API 列表在本次运行中失败。对于全局资源，该账户任何一次失败的 Tagging API 列表都算。 |
| `listing_not_read` | 检查需要的某个列表在本次运行中失败。需要该列表的每项检查各为该列表及其区域写一行：一个失败的 `ec2` 列表会产生四行（`FIN-001`、`FIN-003`、`FIN-004`、`FIN-006`）。 |

## FinOps 工作表 {#the-finops-sheet}

工作表的第一行写着："These are observations from the inventory. A resource listed here may be intended."（这些是来自清单的观察结果；这里列出的资源可能是有意为之。）

然后是列出的结果，列为：`Check ID`、`Check`、`Result`、`Reason`、`Account`、`Region`、`Service`、`Resource Type`、`Resource ID`、`Name`、`Observed`。各行按检查 ID、账户、区域和资源 ID 排序。`Observed` 说明检查看到了什么，例如 "no attachment"、"started 2026-05-02"、"state stopped" 或 "missing: CostCenter, Owner"。API 应答中的其他内容都不会复制到工作表中。

列出的结果之后是一张表，每项检查一行，列出 `Fail`、`Not evaluated` 和 `Pass` 的计数。

以下示例由文档生成器根据模拟的 AWS 账户生成：

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `FinOps`

`FinOps` sheet:

> These are observations from the inventory. A ...  

| Check ID | Check | Result | Reason | Account | Region | Service | Resource Type | Resource ID | Name | Observed |
|---|---|---|---|---|---|---|---|---|---|---|
| FIN-001 | EBS volume with no attachment | fail |  | 123456789012 | us-east-1 | EC2 | Volume | vol-57d5df4cfc9884b48 | acme-build-cache | no attachment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | global | IAM | Role | acme-orders-api-role |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | VPC | NetworkAcl | acl-3118daa9d5cc099a7 |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | missing: Project |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-inventory-reports | acme-inventory-reports | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-new-bucket | acme-new-bucket | missing: CostCenter, Owner, Project, Environment |

使用 `--per-account-reports` 时，每个账户的报告只列出该账户的结果。

使用 `--template` 时，这些检查不运行：InvenTag 显示一条警告，不写 `FinOps` 工作表。

## `finops_checks` 结果 {#the-finops_checks-result}

命令行只以 `FinOps` 工作表的形式写出结果。在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 在 `finops_checks` 键下返回结果，用 `json` 输出格式写出的 JSON 报告的 `metadata` 中也有同一个键。该键包含：

- `schema_version`：`1`。
- `summary`：每项检查一个条目，包括 `policy`（检查 ID）、`check`、`fail`、`not_evaluated` 和 `pass`。
- `findings`：列出的结果，包括 `policy`、`result`、`reason`、`account`、`region`、`service`、`resource_type`、`resource`、`name` 和 `message`（即 `Observed` 的文字）。

不使用该参数时没有这个键。

## 从 Cost Explorer 读取成本分配 {#cost-allocation-from-cost-explorer}

`--finops-cost-allocation` 是第二个参数，默认关闭，与 `--finops-checks` 和 `--enable-cost-analysis` 相互独立。它用每个账户自己的凭证，从 Cost Explorer 读取该账户上个月的支出，并在 Excel 报告末尾添加一个名为 `FinOps costs` 的工作表。

```bash
inventag --create-excel --finops-cost-allocation
```

### 请求 {#requests}

对每个账户，按以下顺序：

| 请求 | 数量 |
|---|---|
| 针对 `CostCenter`、`Owner`、`Project` 和 `Environment`（内置标签策略 `finops-cost-allocation` 的键）的 `ListCostAllocationTags` | 1 |
| 按服务分组的 `GetCostAndUsage` | 1 |
| 按关联账户分组的 `GetCostAndUsage` | 1 |
| 按这些键中每个已作为成本分配标签激活的键分组的 `GetCostAndUsage` | 0 到 4 |

即每个账户最多 7 个请求。`ListCostAllocationTags` 显示为未激活或未列出的键不会被查询；它的表格显示 "not active as a cost allocation tag" 或 "not found as a cost allocation tag"。如果 `ListCostAllocationTags` 本身失败，四个键都会被查询。

应答的后续页面（`NextPageToken`）也是一个请求。它从同样的 7 个中扣除，每个分组最多 3 页。需要更多页面的表格标记为 "incomplete"。

在发现开始之前，运行会显示一行警告，给出最多的请求数，例如：`Cost Explorer: up to 7 request(s) in this run (billing validation: 0; cost trend: 0; cost allocation: 7). AWS charges for each.` 只读防护的审计（`--audit-output`）统计到的该功能请求数从不超过这一行所说的数。

SDK 会重试被限流的请求，每次重试都是一个新请求。AWS 对每个 Cost Explorer 请求收费：见 [Cost Explorer 定价](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。未针对真实的 AWS 验证：AWS 对这些请求（包括重试和 `ListCostAllocationTags`）如何收费。

### FinOps costs 工作表 {#the-finops-costs-sheet}

工作表以一条说明开头：金额是 Cost Explorer 为每个账户返回的数值，用该账户自己的凭证读取，属于上一个完整的月份，并不是单个资源的成本。然后每个账户、分组和值各占一行，列为 `Account`、`Grouping`、`Value`、`Amount`、`Currency`、`Metric`、`Period start`、`Period end` 和 `Status`。

- 时间段是运行开始所在月份的前一个自然月。`Period end` 是运行所在月份的第一天。
- 指标是 `UnblendedCost`。金额是 AWS 返回的文本；InvenTag 不对其求和、拆分或取整。
- 在按标签的分组中，值 `(no value)` 表示没有该标签键的支出。
- 无法读取的表格有一行显示其状态，例如 "not read: access denied"。运行说明中也会写出它，被拒绝的请求会有一行 `Permissions:`。扫描结果和退出码与不使用该参数时相同。

使用 `--per-account-reports` 时，每个账户的报告只包含该账户的表格。使用 `--template` 时不发出任何请求：InvenTag 显示一条警告，不写 `FinOps costs` 工作表。

### `finops_costs` 键、快照和变更报告 {#the-finops_costs-key-the-snapshot-and-the-change-report}

- 在 Python 中，`CloudBOMGenerator.generate_multi_account_bom()` 的结果和 JSON 报告的 `metadata` 带有 `finops_costs` 键：`schema_version`、`metric`，以及每个账户的时间段、请求数、每个标签键的状态和表格。
- 状态快照带有 `metadata.tags.cost_allocation`：只有表格（按服务、关联账户和标签值的合计；没有资源 ID）。快照仍然只有所有者可读（模式 0600）。`--no-cost-in-snapshot` 不把这些数字写入快照；工作表照常写出。不使用 `--finops-cost-allocation` 时，该参数不改变任何内容，并会显示一条警告说明这一点。
- 当本次运行读取了成本分配时，变更报告会有一个 "Cost, previous run to this run" 区块。两个快照的月份不同时，它把上一次运行和本次运行的每个值并排列出。否则用一行说明为什么没有比较：上一个快照没有这些数字、两次运行读取的是同一个月，或者使用了 `--no-cost-in-snapshot`。

### 需要什么，以及未验证的内容 {#what-it-needs-and-what-is-not-verified}

该参数需要 `ce:GetCostAndUsage` 和 `ce:ListCostAllocationTags`。两者都在仓库策略中（见 [IAM 权限](../reference/iam-permissions.md)）。

未针对真实的 AWS 验证：

- 标签键只有在付费（payer）账户中被激活为成本分配标签之后，才会显示支出。
- 组织中的成员账户看到的可能比付费账户少，并且 `ListCostAllocationTags` 可能无法从成员账户应答。
- 应答的形式与测试使用的一致。测试使用的应答与 Cost Explorer 应答的形式相同，并已对照 botocore 服务模型检查。

## 检查看不到的内容 {#what-the-checks-cannot-see}

- `FIN-004` 不给出时长。实例列表中没有可靠的停止时间，所以已停止的实例不论停止多久都会列出。
- `FIN-005` 不读取目标的健康状态。目标全部不健康的负载均衡器结果为 pass。读取目标健康状态需要新的 AWS 调用。
- 这里列出的资源可能是有意为之：例如故意停止的实例，或按保留规则保存的快照。
- 这些检查不显示任何金额。
- 未针对真实的 AWS 验证：在每种账户类型上，列表都带有每项检查需要的字段。
