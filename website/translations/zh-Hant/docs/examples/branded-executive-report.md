---
title: "範例：帶品牌標識的高管 Word 報告"
description: 使用 InvenTag 報告範本，為管理層生成一份帶有你的徽標、顏色和標籤合規摘要的簡短橫向 Word 報告。
sidebar_position: 7
---

# 範例：帶品牌標識的高管 Word 報告

**目標：** 一份給管理層看的簡短 Word 文件，帶有你的徽標和顏色：
包含總數、服務和標籤合規情況，不含逐個資源的表格。

**你需要：** 唯讀憑證，以及一個 PNG、JPEG、GIF 或 BMP 格式的徽標檔案。
Word 無法嵌入 SVG 徽標。

## 範本 {#template}

把徽標放在範本旁邊，同一資料夾或子資料夾中均可：

```text title="Project layout"
.inventag/templates/
  board-report.yaml
  brand/
    acme-logo.png
```

```yaml title=".inventag/templates/board-report.yaml"
format_version: 1
kind: report
name: board-report
description: Branded summary for the leadership team
extends: executive-summary
spec:
  title: Cloud Estate Summary
  subtitle: Quarterly review
  company_name: Acme Ltd
  logo: brand/acme-logo.png
  logo_alt_text: Acme Ltd logo        # read by screen readers
  colors:
    header_fill: "4B2E83"             # 10.4:1 contrast with white text
  tag_policy: security-baseline
  word:
    orientation: landscape
```

## 命令 {#command}

```bash title="Terminal"
inventag templates validate board-report
inventag --template board-report --create-word --account-regions us-east-1
```

## 輸出 {#output}

```text title="輸出"
OK    ~/acme-infra/.inventag/templates/board-report.yaml (report 'board-report')
```

```text title="輸出"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Wrote bom_output/tag_compliance_20261112_090000.json
Wrote bom_output/multi_account_bom_20261112_090000.docx
Tag policy 'security-baseline': 1 of 23 resources compliant (4.3%), 22 non-compliant, 14 out of scope.
```

**文件大綱：**

- **Cloud Estate Summary**（標題）
- Summary
- Resources by service
- Tag compliance
  - Required tags
  - Non-compliant resources
- About this report

文件中的一個表格：

| Tag key | Rule | Missing | Invalid value |
|---|---|---|---|
| Owner | Any value | 17 | 0 |
| Environment | One of: prod, staging, dev, test, sandbox (an... | 17 | 1 |
| DataClassification | One of: public, internal, confidential, restr... | 22 | 0 |

![帶品牌標識的橫向 Word 報告第一頁：紫色方形徽標、標題 Cloud Estate Summary、Quarterly review、Prepared for Acme Ltd，以及摘要列表（範例資料）](../assets/examples/img/board-report-word-page1.png)

[下載範例 Word 報告](pathname:///inventag-aws/downloads/board-report-sample.docx)（38 KB，範例資料）

如果徽標缺失，或者不是 Word 支援的圖片格式，執行會在掃描之前停止：

```text title="Terminal"
inventag - ERROR - Template problem:
inventag - ERROR -   ~/acme-infra/.inventag/templates/board-report.yaml:10: spec.logo: logo file not found: ~/acme-infra/.inventag/templates/brand/acme-logo.png
$ echo $?
1
```

## 下一步 {#next-steps}

- 保持顏色易讀：選擇與表頭文字對比度至少為 4.5:1 的表頭顏色。
- 把完整清單也生成為 Excel 檔案：
  `inventag --template board-report --create-word --create-excel`。
