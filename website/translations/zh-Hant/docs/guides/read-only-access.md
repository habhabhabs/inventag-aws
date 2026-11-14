---
title: 設定唯讀存取
description: 用 IAM Identity Center 或 IAM 角色，為 InvenTag 提供最小權限的唯讀 AWS 身份，並確認它無法更改任何內容。
sidebar_position: 2
slug: /user-guides/production-safety
---

# 設定唯讀存取

**適合誰閱讀：** 負責建立 InvenTag 所用 AWS 身份的人。

**讀完後你可以：** 為 InvenTag 建立唯讀身份，並確認它無法更改你的資源。

## 為什麼這很重要 {#why-this-matters}

InvenTag 只需要讀取權限；如果用 `--s3-bucket` 上傳報告，還需要 `s3:PutObject`。它有自己的唯讀防護，會在傳送前攔截所有非讀取的 AWS 呼叫。
你的 IAM 策略是第二道獨立的安全網：即使某個缺陷繞過了防護，AWS 仍會拒絕該呼叫。
只給 InvenTag 它所需要的權限，不要更多。

未針對 真實的 AWS 驗證：唯讀 IAM 策略會拒絕繞過防護的呼叫。

## 方案 1：AWS 託管的 ReadOnlyAccess 加三項額外權限（最簡單） {#option-1-aws-managed-readonlyaccess-plus-three-extras-simplest}

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
| `ce:GetCostAndUsage` | 查詢有支出的服務。 |
| `ec2:DescribeRegions` | 列出帳戶中已啟用的區域。 |

AWS 對每次 Cost Explorer 請求收費：見 [Cost Explorer 定價](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/)。

InvenTag 還會呼叫 `account:ListRegions`，但僅在 `ec2:DescribeRegions` 失敗時，用它讀取已啟用的區域。如果你想要這個回退，就新增它。

只有在使用 `--enable-cost-analysis` 時才需要新增 `pricing:GetProducts`（它還會呼叫
`cloudwatch:GetMetricStatistics`，`ReadOnlyAccess` 已覆蓋該呼叫）；
如果使用 `--s3-bucket`，則需要在報告儲存貯體上新增 `s3:PutObject`。

`ReadOnlyAccess` 範圍很寬：它可以讀取 S3 物件列表等資料，以及 InvenTag 從不檢視的某些設定。
如果這對你的組織來說太寬，請使用方案 2。

未針對 AWS 驗證：AWS 託管策略 `ReadOnlyAccess` 目前允許什麼，以及它覆蓋其中哪些呼叫。

## 方案 2：儲存庫中範圍更窄的策略 {#option-2-the-narrower-policy-in-the-repository}

`config/defaults/iam-policy-read-only.json` 列出了 122 個具體的讀取操作，
包括 `tag:GetResources`、`ce:GetCostAndUsage` 和 `pricing:GetProducts`，
另有隻用於 API 後設資料（不含 API 金鑰）的 `apigateway:GET`。它由程式碼所用的同一份清單生成，因此與 InvenTag 實際發出的呼叫一致。
它包含 InvenTag 用自己的呼叫列舉的各項服務所需的操作，以及
[網路與安全分析](./network-and-security-analysis.md#permissions)所需的 `ec2:DescribeRouteTables` 和 `ec2:DescribeNetworkInterfaces`。
如果你複製過舊版本的檔案，請重新複製。缺少某個操作不會讓執行停止，但該服務或細節會缺失。

未針對 真實的 AWS 驗證：`apigateway:GET` 語句讓 API 金鑰的值無法被讀取。

其中的 `OptionalS3ReportUpload` 語句允許帶服務端加密的 `s3:PutObject`，用於 `--s3-bucket`。
請把 `YOUR-REPORTS-BUCKET-NAME` 替換為你的儲存貯體；如果不上傳報告，就刪除這條語句。

未針對 真實的 AWS 驗證：該語句只在使用服務端加密時才允許上傳。

如果缺少某個列舉操作，InvenTag 會為該服務記錄一條警告，並在沒有它的資源的情況下繼續：

```text
No permission for sqs (list_queues in us-east-1: AccessDenied). Resources of sqs are skipped; add the read permission to see them.
```

如果缺少的是某個資源細節所需的操作，發現過程會繼續進行，並把該細節留空。

## 唯讀保護攔截什麼 {#what-the-read-only-guard-blocks}

InvenTag 會在程序中的每一次 AWS 呼叫發出之前檢查它。它只允許名稱以 `List`、`Describe`、`Get`、`Head`、`Lookup`、`Search` 或 `BatchGet` 開頭的操作，
外加用於存取其他帳戶的 `sts:AssumeRole`。它無法關閉。

有些操作看起來像讀取，卻會返回機密或客戶資料。保護機制也會攔截它們，所以範圍很寬的策略也不會透過 InvenTag 洩露這些內容。
例如：`secretsmanager:GetSecretValue`、`ssm:GetParameter`、`s3:GetObject`、`dynamodb:GetItem`、`lambda:GetFunction`（它會返回程式碼的下載連結）、
`cloudformation:GetTemplate`、`ec2:GetLaunchTemplateData`、`glue:GetConnection` 和 Athena 查詢結果。
它還會攔截帶值的 API 金鑰以及用於獲取使用者資料的 `ec2:DescribeInstanceAttribute`，並按同樣的規則檢查預簽名 URL 和資料庫認證權杖。
可以用 `inventag --validate-operations <service>:<Operation>` 檢查某個名稱。它只按名稱回答：`apigateway:GetApiKeys` 和 `ec2:DescribeInstanceAttribute` 在這裡顯示 ALLOWED，只有在帶 `includeValues` 或 `Attribute=userData` 呼叫它們時，保護機制才會攔截。

IAM Identity Center（SSO）和 web identity 設定檔在保護機制下可以正常工作。保護機制只允許登入步驟用權杖換取憑證，別的都不允許。

未針對 AWS IAM Identity Center 驗證：使用真實的 SSO 或 web identity 設定檔登入。

Python 庫中有兩個函式，在你自己的程式碼裡呼叫時可以寫入 AWS。`inventag` 命令從不呼叫它們，在命令執行中保護機制也會攔截它們。
`CredentialManager.setup_cross_account_roles()` 會建立 IAM 角色，只有帶 `allow_iam_writes=True` 時才會執行。
S3 生命週期輔助函式會修改儲存貯體規則，只有帶 `allow_bucket_writes=True` 時才會執行。

## 使用 IAM Identity Center（SSO） {#with-iam-identity-center-sso}

建立一個包含該策略的權限集，然後把它分配給你想掃描的每個帳戶：

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

未針對 真實的 AWS 驗證：`aws sso-admin` 命令及其建立的權限集。

未針對 AWS 驗證：AWS 託管策略 `ReadOnlyAccess` 目前允許什麼，以及它覆蓋其中哪些呼叫。

然後用 `aws sso login --profile <profile>` 登入，並以 `AWS_PROFILE=<profile>` 執行 InvenTag。

未針對 AWS CLI 驗證：本節中的登入命令。

## 在每個帳戶中使用 IAM 角色 {#with-an-iam-role-in-each-account}

對於跨多個帳戶的掃描，請在每個帳戶中建立同名的角色，例如 `InvenTagReadOnly`。
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
掃描身份本身只需要對這些角色擁有 `sts:AssumeRole` 權限。

未針對 真實的 AWS 驗證：僅憑信任策略和 `sts:AssumeRole` 就足以完成掃描。

## 確認它無法寫入 {#check-that-it-cannot-write}

用 IAM 策略模擬器確認寫入操作會被拒絕：

```bash title="Terminal"
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/InvenTagReadOnly \
  --action-names s3:PutObject ec2:TerminateInstances \
  --query "EvaluationResults[].[EvalActionName,EvalDecision]" --output table
```

兩者都應顯示 `implicitDeny` 或 `explicitDeny`。

未針對 真實的 AWS 驗證：這兩個操作在策略模擬器中的結果。

你也可以問 InvenTag 的防護，它會允許哪些操作（來自離線執行的範例輸出）：

```text title="輸出"
ALLOWED  ec2:DescribeInstances (read-only prefix)
ALLOWED  s3:GetBucketTagging (read-only prefix)
BLOCKED  s3:PutObject (operation is not on the read-only allowlist)
BLOCKED  secretsmanager:GetSecretValue (operation returns secrets, signed URLs or customer data)
```

```bash title="Terminal"
echo $?
```

```text title="輸出"
1
```

要檢視一次真實執行呼叫了什麼，請新增 `--audit-output audit.json`。
下面是一次離線執行的節選（範例資料）：

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
  "total_calls": 96,
  "allowed_calls": 96,
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
      "service": "appsync",
      "operation": "ListGraphqlApis",
      "allowed": true,
      "count": 1
    },
    {
      "service": "athena",
      "operation": "ListWorkGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "autoscaling",
      "operation": "DescribeAutoScalingGroups",
      "allowed": true,
      "count": 1
    },
    {
      "service": "backup",
      "operation": "ListBackupVaults",
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
在 AWS CloudTrail 中檢查該身份發出的、你意料之外的呼叫，並保持該身份為唯讀。
更多內容見[安全](../security/index.md)頁面。

## 下一步 {#next-steps}

- [IAM 權限參考](../reference/iam-permissions.md)
- [掃描多個帳戶](./scan-multiple-accounts.md)
