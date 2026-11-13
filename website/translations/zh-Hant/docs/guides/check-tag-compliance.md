---
title: 按策略檢查標籤
description: 使用 InvenTag 標籤策略範本，檢查 AWS 資源是否帶有必需的標籤且取值合規，並解讀檢查結果。
sidebar_position: 4
slug: /architecture/tag-compliance
---

# 按策略檢查標籤

**適合誰閱讀：** 你負責制定標籤規範，想知道哪些資源違反了它。

**讀完後你可以：** 執行標籤檢查、解讀結果，並編寫自己的策略。

## 執行檢查 {#run-a-check}

選擇一個內建策略，或者使用你自己的：

```bash
inventag --template finops-cost-allocation --create-excel --account-regions us-east-1
```

InvenTag 照常掃描，然後檢查範圍內的每個資源。下面是使用
`--template finops-cost-report` 離線執行的範例輸出（範例資料）：

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'finops-cost-allocation': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

## 解讀結果 {#read-the-results}

| 位置 | 內容 |
|---|---|
| Excel，**Tag Compliance** 工作表 | 範圍內每個資源一列：帳戶、區域、服務、型別、資源、ARN、狀態、缺少的標籤和其他問題。不合規的行排在最前。表格下方列出每條規則，以及有多少資源缺少該標籤或取值錯誤。 |
| Excel，**Summary** 工作表 | 計數：已檢查、合規、不合規、範圍外、百分比。 |
| Word，**Tag compliance** 章節 | 同樣的計數、各條規則，以及不合規資源的表格（預設最多 100 列）。 |
| `tag_compliance_<timestamp>.json` | 每條規則的計數和每個不合規資源，供指令碼和 CI 使用。 |

當資源具有所有必需標籤，並且每個取值都符合其規則時，該資源即為**合規**。
問題會被逐一寫明，例如：

- `CostCenter: '1234' does not match CC-[0-9]{4}`（格式錯誤）
- `Environment: 'Production' is not one of prod, staging, dev, test, sandbox`
- `Owner: found 'owner' instead (tag keys are case-sensitive)`

同一範例中的 Tag Compliance 工作表：

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Tag Compliance`

`Tag Compliance` 工作表的前幾列：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | CostCenter, Project |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | CostCenter, Owner, Project, Environment |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | CostCenter, Owner, Project, Environment |  |

Word 章節：

**文件大綱：**

- **Cost Allocation Tag Report**（標題）
- Summary
- Tag compliance
  - Required tags
  - Non-compliant resources
- Resources by service
- About this report

文件中的一張表：

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| CostCenter | Matches: CC-[0-9]&#123;4&#125; | 20 | 1 |
| Owner | Any value | 17 | 0 |
| Project | Any value | 21 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 17 | 1 |

JSON 檔案中的 `summary` 部分：

```json title="summary"
{
  "checked": 23,
  "compliant": 1,
  "non_compliant": 22,
  "out_of_scope": 14,
  "percent_compliant": 4.3,
  "missing_by_key": {
    "CostCenter": 20,
    "Owner": 17,
    "Project": 21,
    "Environment": 17
  },
  "invalid_by_key": {
    "CostCenter": 1,
    "Owner": 0,
    "Project": 0,
    "Environment": 1
  }
}
```

**範圍外**的資源只計數、不檢查：策略的 `scope` 把它們排除在外，
例如無法攜帶標籤的 KMS 別名。

**在相信這些數字之前請先了解：** InvenTag 會按 ARN 把 Resource Groups Tagging API
返回的標籤與資源匹配；當 ARN 不一致時，則退而使用服務、區域和資源 ID 匹配。
使用 moto 的離線測試針對每個有自己發現程式碼的服務檢查了這一點。真實的 AWS
可能給出不同的答案，因此在依賴某個策略結果之前，請把 ARN 欄中的幾行與控制檯對照一下。

## 編寫你自己的策略 {#write-your-own-policy}

從一個內建策略出發，只修改不同的部分：

```bash
inventag templates init finops-cost-allocation --output .inventag/templates/our-tags.yaml --extend
```

```yaml
format_version: 1
kind: tag-policy
name: our-tags
description: Our cost-allocation tags
extends: finops-cost-allocation
spec:
  required_tags:
    - key: Environment                 # replaces the inherited rule
      allowed_values: [production, staging, development]
    - key: Project                     # drops an inherited tag
      remove: true
    - key: DataClassification          # adds a new one
      allowed_values: [public, internal, confidential]
  scope:
    services: [EC2, S3, RDS, LAMBDA]   # only check these services
```

每個標籤的規則：

- `allowed_values`：取值必須是其中之一。除非設定 `case_sensitive: true`，否則不區分大小寫。
- `pattern`：整個取值必須匹配這個正規表示式。
- 兩者都不寫：只要標籤存在，任何取值都可以。

每個標籤使用 `allowed_values` 或 `pattern` 之一，不要兩者同時使用。所有欄位都列在
[範本參考](../templates/reference.md)中。

## 發現違規時讓流水線失敗 {#fail-a-pipeline-on-violations}

新增一個設定了 `fail_on_tag_violations: true` 的設定範本。InvenTag 仍會寫出所有報告，
然後以結束代碼 3 退出。如果你還傳了 `--fail-on-account-error` 或 `--fail-if-empty`，並且其中一個條件成立，
則改用結束代碼 5 或 6，因為資料不完整。參見
[在 CI 中強制執行標籤策略](../examples/tag-policy-in-ci.md)。

## 舊版檢查指令碼 {#the-older-checker-script}

`scripts/legacy/tag_compliance_checker.py --config policy.yaml` 早於範本出現，
有自己的選項（`--help` 會列出）。它只檢查必需的標籤鍵是否存在。它不執行其策略檔案中的 `allowed_values`、`pattern` 或任何其他欄位：
它會記錄一條警告，並把這些欄位列在其報告的 `summary.ignored_policy_fields` 中。它會忽略鍵以 `aws:` 開頭的標籤，因為這些標籤由 AWS 建立，
所以只有 `aws:` 標籤的資源算作未打標籤，而以 `aws:` 開頭的必需標籤鍵會報錯。除此之外，本文件不涵蓋它。請優先使用標籤策略範本。

## 下一步 {#next-steps}

- [內建標籤策略](../templates/catalogue.md#tag-policy-templates)
- [範例：FinOps 成本分攤標籤](../examples/finops-cost-allocation.md)
