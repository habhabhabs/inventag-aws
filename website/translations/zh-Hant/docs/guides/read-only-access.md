---
title: 設定只讀訪問
description: 用 IAM Identity Center 或 IAM 角色，為 InvenTag 提供最小許可權的只讀 AWS 身份，並確認它無法更改任何內容。
sidebar_position: 2
slug: /user-guides/production-safety
---

# 設定只讀訪問

**適合誰閱讀：** 負責建立 InvenTag 所用 AWS 身份的人。

**讀完後你可以：** 為 InvenTag 建立只讀身份，並確認它無法更改你的資源。

## 為什麼這很重要 {#why-this-matters}

InvenTag 只需要讀取。它有自己的只讀防護，會在傳送前攔截所有非讀取的 AWS 呼叫。
你的 IAM 策略是第二道獨立的安全網：即使某個缺陷繞過了防護，AWS 仍會拒絕該呼叫。
只給 InvenTag 它所需要的許可權，不要更多。

## 方案 1：AWS 託管的 ReadOnlyAccess 加三項額外許可權（最簡單） {#option-1-aws-managed-readonlyaccess-plus-three-extras-simplest}

1. 附加 AWS 託管策略 `ReadOnlyAccess`。
2. 為 `ReadOnlyAccess` 可能沒有覆蓋的呼叫，新增下面這條內聯策略：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvenTagExtras",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "ce:GetCostAndUsage",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    }
  ]
}
```

| 操作 | InvenTag 為什麼需要它 |
|---|---|
| `tag:GetResources` | 透過 Resource Groups Tagging API 查詢帶標籤的資源（它的 IAM 字首是 `tag`）。 |
| `ce:GetCostAndUsage` | 查詢有支出的服務。AWS 按請求收費。 |
| `ec2:DescribeRegions` | 列出賬戶中已啟用的區域。 |

只有在使用 `--enable-cost-analysis` 時才需要新增 `pricing:GetProducts`（它還會呼叫
`cloudwatch:GetMetricStatistics`，`ReadOnlyAccess` 已覆蓋該呼叫）；
如果使用 `--s3-bucket`，則需要在報告儲存桶上新增 `s3:PutObject`。

`ReadOnlyAccess` 範圍很寬：它可以讀取 S3 物件列表等資料，以及 InvenTag 從不檢視的某些配置。
如果這對你的組織來說太寬，請使用方案 2。

## 方案 2：倉庫中範圍更窄的策略 {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` 列出了 106 個具體的讀取操作，
包括 `tag:GetResources`、`ce:GetCostAndUsage` 和 `pricing:GetProducts`。
它由程式碼所用的同一份清單生成，因此與 InvenTag 實際發出的呼叫一致。

其中的 `OptionalS3ReportUpload` 語句允許帶服務端加密的 `s3:PutObject`，用於 `--s3-bucket`。
請把 `YOUR-REPORTS-BUCKET-NAME` 替換為你的儲存桶；如果不上傳報告，就刪除這條語句。

如果缺少某個操作，發現過程會繼續進行，不列印任何訊息，並把相應的細節留空。

## 使用 IAM Identity Center（SSO） {#with-iam-identity-center-sso}

建立一個包含該策略的許可權集，然後把它分配給你想掃描的每個賬戶：

```bash
aws sso-admin create-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --name InvenTagReadOnly \
  --description "Read-only access for InvenTag"

aws sso-admin attach-managed-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

aws sso-admin put-inline-policy-to-permission-set \
  --instance-arn arn:aws:sso:::instance/ssoins-EXAMPLE \
  --permission-set-arn arn:aws:sso:::permissionSet/ssoins-EXAMPLE/ps-EXAMPLE \
  --inline-policy file://inventag-extras.json
```

然後用 `aws sso login --profile <profile>` 登入，並以 `AWS_PROFILE=<profile>` 執行 InvenTag。

## 在每個賬戶中使用 IAM 角色 {#with-an-iam-role-in-each-account}

對於跨多個賬戶的掃描，請在每個賬戶中建立同名的角色，例如 `InvenTagReadOnly`。
附加該策略，並且只允許你的掃描身份來擔任它。對應的信任策略如下：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::999999999999:role/InvenTagScanner" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

請把 `999999999999:role/InvenTagScanner` 替換為執行 InvenTag 的身份。
掃描身份本身只需要對這些角色擁有 `sts:AssumeRole` 許可權。

## 確認它無法寫入 {#check-that-it-cannot-write}

用 IAM 策略模擬器確認寫入操作會被拒絕：

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

兩者都應顯示 `implicitDeny` 或 `explicitDeny`。

你也可以問 InvenTag 的防護，它會允許哪些操作（來自離線執行的示例輸出）：

```text title="Terminal"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
$ echo $?
1
```

要檢視一次真實執行呼叫了什麼，請新增 `--audit-output audit.json`。
下面是一次離線執行的節選（示例資料）：

```json title="audit.json (first operations shown)"
{
  "read_only_enforced": true,
  "started_at": "2026-11-12T09:00:00+00:00",
  "generated_at": "2026-11-12T09:00:00+00:00",
  "allowed_prefixes": [
    "List",
    "Describe",
    "Get",
    "Head",
    "Lookup",
    "Search",
    "BatchGet"
  ],
  "total_calls": 73,
  "allowed_calls": 73,
  "blocked_calls": 0,
  "operations": [
    {
      "service": "acm",
      "operation": "ListCertificates",
      "allowed": true,
      "count": 1
    },
    {
      "service": "apigateway",
      "operation": "GetRestApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "ce",
      "operation": "GetCostAndUsage",
      "allowed": true,
      "count": 2
    },
    {
      "service": "cloudformation",
      "operation": "DescribeStacks",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudformation",
      "operation": "ListStackSets",
      "allowed": true,
      "count": 1
    },
    {
      "service": "cloudfront",
      "operation": "ListDistributions",
      "allowed": true,
      "count": 1
    },
    "..."
  ],
  "blocked": []
}
```

## 安全事件之後 {#after-a-security-incident}

如果你懷疑憑證或某個依賴項已被入侵，請輪換或吊銷 InvenTag 使用過的憑證，
在 AWS CloudTrail 中檢查該身份發出的、你意料之外的呼叫，並保持該身份為只讀。
更多內容見[安全](../security/index.md)頁面。

## 下一步 {#next-steps}

- [IAM 許可權參考](../reference/iam-permissions.md)
- [掃描多個賬戶](./scan-multiple-accounts.md)
