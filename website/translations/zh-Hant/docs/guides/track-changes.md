---
title: 跟蹤兩次執行之間的變化
description: InvenTag 如何把每次執行的快照儲存到 bom_output/state，變更報告包含什麼，以及在依賴它之前需要了解什麼。
sidebar_position: 6
slug: /architecture/state-management
---

# 跟蹤兩次執行之間的變化

**適合誰閱讀：** 你定時執行 InvenTag，想知道發生了哪些變化。

**讀完後你會了解：** 快照存放在哪裡、變更報告包含什麼，以及如何自己比較兩次執行。

## 快照 {#snapshots}

每次執行都會把發現的內容儲存在輸出資料夾中。針對模擬 AWS 執行兩次之後（範例資料）：

```text title="bom_output/ after two runs (reports omitted)"
bom_output/changelog_20261112_090100.md
bom_output/state/metadata.json
bom_output/state/state_20261112_090000.json
bom_output/state/state_20261112_090100.json
```

每個快照都包含這次執行發現的所有資源：

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

如果想保留歷史記錄，請在兩次執行之間保留 `state/` 資料夾，例如作為 CI 快取或放在儲存貯體中。
用 `--disable-state-management` 可以關閉快照。

## 變更報告 {#the-change-report}

從第二次執行開始，InvenTag 會把新快照與上一個快照比較，並在輸出資料夾中寫出
`changelog_<timestamp>.md`。第一次執行沒有可比較的物件，因此不會寫出變更報告。

在這個範例中，兩次執行之間新增了一個儲存貯體。變更報告列出了它：

<details>
<summary>changelog_20261112_090100.md（前 30 列）</summary>

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
| Total Changes | 1 |
| Critical Changes | 0 |
| High Severity | 0 |
| Security Changes | 0 |
| Compliance Changes | 0 |
| Network Changes | 0 |

**Most Impacted Services:**
- S3: 1 changes

## S3 Service Changes

Changes detected in S3 service resources

### New Bucket 'acme-new-bucket' was created in S3
- **Type:** added
```

</details>

報告包含一張摘要表，然後為每個有變化的服務各欄一節。每項變化都有型別（例如 `added`）、嚴重程度、資源及其 ARN。

需要了解的事項：

- 它把一次執行與它之前的那次執行比較，不會與你指定的更早的執行比較。
- 它比較的是每次執行發現的資源。兩次執行請使用相同的區域、服務和過濾條件，
  這樣範圍的變化就不會被誤讀為你的資產發生了變化。
- `--no-generate-changelog` 會停止生成報告，但保留快照。`--disable-delta-detection`
  同樣會停止生成報告。`--disable-state-management` 會同時停止快照和報告。
- InvenTag 會刪除超過 30 天，或者超出最新 100 個的快照。全新執行器上的定時作業沒有更早的快照，
  所以請在兩次執行之間保留 `state/` 資料夾。

## 自己比較兩個快照 {#compare-two-snapshots-yourself}

你可以比較任意兩個快照，因為每個快照都是帶有 `resources` 列表的 JSON：

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

在兩次執行之間新增一個儲存貯體之後的範例輸出（範例資料）：

```text title="Terminal"
Added: ['arn:aws:s3:::acme-new-bucket']
Removed: []
```

## 下一步 {#next-steps}

- [功能狀態與已知限制](../getting-started/status.md)
- [在 CI/CD 中執行 InvenTag](./run-in-ci.md)
