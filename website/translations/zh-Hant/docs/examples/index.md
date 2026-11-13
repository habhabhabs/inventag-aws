---
title: 示例
description: 可直接複製的 InvenTag 常見任務方案，每個都附有命令、模板和生成的輸出，從快速審計到定時上傳到 S3。
sidebar_position: 1
---

# 示例

**適合誰閱讀：** 你清楚自己要完成什麼任務，想要一個可以直接複製的方案。

**你會得到：** 每個示例的目標、模板、命令、生成的輸出，以及下一步該做什麼。

這些頁面上的每一份輸出都來自針對模擬 AWS（[moto](https://github.com/getmoto/moto)）的真實 InvenTag 執行，而不是來自真實賬戶。
它們是**示例資料**：賬戶（例如 `123456789012`）和 `acme-*` 資源都是虛構的，你的名稱和數量會有所不同。
這些示例由 `scripts/docs/generate_example_outputs.py` 生成，因此與當前程式碼保持一致。

| 示例 | 你將得到 |
|---|---|
| [快速審計一個賬戶](./quick-audit.md) | 你當前登入賬戶的 Excel 和 Word 清單 |
| [盤點組織中的每個賬戶](./accounts-setup.md) | 透過每個賬戶中的只讀角色生成覆蓋多個賬戶的一份報告 |
| [在 CI 中強制執行標籤策略](./tag-policy-in-ci.md) | 資源違反標籤規則時會失敗的流水線步驟 |
| [FinOps 成本分攤標籤](./finops-cost-allocation.md) | 一份報告，說明哪些資源帶有成本報告所需的標籤 |
| [安全標籤審查](./security-review.md) | Owner、Environment 和資料分類標籤的覆蓋情況 |
| [帶品牌標識的高管 Word 報告](./branded-executive-report.md) | 帶有你的徽標和顏色的簡短橫向 Word 報告 |
| [自定義列](./custom-columns.md) | 只包含你所選列、且在同一個工作表上的工作簿 |
| [按計劃將報告上傳到 S3](./scheduled-s3-upload.md) | 每次執行後，S3 儲存桶中都有加密的報告 |

所有示例都假定你已經[安裝了 InvenTag](../getting-started/installation.md)，
並使用[只讀身份](../guides/read-only-access.md)登入。
