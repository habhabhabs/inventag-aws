---
title: 標籤證據範本
description: 五個證據標籤策略範本（SOC 2、HIPAA、PCI DSS、GDPR、PDPA）檢查什麼、從不聲稱什麼、使用哪些標籤和值，以及如何複製其中一個並修改其範圍。
sidebar_position: 6
---

# 標籤證據範本

**適合誰閱讀：** 你正在準備一場關於 SOC 2、HIPAA、PCI DSS、GDPR 或 PDPA 的討論，想知道哪些資源對這場討論一開始會問的問題沒有留下記錄。

**讀完後你可以：** 為你的框架選出範本，正確解讀它的結果，並複製它以適應你自己的標籤和資源型別。

## 它們檢查什麼 {#what-they-check}

每個範本都是一個標籤策略。它檢查範圍內的每個資源是否帶有範本列出的標籤，且值在允許的列表中或符合允許的形式。僅此而已。這些標籤就是證據：由資源所有者寫下的、關於範圍、資料型別、保留期限或位置的記錄。

這五個範本在[內建目錄](./catalogue.md#tag-evidence-templates)中。全部是 `evidence-soc2`、`evidence-hipaa`、`evidence-pci-dss`、`evidence-gdpr` 和 `evidence-pdpa`。

## 它們從不聲稱什麼 {#what-they-never-claim}

- 它們只檢查標籤證據。它們不評估控制措施、保障措施、網路分段、合法性或同意。
- 標籤值由資源所有者自行填寫。InvenTag 無法核實。
- 檢查透過並不代表帳戶滿足 SOC 2、HIPAA、PCI DSS、GDPR 或 PDPA。它只表示標籤存在。
- InvenTag 是隻讀的。它讀取標籤並寫出報告；它從不更改任何資源。

每個範本都在其描述和檔案頭部寫明瞭這一點。複製任何範本時，請在你的描述中保留這句話：「Checks tag evidence only; certifies nothing.」

## 標籤 {#the-tags}

五個範本都還會檢查來自 `security-baseline` 的三個標籤：`Owner`（任意值）、`Environment`（`prod`、`staging`、`dev`、`test`、`sandbox`）和 `DataClassification`（`public`、`internal`、`confidential`、`restricted`）。`evidence-hipaa` 取代最後一條規則並加入 `phi`。

| 範本 | 標籤鍵 | 允許的值 |
|---|---|---|
| `evidence-soc2` | `Soc2Scope` | `in-scope`, `out-of-scope` |
|  | `SystemName` | 任意非空文字 |
|  | `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual`, `other` |
|  | `Criticality` | `high`, `medium`, `low` |
| `evidence-hipaa` | `PHI` | `yes`, `no` |
|  | `DataClassification` | `public`, `internal`, `confidential`, `restricted`, `phi` |
|  | `RetentionPeriod` | 數字加 `d` 或 `y`，或 `indefinite` |
| `evidence-pci-dss` | `PciScope` | `cde`, `connected`, `out-of-scope` |
|  | `CardholderData` | `stores`、`processes`、`transmits`、`none`（只填一個值） |
| `evidence-gdpr` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `ProcessingRecord` | 1 到 64 個字母、數字、`.`、`_` 或 `-` |
|  | `DataResidency` | `eu`, `uk`, `other` |
|  | `RetentionPeriod` | 數字加 `d` 或 `y`，或 `indefinite` |
| `evidence-pdpa` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `Purpose` | 任意非空文字 |
|  | `RetentionPeriod` | 數字加 `d` 或 `y`，或 `indefinite` |
|  | `DataLocation` | `sg`, `overseas` |

`evidence-gdpr` 和 `evidence-pdpa` 使用相同的 `PersonalData` 鍵和相同的值。如果你為其中一個給資源打了標籤，這個標籤對另一個同樣適用。一次執行只使用一個範本，所以要同時檢視兩者，請執行兩次檢查。

標籤值可以包含字母、數字、空格和 `_ . : / = + - @`。上面的值都符合。

## 複製範本並修改範圍 {#copy-a-template-and-change-its-scope}

`evidence-soc2` 檢查除 KMS 別名之外的所有資源型別。其他四個範本列出它們檢查的資源型別。該列表屬於整個範本，所以它也會限制 `Owner`、`Environment` 和 `DataClassification` 的檢查。其他型別的資源會計為範圍之外，而不是失敗。

要檢視範本確切檢查什麼，請列印繼承之後的結果：

```bash title="Terminal"
inventag templates show evidence-hipaa --resolved
```

要建立繼承全部內容的自己的副本：

```bash title="Terminal"
inventag templates init evidence-soc2 --output .inventag/templates/our-soc2.yaml --extend
```

要檢查更少的服務，請在你的副本中設定 `services`：

```yaml title=".inventag/templates/data-soc2.yaml"
format_version: 1
kind: tag-policy
name: data-soc2
description: SOC 2 tag evidence for data stores only. Checks tag evidence only; certifies nothing.
extends: evidence-soc2
spec:
  scope:
    services: [S3, DYNAMODB, SQS]
```

要檢查更多資源型別，請從 `inventag templates show <name> --resolved` 複製完整的 `resource_types` 列表並加入該型別。副本中的列表會替換繼承的列表，而不是在其基礎上追加。新型別請使用你的報告中 Type 欄裡的值。

使用副本之前先檢查它，然後執行：

```bash title="Terminal"
inventag templates validate data-soc2
inventag --template data-soc2 --create-excel
```

## 引擎無法表達的內容 {#what-the-engine-cannot-express}

- 每次執行只能使用一個標籤策略範本。
- 沒有「僅當」規則。標有 `PersonalData=none` 的資源仍然需要 `ProcessingRecord` 標籤，值為 `none`。
- 不會在標籤之間或標籤與資源所在區域之間交叉核對。`PHI=no` 同時帶有 `DataClassification=phi` 不會被標出，另一個區域中的資源帶有 `DataResidency=eu` 也不會。
- 模式按原樣區分大小寫：`7y` 透過，`7Y` 不透過。允許值列表不區分大小寫。
- `ProcessingRecord` 的模式只檢查 ID 的形式。請在你的副本中把它改成你自己的 ID 格式。

## 下一步 {#next-steps}

- [範例：在 SOC 2 範圍討論之前檢查標籤證據](../examples/evidence-soc2.md)
- [調整範本](./adapt-a-template.md)
- [按策略檢查標籤](../guides/check-tag-compliance.md)
