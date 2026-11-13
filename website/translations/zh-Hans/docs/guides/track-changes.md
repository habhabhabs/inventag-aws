---
title: 跟踪两次运行之间的变化
description: InvenTag 如何把每次运行的快照保存到 bom_output/state，变更报告包含什么，以及在依赖它之前需要了解什么。
sidebar_position: 6
slug: /architecture/state-management
---

# 跟踪两次运行之间的变化

**适合谁阅读：** 你定时运行 InvenTag，想知道发生了哪些变化。

**读完后你会了解：** 快照存放在哪里、变更报告包含什么，以及如何自己比较两次运行。

## 快照 {#snapshots}

每次运行都会把发现的内容保存在输出文件夹中。针对模拟 AWS 运行两次之后（示例数据）：

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

每个快照都包含这次运行发现的所有资源：

```json title="state/state_<timestamp>.json (structure)"
{
  "top_level_keys": [
    "compliance_data",
    "metadata",
    "network_analysis",
    "resources",
    "security_analysis"
  ],
  "one_resource": {
    "service": "S3",
    "resource_type": "Bucket",
    "resource_id": "acme-app-logs",
    "arn": "arn:aws:s3:::acme-app-logs",
    "region": "us-east-1",
    "tags": {
      "Environment": "prod",
      "Owner": "platform",
      "CostCenter": "CC-1001",
      "Project": "storefront",
      "DataClassification": "internal"
    },
    "source_account_id": "123456789012"
  }
}
```

快照的 `metadata` 部分记录快照版本（`1.1`；`1.0` 版本的文件仍可加载）、`accounts_scanned` 和 `accounts_failed`。
经常保存机密的字段的值，例如 Lambda 环境变量、密码、令牌和私钥，会被替换为 `***REDACTED***`；名称保留。
这类值的变化不会被报告。早期版本的快照中可能仍有这些值，所以请删除或限制访问旧的 `bom_output/` 文件夹。
升级后的第一次运行会把被屏蔽的值显示为已变化。

如果想保留历史记录，请在两次运行之间保留 `state/` 文件夹，例如作为 CI 缓存或放在存储桶中。
用 `--disable-state-management` 可以关闭快照。`state/partial/` 文件夹保存供 [`--resume`](./run-a-scan.md#continue-after-a-failed-run) 使用的账户结果，它不属于历史记录。

## 变更报告 {#the-change-report}

从第二次运行开始，InvenTag 会把新快照与上一个快照比较，并在输出文件夹中写出
`changelog_<timestamp>.md`。第一次运行没有可比较的对象，因此不会写出变更报告。

在这个示例中，两次运行之间新增了一个存储桶。变更报告列出了它：

<details>
<summary>changelog_20261112_090100.md（前 30 行）</summary>

```markdown
# Multi-Account Infrastructure Changes

**Generated:** 2026-11-12T09:00:00+00:00

## State Comparison

- **from_state:** 20261112_090000
- **to_state:** 20261112_090100
- **comparison_timestamp:** 2026-11-12T09:00:00+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Changes | 2 |
| Critical Changes | 0 |
| High Severity | 0 |
| Security Changes | 0 |
| Compliance Changes | 0 |
| Network Changes | 0 |

**Most Impacted Services:**
- S3: 1 changes
- ATHENA: 1 changes

## S3 Service Changes

Changes detected in S3 service resources

### New Bucket 'acme-new-bucket' was created in S3
```

</details>

报告包含一张摘要表，然后为每个有变化的服务各列一节。每项变化都有类型（例如 `added`）、严重程度、资源及其 ARN。

需要了解的事项：

- 它把一次运行与它之前的那次运行比较，不会与你指定的更早的运行比较。
- 它比较的是每次运行发现的资源。两次运行请使用相同的区域、服务和过滤条件，
  这样范围的变化就不会被误读为你的资产发生了变化。
- `--no-generate-changelog` 会停止生成报告，但保留快照。`--disable-delta-detection`
  同样会停止生成报告。`--disable-state-management` 会同时停止快照和报告。
- 如果某个账户在两次运行中的任何一次里无法扫描或只扫描了一部分，它的资源会被排除在比较之外。
  否则它的所有资源都会显示为新增或删除。变更报告会在“State Comparison”部分（`accounts_not_compared`）列出该账户。
- InvenTag 把列表当作无序处理，所以列表中项目的顺序变化不算变更。它还会忽略每次运行都会变化的字段：
  发现途径、成本数字，以及 `ItemCount` 或 `ApproximateNumberOfMessages` 之类的使用计数器。
- 运行保存快照时，InvenTag 会删除超过 30 天或超出最新 100 个的快照。用 `--state-retention-days N` 和
  `--state-max-snapshots N` 修改限制；`0` 或 `none` 表示关闭该限制。刚写入的快照和与它比较的快照永远不会被删除，
  所以 `--state-max-snapshots 1` 会留下两个文件。InvenTag 只会删除它自己写入的 `state_<timestamp>.json` 文件。
  全新运行器上的定时作业没有更早的快照，所以请在两次运行之间保留 `state/` 文件夹。

## 自己比较两个快照 {#compare-two-snapshots-yourself}

你可以比较任意两个快照，因为每个快照都是带有 `resources` 列表的 JSON：

```bash
python3 - <<'EOF'
import json, sys, glob
old, new = sorted(glob.glob("bom_output/state/state_*.json"))[-2:]
ids = lambda f: {r.get("arn") or r.get("id") for r in json.load(open(f))["resources"]}
a, b = ids(old), ids(new)
print("Added:", sorted(b - a))
print("Removed:", sorted(a - b))
EOF
```

在两次运行之间新增一个存储桶之后的示例输出（示例数据）：

```text title="Terminal"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

## 下一步 {#next-steps}

- [功能状态与已知限制](../getting-started/status.md)
- [在 CI/CD 中运行 InvenTag](./run-in-ci.md)
