---
title: 标签证据模板
description: 五个证据标签策略模板（SOC 2、HIPAA、PCI DSS、GDPR、PDPA）检查什么、从不声称什么、使用哪些标签和值，以及如何复制其中一个并修改其范围。
sidebar_position: 6
---

# 标签证据模板

**适合谁阅读：** 你正在准备一场关于 SOC 2、HIPAA、PCI DSS、GDPR 或 PDPA 的讨论，想知道哪些资源对这场讨论一开始会问的问题没有留下记录。

**读完后你可以：** 为你的框架选出模板，正确解读它的结果，并复制它以适应你自己的标签和资源类型。

## 它们检查什么 {#what-they-check}

每个模板都是一个标签策略。它检查范围内的每个资源是否带有模板列出的标签，且值在允许的列表中或符合允许的形式。仅此而已。这些标签就是证据：由资源所有者写下的、关于范围、数据类型、保留期限或位置的记录。

这五个模板在[内置目录](./catalogue.md#tag-evidence-templates)中。全部是 `evidence-soc2`、`evidence-hipaa`、`evidence-pci-dss`、`evidence-gdpr` 和 `evidence-pdpa`。

## 它们从不声称什么 {#what-they-never-claim}

- 它们只检查标签证据。它们不评估控制措施、保障措施、网络分段、合法性或同意。
- 标签值由资源所有者自行填写。InvenTag 无法核实。
- 检查通过并不代表账户满足 SOC 2、HIPAA、PCI DSS、GDPR 或 PDPA。它只表示标签存在。
- InvenTag 是只读的。它读取标签并写出报告；它从不更改任何资源。

每个模板都在其描述和文件头部写明了这一点。复制任何模板时，请在你的描述中保留这句话：“Checks tag evidence only; certifies nothing.”

## 标签 {#the-tags}

五个模板都还会检查来自 `security-baseline` 的三个标签：`Owner`（任意值）、`Environment`（`prod`、`staging`、`dev`、`test`、`sandbox`）和 `DataClassification`（`public`、`internal`、`confidential`、`restricted`）。`evidence-hipaa` 取代最后一条规则并加入 `phi`。

| 模板 | 标签键 | 允许的值 |
|---|---|---|
| `evidence-soc2` | `Soc2Scope` | `in-scope`, `out-of-scope` |
|  | `SystemName` | 任意非空文本 |
|  | `ManagedBy` | `terraform`, `cloudformation`, `cdk`, `manual`, `other` |
|  | `Criticality` | `high`, `medium`, `low` |
| `evidence-hipaa` | `PHI` | `yes`, `no` |
|  | `DataClassification` | `public`, `internal`, `confidential`, `restricted`, `phi` |
|  | `RetentionPeriod` | 数字加 `d` 或 `y`，或 `indefinite` |
| `evidence-pci-dss` | `PciScope` | `cde`, `connected`, `out-of-scope` |
|  | `CardholderData` | `stores`、`processes`、`transmits`、`none`（只填一个值） |
| `evidence-gdpr` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `ProcessingRecord` | 1 到 64 个字母、数字、`.`、`_` 或 `-` |
|  | `DataResidency` | `eu`, `uk`, `other` |
|  | `RetentionPeriod` | 数字加 `d` 或 `y`，或 `indefinite` |
| `evidence-pdpa` | `PersonalData` | `none`, `personal`, `special-category` |
|  | `Purpose` | 任意非空文本 |
|  | `RetentionPeriod` | 数字加 `d` 或 `y`，或 `indefinite` |
|  | `DataLocation` | `sg`, `overseas` |

`evidence-gdpr` 和 `evidence-pdpa` 使用相同的 `PersonalData` 键和相同的值。如果你为其中一个给资源打了标签，这个标签对另一个同样适用。一次运行只使用一个模板，所以要同时查看两者，请运行两次检查。

标签值可以包含字母、数字、空格和 `_ . : / = + - @`。上面的值都符合。

## 复制模板并修改范围 {#copy-a-template-and-change-its-scope}

`evidence-soc2` 检查除 KMS 别名之外的所有资源类型。其他四个模板列出它们检查的资源类型。该列表属于整个模板，所以它也会限制 `Owner`、`Environment` 和 `DataClassification` 的检查。其他类型的资源会计为范围之外，而不是失败。

要查看模板确切检查什么，请打印继承之后的结果：

```bash title="Terminal"
inventag templates show evidence-hipaa --resolved
```

要创建继承全部内容的自己的副本：

```bash title="Terminal"
inventag templates init evidence-soc2 --output .inventag/templates/our-soc2.yaml --extend
```

要检查更少的服务，请在你的副本中设置 `services`：

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

要检查更多资源类型，请从 `inventag templates show <name> --resolved` 复制完整的 `resource_types` 列表并加入该类型。副本中的列表会替换继承的列表，而不是在其基础上追加。新类型请使用你的报告中 Type 列里的值。

使用副本之前先检查它，然后运行：

```bash title="Terminal"
inventag templates validate data-soc2
inventag --template data-soc2 --create-excel
```

## 引擎无法表达的内容 {#what-the-engine-cannot-express}

- 每次运行只能使用一个标签策略模板。
- 没有“仅当”规则。标有 `PersonalData=none` 的资源仍然需要 `ProcessingRecord` 标签，值为 `none`。
- 不会在标签之间或标签与资源所在区域之间交叉核对。`PHI=no` 同时带有 `DataClassification=phi` 不会被标出，另一个区域中的资源带有 `DataResidency=eu` 也不会。
- 模式按原样区分大小写：`7y` 通过，`7Y` 不通过。允许值列表不区分大小写。
- `ProcessingRecord` 的模式只检查 ID 的形式。请在你的副本中把它改成你自己的 ID 格式。

## 下一步 {#next-steps}

- [示例：在 SOC 2 范围讨论之前检查标签证据](../examples/evidence-soc2.md)
- [调整模板](./adapt-a-template.md)
- [按策略检查标签](../guides/check-tag-compliance.md)
