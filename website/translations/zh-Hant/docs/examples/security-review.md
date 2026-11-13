---
title: "範例：安全標籤審查"
description: 使用 InvenTag 的 security-baseline 標籤策略，在安全審查之前檢查 AWS 資源是否帶有 Owner、Environment 和 DataClassification 標籤。
sidebar_position: 6
---

# 範例：安全標籤審查

**目標：** 在安全審查或事件演練之前，找出沒有負責人、沒有環境或沒有資料分類的資源。

**你需要：** 唯讀憑證。

這裡只檢查標籤。它不評估任何東西的設定有多安全，透過檢查也不代表你符合任何框架的要求。

## 範本 {#template}

內建的 `security-baseline` 標籤策略要求：

| 標籤鍵 | 規則 |
|---|---|
| `Owner` | 任意值 |
| `Environment` | `prod`、`staging`、`dev`、`test` 或 `sandbox` |
| `DataClassification` | `public`、`internal`、`confidential` 或 `restricted` |

## 命令 {#command}

```bash title="Terminal"
inventag --template standard-bom --template security-baseline \
  --create-excel --create-word --account-regions us-east-1
```

## 輸出 {#output}

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Wrote bom_output/multi_account_bom_20261112_090000.xlsx
Tag policy 'security-baseline': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

**工作表：** `Summary`、`ATHENA`、`DYNAMODB`、`EC2`、`EVENTS`、`IAM`、`KMS`、`LAMBDA`、`S3`、`VPC`、`Tag Compliance`

`Tag Compliance` 工作表的前幾列：

| Account | Region | Service | Type | Resource | ARN | Status | Missing tags | Problems |
|---|---|---|---|---|---|---|---|---|
| 123456789012 | us-east-1 | DYNAMODB | Table | acme-orders | arn:aws:dynamodb:us-east-1:123456789012:table... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Instance | acme-web-1 | arn:aws:ec2:us-east-1:123456789012:instance/i... | Non-compliant | DataClassification |  |
| 123456789012 | us-east-1 | EC2 | Volume | acme-build-cache | arn:aws:ec2:us-east-1:123456789012:volume/vol... | Non-compliant | Owner, Environment, DataClassification |  |
| 123456789012 | global | IAM | Role | acme-orders-api-role | arn:aws:iam::123456789012:role/acme-orders-ap... | Non-compliant | Owner, Environment, DataClassification |  |

在 "Missing tags" 欄中篩選 `Owner`，即可先找出沒有負責人的資源。

## 下一步 {#next-steps}

- 為沒有負責人的資源確定負責人，然後在你的基礎設施程式碼中為它們打上標籤。
- 把檢查範圍縮小到僅資料儲存：

```yaml title=".inventag/templates/data-stores.yaml"
format_version: 1
kind: tag-policy
name: data-stores
description: Classification on data stores only
extends: security-baseline
spec:
  scope:
    services: [S3, DYNAMODB, RDS]
```
